from __future__ import annotations

import ipaddress
import uuid
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, cast
from urllib.parse import urlsplit

from sqlalchemy import select
from sqlalchemy.orm import Session

from .errors import AppError
from .ingestion import stable_hash
from .models import Connector, ConnectorRecord, ConnectorRun, utcnow


def validate_connector_destination(base_url: str, allow_hosts: tuple[str, ...]) -> str:
    """Validate a connector URL against an exact administrative host allow-list.

    Runtime adapters must repeat this check after DNS resolution and for every redirect. This
    function intentionally performs no connection or DNS lookup while configuration is saved.
    """

    try:
        parsed = urlsplit(base_url)
        host = (parsed.hostname or "").lower().rstrip(".")
        port = parsed.port
    except ValueError as exc:
        raise _destination_denied() from exc
    if parsed.scheme != "https" or not host or parsed.username or parsed.password:
        raise _destination_denied()
    allowed = {item.lower().rstrip(".") for item in allow_hosts}
    host_with_port = f"{host}:{port}" if port else host
    if host not in allowed and host_with_port not in allowed:
        raise _destination_denied()
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None and _unsafe_address(address) and host not in allowed:
        raise _destination_denied()
    return base_url.rstrip("/")


def validate_resolved_addresses(addresses: list[str], explicitly_private: bool = False) -> None:
    if not addresses:
        raise _destination_denied()
    for raw in addresses:
        try:
            address = ipaddress.ip_address(raw)
        except ValueError as exc:
            raise _destination_denied() from exc
        if _unsafe_address(address) and not explicitly_private:
            raise _destination_denied()


