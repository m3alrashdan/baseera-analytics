from __future__ import annotations

from fastapi.testclient import TestClient

from .conftest import login


def test_demo_login_sets_secure_session_and_returns_scoped_context(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "executive@demo.baseera.local", "password": "BaseeraDemo!2026"},
    )

    assert response.status_code == 200
    assert response.json()["tenant"]["id"] == "tenant-demo"
    assert response.json()["tenant"]["is_demo"] is True
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=lax" in cookie
    assert "path=/" in cookie
    assert "baseera_session=" in cookie


def test_invalid_login_is_generic_and_does_not_create_session(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "executive@demo.baseera.local", "password": "wrong-password"},
    )

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_credentials"
    assert "baseera_session" not in response.cookies


def test_mutation_requires_matching_csrf_token(client: TestClient) -> None:
    login(client)

    missing = client.post("/api/v1/decisions", json={"title": "Review support staffing"})
    wrong = client.post(
        "/api/v1/decisions",
        json={"title": "Review support staffing"},
        headers={"X-CSRF-Token": "wrong"},
    )

    assert missing.status_code == 403
    assert missing.json()["error"]["code"] == "csrf_failed"
    assert wrong.status_code == 403


def test_tenant_owned_identifiers_cannot_be_read_across_tenants(client: TestClient) -> None:
    demo_headers = login(client)
    upload = client.post(
        "/api/v1/datasets/upload",
        files={"file": ("orders.csv", b"order_id,revenue\n0001,10\n", "text/csv")},
        headers=demo_headers,
    )
    assert upload.status_code == 201
    dataset_id = upload.json()["dataset"]["id"]

    client.post("/api/v1/auth/logout", headers=demo_headers)
    login(client, "viewer@empty.baseera.local", "BaseeraEmpty!2026")
    response = client.get(f"/api/v1/datasets/{dataset_id}")

    # Do not reveal whether an object in another tenant exists.
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_security_headers_and_correlation_id_are_present(client: TestClient) -> None:
    response = client.get("/api/v1/health/live")

    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert "default-src 'self'" in response.headers["content-security-policy"]
    assert response.headers["x-correlation-id"]
