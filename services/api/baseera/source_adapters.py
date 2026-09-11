"""Bounded, read-only external source adapters.

Configuration is non-secret. Credentials and destination policy must be injected by the
server after tenant authorization, never copied from a browser request. A returned batch
is staged data; the caller commits its checkpoint only after durable publication.

Odoo protocol: https://www.odoo.com/documentation/19.0/developer/reference/external_api.html
Only fields_get and search_read are exposed; arbitrary RPC methods and SQL are excluded.
"""

from __future__ import annotations

import ipaddress
import json
import math
import re
import socket
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from urllib.parse import urlsplit
from uuid import UUID

import httpx
from sqlalchemy import MetaData, Table, and_, create_engine, or_, select, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.pool import NullPool

from .connectors import validate_resolved_addresses
from .errors import AppError

Resolver = Callable[[str, int], list[str]]
IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,62}\Z")
MODEL = re.compile(r"[a-z_][a-z0-9_]*(?:\.[a-z_][a-z0-9_]*)*\Z")


@dataclass(frozen=True, slots=True)
class SourcePolicy:
    allowed_hosts: tuple[str, ...]
    private_hosts: tuple[str, ...] = ()
    postgres_sslmode: str = "verify-full"

    def __post_init__(self) -> None:
        if self.postgres_sslmode not in {"verify-full", "verify-ca", "require", "disable"}:
            raise ValueError("Unsupported PostgreSQL TLS policy")


@dataclass(frozen=True, slots=True)
class SourceLimits:
    max_rows: int = 10_000
    max_pages: int = 20
    page_size: int = 500
    timeout_seconds: float = 10
    max_response_bytes: int = 10 * 1024 * 1024

    def __post_init__(self) -> None:
        for name, maximum in [
            ("max_rows", 100_000),
            ("max_pages", 100),
            ("page_size", 10_000),
            ("max_response_bytes", 50 * 1024 * 1024),
        ]:
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= maximum:
                raise ValueError(f"{name} is outside its safe bounds")
        if not 0 < self.timeout_seconds <= 60:
            raise ValueError("timeout_seconds must be greater than zero and at most 60")


@dataclass(frozen=True, slots=True)
class SourceBatch:
    records: list[dict[str, Any]]
    schema: dict[str, str]
    checkpoint: dict[str, Any]
    complete: bool
    pages_read: int
    checkpoint_mode: str = "watermark"
    limitations: tuple[str, ...] = field(default_factory=tuple)

    def to_sync_payload(self) -> dict[str, Any]:
        return {
            "records": self.records,
            "schema": self.schema,
            "checkpoint": self.checkpoint,
            "checkpoint_mode": self.checkpoint_mode,
        }


def resolve_addresses(host: str, port: int) -> list[str]:
    try:
        return list(
            dict.fromkeys(
                str(item[4][0]) for item in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
            )
        )
    except (OSError, UnicodeError) as exc:
        raise AppError(
            502, "connector_dns_failed", "The approved source could not be resolved"
        ) from exc


def fetch_source(
    kind: str,
    configuration: Mapping[str, Any],
    credentials: Mapping[str, str],
    *,
    policy: SourcePolicy,
    checkpoint: Mapping[str, Any] | None = None,
    limits: SourceLimits | None = None,
    resolver: Resolver = resolve_addresses,
    transport: httpx.BaseTransport | None = None,
) -> SourceBatch:
    """Fetch one bounded batch, without modifying either the source or local metadata.

    ``transport`` and ``resolver`` are injectable for protocol tests. Production calls
    should use their defaults so DNS validation and address pinning are both applied.
    """
    effective_limits = limits or SourceLimits()
    if kind == "rest":
        return _fetch_rest(
            configuration,
            credentials,
            dict(checkpoint or {}),
            policy,
            effective_limits,
            resolver,
            transport,
        )
    if kind == "odoo_json2":
        return _fetch_odoo(
            configuration,
            credentials,
            dict(checkpoint or {}),
            policy,
            effective_limits,
            resolver,
            transport,
        )
    if kind == "postgresql":
        return _fetch_postgres(
            configuration, credentials, dict(checkpoint or {}), policy, effective_limits, resolver
        )
    raise AppError(422, "connector_adapter_unavailable", "This source adapter is not implemented")


def _invalid(message: str = "The connector configuration is invalid") -> AppError:
    return AppError(422, "connector_configuration_invalid", message)


def _deny() -> AppError:
    return AppError(
        422,
        "connector_destination_denied",
        "The source destination is not permitted by the server policy",
    )