def _unsafe_address(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return bool(
        address.is_loopback
        or address.is_link_local
        or address.is_multicast
        or address.is_unspecified
        or address.is_reserved
        or address.is_private
    )


def _destination_denied() -> AppError:
    return AppError(
        422,
        "connector_destination_denied",
        "The connector destination is not an explicitly approved HTTPS host.",
    )


def schema_fingerprint(schema: dict[str, str]) -> str:
    if not schema or not all(
        isinstance(key, str) and isinstance(value, str) for key, value in schema.items()
    ):
        raise AppError(422, "invalid_connector_schema", "Schema must map field names to type names")
    return stable_hash(schema)


def sync_records(
    db: Session,
    connector: Connector,
    payload: dict[str, Any],
    idempotency_key: str,
) -> dict[str, Any]:
    request_hash = stable_hash(payload)
    existing = db.scalar(
        select(ConnectorRun).where(
            ConnectorRun.organization_id == connector.organization_id,
            ConnectorRun.connector_id == connector.id,
            ConnectorRun.idempotency_key == idempotency_key,
        )
    )
    if existing is not None:
        if existing.request_hash != request_hash:
            raise AppError(
                409,
                "idempotency_conflict",
                "This idempotency key was already used with a different sync payload.",
            )
        return _run_payload(existing, deduplicated=True)

    schema = payload.get("schema")
    records = payload.get("records")
    checkpoint = payload.get("checkpoint")
    checkpoint_mode = payload.get("checkpoint_mode", "watermark")
    if (
        not isinstance(schema, dict)
        or not isinstance(records, list)
        or not isinstance(checkpoint, dict)
        or checkpoint_mode not in {"watermark", "keyset", "opaque"}
    ):
        raise AppError(
            422,
            "invalid_sync_batch",
            "Sync requires schema, records, checkpoint, and an approved checkpoint mode",
        )
    fingerprint = schema_fingerprint(schema)
    run = ConnectorRun(
        id=f"sync-{uuid.uuid4().hex}",
        organization_id=connector.organization_id,
        connector_id=connector.id,
        status="running",
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        schema_fingerprint=fingerprint,
        prior_checkpoint=dict(connector.checkpoint or {}),
        attempted=len(records),
    )
    db.add(run)

    if connector.schema_fingerprint and connector.schema_fingerprint != fingerprint:
        connector.status = "schema_drift"
        connector.last_checked_at = utcnow()
        run.status = "failed"
        run.error = {
            "code": "schema_drift",
            "message": "Source schema changed; mapping review is required before publication.",
            "previous_fingerprint": connector.schema_fingerprint,
            "observed_fingerprint": fingerprint,
        }
        run.finished_at = utcnow()
        db.commit()
        raise AppError(
            409,
            "schema_drift",
            "Source schema changed; the previous checkpoint remains authoritative.",
            details={
                "run_id": run.id,
                "previous_fingerprint": connector.schema_fingerprint,
                "observed_fingerprint": fingerprint,
            },
        )

    if connector.checkpoint and _checkpoint_regresses(
        checkpoint,
        connector.checkpoint,
        checkpoint_mode=checkpoint_mode,
        incremental_field=str(connector.configuration.get("incremental_field", "updated_at")),
        primary_key=str(connector.configuration.get("primary_key", "id")),
    ):
        db.rollback()
        raise AppError(409, "checkpoint_regression", "A sync checkpoint cannot move backwards")

    primary_key = str(connector.configuration.get("primary_key", "id"))
    incremental_field = str(connector.configuration.get("incremental_field", "updated_at"))
    inserted = updated = unchanged = 0
    for index, record in enumerate(records):
        if not isinstance(record, dict) or record.get(primary_key) in {None, ""}:
            db.rollback()
            raise AppError(
                422,
                "invalid_sync_record",
                "Every record must be an object with the configured stable primary key.",
                details={"record_index": index, "primary_key": primary_key},
            )
        source_key = str(record[primary_key])
        incoming_hash = stable_hash(record)
        incoming_version = record.get(incremental_field)
        stored = db.scalar(
            select(ConnectorRecord).where(
                ConnectorRecord.organization_id == connector.organization_id,
                ConnectorRecord.connector_id == connector.id,
                ConnectorRecord.source_key == source_key,
            )
        )
        if stored is None:
            db.add(
                ConnectorRecord(
                    id=f"connector-record-{uuid.uuid4().hex}",
                    organization_id=connector.organization_id,
                    connector_id=connector.id,
                    source_key=source_key,
                    source_version=str(incoming_version) if incoming_version is not None else None,
                    payload=record,
                    payload_hash=incoming_hash,
                )
            )
            inserted += 1
        elif stored.payload_hash == incoming_hash:
            unchanged += 1
        elif _is_newer(incoming_version, stored.source_version):
            stored.payload = record
            stored.payload_hash = incoming_hash
            stored.source_version = str(incoming_version) if incoming_version is not None else None
            updated += 1
        else:
            unchanged += 1

    connector.schema_fingerprint = fingerprint
    connector.checkpoint = checkpoint
    connector.status = "ready"
    connector.last_checked_at = utcnow()
    run.status = "completed"
    run.committed_checkpoint = checkpoint
    run.committed = inserted + updated + unchanged
    run.inserted = inserted
    run.updated = updated
    run.unchanged = unchanged
    run.finished_at = utcnow()
    db.commit()
    return _run_payload(run, deduplicated=False)


def _is_newer(incoming: Any, stored: str | None) -> bool:
    if incoming is None:
        return stored is None
    return stored is None or str(incoming) > stored


def _checkpoint_regresses(
    incoming: dict[str, Any],
    committed: dict[str, Any],
    *,
    checkpoint_mode: str,
    incremental_field: str,
    primary_key: str,
) -> bool:
    """Compare only checkpoint formats whose ordering is defined by the source contract.

    REST cursors are opaque tokens, not sortable watermarks. Comparing them as strings can
    discard valid pages (for example ``"a"`` can be newer than ``"z"``). Adapter code is
    responsible for validating opaque cursor progression before durable publication.
    """
    if checkpoint_mode == "opaque":
        return False
    keys = (
        ("watermark", "primary_key")
        if checkpoint_mode == "keyset"
        else (incremental_field, primary_key)
    )
    if not incoming or not committed:
        return False
    if set(incoming) != set(keys) or set(committed) != set(keys):
        raise AppError(
            422,
            "invalid_checkpoint",
            "The checkpoint does not match the connector's declared incremental key.",
        )
    incoming_watermark = _comparable_checkpoint_value(incoming[keys[0]])
    committed_watermark = _comparable_checkpoint_value(committed[keys[0]])
    if incoming_watermark != committed_watermark:
        return _checkpoint_less_than(incoming_watermark, committed_watermark)
    incoming_key = _comparable_checkpoint_value(incoming[keys[1]])
    committed_key = _comparable_checkpoint_value(committed[keys[1]])
    return _checkpoint_less_than(incoming_key, committed_key)


def _checkpoint_less_than(
    incoming: datetime | date | Decimal | str,
    committed: datetime | date | Decimal | str,
) -> bool:
    if type(incoming) is not type(committed):
        raise AppError(422, "invalid_checkpoint", "The checkpoint value type changed.")
    # Exact runtime types are verified above. ``cast`` expresses that narrowing to
    # mypy; it does not coerce source values or widen accepted checkpoint formats.
    return bool(cast(Any, incoming) < cast(Any, committed))


def _comparable_checkpoint_value(value: Any) -> datetime | date | Decimal | str:
    if isinstance(value, bool) or value is None:
        raise AppError(422, "invalid_checkpoint", "Checkpoint values cannot be blank or boolean.")
    if isinstance(value, datetime | date):
        return value
    if isinstance(value, int | float | Decimal):
        try:
            return Decimal(str(value))
        except InvalidOperation as exc:
            raise AppError(422, "invalid_checkpoint", "The numeric checkpoint is invalid.") from exc
    if not isinstance(value, str) or not value or len(value) > 4096:
        raise AppError(422, "invalid_checkpoint", "Checkpoint values must be bounded scalars.")
    iso_value = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        return datetime.fromisoformat(iso_value)
    except ValueError:
        pass
    try:
        return date.fromisoformat(value)
    except ValueError:
        pass
    try:
        return Decimal(value)
    except InvalidOperation:
        return value


def _run_payload(run: ConnectorRun, *, deduplicated: bool) -> dict[str, Any]:
    return {
        "run_id": run.id,
        "status": run.status,
        "attempted": run.attempted,
        "committed": run.committed,
        "inserted": run.inserted,
        "updated": run.updated,
        "unchanged": run.unchanged,
        "checkpoint": run.committed_checkpoint,
        "deduplicated": deduplicated,
        "error": run.error,
    }
