from __future__ import annotations

import json
from dataclasses import replace
from datetime import date
from pathlib import Path

import httpx
import pytest
from baseera.config import load_settings
from baseera.errors import AppError
from baseera.ollama import AnalysisPlan, OllamaPlanner


def planner(handler):
    settings = replace(
        load_settings(),
        llm_provider="ollama",
        llm_model="qwen3.5:9b",
        llm_base_url="http://127.0.0.1:11434",
    )
    return OllamaPlanner(settings, httpx.MockTransport(handler))


def test_ollama_uses_typed_schema_and_never_exposes_thinking() -> None:
    requests = []

    def handle(request: httpx.Request) -> httpx.Response:
        requests.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "done": True,
                "done_reason": "stop",
                "eval_count": 51,
                "message": {
                    "content": json.dumps(
                        {
                            "action": "metric_query",
                            "metric_ids": ["net_revenue"],
                            "period": "this_month",
                        }
                    ),
                    "thinking": "private internal text",
                },
            },
        )

    plan, meta = planner(handle).plan(
        "ما الإيرادات هذا الشهر؟", locale="ar", as_of=date(2026, 6, 30)
    )
    assert plan.metric_ids == ["net_revenue"]
    assert plan.period == "this_month"
    assert requests[0]["think"] is False
    assert requests[0]["format"]["additionalProperties"] is False
    assert requests[0]["options"]["num_ctx"] <= 16384
    assert meta["live_verified"] is False
    assert "private internal text" not in str(meta)


@pytest.mark.parametrize(
    "content",
    [
        '{"action":"execute_python","code":"print(1)"}',
        '{"action":"metric_query","metric_ids":["salary"]}',
        '{"action":"metric_query","metric_ids":[]}',
        '{"action":"metric_query","metric_ids":["net_revenue"],"period":"custom"}',
        "not json",
    ],
)
def test_invalid_model_plans_cannot_execute(content: str) -> None:
    local = planner(
        lambda _: httpx.Response(200, json={"done": True, "message": {"content": content}})
    )
    with pytest.raises(AppError) as caught:
        local.plan("query", locale="en", as_of=None)
    assert caught.value.code == "provider_output_invalid"


def test_provider_failure_is_redacted_and_retryable() -> None:
    local = planner(lambda _: httpx.Response(500, text="password=do-not-expose"))
    with pytest.raises(AppError) as caught:
        local.plan("query", locale="en", as_of=None)
    assert caught.value.status_code == 503
    assert "do-not-expose" not in caught.value.message


def test_missing_model_status_is_distinct_from_unreachable() -> None:
    local = planner(lambda _: httpx.Response(200, json={"models": []}))
    status = local.status()
    assert status["status"] == "model_missing"
    assert status["live_verified"] is False
    assert status["availability_checked"] is False


def test_invalid_plan_requires_clarification_without_guessing_filters(monkeypatch):
    from types import SimpleNamespace

    from baseera.assistant import _plan

    def invalid(*args, **kwargs):
        raise AppError(502, "provider_output_invalid", "Invalid plan")

    monkeypatch.setattr(OllamaPlanner, "plan", invalid)
    state = {
        "request": {"question": "Revenue for customer 003 in 2025 versus 2024", "locale": "en"},
        "context": SimpleNamespace(organization=SimpleNamespace(reporting_date=date(2026, 6, 30))),
        "settings": load_settings(),
    }
    result = _plan(state)
    assert result["plan"].action == "clarify"
    assert result["plan"].metric_ids == []
    assert result["provider"]["status"] == "invalid_plan"
    assert result["provider"]["live_verified"] is False


def test_graph_executes_real_metrics_and_persists_scoped_conversation(
    tmp_path: Path, monkeypatch
) -> None:
    from baseera.main import create_app
    from fastapi.testclient import TestClient

    monkeypatch.setattr(
        OllamaPlanner,
        "plan",
        lambda *_a, **_k: (
            AnalysisPlan(action="metric_query", metric_ids=["net_revenue"], period="this_month"),
            {"mode": "ollama", "model": "test-double", "live_verified": False},
        ),
    )
    app = create_app(
        database_url=f"sqlite:///{tmp_path / 'assistant.db'}",
        artifact_root=tmp_path / "files",
        testing=True,
        seed_demo=True,
    )
    with TestClient(app) as client:
        login = client.post(
            "/api/v1/auth/login",
            json={"email": "executive@demo.baseera.local", "password": "BaseeraDemo!2026"},
        ).json()
        answer = client.post(
            "/api/v1/assistant/query",
            json={"question": "ما الإيرادات هذا الشهر؟", "locale": "ar"},
            headers={"X-CSRF-Token": login["csrf_token"]},
        )
        assert answer.status_code == 200, answer.text
        body = answer.json()
        assert body["execution"]["engine"] == "langgraph"
        assert body["results"][0]["value"] > 0
        assert body["results"][0]["evidence"]["scope"]["start_date"] == "2026-06-01"
        assert body["results"][0]["evidence"]["scope"]["end_date_exclusive"] == "2026-07-01"
        assert body["results"][0]["result_id"] in body["findings"][0]["evidence_ids"]
        conversation_id = body["conversation_id"]
        assert client.get(f"/api/v1/conversations/{conversation_id}").status_code == 200
        client.post(
            "/api/v1/auth/login",
            json={"email": "viewer@empty.baseera.local", "password": "BaseeraEmpty!2026"},
        )
        assert client.get(f"/api/v1/conversations/{conversation_id}").status_code == 404
        assert client.get("/api/v1/conversations").json()["items"] == []


def test_deterministic_arabic_answer_preserves_missing_cost(tmp_path: Path) -> None:
    from baseera.main import create_app
    from fastapi.testclient import TestClient

    app = create_app(
        database_url=f"sqlite:///{tmp_path / 'missing.db'}",
        artifact_root=tmp_path / "files",
        testing=True,
        seed_demo=True,
    )
    with TestClient(app) as client:
        login = client.post(
            "/api/v1/auth/login",
            json={"email": "executive@demo.baseera.local", "password": "BaseeraDemo!2026"},
        ).json()
        headers = {"X-CSRF-Token": login["csrf_token"]}
        upload = client.post(
            "/api/v1/datasets/upload",
            files={"file": ("missing.csv", b"id,revenue,cost\n001,100,\n", "text/csv")},
            headers=headers,
        ).json()
        answer = client.post(
            "/api/v1/assistant/query",
            json={
                "question": "احسب الربح",
                "locale": "ar",
                "metric_id": "gross_margin",
                "dataset_version_id": upload["version"]["id"],
            },
            headers=headers,
        )
        assert answer.status_code == 200, answer.text
        body = answer.json()
        assert body["status"] == "insufficient_data"
        assert body["results"][0]["value"] is None
        assert body["findings"][0]["classification"] == "insufficient_data"
        assert "غير متاح" in body["answer"]