def _allowed_keys(configuration: Mapping[str, Any], allowed: set[str]) -> None:
    if set(configuration) - allowed:
        raise _invalid("Unsupported configuration fields; secrets and queries are not accepted")


def _identifier(value: Any) -> str:
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise _invalid("Source table and column names must be simple identifiers")
    return value


def _columns(configuration: Mapping[str, Any], key: str, incremental: str) -> list[str]:
    raw = configuration.get("columns")
    if not isinstance(raw, list) or not raw or len(raw) > 200:
        raise _invalid("Choose between one and 200 source columns")
    columns = list(dict.fromkeys(_identifier(item) for item in raw))
    if key not in columns or incremental not in columns:
        raise _invalid("Selected columns must include the primary key and incremental field")
    return columns


def _credential(credentials: Mapping[str, str], key: str) -> str:
    value = credentials.get(key)
    if not isinstance(value, str) or not value:
        raise AppError(
            409,
            "connector_credentials_missing",
            "Configure the required credential in the server secret store",
        )
    if len(value) > 8192 or "\r" in value or "\n" in value:
        raise _invalid("The configured server credential is invalid")
    return value


def _host_entry(host: str, port: int) -> str:
    return f"[{host}]:{port}" if ":" in host else f"{host}:{port}"


def _approved_address(
    host: str, port: int, default_port: int, policy: SourcePolicy, resolver: Resolver
) -> str:
    host = host.lower().rstrip(".")
    allowed = {entry.lower().rstrip(".") for entry in policy.allowed_hosts}
    entry = _host_entry(host, port)
    if entry not in allowed and not (port == default_port and host in allowed):
        raise _deny()
    private = {item.lower().rstrip(".") for item in policy.private_hosts}
    explicitly_private = entry in private or (port == default_port and host in private)
    addresses = resolver(host, port)
    validate_resolved_addresses(addresses, explicitly_private=explicitly_private)
    # Connect to this validated literal address, retaining the original TLS identity.
    return str(ipaddress.ip_address(addresses[0]))


class _PinnedJSONClient:
    def __init__(
        self,
        base_url: Any,
        policy: SourcePolicy,
        limits: SourceLimits,
        resolver: Resolver,
        transport: httpx.BaseTransport | None,
    ) -> None:
        if not isinstance(base_url, str):
            raise _deny()
        try:
            parsed = urlsplit(base_url)
            self.host = (parsed.hostname or "").lower().rstrip(".")
            self.port = parsed.port or 443
            if (
                parsed.scheme != "https"
                or not self.host
                or parsed.username
                or parsed.password
                or parsed.fragment
            ):
                raise _deny()
            self.original_url = httpx.URL(base_url)
        except (ValueError, httpx.InvalidURL) as exc:
            raise _deny() from exc
        self.policy, self.limits, self.resolver, self.transport = (
            policy,
            limits,
            resolver,
            transport,
        )

    def request(
        self,
        method: str,
        *,
        headers: Mapping[str, str],
        path: str | None = None,
        params: Mapping[str, Any] | None = None,
        body: dict | None = None,
    ) -> Any:
        address = _approved_address(self.host, self.port, 443, self.policy, self.resolver)
        url = self.original_url
        if path is not None:
            url = url.copy_with(path=path, query=None)
        url = url.copy_with(host=address)
        original_host = self.host if self.port == 443 else _host_entry(self.host, self.port)
        request_headers = {
            "Accept": "application/json",
            "Accept-Encoding": "identity",
            "User-Agent": "BASEERA/0.1",
            **headers,
            "Host": original_host,
        }
        try:
            with (
                httpx.Client(
                    transport=self.transport,
                    trust_env=False,
                    follow_redirects=False,
                    timeout=httpx.Timeout(self.limits.timeout_seconds),
                ) as client,
                client.stream(
                    method,
                    url,
                    params=params,
                    json=body,
                    headers=request_headers,
                    extensions={"sni_hostname": self.host},
                ) as response,
            ):
                if 300 <= response.status_code < 400:
                    raise AppError(
                        422,
                        "connector_redirect_denied",
                        "Source redirects are disabled; configure its final URL",
                    )
                if response.status_code in {401, 403}:
                    raise AppError(
                        409,
                        "connector_authentication_failed",
                        "The source rejected the configured credential or access",
                    )
                if response.status_code >= 400:
                    raise AppError(
                        502,
                        "connector_upstream_failed",
                        "The source returned an unsuccessful response",
                    )
                if response.headers.get("content-encoding", "identity").lower() != "identity":
                    raise AppError(
                        502,
                        "connector_encoding_unsupported",
                        "The source must respect uncompressed bounded responses",
                    )
                payload = bytearray()
                for chunk in response.iter_bytes(chunk_size=64 * 1024):
                    payload.extend(chunk)
                    if len(payload) > self.limits.max_response_bytes:
                        raise AppError(
                            413,
                            "connector_response_too_large",
                            "A source page exceeded the configured byte limit",
                        )
            return json.loads(payload, parse_constant=_reject_json_constant)
        except httpx.TimeoutException as exc:
            raise AppError(
                504, "connector_timeout", "The source request exceeded its time limit"
            ) from exc
        except httpx.HTTPError as exc:
            raise AppError(
                502,
                "connector_connection_failed",
                "A secure source connection could not be completed",
            ) from exc
        except (ValueError, UnicodeError) as exc:
            raise AppError(
                502, "connector_invalid_response", "The source did not return valid JSON"
            ) from exc


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"Unsupported JSON constant: {value}")


