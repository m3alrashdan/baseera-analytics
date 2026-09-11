import os
import subprocess
import sys
from pathlib import Path

import pytest
from baseera.jobs import claim_next_job, execute_job
from baseera.models import Job, Membership, MetricResult
from fastapi.testclient import TestClient


def test_worker_computes_a_real_persisted_result(client: TestClient, auth_headers: dict[str, str]):
    response = client.post(
        "/api/v1/jobs",
        headers=auth_headers,
        json={"kind": "metric_refresh", "payload": {"metric_id": "net_revenue"}},
    )
    assert response.status_code == 202
    with client.app.state.session_factory() as db:
        job = claim_next_job(db)
        assert job is not None
        execute_job(db, job)
        assert job.status == "completed"
        result = db.get(MetricResult, job.result_ref)
        assert result is not None
        assert result.payload["value"] > 0
        assert result.payload["evidence"]["job_id"] == job.id


def test_worker_rechecks_permissions_after_enqueue(
    client: TestClient, auth_headers: dict[str, str]
):
    client.post(
        "/api/v1/jobs",
        headers=auth_headers,
        json={"kind": "metric_refresh", "payload": {"metric_id": "net_revenue"}},
    )
    with client.app.state.session_factory() as db:
        membership = db.get(Membership, "membership-executive")
        membership.active = False
        db.commit()
        job = claim_next_job(db)
        execute_job(db, job)
        assert job.status == "failed"
        assert job.error["code"] == "permission_revoked"
        assert job.result_ref is None


@pytest.mark.parametrize("metric_id", [{"injected": True}, ["net_revenue"], "unknown_metric"])
def test_worker_rejects_invalid_metric_without_crashing(
    client: TestClient, auth_headers: dict[str, str], metric_id: object
):
    response = client.post(
        "/api/v1/jobs",
        headers=auth_headers,
        json={"kind": "metric_refresh", "payload": {"metric_id": metric_id}},
    )
    assert response.status_code == 202
    with client.app.state.session_factory() as db:
        job = claim_next_job(db)
        execute_job(db, job)
        assert job.status == "failed"
        assert job.error["code"] == "unsupported_job_parameters"
        assert job.result_ref is None


def test_separate_worker_process_publishes_a_readable_result(
    client: TestClient, auth_headers: dict[str, str], tmp_path: Path
):
    response = client.post(
        "/api/v1/jobs",
        headers=auth_headers,
        json={"kind": "metric_refresh", "payload": {"metric_id": "net_revenue"}},
    )
    assert response.status_code == 202
    job_id = response.json()["id"]
    repository = Path(__file__).resolve().parents[2]
    process = subprocess.run(
        [sys.executable, "-m", "baseera.worker", "--once"],
        cwd=repository,
        env={
            **os.environ,
            "PYTHONPATH": str(repository / "services/api"),
            "BASEERA_DATABASE_URL": f"sqlite:///{tmp_path / 'baseera-test.db'}",
        },
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert process.returncode == 0, process.stderr
    with client.app.state.session_factory() as db:
        job = db.get(Job, job_id)
        assert job.status == "completed"
        result = client.get(f"/api/v1/metric-results/{job.result_ref}")
        assert result.status_code == 200
        assert result.json()["value"] > 0
