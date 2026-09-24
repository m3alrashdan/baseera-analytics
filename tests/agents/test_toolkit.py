"""The deterministic analytics toolkit: every number the analyst team publishes."""

from __future__ import annotations

import math

import pytest
from baseera.agents.frame import AnalysisFrame, build_frame
from baseera.agents.toolkit import (
    anomalies,
    drivers,
    overview,
    query,
    segments,
    stats,
    timeseries,
    variance,
)
from baseera.errors import AppError


def test_semantic_model_of_a_transaction_table(retail_frame: AnalysisFrame) -> None:
    frame = retail_frame
    assert frame.time_column == "order_date"
    assert frame.primary_kpi == "revenue"
    assert frame.outcome == "returned"
    assert frame.roles["order_id"].role == "identifier"
    assert frame.roles["customer_id"].role == "entity"
    assert frame.roles["returned"].role == "flag"
    # A 1-5 rating is sliced by, not summed, and is not treated as a business dimension.
    assert frame.roles["satisfaction"].role == "dimension"
    assert "ordinal_scale" in frame.roles["satisfaction"].notes
    # "discount" must not be read as a "count".
    assert frame.roles["discount_pct"].kpi_score < 0.4
    assert frame.roles["discount_pct"].rate_scale == 100.0
    assert frame.roles["revenue"].additive and not frame.roles["unit_price"].additive


def test_entity_table_focuses_on_its_outcome(churn_frame_ar: AnalysisFrame) -> None:
    frame = churn_frame_ar
    # One row per subscriber with a churn flag: the analysis is about churn.
    assert frame.primary_kpi is None
    assert frame.outcome == "تسرب"
    assert frame.roles["رقم_المشترك"].role == "identifier"
    # "بالأشهر" contains the letters of "شهر" but tenure is a measure, not a date part.
    assert frame.roles["مدة_الاشتراك_بالأشهر"].role == "measure"
    assert frame.time_column == "تاريخ_الاشتراك"


def test_empty_dataset_is_refused() -> None:
    with pytest.raises(AppError) as error:
        build_frame([], ["a"])
    assert error.value.code == "insufficient_data"


def test_query_matches_pandas_and_validates(retail_frame: AnalysisFrame) -> None:
    result = query.run_query(
        retail_frame,
        {
            "group_by": ["region"],
            "metrics": [{"column": "revenue", "agg": "sum", "as": "value"}],
            "filters": [{"column": "channel", "op": "eq", "value": "Online"}],
        },
    )
    df = retail_frame.df
    expected = df[df["channel"] == "Online"].groupby("region")["revenue"].sum()
    for row in result["rows"]:
        assert math.isclose(row["value"], expected[row["region"]], rel_tol=1e-6)
    assert result["chart"]["type"] == "bar"
    with pytest.raises(AppError) as unknown:
        query.run_query(retail_frame, {"group_by": ["nope"]})
    assert unknown.value.code == "unknown_column"
    with pytest.raises(AppError) as bad_op:
        query.run_query(retail_frame, {"filters": [{"column": "region", "op": "drop"}]})
    assert bad_op.value.code == "invalid_filter"
    with pytest.raises(AppError) as bad_agg:
        query.run_query(retail_frame, {"metrics": [{"column": "region", "agg": "sum"}]})
    assert bad_agg.value.code == "non_numeric_column"


def test_time_grain_query(retail_frame: AnalysisFrame) -> None:
    result = query.run_query(
        retail_frame, {"time_grain": "quarter", "metrics": [{"agg": "count", "as": "orders"}]}
    )
    assert result["rows"][0]["period"] == "2023-Q3"
    assert sum(row["orders"] for row in result["rows"]) == retail_frame.row_count
    assert result["chart"]["type"] == "line"


def test_contributions_add_up_exactly(retail_frame: AnalysisFrame) -> None:
    result = variance.explain_change(retail_frame, "revenue", grain="quarter", compare="year_ago")
    assert result["period_before"] == "2025-Q2" and result["period_after"] == "2026-Q2"
    for breakdown in result["breakdowns"]:
        total = sum(member["delta"] for member in breakdown["members"])
        if len(breakdown["members"]) < 12:
            assert math.isclose(total, result["change"], rel_tol=1e-6, abs_tol=1e-6)
    # The planted regional drop shows up as the strongest movement against the total.
    region = next(b for b in result["breakdowns"] if b["dimension"] == "region")
    north = next(m for m in region["members"] if m["member"] == "North")
    assert north["delta"] < 0 and north["member_change"] < -0.2
    assert result["noise"] is not None


