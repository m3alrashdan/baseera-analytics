from __future__ import annotations

import json
from unittest.mock import Mock

import httpx
import pytest
from baseera.errors import AppError
from baseera.source_adapters import SourceLimits, SourcePolicy, fetch_source


def policy(*hosts: str) -> SourcePolicy:
    return SourcePolicy(allowed_hosts=hosts)


def public_dns(host: str, port: int) -> list[str]:
    return ["93.184.216.34"]


def test_rest_pins_dns_keeps_tls_identity_and_commits_cursor() -> None:
    requests = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.url.host == "93.184.216.34"
        assert request.headers["host"] == "api.example.com"
        assert request.extensions["sni_hostname"] == "api.example.com"
        assert request.headers["authorization"] == "Bearer server-side-secret"
        if request.url.params.get("cursor") == "second":
            return httpx.Response(200, json={"items": [{"id": 2, "value": 4}], "next": None})
        return httpx.Response(200, json={"items": [{"id": 1, "value": 3}], "next": "second"})

    batch = fetch_source(
        "rest",
        {"base_url": "https://api.example.com/orders", "next_cursor_path": "next"},
        {"token": "server-side-secret"},
        policy=policy("api.example.com"),
        resolver=public_dns,
        transport=httpx.MockTransport(respond),
    )
    assert batch.records == [{"id": 1, "value": 3}, {"id": 2, "value": 4}]
    assert batch.complete is True
    assert batch.pages_read == 2
    assert batch.schema == {"id": "integer", "value": "integer"}
    assert batch.checkpoint_mode == "opaque"
    assert batch.to_sync_payload()["checkpoint_mode"] == "opaque"
    assert len(requests) == 2
    assert "server-side-secret" not in str(batch)
    assert batch.to_sync_payload()["records"] == batch.records


@pytest.mark.parametrize(
    "url",
    [
        "http://api.example.com",
        "https://api.example.com:444/records",
        "https://api.example.com.evil.test",
        "https://user:secret@api.example.com",
        "https://api.example.com/records#fragment",
    ],
)
def test_rest_rejects_destinations_before_network(url: str) -> None:
    responder = Mock()
    with pytest.raises(AppError) as caught:
        fetch_source(
            "rest",
            {"base_url": url},
            {},
            policy=policy("api.example.com"),
            resolver=public_dns,
            transport=httpx.MockTransport(responder),
        )
    assert caught.value.code == "connector_destination_denied"
    responder.assert_not_called()


@pytest.mark.parametrize(
    "addresses", [["127.0.0.1"], ["169.254.169.254"], ["93.184.216.34", "10.1.2.3"], ["::1"], []]
)
def test_rest_rejects_private_or_mixed_dns(addresses: list[str]) -> None:
    responder = Mock()
    with pytest.raises(AppError) as caught:
        fetch_source(
            "rest",
            {"base_url": "https://api.example.com"},
            {},
            policy=policy("api.example.com"),
            resolver=lambda *_: addresses,
            transport=httpx.MockTransport(responder),
        )
    assert caught.value.code == "connector_destination_denied"
    responder.assert_not_called()


def test_rest_never_forwards_credentials_to_redirect() -> None:
    requests = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(302, headers={"location": "https://evil.test/secrets"})

    with pytest.raises(AppError) as caught:
        fetch_source(
            "rest",
            {"base_url": "https://api.example.com"},
            {"token": "secret"},
            policy=policy("api.example.com"),
            resolver=public_dns,
            transport=httpx.MockTransport(respond),
        )
    assert caught.value.code == "connector_redirect_denied"
    assert len(requests) == 1


def test_rest_partial_checkpoint_resumes_exact_next_page() -> None:
    def respond(request: httpx.Request) -> httpx.Response:
        cursor = request.url.params.get("cursor")
        record_id = 2 if cursor == "page-two" else 1
        return httpx.Response(
            200,
            json={
                "items": [{"id": record_id}],
                "next_cursor": "page-two" if record_id == 1 else None,
            },
        )

    kwargs = {
        "policy": policy("api.example.com"),
        "resolver": public_dns,
        "transport": httpx.MockTransport(respond),
        "limits": SourceLimits(max_pages=1, page_size=1, max_rows=1),
    }
    first = fetch_source("rest", {"base_url": "https://api.example.com"}, {}, **kwargs)
    assert first.complete is False
    assert first.checkpoint["cursor"] == "page-two"
    second = fetch_source(
        "rest", {"base_url": "https://api.example.com"}, {}, checkpoint=first.checkpoint, **kwargs
    )
    assert second.complete is True
    assert second.records == [{"id": 2}]


@pytest.mark.parametrize(
    "response,expected",
    [
        (
            httpx.Response(401, text="secret upstream diagnostics"),
            "connector_authentication_failed",
        ),
        (httpx.Response(500, text="secret upstream diagnostics"), "connector_upstream_failed"),
        (httpx.Response(200, text="not JSON"), "connector_invalid_response"),
        (httpx.Response(200, json={"items": [1, 2]}), "connector_invalid_response"),
    ],
)
def test_rest_maps_errors_without_leaking_upstream_body(response, expected) -> None:
    with pytest.raises(AppError) as caught:
        fetch_source(
            "rest",
            {"base_url": "https://api.example.com"},
            {},
            policy=policy("api.example.com"),
            resolver=public_dns,
            transport=httpx.MockTransport(lambda _: response),
        )
    assert caught.value.code == expected
    assert "secret" not in caught.value.message