def _extract(value: Any, path: str, *, optional: bool = False) -> Any:
    for key in path.split(".") if path else []:
        if not isinstance(value, dict) or key not in value:
            if optional:
                return None
            raise AppError(
                502, "connector_invalid_response", "The configured source field is absent"
            )
        value = value[key]
    return value


def _records(value: Any, page_limit: int) -> list[dict[str, Any]]:
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise AppError(
            502, "connector_invalid_response", "A source page must contain record objects"
        )
    if len(value) > page_limit:
        raise AppError(
            502, "connector_page_limit_exceeded", "The source ignored its page size limit"
        )
    if any(not all(isinstance(key, str) for key in item) for item in value):
        raise AppError(502, "connector_invalid_response", "Record field names must be strings")
    return value


def _json_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        if not math.isfinite(value):
            raise AppError(
                502, "connector_invalid_response", "Source numeric values must be finite"
            )
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    raise AppError(502, "connector_invalid_response", "Unsupported source value type")


def _schema_from_records(records: list[dict[str, Any]]) -> dict[str, str]:
    types: dict[str, set[str]] = {}
    for record in records:
        for key, value in record.items():
            types.setdefault(key, set()).add(_json_type(value))
    return {
        key: "|".join(sorted(values - {"null"} or {"null"}))
        for key, values in sorted(types.items())
    }


def _fetch_rest(configuration, credentials, checkpoint, policy, limits, resolver, transport):
    _allowed_keys(
        configuration,
        {
            "base_url",
            "records_path",
            "next_cursor_path",
            "cursor_parameter",
            "page_size_parameter",
            "primary_key",
            "incremental_field",
        },
    )
    client = _PinnedJSONClient(configuration.get("base_url"), policy, limits, resolver, transport)
    token = credentials.get("token")
    headers = {"Authorization": f"Bearer {_credential(credentials, 'token')}"} if token else {}
    records_path = configuration.get("records_path", "items")
    next_path = configuration.get("next_cursor_path", "next_cursor")
    cursor_parameter = _identifier(configuration.get("cursor_parameter", "cursor"))
    size_parameter = _identifier(configuration.get("page_size_parameter", "limit"))
    if not isinstance(records_path, str) or not isinstance(next_path, str):
        raise _invalid("JSON field paths must be strings")
    cursor = checkpoint.get("cursor")
    if cursor is not None and (not isinstance(cursor, str) or len(cursor) > 4096):
        raise _invalid("The source cursor must be a bounded opaque string")
    output, visited, complete = [], set(), False
    pages_read = 0
    for _ in range(limits.max_pages):
        page_limit = min(limits.page_size, limits.max_rows - len(output))
        params = {size_parameter: page_limit}
        if cursor is not None:
            if cursor in visited:
                raise AppError(
                    502, "connector_cursor_loop", "The source repeated a pagination cursor"
                )
            visited.add(cursor)
            params[cursor_parameter] = cursor
        payload = client.request("GET", headers=headers, params=params)
        output.extend(_records(_extract(payload, records_path), page_limit))
        pages_read += 1
        cursor = _extract(payload, next_path, optional=True)
        if cursor in (None, ""):
            cursor, complete = None, True
            break
        if not isinstance(cursor, str) or len(cursor) > 4096:
            raise AppError(502, "connector_invalid_response", "The source cursor is invalid")
        if cursor in visited:
            raise AppError(502, "connector_cursor_loop", "The source repeated a pagination cursor")
        if len(output) == limits.max_rows:
            break
    return SourceBatch(
        output,
        _schema_from_records(output),
        {"cursor": cursor},
        complete,
        pages_read,
        "opaque",
        (
            "REST schemas are inferred from observed records; review schema drift.",
            "Incremental semantics depend on the source's opaque cursor contract.",
        ),
    )


