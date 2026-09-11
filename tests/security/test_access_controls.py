from __future__ import annotations

from datetime import timedelta

from baseera.models import AuthSession, Membership, SalesOrder, utcnow
from fastapi.testclient import TestClient
from sqlalchemy import select

from .conftest import login


def test_anonymous_requests_cannot_read_tenant_resources(security_client: TestClient) -> None:
    for path in (
        "/api/v1/overview",
        "/api/v1/company/people",
        "/api/v1/decisions",
        "/api/v1/reports/not-a-report/export?format=html",
        "/api/v1/jobs/not-a-job",
    ):
        response = security_client.get(path)
        assert response.status_code == 401, (path, response.text)
        assert response.json()["error"]["code"] == "authentication_required"


def test_membership_revocation_takes_effect_on_the_next_request(
    security_client: TestClient,
) -> None:
    login(security_client)
    with security_client.app.state.session_factory() as db:
        membership = db.get(Membership, "membership-executive")
        assert membership is not None
        membership.active = False
        db.commit()

    response = security_client.get("/api/v1/overview")

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "permission_revoked"


def test_expired_sessions_are_rejected(security_client: TestClient) -> None:
    login(security_client)
    with security_client.app.state.session_factory() as db:
        session = db.scalar(select(AuthSession))
        assert session is not None
        session.expires_at = utcnow() - timedelta(seconds=1)
        db.commit()

    response = security_client.get("/api/v1/overview")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "session_expired"


def test_viewer_without_write_permission_cannot_mutate_artifacts(
    security_client: TestClient,
) -> None:
    headers = login(
        security_client,
        "viewer@empty.baseera.local",
        "BaseeraEmpty!2026",
    )

    response = security_client.post(
        "/api/v1/datasets/upload",
        files={"file": ("orders.csv", b"id,revenue\n1,10\n", "text/csv")},
        headers=headers,
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "permission_denied"


def test_aggregate_people_permission_does_not_disclose_individual_fields(
    security_client: TestClient,
) -> None:
    login(security_client)

    response = security_client.get("/api/v1/company/people")

    if response.status_code == 403:
        assert response.json()["error"]["code"] == "permission_denied"
        return
    assert response.status_code == 200, response.text
    forbidden = {"name", "skills", "capacity_hours", "workload_hours"}
    assert all(forbidden.isdisjoint(person) for person in response.json()["items"])


def test_department_manager_operations_are_row_scoped(
    security_client: TestClient,
) -> None:
    # Demo sales are assigned to sales, so add an in-scope row to test both inclusion
    # and exclusion instead of assuming support owns seeded sales orders.
    with security_client.app.state.session_factory() as db:
        order = db.scalar(select(SalesOrder))
        assert order is not None
        order.department_id = "dept-support"
        db.commit()
    login(
        security_client,
        "manager@demo.baseera.local",
        "BaseeraManager!2026",
    )

    response = security_client.get("/api/v1/company/operations")

    assert response.status_code == 200, response.text
    assert response.json()["items"]
    assert {item["department_id"] for item in response.json()["items"]} == {"dept-support"}


def test_login_endpoint_eventually_rate_limits_repeated_failures(
    security_client: TestClient,
) -> None:
    statuses = [
        security_client.post(
            "/api/v1/auth/login",
            json={
                "email": "executive@demo.baseera.local",
                "password": f"invalid-{attempt}",
            },
        ).status_code
        for attempt in range(30)
    ]

    assert 429 in statuses
