from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from baseera.main import create_app
from baseera.models import Job
from fastapi.testclient import TestClient


def test_connector_host_policy_incremental_checkpoint_and_schema_drift(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    rejected = client.post(
        "/api/v1/connectors",
        json={"kind": "rest", "name": "Unsafe", "base_url": "http://127.0.0.1/api"},
        headers=auth_headers,
    )
    assert rejected.status_code == 422
    assert rejected.json()["error"]["code"] == "connector_destination_denied"

    lookalike = client.post(
        "/api/v1/connectors",
        json={
            "kind": "rest",
            "name": "Lookalike",
            "base_url": "https://erp.example.test.attacker.invalid/api",
        },
        headers=auth_headers,
    )
    assert lookalike.status_code == 422

    created = client.post(
        "/api/v1/connectors",
        json={
            "kind": "rest",
            "name": "Approved ERP",
            "base_url": "https://erp.example.test/api/v1",
            "primary_key": "id",
            "incremental_field": "updated_at",
        },
        headers=auth_headers,
    )
    assert created.status_code == 201, created.text
    connector_id = created.json()["id"]

    first_payload = {
        "schema": {"id": "string", "updated_at": "datetime", "amount": "number"},
        "records": [
            {"id": "A", "updated_at": "2026-06-01T10:00:00Z", "amount": 10},
            {"id": "B", "updated_at": "2026-06-01T11:00:00Z", "amount": 20},
        ],
        "checkpoint": {"updated_at": "2026-06-01T11:00:00Z", "id": "B"},
    }
    first = client.post(
        f"/api/v1/connectors/{connector_id}/sync",
        json=first_payload,
        headers={**auth_headers, "Idempotency-Key": "sync-page-1"},
    )
    assert first.status_code == 200, first.text
    assert first.json()["committed"] == 2
    assert first.json()["checkpoint"] == first_payload["checkpoint"]

    retry = client.post(
        f"/api/v1/connectors/{connector_id}/sync",
        json=first_payload,
        headers={**auth_headers, "Idempotency-Key": "sync-page-1"},
    )
    assert retry.status_code == 200
    assert retry.json()["deduplicated"] is True
    assert retry.json()["run_id"] == first.json()["run_id"]

    second = client.post(
        f"/api/v1/connectors/{connector_id}/sync",
        json={
            **first_payload,
            "records": [
                {"id": "B", "updated_at": "2026-06-02T09:00:00Z", "amount": 25},
                {"id": "C", "updated_at": "2026-06-02T10:00:00Z", "amount": 30},
            ],
            "checkpoint": {"updated_at": "2026-06-02T10:00:00Z", "id": "C"},
        },
        headers={**auth_headers, "Idempotency-Key": "sync-page-2"},
    )
    assert second.status_code == 200
    assert second.json()["inserted"] == 1
    assert second.json()["updated"] == 1

    regression = client.post(
        f"/api/v1/connectors/{connector_id}/sync",
        json={
            **first_payload,
            "records": [],
            "checkpoint": {"updated_at": "2026-06-01T10:00:00Z", "id": "A"},
        },
        headers={**auth_headers, "Idempotency-Key": "sync-regression"},
    )
    assert regression.status_code == 409
    assert regression.json()["error"]["code"] == "checkpoint_regression"

    opaque = client.post(
        "/api/v1/connectors",
        json={
            "kind": "rest",
            "name": "Cursor-based ERP",
            "base_url": "https://erp.example.test/cursor-api",
            "primary_key": "id",
            "incremental_field": "updated_at",
        },
        headers=auth_headers,
    )
    opaque_id = opaque.json()["id"]
    cursor_schema = {"id": "string", "updated_at": "datetime"}
    first_cursor = client.post(
        f"/api/v1/connectors/{opaque_id}/sync",
        json={
            "schema": cursor_schema,
            "records": [{"id": "A", "updated_at": "2026-06-01T10:00:00Z"}],
            "checkpoint": {"cursor": "z-page-token"},
            "checkpoint_mode": "opaque",
        },
        headers={**auth_headers, "Idempotency-Key": "cursor-page-1"},
    )
    assert first_cursor.status_code == 200
    # Opaque cursor order is owned by the source API; lexical comparison is unsafe.
    second_cursor = client.post(
        f"/api/v1/connectors/{opaque_id}/sync",
        json={
            "schema": cursor_schema,
            "records": [],
            "checkpoint": {"cursor": "a-next-token"},
            "checkpoint_mode": "opaque",
        },
        headers={**auth_headers, "Idempotency-Key": "cursor-page-2"},
    )
    assert second_cursor.status_code == 200
    assert second_cursor.json()["checkpoint"] == {"cursor": "a-next-token"}

    drift = client.post(
        f"/api/v1/connectors/{connector_id}/sync",
        json={
            "schema": {**first_payload["schema"], "currency": "string"},
            "records": [],
            "checkpoint": {"updated_at": "2026-06-03T00:00:00Z", "id": "Z"},
        },
        headers={**auth_headers, "Idempotency-Key": "sync-drift"},
    )
    assert drift.status_code == 409
    assert drift.json()["error"]["code"] == "schema_drift"
    state = client.get(f"/api/v1/connectors/{connector_id}").json()
    assert state["checkpoint"] == second.json()["checkpoint"]
    assert state["status"] == "schema_drift"
    records = client.get(f"/api/v1/connectors/{connector_id}/records").json()["items"]
    assert {item["source_key"]: item["payload"]["amount"] for item in records} == {
        "A": 10,
        "B": 25,
        "C": 30,
    }


def test_report_patch_preserves_history_and_exports_bound_evidence(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    upload = client.post(
        "/api/v1/datasets/upload",
        files={"file": ("orders.csv", b"id,revenue\n0001,42\n", "text/csv")},
        headers=auth_headers,
    ).json()
    result = client.post(
        "/api/v1/metrics/query",
        json={"metric_id": "net_revenue", "dataset_version_id": upload["version"]["id"]},
        headers=auth_headers,
    ).json()
    report = client.post(
        "/api/v1/reports",
        json={"title": "Evidence report", "language": "en", "sections": []},
        headers=auth_headers,
    ).json()

    patched = client.post(
        f"/api/v1/reports/{report['id']}/patches",
        json={
            "expected_version": 1,
            "operations": [
                {"op": "replace_title", "value": "Evidence report v2"},
                {
                    "op": "append_section",
                    "value": {
                        "kind": "linked_metric",
                        "title": "Revenue",
                        "result_id": result["result_id"],
                    },
                },
            ],
        },
        headers=auth_headers,
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["version"] == 2
    assert patched.json()["sections"][0]["result"]["result_id"] == result["result_id"]
    versions = client.get(f"/api/v1/reports/{report['id']}/versions").json()["items"]
    assert [item["version"] for item in versions] == [1, 2]
    assert versions[0]["sections"] == []

    html = client.get(f"/api/v1/reports/{report['id']}/export?format=html")
    assert html.status_code == 200
    assert result["result_id"] in html.text
    assert "42.0" in html.text
    assert html.headers["x-baseera-report-version"] == "2"

    docx = client.get(f"/api/v1/reports/{report['id']}/export?format=docx")
    assert docx.status_code == 200
    assert docx.content.startswith(b"PK")


def test_job_cancellation_is_scoped_and_interrupted_jobs_recover(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'jobs.db'}"
    app = create_app(
        database_url=database_url,
        artifact_root=tmp_path / "artifacts",
        testing=True,
        seed_demo=True,
    )
    with TestClient(app) as client:
        login = client.post(
            "/api/v1/auth/login",
            json={"email": "executive@demo.baseera.local", "password": "BaseeraDemo!2026"},
        ).json()
        headers = {"X-CSRF-Token": login["csrf_token"]}
        created = client.post(
            "/api/v1/jobs",
            json={"kind": "metric_refresh", "payload": {"metric_id": "net_revenue"}},
            headers={**headers, "Idempotency-Key": "job-1"},
        )
        assert created.status_code == 202
        job_id = created.json()["id"]
        cancelled = client.post(f"/api/v1/jobs/{job_id}/cancel", headers=headers)
        assert cancelled.status_code == 200
        assert cancelled.json()["status"] == "cancelled"

        with app.state.session_factory() as db:
            stale = Job(
                id="job-interrupted",
                organization_id="tenant-demo",
                user_id="user-executive",
                kind="metric_refresh",
                status="running",
                payload={},
                attempt=1,
                max_attempts=3,
                heartbeat_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(minutes=10),
            )
            db.add(stale)
            db.commit()

    restarted = create_app(
        database_url=database_url,
        artifact_root=tmp_path / "artifacts",
        testing=True,
        seed_demo=True,
    )
    with TestClient(restarted) as client:
        login = client.post(
            "/api/v1/auth/login",
            json={"email": "executive@demo.baseera.local", "password": "BaseeraDemo!2026"},
        ).json()
        recovered = client.get(
            "/api/v1/jobs/job-interrupted",
            headers={"X-CSRF-Token": login["csrf_token"]},
        )
        assert recovered.status_code == 200
        assert recovered.json()["status"] == "queued"
        assert recovered.json()["error"]["code"] == "worker_interrupted"
