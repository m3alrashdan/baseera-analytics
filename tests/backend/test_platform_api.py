from __future__ import annotations

from fastapi.testclient import TestClient


def test_seeded_overview_and_company_modules_use_real_related_records(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    overview = client.get("/api/v1/overview").json()

    assert overview["as_of"] == "2026-06-30"
    assert overview["is_demo"] is True
    assert overview["metrics"]["net_revenue"]["value"] > 0
    assert overview["metrics"]["gross_margin"]["value"] is not None
    assert overview["attention"]

    expected_nonempty = {
        "customers",
        "people",
        "projects",
        "operations",
        "costs",
        "support",
        "suppliers",
        "objectives",
    }
    for module in expected_nonempty:
        response = client.get(f"/api/v1/company/{module}")
        assert response.status_code == 200, (module, response.text)
        assert response.json()["items"], module
        assert response.json()["scope"]["tenant_id"] == "tenant-demo"


def test_department_manager_scope_and_hr_field_protection(client: TestClient) -> None:
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "manager@demo.baseera.local", "password": "BaseeraManager!2026"},
    )
    assert login.status_code == 200
    people = client.get("/api/v1/company/people").json()

    assert {person["department_id"] for person in people["items"]} == {"dept-support"}
    assert all("salary" not in person for person in people["items"])
    assert all("personal_email" not in person for person in people["items"])


def test_deterministic_tool_answer_and_honest_provider_unavailability(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    deterministic = client.post(
        "/api/v1/assistant/query",
        json={"question": "What is revenue?", "metric_id": "net_revenue"},
        headers=auth_headers,
    )
    assert deterministic.status_code == 200
    answer = deterministic.json()
    assert answer["status"] == "completed"
    assert answer["provider"]["mode"] == "deterministic_tool"
    assert answer["findings"][0]["classification"] == "observed_fact"
    assert answer["findings"][0]["evidence_ids"]

    unavailable = client.post(
        "/api/v1/assistant/query",
        json={"question": "Write a creative strategic narrative about everything"},
        headers=auth_headers,
    )
    assert unavailable.status_code == 503
    assert unavailable.json()["error"]["code"] == "provider_unavailable"
    assert unavailable.json()["error"]["details"]["configuration_key"] == ("BASEERA_LLM_BASE_URL")


def test_forecast_process_optimization_simulation_and_causal_boundaries(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    forecast = client.post(
        "/api/v1/forecasts",
        json={"metric_id": "order_count", "horizon": 3},
        headers=auth_headers,
    )
    assert forecast.status_code == 201, forecast.text
    assert forecast.json()["status"] == "completed"
    assert len(forecast.json()["forecast"]) == 3
    assert forecast.json()["backtest"]["mae"] >= 0
    assert forecast.json()["classification"] == "forecast"

    process = client.post("/api/v1/process/analyze", json={}, headers=auth_headers)
    assert process.status_code == 200
    assert process.json()["case_count"] > 0
    assert process.json()["paths"]
    assert process.json()["limitations"]

    optimization = client.post(
        "/api/v1/optimizations",
        json={
            "workers": [
                {"id": "w1", "skills": ["arabic"], "capacity_hours": 8},
                {"id": "w2", "skills": ["technical"], "capacity_hours": 8},
            ],
            "tasks": [
                {"id": "t1", "required_skill": "arabic", "hours": 4},
                {"id": "t2", "required_skill": "technical", "hours": 5},
            ],
        },
        headers=auth_headers,
    )
    assert optimization.status_code == 201
    assert optimization.json()["feasibility"] == "feasible"
    assert len(optimization.json()["assignments"]) == 2
    assert optimization.json()["solver"]["claim"] == "optimal_for_bounded_search"

    infeasible = client.post(
        "/api/v1/optimizations",
        json={
            "workers": [{"id": "w1", "skills": ["arabic"], "capacity_hours": 2}],
            "tasks": [{"id": "t1", "required_skill": "technical", "hours": 5}],
        },
        headers=auth_headers,
    ).json()
    assert infeasible["feasibility"] == "infeasible"
    assert infeasible["violations"]

    simulation = client.post(
        "/api/v1/simulations",
        json={
            "arrival_rate_per_hour": 2.0,
            "service_rate_per_hour": 1.5,
            "baseline_agents": 2,
            "proposed_agents": 3,
            "hours": 40,
            "replications": 20,
            "seed": 41,
        },
        headers=auth_headers,
    )
    assert simulation.status_code == 201
    simulation_again = client.post(
        "/api/v1/simulations",
        json={
            "arrival_rate_per_hour": 2.0,
            "service_rate_per_hour": 1.5,
            "baseline_agents": 2,
            "proposed_agents": 3,
            "hours": 40,
            "replications": 20,
            "seed": 41,
        },
        headers=auth_headers,
    )
    assert simulation.json()["baseline"] == simulation_again.json()["baseline"]
    assert simulation.json()["model_boundary"]

    causal = client.post(
        "/api/v1/causal/analyze",
        json={"treatment": "policy_change", "outcome": "resolution_hours"},
        headers=auth_headers,
    )
    assert causal.status_code == 422
    assert causal.json()["error"]["code"] == "causal_assumptions_required"


def test_capabilities_connectors_jobs_schedules_decisions_and_version_conflicts(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    capabilities = client.get("/api/v1/capabilities").json()["items"]
    by_id = {item["id"]: item for item in capabilities}
    assert by_id["file.csv"]["status"] == "ready"
    assert by_id["file.xls"]["status"] == "unsupported"
    assert by_id["llm.ollama"]["status"] == "needs_configuration"

    connectors = client.get("/api/v1/connectors/capabilities").json()["items"]
    postgres = next(item for item in connectors if item["id"] == "postgresql")
    assert postgres["mode"] == "read_only"
    assert postgres["status"] == "needs_configuration"

    decision = client.post(
        "/api/v1/decisions",
        json={
            "title": "Review staffing scenario",
            "owner": "Operations lead",
            "review_date": "2026-07-15",
            "status": "draft",
        },
        headers=auth_headers,
    )
    assert decision.status_code == 201
    assert client.get("/api/v1/decisions").json()["items"][0]["version"] == 1

    schedule = client.post(
        "/api/v1/schedules",
        json={
            "name": "Weekly KPI refresh",
            "kind": "metric_refresh",
            "cron": "0 8 * * 1",
            "timezone": "Asia/Amman",
        },
        headers=auth_headers,
    )
    assert schedule.status_code == 201
    assert schedule.json()["active"] is True

    report = client.post(
        "/api/v1/reports",
        json={"title": "Versioned report", "language": "en", "sections": []},
        headers=auth_headers,
    ).json()
    updated = client.patch(
        f"/api/v1/reports/{report['id']}",
        json={"expected_version": 1, "title": "Revised report"},
        headers=auth_headers,
    )
    assert updated.status_code == 200
    conflict = client.patch(
        f"/api/v1/reports/{report['id']}",
        json={"expected_version": 1, "title": "Stale update"},
        headers=auth_headers,
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "version_conflict"
