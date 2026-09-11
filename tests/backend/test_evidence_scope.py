from datetime import date

from baseera.jobs import claim_next_job, execute_job
from baseera.models import Membership, MetricResult, SalesOrder
from fastapi.testclient import TestClient
from sqlalchemy import select

from .conftest import login


def test_overview_assistant_and_worker_share_the_reporting_cutoff(
    client: TestClient, auth_headers: dict[str, str]
):
    before = client.get("/api/v1/overview").json()["metrics"]["net_revenue"]["value"]
    with client.app.state.session_factory() as db:
        order = db.scalar(select(SalesOrder).where(SalesOrder.organization_id == "tenant-demo"))
        future_revenue = order.revenue
        order.order_date = date(2026, 7, 15)
        db.commit()
    overview = client.get("/api/v1/overview").json()["metrics"]["net_revenue"]
    assert abs(overview["value"] - (before - future_revenue)) < 0.01
    answer = client.post(
        "/api/v1/assistant/query",
        json={"question": "All available revenue", "metric_id": "net_revenue", "locale": "en"},
        headers=auth_headers,
    )
    assert answer.status_code == 200, answer.text
    result = answer.json()["results"][0]
    assert result["value"] == overview["value"]
    assert result["evidence"]["scope"]["end_date_exclusive"] == "2026-07-01"
    assert "2026-07-01" in answer.json()["answer"]
    queued = client.post(
        "/api/v1/jobs",
        json={"kind": "metric_refresh", "payload": {"metric_id": "net_revenue"}},
        headers=auth_headers,
    )
    assert queued.status_code == 202
    with client.app.state.session_factory() as db:
        job = claim_next_job(db)
        execute_job(db, job)
        assert job.status == "completed"
        assert db.get(MetricResult, job.result_ref).payload["value"] == overview["value"]


def test_manager_cannot_reuse_broader_evidence(client: TestClient, auth_headers: dict[str, str]):
    upload = client.post(
        "/api/v1/datasets/upload",
        headers=auth_headers,
        files={"file": ("sales.csv", b"id,revenue,cost\n1,10,4\n", "text/csv")},
    ).json()
    result = client.post(
        "/api/v1/assistant/query",
        headers=auth_headers,
        json={"question": "Revenue", "metric_id": "net_revenue"},
    ).json()["results"][0]
    manager = login(client, "manager@demo.baseera.local", "BaseeraManager!2026")
    assert (
        client.get(f"/api/v1/dataset-versions/{upload['version']['id']}/profile").status_code == 404
    )
    assert client.get(f"/api/v1/metric-results/{result['result_id']}").status_code == 404
    response = client.post(
        "/api/v1/reports",
        headers=manager,
        json={
            "title": "Restricted",
            "sections": [{"type": "metric", "result_id": result["result_id"]}],
        },
    )
    assert response.status_code == 404


def test_saved_report_rechecks_scope_after_demotion(
    client: TestClient, auth_headers: dict[str, str]
):
    result = client.post(
        "/api/v1/assistant/query",
        headers=auth_headers,
        json={"question": "Revenue", "metric_id": "net_revenue"},
    ).json()["results"][0]
    report = client.post(
        "/api/v1/reports",
        headers=auth_headers,
        json={
            "title": "Executive",
            "sections": [{"type": "metric", "result_id": result["result_id"]}],
        },
    ).json()
    with client.app.state.session_factory() as db:
        membership = db.get(Membership, "membership-executive")
        membership.role = "department_manager"
        membership.department_ids = ["dept-support"]
        db.commit()
    assert client.get(f"/api/v1/reports/{report['id']}/versions").status_code == 404
    assert client.get(f"/api/v1/reports/{report['id']}/export?format=html").status_code == 404


def test_dashboard_versions_are_immutable_and_conflict_safe(
    client: TestClient, auth_headers: dict[str, str]
):
    saved = client.post(
        "/api/v1/dashboards", headers=auth_headers, json={"title": "First", "widgets": []}
    ).json()
    assert client.get("/api/v1/dashboards").json()["items"][0]["id"] == saved["id"]
    patch = {
        "title": "Second",
        "widgets": [{"type": "note", "content": "Review"}],
        "expected_version": 1,
    }
    updated = client.patch(f"/api/v1/dashboards/{saved['id']}", headers=auth_headers, json=patch)
    assert updated.status_code == 200
    assert updated.json()["version"] == 2
    assert (
        client.patch(
            f"/api/v1/dashboards/{saved['id']}", headers=auth_headers, json=patch
        ).status_code
        == 409
    )
    assert client.get(f"/api/v1/dashboards/{saved['id']}?version=1").json()["widgets"] == []
    assert (
        client.get(f"/api/v1/dashboards/{saved['id']}").json()["widgets"][0]["content"] == "Review"
    )


def test_nested_json_is_profiled_without_server_error(
    client: TestClient, auth_headers: dict[str, str]
):
    response = client.post(
        "/api/v1/datasets/upload",
        headers=auth_headers,
        files={"file": ("nested.json", b'[{"id":{"key":1},"tags":["a"]}]', "application/json")},
    )
    assert response.status_code == 201, response.text
