"""The analyst team over HTTP: runs, live events, conversations, exports and isolation."""

from __future__ import annotations

from fastapi.testclient import TestClient

from .conftest import login


def _sample(
    client: TestClient, headers: dict[str, str], sample: str = "customer_churn", locale: str = "en"
) -> str:
    response = client.post(
        f"/api/v1/analyst/samples/{sample}", json={"locale": locale}, headers=headers
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["version"]["row_count"] == 3000
    return body["version"]["id"]


def test_team_and_samples_describe_the_product(client: TestClient) -> None:
    login(client)
    team = client.get("/api/v1/analyst/team").json()
    assert [member["id"] for member in team["team"]][:2] == ["chief", "data_engineer"]
    assert team["engine"]["provider"] == "deterministic"
    assert {tool["name"] for tool in team["tools"]} >= {"forecast", "key_drivers", "explain_change"}
    samples = client.get("/api/v1/analyst/samples").json()["items"]
    assert {sample["id"] for sample in samples} == {"retail_sales", "customer_churn"}


def test_full_analysis_lifecycle_and_exports(client: TestClient) -> None:
    headers = login(client)
    version_id = _sample(client, headers, locale="ar")
    created = client.post(
        "/api/v1/analyst/runs",
        json={"dataset_version_id": version_id, "mode": "autopilot", "locale": "ar"},
        headers=headers,
    )
    assert created.status_code == 202, created.text
    run = created.json()
    assert run["status"] == "completed"
    assert run["result"]["findings"] and run["result"]["recommendations"]
    assert run["events_total"] > 10

    page = client.get(
        f"/api/v1/analyst/runs/{run['id']}", params={"since": run["events_total"] - 2}
    ).json()
    assert len(page["events"]) == 2 and page["events"][-1]["type"] == "done"

    magic = {"pdf": b"%PDF", "docx": b"PK", "pptx": b"PK", "html": b"<!doctype html>"}
    for kind in ("pdf", "docx", "pptx", "html", "md", "json"):
        exported = client.get(f"/api/v1/analyst/runs/{run['id']}/export", params={"format": kind})
        assert exported.status_code == 200, (kind, exported.text[:200])
        assert "attachment" in exported.headers["content-disposition"]
        if kind in magic:
            assert exported.content.startswith(magic[kind]), kind
    english = client.get(
        f"/api/v1/analyst/runs/{run['id']}/export", params={"format": "md", "locale": "en"}
    )
    assert "Analysis dossier" in english.text

    workspace = client.get("/api/v1/analyst/workspace").json()["items"]
    assert workspace[0]["last_analysis"]["status"] == "completed"
    listing = client.get("/api/v1/analyst/runs", params={"dataset_version_id": version_id}).json()
    assert listing["items"][0]["summary"]["findings"] == len(run["result"]["findings"])


def test_conversation_threads(client: TestClient) -> None:
    headers = login(client)
    version_id = _sample(client, headers)
    first = client.post(
        "/api/v1/analyst/runs",
        json={
            "dataset_version_id": version_id,
            "mode": "question",
            "question": "What drives churned?",
            "locale": "en",
        },
        headers=headers,
    ).json()
    assert first["status"] == "completed" and first["thread_id"].startswith("thread-")
    assert "[ev-1]" in first["result"]["answer"]
    follow_up = client.post(
        "/api/v1/analyst/runs",
        json={
            "dataset_version_id": version_id,
            "mode": "question",
            "question": "And the forecast of signups?",
            "locale": "en",
            "thread_id": first["thread_id"],
        },
        headers=headers,
    ).json()
    assert follow_up["thread_id"] == first["thread_id"]
    threads = client.get(
        "/api/v1/analyst/threads", params={"dataset_version_id": version_id}
    ).json()
    assert threads["items"][0]["turns"] == 2
    not_exportable = client.get(f"/api/v1/analyst/runs/{first['id']}/export")
    assert not_exportable.status_code == 409


def test_validation_and_cancellation(client: TestClient) -> None:
    headers = login(client)
    version_id = _sample(client, headers)
    base = {"dataset_version_id": version_id, "locale": "en"}
    assert (
        client.post(
            "/api/v1/analyst/runs", json={**base, "mode": "question"}, headers=headers
        ).status_code
        == 422
    )
    assert (
        client.post(
            "/api/v1/analyst/runs",
            json={**base, "mode": "question", "question": "q", "thread_id": "../../x"},
            headers=headers,
        ).status_code
        == 422
    )
    missing = client.post(
        "/api/v1/analyst/runs",
        json={"dataset_version_id": "dataset-version-missing", "mode": "autopilot"},
        headers=headers,
    )
    assert missing.status_code == 404
    no_csrf = client.post("/api/v1/analyst/runs", json={**base, "mode": "autopilot"})
    assert no_csrf.status_code == 403
    done = client.post(
        "/api/v1/analyst/runs", json={**base, "mode": "autopilot"}, headers=headers
    ).json()
    cancelled = client.post(
        f"/api/v1/analyst/runs/{done['id']}/cancel", json={}, headers=headers
    ).json()
    assert cancelled["status"] == "completed"  # a finished run is not rewritten


def test_runs_are_private_to_their_owner_and_tenant(client: TestClient) -> None:
    headers = login(client)
    version_id = _sample(client, headers)
    run = client.post(
        "/api/v1/analyst/runs",
        json={"dataset_version_id": version_id, "mode": "autopilot"},
        headers=headers,
    ).json()
    client.post("/api/v1/auth/logout", headers=headers)

    # Another tenant sees nothing.
    other = login(client, "viewer@empty.baseera.local", "BaseeraEmpty!2026")
    assert client.get(f"/api/v1/analyst/runs/{run['id']}").status_code == 404
    assert client.get("/api/v1/analyst/workspace").json()["items"] == []
    assert client.post(
        "/api/v1/analyst/runs",
        json={"dataset_version_id": version_id, "mode": "autopilot"},
        headers=other,
    ).status_code in {403, 404}
    client.post("/api/v1/auth/logout", headers=other)

    # A department-scoped manager in the same tenant cannot open the executive's upload.
    manager = login(client, "manager@demo.baseera.local", "BaseeraManager!2026")
    assert client.get(f"/api/v1/analyst/runs/{run['id']}").status_code == 404
    denied = client.post(
        "/api/v1/analyst/runs",
        json={"dataset_version_id": version_id, "mode": "autopilot"},
        headers=manager,
    )
    assert denied.status_code == 404