def test_rest_enforces_response_byte_limit() -> None:
    with pytest.raises(AppError) as caught:
        fetch_source(
            "rest",
            {"base_url": "https://api.example.com"},
            {},
            policy=policy("api.example.com"),
            resolver=public_dns,
            limits=SourceLimits(max_response_bytes=128),
            transport=httpx.MockTransport(lambda _: httpx.Response(200, text="x" * 129)),
        )
    assert caught.value.code == "connector_response_too_large"


def test_rest_rejects_overfull_page_and_cursor_loop_without_publishing() -> None:
    with pytest.raises(AppError) as caught:
        fetch_source(
            "rest",
            {"base_url": "https://api.example.com"},
            {},
            policy=policy("api.example.com"),
            resolver=public_dns,
            limits=SourceLimits(page_size=1, max_rows=1),
            transport=httpx.MockTransport(
                lambda _: httpx.Response(200, json={"items": [{"id": 1}, {"id": 2}]})
            ),
        )
    assert caught.value.code == "connector_page_limit_exceeded"
    with pytest.raises(AppError) as caught:
        fetch_source(
            "rest",
            {"base_url": "https://api.example.com"},
            {},
            policy=policy("api.example.com"),
            resolver=public_dns,
            transport=httpx.MockTransport(
                lambda _: httpx.Response(200, json={"items": [{"id": 1}], "next_cursor": "same"})
            ),
        )
    assert caught.value.code == "connector_cursor_loop"


def test_odoo_json2_only_calls_read_methods_and_uses_keyset_pagination() -> None:
    requests = []

    def respond(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.headers["authorization"] == "Bearer odoo-server-secret"
        assert request.headers["x-odoo-database"] == "tenant-db"
        if request.url.path.endswith("/fields_get"):
            return httpx.Response(
                200,
                json={
                    "id": {"type": "integer"},
                    "write_date": {"type": "datetime"},
                    "name": {"type": "char"},
                },
            )
        assert request.url.path == "/json/2/res.partner/search_read"
        body = json.loads(request.content)
        assert body["order"] == "write_date asc,id asc"
        if body["domain"]:
            assert ["id", ">", 1] in body["domain"]
            return httpx.Response(200, json=[])
        return httpx.Response(
            200, json=[{"id": 1, "write_date": "2026-09-05 00:00:00", "name": "شركة اختبار"}]
        )

    batch = fetch_source(
        "odoo_json2",
        {
            "base_url": "https://odoo.example.com",
            "model": "res.partner",
            "database": "tenant-db",
            "columns": ["id", "write_date", "name"],
        },
        {"api_key": "odoo-server-secret"},
        policy=policy("odoo.example.com"),
        limits=SourceLimits(page_size=1),
        resolver=public_dns,
        transport=httpx.MockTransport(respond),
    )
    assert batch.complete is True
    assert batch.records[0]["name"] == "شركة اختبار"
    assert batch.checkpoint == {"watermark": "2026-09-05 00:00:00", "primary_key": 1}
    assert batch.checkpoint_mode == "keyset"
    assert batch.schema["write_date"] == "datetime"
    assert len(requests) == 3


@pytest.mark.parametrize(
    "kind,config",
    [
        (
            "odoo_json2",
            {
                "base_url": "https://odoo.example.com",
                "model": "res.partner",
                "columns": ["id", "write_date"],
            },
        ),
        (
            "postgresql",
            {
                "host": "db.example.com",
                "database": "analytics",
                "table": "orders",
                "columns": ["id", "updated_at"],
            },
        ),
    ],
)
def test_missing_server_credentials_is_explicit_and_never_connects(kind, config) -> None:
    responder = Mock()
    with pytest.raises(AppError) as caught:
        fetch_source(
            kind,
            config,
            {},
            policy=policy("odoo.example.com", "db.example.com"),
            resolver=public_dns,
            transport=httpx.MockTransport(responder),
        )
    assert caught.value.code == "connector_credentials_missing"
    responder.assert_not_called()


def test_postgres_rejects_sql_and_unsafe_identifiers_before_connection() -> None:
    for config in [
        {"query": "SELECT * FROM secrets"},
        {"table": "orders; DROP TABLE orders; --"},
        {"columns": ["id", "pg_sleep(10)"]},
    ]:
        with pytest.raises(AppError) as caught:
            fetch_source(
                "postgresql",
                {
                    "host": "db.example.com",
                    "database": "analytics",
                    "table": "orders",
                    "columns": ["id", "updated_at"],
                    **config,
                },
                {"username": "reader", "password": "secret"},
                policy=policy("db.example.com"),
                resolver=public_dns,
            )
        assert caught.value.code == "connector_configuration_invalid"
