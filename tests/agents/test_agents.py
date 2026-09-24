"""The analyst team: critic, orchestration, providers and the model tool loop."""

from __future__ import annotations

import json
from dataclasses import replace
from types import SimpleNamespace
from typing import Any

import httpx
import pytest
from baseera.agents import critic
from baseera.agents.frame import AnalysisFrame
from baseera.agents.llm import AnthropicProvider, OllamaProvider, ToolCall, Turn, select_provider
from baseera.agents.orchestrator import run_autopilot, run_question
from baseera.agents.router import detect_intents, plan
from baseera.agents.workspace import Cancelled
from baseera.config import load_settings
from baseera.errors import AppError

SETTINGS = replace(load_settings(), agent_provider="deterministic", anthropic_api_key=None)


# --------------------------------------------------------------------------- critic
def test_verify_numbers_accepts_evidence_and_flags_inventions() -> None:
    evidence = {1250.5, 0.123, 3000.0}
    ok = critic.verify_numbers("Revenue was 1,250.5 and grew 12.3% across 3,000 rows.", evidence)
    assert ok["passed"] and ok["numbers_checked"] == 3
    bad = critic.verify_numbers("Revenue will reach 9,999 next year.", evidence)
    assert bad["unverified"] == ["9999"] and not bad["passed"]
    arabic = critic.verify_numbers("نما بنسبة ١٢٫٣٪ في عام 2025", evidence)
    assert arabic["passed"] and arabic["numbers_checked"] == 1
    compact = critic.verify_numbers("about 1.25K orders", evidence)
    assert compact["passed"]
    causal = critic.verify_numbers("Discounts cause returns.", evidence)
    assert causal["causal_language"]


def test_review_downgrades_weak_findings() -> None:
    findings = [
        {
            "kind": "group_difference",
            "confidence_score": 0.8,
            "evidence": {"n": 20, "p_value": 0.3, "effect_magnitude": "negligible"},
        },
        {
            "kind": "forecast",
            "confidence_score": 0.8,
            "evidence": {"beats_benchmark": False, "wape": 0.45},
        },
    ]
    reviewed = critic.review(findings, {"score": 95})
    assert reviewed[0]["confidence"] == "low" and len(reviewed[0]["caveats"]) == 3
    assert reviewed[1]["confidence"] == "low"


# ----------------------------------------------------------------------- deterministic
def test_autopilot_produces_a_complete_dossier(churn_frame: AnalysisFrame) -> None:
    events: list[dict[str, Any]] = []
    dossier = run_autopilot(churn_frame, {"name": "churn"}, "en", None, SETTINGS, events.append)
    kinds = {finding["kind"] for finding in dossier["findings"]}
    assert {"schema", "kpi", "drivers", "trend", "forecast"} <= kinds
    assert dossier["recommendations"] and dossier["recommendations"][0]["rank"] == 1
    assert dossier["executive_summary"]["en"] and dossier["executive_summary"]["ar"]
    assert dossier["verification"]["mode"] == "deterministic"
    assert {event["type"] for event in events} >= {"plan", "tool_call", "finding", "done"}
    ids = {finding["id"] for finding in dossier["findings"]}
    for section in dossier["sections"]:
        assert set(section["findings"]) <= ids
    for finding in dossier["findings"]:
        if finding["evidence_id"]:
            assert finding["evidence_id"] in dossier["evidence"]
    for rec in dossier["recommendations"]:
        assert set(rec["based_on"]) <= ids
    json.dumps(dossier)  # the dossier is stored as JSON


def test_autopilot_can_be_cancelled(churn_frame: AnalysisFrame) -> None:
    with pytest.raises(Cancelled):
        run_autopilot(churn_frame, {"name": "c"}, "en", None, SETTINGS, None, lambda: True)


@pytest.mark.parametrize(
    ("question", "tool"),
    [
        ("What drives churned?", "key_drivers"),
        ("forecast the number of signups for next 6 months", "forecast"),
        ("ما العوامل التي تؤثر على churned؟", "key_drivers"),
        ("which records look unusual", "record_anomalies"),
        ("What if usage_hours increases by 20%?", "what_if"),
        ("top plan by monthly_fee", "query_data"),
    ],
)
def test_router_maps_questions_to_tools(
    churn_frame: AnalysisFrame, question: str, tool: str
) -> None:
    assert plan(churn_frame, question)[0][0] == tool


def test_router_ignores_intent_words_inside_column_names(churn_frame_ar: AnalysisFrame) -> None:
    steps = plan(churn_frame_ar, "ما أعلى الباقة حسب الرسوم_الشهرية")
    assert [tool for tool, _ in steps] == ["query_data"]
    assert detect_intents("hello") == ["summary"]