def _keyset_domain(incremental: str, key: str, checkpoint: dict[str, Any]) -> list[Any]:
    if not checkpoint:
        return []
    if set(checkpoint) != {"watermark", "primary_key"}:
        raise _invalid("Incremental checkpoints require a watermark and primary key")
    return [
        "|",
        [incremental, ">", checkpoint["watermark"]],
        "&",
        [incremental, "=", checkpoint["watermark"]],
        [key, ">", checkpoint["primary_key"]],
    ]


def _fetch_odoo(configuration, credentials, checkpoint, policy, limits, resolver, transport):
    _allowed_keys(
        configuration,
        {"base_url", "model", "database", "columns", "primary_key", "incremental_field"},
    )
    api_key = _credential(credentials, "api_key")
    model = configuration.get("model")
    if not isinstance(model, str) or len(model) > 128 or not MODEL.fullmatch(model):
        raise _invalid("An Odoo technical model name is required")
    key = _identifier(configuration.get("primary_key", "id"))
    incremental = _identifier(configuration.get("incremental_field", "write_date"))
    if key == incremental:
        raise _invalid("Primary key and incremental field must be different")
    columns = _columns(configuration, key, incremental)
    client = _PinnedJSONClient(configuration.get("base_url"), policy, limits, resolver, transport)
    headers = {"Authorization": f"Bearer {api_key}"}
    database = configuration.get("database")
    if database:
        if not isinstance(database, str) or not re.fullmatch(r"[\w.-]{1,128}", database):
            raise _invalid("The Odoo database name is invalid")
        headers["X-Odoo-Database"] = database
    metadata = client.request(
        "POST",
        headers=headers,
        path=f"/json/2/{model}/fields_get",
        body={"allfields": columns, "attributes": ["type"]},
    )
    if not isinstance(metadata, dict) or any(
        not isinstance(metadata.get(column), dict)
        or not isinstance(metadata[column].get("type"), str)
        for column in columns
    ):
        raise AppError(502, "connector_invalid_response", "Odoo field metadata is incomplete")
    schema = {column: metadata[column]["type"] for column in columns}
    output, complete, pages_read = [], False, 0
    for _ in range(limits.max_pages):
        page_limit = min(limits.page_size, limits.max_rows - len(output))
        payload = client.request(
            "POST",
            headers=headers,
            path=f"/json/2/{model}/search_read",
            body={
                "domain": _keyset_domain(incremental, key, checkpoint),
                "fields": columns,
                "order": f"{incremental} asc,{key} asc",
                "limit": page_limit,
                "context": {"active_test": False},
            },
        )
        records = _records(payload, page_limit)
        pages_read += 1
        for record in records:
            if any(column not in record for column in columns):
                raise AppError(502, "connector_invalid_response", "Odoo omitted a selected field")
            watermark, primary = record[incremental], record[key]
            if not isinstance(watermark, str) or not watermark or not isinstance(primary, int):
                raise AppError(
                    502, "connector_invalid_response", "Odoo checkpoint fields are invalid"
                )
            if checkpoint and (watermark, primary) <= (
                checkpoint["watermark"],
                checkpoint["primary_key"],
            ):
                raise AppError(
                    502, "connector_cursor_loop", "Odoo records did not advance the checkpoint"
                )
            checkpoint = {"watermark": watermark, "primary_key": primary}
            output.append({column: record[column] for column in columns})
        if len(records) < page_limit:
            complete = True
            break
        if len(output) == limits.max_rows:
            break
    return SourceBatch(
        output,
        schema,
        checkpoint,
        complete,
        pages_read,
        "keyset",
        (
            "Requires Odoo 19+ JSON-2 access and a dedicated read-only bot account.",
            "Odoo requests are separate transactions; source deletions need reconciliation.",
        ),
    )