def test_group_comparison_reports_effect_size(retail_frame: AnalysisFrame) -> None:
    result = stats.compare_groups(retail_frame, "revenue", "customer_segment")
    assert result["significant"]
    assert result["top_group"] == "Corporate"
    assert result["effect_magnitude"] in {"small", "medium", "large"}
    assert result["method"] in {"kruskal_wallis", "one_way_anova"}


def test_correlations_are_multiple_testing_corrected(retail_frame: AnalysisFrame) -> None:
    result = stats.correlations(retail_frame)
    assert all("q_value" in pair and pair["q_value"] >= pair["p_value"] for pair in result["pairs"])
    assert result["chart"]["type"] == "heatmap"


def test_trend_and_forecast(retail_frame: AnalysisFrame) -> None:
    trend = timeseries.trend(retail_frame, "revenue")
    assert trend["grain"] == "month"
    assert trend["direction"] == "increasing"
    assert trend["seasonality"]["is_seasonal"]
    forecast = timeseries.forecast(retail_frame, "revenue", horizon=6)
    assert forecast["status"] == "completed"
    assert len(forecast["forecast"]) == 6
    assert forecast["forecast"][0]["period"] == "2026-07"
    for point in forecast["forecast"]:
        assert point["lower"] <= point["value"] <= point["upper"]
    assert forecast["outlook"]["horizon_total"] > 0
    assert forecast["chart"]["type"] == "forecast"


def test_incomplete_last_period_is_dropped() -> None:
    rows = [
        {"day": f"2025-{month:02d}-{day:02d}", "amount": 10}
        for month in range(1, 13)
        for day in range(1, 29)
    ] + [{"day": "2026-01-03", "amount": 10}]
    frame = build_frame(rows, ["day", "amount"])
    series = timeseries.build_series(frame, "amount", "sum", "month")
    assert series["periods"][-1] == "2025-12"
    assert series["dropped_incomplete_period"] == "2026-01"


def test_drivers_recover_planted_churn_causes(churn_frame: AnalysisFrame) -> None:
    result = drivers.key_drivers(churn_frame, "churned")
    assert result["task"] == "classification"
    assert result["model"]["cv_score"] > 0.7
    top = {driver["feature"] for driver in result["drivers"][:5]}
    assert {"usage_hours", "support_tickets", "tenure_months"} <= top
    usage = next(d for d in result["drivers"] if d["feature"] == "usage_hours")
    assert usage["direction"] == "negative"


def test_drivers_exclude_sibling_outcomes(retail_frame: AnalysisFrame) -> None:
    result = drivers.key_drivers(retail_frame, "revenue")
    excluded = {item["column"] for item in result["excluded_features"]}
    assert {"profit", "cost"} <= excluded
    assert all(d["feature"] not in {"profit", "cost"} for d in result["drivers"])


def test_what_if_moves_in_the_modelled_direction(churn_frame: AnalysisFrame) -> None:
    result = drivers.what_if(
        churn_frame, "churned", [{"column": "usage_hours", "percent_change": 30}]
    )
    assert result["change_per_record"] < 0
    with pytest.raises(AppError):
        drivers.what_if(churn_frame, "churned", [{"column": "customer_id", "set_to": 1}])


def test_record_anomalies_find_planted_entry_errors(retail_frame: AnalysisFrame) -> None:
    result = anomalies.record_anomalies(retail_frame)
    assert result["flagged"] > 0
    reasons = {reason["column"] for record in result["top_records"] for reason in record["reasons"]}
    assert reasons & {"units", "revenue", "cost", "profit"}


def test_segments_rfm_and_cohorts(retail_frame: AnalysisFrame) -> None:
    result = segments.segment(retail_frame)
    assert 2 <= result["k"] <= 6
    assert math.isclose(sum(s["share"] for s in result["segments"]), 1.0, rel_tol=1e-6)
    tiers = segments.rfm(retail_frame)
    assert math.isclose(sum(t["share_of_entities"] for t in tiers["tiers"]), 1.0, rel_tol=1e-6)
    cohort = segments.cohorts(retail_frame)
    assert cohort["cohorts"] and cohort["average_retention"][0] == pytest.approx(1.0)


def test_health_and_kpis(retail_frame: AnalysisFrame) -> None:
    health = overview.data_health(retail_frame)
    assert health["readiness"]["checks"]["forecasting"]
    assert health["schema"]["primary_kpi"] == "revenue"
    kpis = overview.headline_kpis(retail_frame)
    revenue = next(card for card in kpis["cards"] if card["measure"] == "revenue")
    assert math.isclose(revenue["value"], float(retail_frame.df["revenue"].sum()), rel_tol=1e-9)
    assert revenue.get("yoy_change") is not None
    assert "year earlier" in kpis["summary"]["en"]