def test_deterministic_question_cites_evidence(churn_frame: AnalysisFrame) -> None:
    answer = run_question(churn_frame, {"name": "c"}, "What drives churned?", "en", None, SETTINGS)
    assert "[ev-1]" in answer["answer"]
    assert answer["evidence"][0]["tool"] == "key_drivers"
    assert answer["verification"]["mode"] == "deterministic"


# ------------------------------------------------------------------------ model loop
class ScriptedSession:
    def __init__(self, script: list[Turn]) -> None:
        self.script = script
        self.sent: list[Any] = []

    def send(self, text: str) -> Turn:
        self.sent.append(text)
        return self.script.pop(0)

    def send_tool_results(self, results: list[tuple[ToolCall, str, bool]]) -> Turn:
        self.sent.append(results)
        return self.script.pop(0)


class ScriptedProvider:
    name = "scripted"
    model = "test-model"

    def __init__(self, scripts: list[list[Turn]]) -> None:
        self.scripts = scripts
        self.sessions: list[ScriptedSession] = []

    def status(self) -> dict[str, Any]:
        return {"provider": self.name, "model": self.model}

    def session(
        self, system: str, tools: list[dict[str, Any]], json_schema: Any = None
    ) -> ScriptedSession:
        session = ScriptedSession(self.scripts.pop(0))
        self.sessions.append(session)
        return session


def test_model_answer_is_verified_against_tool_evidence(churn_frame: AnalysisFrame) -> None:
    provider = ScriptedProvider(
        [
            [
                Turn(
                    "",
                    [
                        ToolCall(
                            "c1",
                            "query_data",
                            {"group_by": ["plan"], "metrics": [{"agg": "count", "as": "n"}]},
                        )
                    ],
                    "tool_use",
                ),
                Turn("There are 3,000 subscribers [ev-1]; churn will hit 87,654 next year.", []),
            ]
        ]
    )
    answer = run_question(churn_frame, {"name": "c"}, "How many?", "en", provider, SETTINGS)  # type: ignore[arg-type]
    assert answer["engine"]["provider"] == "scripted"
    assert answer["evidence"][0]["tool"] == "query_data"
    assert answer["verification"]["unverified"] == ["87654"]
    results = provider.sessions[0].sent[1]
    assert results[0][1].startswith("[ev-1] ") and results[0][2] is False


def test_tool_budget_and_bad_tools_are_reported_to_the_model(churn_frame: AnalysisFrame) -> None:
    calls = [ToolCall(f"c{i}", "headline_kpis", {}) for i in range(3)] + [
        ToolCall("x", "drop_database", {})
    ]
    provider = ScriptedProvider([[Turn("", calls, "tool_use"), Turn("done", [])]])
    settings = replace(SETTINGS, agent_max_tool_calls=2)
    run_question(churn_frame, {"name": "c"}, "q", "en", provider, settings)  # type: ignore[arg-type]
    results = provider.sessions[0].sent[1]
    assert [is_error for _, _, is_error in results] == [False, False, True, True]
    assert "budget" in results[2][1] and "Unknown tool" in results[3][1]


def test_autopilot_merges_verified_model_writing(churn_frame: AnalysisFrame) -> None:
    writing = {
        "headline": "Churn is concentrated among low-usage subscribers.",
        "executive_summary": "Churn is driven by usage and support load.",
        "insights": [{"finding_id": "f-1", "so_what": "The data supports the analysis."}],
        "recommendations": [],
        "risks": ["Association is not causation."],
        "next_questions": ["Which plan churns most?"],
    }
    provider = ScriptedProvider(
        [
            [Turn("- Usage is the strongest lever [ev-3].", [])],
            [Turn(json.dumps(writing), [])],
        ]
    )
    dossier = run_autopilot(churn_frame, {"name": "c"}, "en", provider, SETTINGS)  # type: ignore[arg-type]
    assert dossier["engine"]["provider"] == "scripted"
    assert dossier["executive_summary"]["en"] == writing["executive_summary"]
    assert dossier["executive_summary"]["source"] == "model"
    assert dossier["headline"]["en"] == writing["headline"]
    assert any(f["kind"] == "investigation" for f in dossier["findings"])
    assert dossier["verification"]["mode"] == "model_written_verified"


def test_provider_failure_falls_back_to_the_expert_engine(churn_frame: AnalysisFrame) -> None:
    class Broken(ScriptedProvider):
        def session(self, *args: Any, **kwargs: Any) -> ScriptedSession:
            raise AppError(503, "provider_unavailable", "down")

    dossier = run_autopilot(churn_frame, {"name": "c"}, "ar", Broken([]), SETTINGS)  # type: ignore[arg-type]
    assert dossier["engine"]["error"]["code"] == "provider_unavailable"
    assert dossier["executive_summary"]["ar"]
    answer = run_question(
        churn_frame, {"name": "c"}, "What drives churned?", "en", Broken([]), SETTINGS
    )  # type: ignore[arg-type]
    assert answer["engine"]["error"]["code"] == "provider_unavailable"
    assert answer["evidence"]


