from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from baseera.main import create_app
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    database_url = f"sqlite:///{tmp_path / 'baseera-test.db'}"
    app = create_app(
        database_url=database_url,
        artifact_root=tmp_path / "artifacts",
        testing=True,
        seed_demo=True,
        connector_allow_hosts=("erp.example.test",),
    )
    with TestClient(app) as test_client:
        yield test_client


def login(
    client: TestClient,
    email: str = "executive@demo.baseera.local",
    password: str = "BaseeraDemo!2026",
) -> dict[str, str]:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    body = response.json()
    return {"X-CSRF-Token": body["csrf_token"]}


@pytest.fixture
def auth_headers(client: TestClient) -> dict[str, str]:
    return login(client)
