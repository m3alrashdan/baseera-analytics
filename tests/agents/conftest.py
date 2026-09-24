from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from baseera.agents.frame import AnalysisFrame, build_frame
from baseera.agents.samples import generate
from baseera.main import create_app
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def retail_frame() -> AnalysisFrame:
    columns, rows = generate("retail_sales")
    return build_frame(rows, columns)


@pytest.fixture(scope="session")
def churn_frame() -> AnalysisFrame:
    columns, rows = generate("customer_churn")
    return build_frame(rows, columns)


@pytest.fixture(scope="session")
def churn_frame_ar() -> AnalysisFrame:
    columns, rows = generate("customer_churn", "ar")
    return build_frame(rows, columns)


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    app = create_app(
        database_url=f"sqlite:///{tmp_path / 'agents.db'}",
        artifact_root=tmp_path / "artifacts",
        testing=True,
        seed_demo=True,
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
    return {"X-CSRF-Token": response.json()["csrf_token"]}