# ------------------------------------------------------------------------- providers
class FakeMessages:
    def __init__(self, responses: list[Any]) -> None:
        self.responses = responses
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return self.responses.pop(0)


def _message(content: list[Any], stop_reason: str = "end_turn") -> Any:
    return SimpleNamespace(
        content=content,
        stop_reason=stop_reason,
        model="claude-opus-5",
        usage=SimpleNamespace(input_tokens=10, output_tokens=5, cache_read_input_tokens=0),
    )


def test_anthropic_session_follows_the_messages_contract() -> None:
    tool_use = SimpleNamespace(type="tool_use", id="toolu_1", name="headline_kpis", input={})
    thinking = SimpleNamespace(type="thinking", thinking="", signature="sig")
    messages = FakeMessages(
        [
            _message([thinking, tool_use], "tool_use"),
            _message([SimpleNamespace(type="text", text="Answer [ev-1]")]),
        ]
    )
    client = SimpleNamespace(beta=SimpleNamespace(messages=messages), messages=messages)
    provider = AnthropicProvider(replace(SETTINGS, anthropic_fallbacks=True), client=client)
    session = provider.session(
        "system",
        [{"name": "headline_kpis", "description": "d", "input_schema": {"type": "object"}}],
    )
    first = session.send("hello")
    assert first.tool_calls[0].name == "headline_kpis"
    call = messages.calls[0]
    assert call["model"] == "claude-opus-5"
    assert call["thinking"] == {"type": "adaptive"}
    assert call["output_config"] == {"effort": "high"}
    assert call["cache_control"] == {"type": "ephemeral"}
    assert call["betas"] == ["server-side-fallback-2026-07-01"] and call["fallbacks"] == "default"
    second = session.send_tool_results([(first.tool_calls[0], "[ev-1] {}", False)])
    assert second.text == "Answer [ev-1]"
    history = messages.calls[1]["messages"]
    # Thinking and tool-use blocks go back unchanged; all results share one user turn.
    assert history[1]["content"] == [thinking, tool_use]
    assert history[2]["content"] == [
        {"type": "tool_result", "tool_use_id": "toolu_1", "content": "[ev-1] {}"}
    ]


def test_anthropic_structured_output_and_refusal() -> None:
    messages = FakeMessages([_message([], "refusal")])
    client = SimpleNamespace(beta=SimpleNamespace(messages=messages), messages=messages)
    provider = AnthropicProvider(replace(SETTINGS, anthropic_fallbacks=False), client=client)
    session = provider.session("system", [], {"type": "object"})
    with pytest.raises(AppError) as refused:
        session.send("write")
    assert refused.value.code == "provider_refused"
    call = messages.calls[0]
    assert call["output_config"]["format"] == {"type": "json_schema", "schema": {"type": "object"}}
    assert "tools" not in call and "betas" not in call


def test_ollama_session_uses_function_calling() -> None:
    replies = [
        {
            "message": {
                "role": "assistant",
                "content": "",
                "tool_calls": [{"function": {"name": "headline_kpis", "arguments": {}}}],
            },
            "done": True,
        },
        {"message": {"role": "assistant", "content": "final"}, "done": True},
    ]
    seen: list[dict[str, Any]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return httpx.Response(200, json=replies.pop(0))

    settings = replace(SETTINGS, llm_base_url="http://127.0.0.1:11434", llm_provider="ollama")
    provider = OllamaProvider(settings, transport=httpx.MockTransport(handler))
    session = provider.session(
        "sys", [{"name": "headline_kpis", "description": "d", "input_schema": {"type": "object"}}]
    )
    turn = session.send("q")
    assert turn.tool_calls[0].name == "headline_kpis"
    assert seen[0]["tools"][0]["function"]["name"] == "headline_kpis"
    final = session.send_tool_results([(turn.tool_calls[0], "result", False)])
    assert final.text == "final"
    assert seen[1]["messages"][-1] == {
        "role": "tool",
        "content": "result",
        "tool_name": "headline_kpis",
    }


def test_provider_selection() -> None:
    assert select_provider(replace(SETTINGS, agent_provider="deterministic")) is None
    assert isinstance(
        select_provider(replace(SETTINGS, agent_provider="auto", anthropic_api_key="k")),
        AnthropicProvider,
    )
    local = replace(
        SETTINGS, agent_provider="auto", llm_provider="ollama", llm_base_url="http://127.0.0.1:1"
    )
    assert isinstance(select_provider(local), OllamaProvider)