def _json_value(value: Any) -> Any:
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, dict):
        return {str(key): _json_value(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_json_value(item) for item in value]
    _json_type(value)
    return value


def _checkpoint_value(column, value):
    try:
        python_type = column.type.python_type
        if python_type in (datetime, date):
            return python_type.fromisoformat(value)
        return python_type(value)
    except (ValueError, TypeError, NotImplementedError) as exc:
        raise _invalid("The checkpoint value does not match the source column type") from exc


def _fetch_postgres(configuration, credentials, checkpoint, policy, limits, resolver):
    _allowed_keys(
        configuration,
        {
            "host",
            "port",
            "database",
            "schema",
            "table",
            "columns",
            "primary_key",
            "incremental_field",
        },
    )
    username, password = _credential(credentials, "username"), _credential(credentials, "password")
    schema_name = _identifier(configuration.get("schema", "public"))
    table_name = _identifier(configuration.get("table"))
    key = _identifier(configuration.get("primary_key", "id"))
    incremental = _identifier(configuration.get("incremental_field", "updated_at"))
    columns = _columns(configuration, key, incremental)
    if key == incremental:
        raise _invalid("Primary key and incremental field must be different")
    host, database = configuration.get("host"), configuration.get("database")
    port = configuration.get("port", 5432)
    if (
        not isinstance(host, str)
        or not host
        or not isinstance(database, str)
        or not database
        or not isinstance(port, int)
        or isinstance(port, bool)
        or not 1 <= port <= 65535
    ):
        raise _invalid("A PostgreSQL host, database and valid port are required")
    if checkpoint and set(checkpoint) != {"watermark", "primary_key"}:
        raise _invalid("Incremental checkpoints require a watermark and primary key")
    address = _approved_address(host, port, 5432, policy, resolver)
    if (
        policy.postgres_sslmode == "disable"
        and host not in policy.private_hosts
        and _host_entry(host, port) not in policy.private_hosts
    ):
        raise _deny()
    url = URL.create(
        "postgresql+psycopg",
        username=username,
        password=password,
        host=host,
        port=port,
        database=database,
    )
    engine = create_engine(
        url,
        poolclass=NullPool,
        hide_parameters=True,
        connect_args={
            "hostaddr": address,
            "connect_timeout": max(1, math.ceil(limits.timeout_seconds)),
            "sslmode": policy.postgres_sslmode,
            "options": f"-c statement_timeout={int(limits.timeout_seconds * 1000)} "
            "-c default_transaction_read_only=on -c lock_timeout=2000",
        },
    )
    try:
        with (
            engine.connect().execution_options(
                isolation_level="REPEATABLE READ", postgresql_readonly=True
            ) as connection,
            connection.begin(),
        ):
            # Execute explicit SQL as well: this remains effective across driver versions.
            connection.execute(text("SET TRANSACTION READ ONLY"))
            table = Table(table_name, MetaData(), schema=schema_name, autoload_with=connection)
            if any(column not in table.c for column in columns):
                raise _invalid("A selected column does not exist in the source table")
            if key not in {column.name for column in table.primary_key.columns}:
                raise _invalid("The configured source key must be a declared primary key")
            if len(table.primary_key.columns) != 1:
                raise _invalid("Composite source keys require an explicit stable surrogate key")
            if (
                connection.execute(
                    select(table.c[key]).where(table.c[incremental].is_(None)).limit(1)
                ).first()
                is not None
            ):
                raise AppError(
                    422,
                    "connector_null_checkpoint",
                    "Source checkpoint fields cannot contain null values",
                )
            selected = [table.c[column] for column in columns]
            statement = select(*selected).order_by(table.c[incremental], table.c[key])
            if checkpoint:
                watermark = _checkpoint_value(table.c[incremental], checkpoint["watermark"])
                primary = _checkpoint_value(table.c[key], checkpoint["primary_key"])
                statement = statement.where(
                    or_(
                        table.c[incremental] > watermark,
                        and_(table.c[incremental] == watermark, table.c[key] > primary),
                    )
                )
            # One keyset query makes a bounded snapshot; the extra row determines completeness.
            row_limit = min(limits.max_rows, limits.max_pages * limits.page_size)
            rows = connection.execute(statement.limit(row_limit + 1)).mappings().all()
            complete = len(rows) <= row_limit
            rows = rows[:row_limit]
            output = []
            for row in rows:
                if row[incremental] is None or row[key] is None:
                    raise AppError(
                        422,
                        "connector_null_checkpoint",
                        "Source checkpoint fields cannot contain null values",
                    )
                output.append({column: _json_value(row[column]) for column in columns})
            if output:
                checkpoint = {
                    "watermark": output[-1][incremental],
                    "primary_key": output[-1][key],
                }
            schema = {column: str(table.c[column].type) for column in columns}
        return SourceBatch(
            output,
            schema,
            checkpoint,
            complete,
            1,
            "keyset",
            ("Source deletions require periodic full reconciliation.",),
        )
    except SQLAlchemyError as exc:
        raise AppError(
            502,
            "connector_database_failed",
            "The read-only source query failed; check access and selected fields",
        ) from exc
    finally:
        engine.dispose()
