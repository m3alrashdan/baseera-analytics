"""Server-side connector execution and encrypted credential storage.

These tests pin the behaviour a customer deployment depends on: the server holds the
credentials, reaches the source itself, and never hands the secret back out again.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
from baseera.connectors import load_credentials, run_source_fetch, store_credentials
from baseera.credentials import SecretBox, generate_key
from baseera.errors import AppError
from baseera.main import create_app
from baseera.models import Connector, ConnectorSecret
from baseera.source_adapters import SourcePolicy
from fastapi.testclient import TestClient
from sqlalchemy import select

CREDENTIALS = {"token": "server-side-secret"}


@pytest.fixture
def secret_key(monkeypatch: pytest.MonkeyPatch) -> str:
    entry = generate_key("v1")
    monkeypatch.setenv("BASEERA_SECRET_KEY", entry)
    monkeypatch.delenv("BASEERA_SECRET_KEYS_RETIRED", raising=False)
    return entry


@pytest.fixture
def client(tmp_path: Path, secret_key: str) -> Iterator[TestClient]:
    app = create_app(
        database_url=f"sqlite:///{tmp_path / 'fetch-test.db'}",
        artifact_root=tmp_path / "artifacts",
        testing=True,
        seed_demo=True,
        connector_allow_hosts=("api.example.com",),
    )
    with TestClient(app) as test_client:
        yield test_client


def _login(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return {"X-CSRF-Token": response.json()["csrf_token"]}


def _executive(client: TestClient) -> dict[str, str]:
    return _login(client, "executive@demo.baseera.local", "BaseeraDemo!2026")


def _create_connector(client: TestClient, headers: dict[str, str]) -> str:
    response = client.post(
        "/api/v1/connectors",
        headers=headers,
        json={
            "kind": "rest",
            "name": "Orders",
            "base_url": "https://api.example.com/orders",
            "primary_key": "id",
            "incremental_field": "updated_at",
        },
    )
    assert response.status_code == 201, response.text
    return str(response.json()["id"])


def test_credentials_are_encrypted_at_rest_and_never_returned(client: TestClient) -> None:
    headers = _executive(client)
    connector_id = _create_connector(client, headers)

    saved = client.put(
        f"/api/v1/connectors/{connector_id}/credentials",
        headers=headers,
        json={"credentials": CREDENTIALS},
    )
    assert saved.status_code == 200, saved.text
    state = saved.json()["credentials"]
    assert state["configured"] is True
    assert state["key_id"] == "v1"
    assert "server-side-secret" not in saved.text

    read_back = client.get(f"/api/v1/connectors/{connector_id}")
    assert read_back.status_code == 200
    assert "server-side-secret" not in read_back.text
    assert read_back.json()["credentials"]["configured"] is True

    session_factory = client.app.state.session_factory  # type: ignore[attr-defined]
    with session_factory() as db:
        stored = db.scalar(select(ConnectorSecret))
        assert stored is not None
        assert "server-side-secret" not in stored.ciphertext
        assert stored.ciphertext.startswith("v1.")


def test_server_side_fetch_pulls_records_and_commits_a_checkpoint(client: TestClient) -> None:
    headers = _executive(client)
    connector_id = _create_connector(client, headers)
    client.put(
        f"/api/v1/connectors/{connector_id}/credentials",
        headers=headers,
        json={"credentials": CREDENTIALS},
    )

    seen: list[httpx.Request] = []

    def respond(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        assert request.headers["authorization"] == "Bearer server-side-secret"
        return httpx.Response(
            200,
            json={
                "items": [
                    {"id": 1, "updated_at": "2026-01-01T00:00:00Z", "amount": 10},
                    {"id": 2, "updated_at": "2026-01-02T00:00:00Z", "amount": 20},
                ],
                "next": None,
            },
        )

    session_factory = client.app.state.session_factory  # type: ignore[attr-defined]
    box = client.app.state.secret_box  # type: ignore[attr-defined]
    with session_factory() as db:
        connector = db.scalar(select(Connector).where(Connector.id == connector_id))
        assert connector is not None
        connector.configuration = {**connector.configuration, "next_cursor_path": "next"}
        db.commit()
        result = run_source_fetch(
            db,
            box,
            connector,
            policy=SourcePolicy(allowed_hosts=("api.example.com",)),
            idempotency_key="fetch-1",
            transport=httpx.MockTransport(respond),
            resolver=lambda host, port: ["93.184.216.34"],
        )
        db.commit()

    assert seen, "the adapter never reached the source"
    assert result["status"] == "completed"
    assert result["source"]["records_fetched"] == 2
    assert result["inserted"] == 2

    records = client.get(f"/api/v1/connectors/{connector_id}/records")
    assert records.status_code == 200
    assert len(records.json()["items"]) == 2


def test_fetch_without_stored_credentials_fails_closed(client: TestClient) -> None:
    headers = _executive(client)
    connector_id = _create_connector(client, headers)

    session_factory = client.app.state.session_factory  # type: ignore[attr-defined]
    box = client.app.state.secret_box  # type: ignore[attr-defined]
    with session_factory() as db:
        connector = db.scalar(select(Connector).where(Connector.id == connector_id))
        assert connector is not None
        with pytest.raises(AppError) as excinfo:
            run_source_fetch(
                db,
                box,
                connector,
                policy=SourcePolicy(allowed_hosts=("api.example.com",)),
                idempotency_key="fetch-missing",
            )
    assert excinfo.value.code == "credentials_missing"


def test_fetch_requires_an_idempotency_key(client: TestClient) -> None:
    headers = _executive(client)
    connector_id = _create_connector(client, headers)
    response = client.post(f"/api/v1/connectors/{connector_id}/fetch", headers=headers, json={})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "idempotency_key_required"


def test_a_non_administrator_cannot_store_or_remove_credentials(client: TestClient) -> None:
    admin_headers = _executive(client)
    connector_id = _create_connector(client, admin_headers)

    client.post("/api/v1/auth/logout", headers=admin_headers)
    hr_headers = _login(client, "hr@demo.baseera.local", "BaseeraHR!2026")

    denied = client.put(
        f"/api/v1/connectors/{connector_id}/credentials",
        headers=hr_headers,
        json={"credentials": CREDENTIALS},
    )
    assert denied.status_code == 403
    removal = client.delete(f"/api/v1/connectors/{connector_id}/credentials", headers=hr_headers)
    assert removal.status_code == 403


def test_credentials_can_be_removed(client: TestClient) -> None:
    headers = _executive(client)
    connector_id = _create_connector(client, headers)
    client.put(
        f"/api/v1/connectors/{connector_id}/credentials",
        headers=headers,
        json={"credentials": CREDENTIALS},
    )
    removed = client.delete(f"/api/v1/connectors/{connector_id}/credentials", headers=headers)
    assert removed.status_code == 200
    assert removed.json()["removed"] is True
    assert (
        client.get(f"/api/v1/connectors/{connector_id}").json()["credentials"]["configured"]
        is False
    )


def test_a_credential_cannot_be_replayed_against_another_connector(client: TestClient) -> None:
    """A ciphertext moved to a different connector row must not decrypt."""

    headers = _executive(client)
    first = _create_connector(client, headers)
    second = _create_connector(client, headers)
    client.put(
        f"/api/v1/connectors/{first}/credentials",
        headers=headers,
        json={"credentials": CREDENTIALS},
    )

    session_factory = client.app.state.session_factory  # type: ignore[attr-defined]
    box = client.app.state.secret_box  # type: ignore[attr-defined]
    with session_factory() as db:
        stolen = db.scalar(select(ConnectorSecret))
        assert stolen is not None
        db.add(
            ConnectorSecret(
                id="connector-secret-replayed",
                organization_id=stolen.organization_id,
                connector_id=second,
                ciphertext=stolen.ciphertext,
                key_id=stolen.key_id,
                fingerprint=stolen.fingerprint,
            )
        )
        db.commit()
        target = db.scalar(select(Connector).where(Connector.id == second))
        assert target is not None
        with pytest.raises(AppError) as excinfo:
            load_credentials(db, box, target)
    assert excinfo.value.code == "credential_unreadable"


def test_a_retired_key_still_decrypts_and_the_value_is_re_encrypted(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    headers = _executive(client)
    connector_id = _create_connector(client, headers)

    session_factory = client.app.state.session_factory  # type: ignore[attr-defined]
    old_box = client.app.state.secret_box  # type: ignore[attr-defined]
    with session_factory() as db:
        connector = db.scalar(select(Connector).where(Connector.id == connector_id))
        assert connector is not None
        store_credentials(db, old_box, connector, CREDENTIALS)
        db.commit()

    retired = os.environ["BASEERA_SECRET_KEY"]
    monkeypatch.setenv("BASEERA_SECRET_KEY", generate_key("v2"))
    monkeypatch.setenv("BASEERA_SECRET_KEYS_RETIRED", retired)
    rotated_box = SecretBox.from_environment("production")
    assert rotated_box is not None

    with session_factory() as db:
        connector = db.scalar(select(Connector).where(Connector.id == connector_id))
        assert connector is not None
        assert load_credentials(db, rotated_box, connector) == CREDENTIALS
        db.commit()
        stored = db.scalar(select(ConnectorSecret))
        assert stored is not None
        assert stored.ciphertext.startswith("v2."), "the value should be re-sealed by the new key"


def test_oversized_and_non_string_credentials_are_rejected(client: TestClient) -> None:
    headers = _executive(client)
    connector_id = _create_connector(client, headers)

    too_large = client.put(
        f"/api/v1/connectors/{connector_id}/credentials",
        headers=headers,
        json={"credentials": {"token": "x" * 5000}},
    )
    assert too_large.status_code == 422

    wrong_type = client.put(
        f"/api/v1/connectors/{connector_id}/credentials",
        headers=headers,
        json={"credentials": {"token": {"nested": "value"}}},
    )
    assert wrong_type.status_code == 422


def test_production_refuses_to_start_without_a_secret_key(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("BASEERA_SECRET_KEY", raising=False)
    monkeypatch.setenv("BASEERA_ENVIRONMENT", "production")
    with pytest.raises(Exception) as excinfo:
        create_app(
            database_url=f"sqlite:///{tmp_path / 'no-key.db'}",
            artifact_root=tmp_path / "artifacts",
        )
    assert "BASEERA_SECRET_KEY" in str(excinfo.value)


def test_stored_credentials_round_trip_through_the_box(client: TestClient) -> None:
    headers = _executive(client)
    connector_id = _create_connector(client, headers)
    payload = {"user": "readonly", "password": "p@ss:word/with.separators"}

    session_factory = client.app.state.session_factory  # type: ignore[attr-defined]
    box = client.app.state.secret_box  # type: ignore[attr-defined]
    with session_factory() as db:
        connector = db.scalar(select(Connector).where(Connector.id == connector_id))
        assert connector is not None
        store_credentials(db, box, connector, payload)
        db.commit()
        assert load_credentials(db, box, connector) == payload
        stored = db.scalar(select(ConnectorSecret))
        assert stored is not None
        assert json.dumps(payload) not in stored.ciphertext
