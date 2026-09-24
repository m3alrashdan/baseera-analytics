"""Time: build series at the right grain, read the trend, and forecast honestly.

Forecasting reuses BASEERA's backtested engine (``forecasting.forecast_series``):
model tournament on rolling origins, conformal intervals calibrated on unseen
residuals, a reserved holdout, and an explicit comparison against a naive benchmark.
This module adds grain selection (day/week/month/quarter), trend statistics that
survive noise (Theil-Sen slope, Mann-Kendall test), growth rates and change points.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from scipy import stats as sps

from ...errors import AppError
from ...forecasting import detect_anomalies, detect_level_shift, detect_seasonality, forecast_series
from ..common import bi, clean, measure_label, p_text, pct, safe_div
from ..frame import AnalysisFrame
from .query import add_period, apply_filters

SEASONAL_PERIOD = {"day": 7, "week": 52, "month": 12, "quarter": 4, "year": 1}
GRAIN_ORDER = ["day", "week", "month", "quarter", "year"]


def choose_grain(frame: AnalysisFrame, time_column: str | None = None) -> str:
    column = time_column or frame.time_column
    if not column:
        raise AppError(422, "time_column_required", "This dataset has no date column.")
    values = frame.df[column].dropna()
    if values.empty:
        raise AppError(422, "insufficient_data", "The date column has no readable values.")
    span_days = (values.max() - values.min()).days + 1
    if span_days >= 365 * 2 - 31:
        return "month"
    if span_days >= 140:
        return "week"
    return "day"


def _step_function(grain: str):
    def step(label: str, steps: int) -> str:
        if grain == "day":
            return (pd.Timestamp(label) + pd.Timedelta(days=steps)).strftime("%Y-%m-%d")
        if grain == "week":
            return (pd.Timestamp(label) + pd.Timedelta(weeks=steps)).strftime("%Y-%m-%d")
        if grain == "month":
            return (pd.Period(label, freq="M") + steps).strftime("%Y-%m")
        if grain == "quarter":
            period = pd.Period(label.replace("-Q", "Q"), freq="Q") + steps
            return f"{period.year}-Q{period.quarter}"
        return str(int(label) + steps)

    return step


def _full_index(labels: list[str], grain: str) -> list[str]:
    """Fill gaps so missing periods show as zero activity instead of vanishing."""

    if not labels:
        return []
    step = _step_function(grain)
    ordered = sorted(labels)
    result = [ordered[0]]
    guard = 0
    while result[-1] < ordered[-1] and guard < 5000:
        result.append(step(result[-1], 1))
        guard += 1
    return result


def build_series(
    frame: AnalysisFrame,
    measure: str | None,
    agg: str = "sum",
    grain: str | None = None,
    filters: list[dict[str, Any]] | None = None,
    time_column: str | None = None,
    drop_incomplete_last: bool = True,
) -> dict[str, Any]:
    column = frame.require(time_column) if time_column else frame.time_column
    if not column:
        raise AppError(422, "time_column_required", "This dataset has no date column.")
    grain = grain or choose_grain(frame, column)
    if grain not in SEASONAL_PERIOD:
        raise AppError(422, "invalid_time_grain", f"Unsupported grain {grain!r}.")
    if agg not in {"sum", "mean", "count", "median", "nunique"}:
        raise AppError(422, "invalid_aggregation", "Use sum, mean, median, count or nunique.")
    df = apply_filters(frame, filters)
    df = df[df[column].notna()]
    if agg != "count":
        if not measure:
            raise AppError(422, "column_required", f"{agg} needs a measure column.")
        measure = frame.require(measure)
    if df.empty:
        raise AppError(422, "insufficient_data", "No dated rows match the filters.")
    work = pd.DataFrame({"period": add_period(df, column, grain)})
    if agg == "count":
        grouped = work.groupby("period").size().astype(float)
    elif agg == "nunique":
        work["v"] = df[measure].astype(str).where(df[measure].notna())
        grouped = work.groupby("period")["v"].nunique().astype(float)
    else:
        work["v"] = pd.to_numeric(df[measure], errors="coerce")
        grouped = getattr(work.groupby("period")["v"], agg)()
    labels = _full_index([str(v) for v in grouped.index], grain)
    fill = 0.0 if agg in {"sum", "count", "nunique"} else np.nan
    series = grouped.reindex(labels, fill_value=fill)
    if agg not in {"sum", "count", "nunique"}:
        series = series.interpolate(limit_direction="both")
    incomplete = None
    if drop_incomplete_last and len(series) > 3:
        incomplete = _incomplete_last_period(df[column], grain)
        if incomplete and labels[-1] == incomplete:
            series = series.iloc[:-1]
    return {
        "time_column": column,
        "measure": measure,
        "agg": agg,
        "grain": grain,
        "periods": [str(p) for p in series.index],
        "values": [float(v) for v in series.to_numpy()],
        "dropped_incomplete_period": incomplete
        if incomplete and incomplete not in series.index
        else None,
        "rows_used": int(len(df)),
    }


def _incomplete_last_period(values: pd.Series, grain: str) -> str | None:
    last = values.max()
    if pd.isna(last):
        return None
    if grain == "day":
        return None
    if grain == "week":
        complete = last.weekday() == 6
        label = (last - pd.Timedelta(days=last.weekday())).strftime("%Y-%m-%d")
    elif grain == "month":
        complete = last.day >= last.days_in_month - 1
        label = last.strftime("%Y-%m")
    elif grain == "quarter":
        end = (pd.Period(last, freq="Q").end_time).normalize()
        complete = (end - last.normalize()).days <= 2
        label = f"{last.year}-Q{last.quarter}"
    else:
        complete = last.month == 12 and last.day >= 30
        label = str(last.year)
    return None if complete else label


def trend(
    frame: AnalysisFrame,
    measure: str | None,
    agg: str = "sum",
    grain: str | None = None,
    filters: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    series = build_series(frame, measure, agg, grain, filters)
    periods, values = series["periods"], series["values"]
    if len(values) < 4:
        raise AppError(
            422, "insufficient_data", f"Only {len(values)} periods; a trend needs at least 4."
        )
    array = np.asarray(values, dtype=float)
    index = np.arange(len(array))
    slope, intercept, low, high = sps.theilslopes(array, index)
    tau, p_value = sps.kendalltau(index, array)
    mean_level = float(np.mean(array)) or 1.0
    grain_name = series["grain"]
    season = SEASONAL_PERIOD[grain_name]
    seasonality = detect_seasonality(values, season) if season > 1 else {"is_seasonal": False}
    shift = detect_level_shift(values)
    anomalies = detect_anomalies(periods, values, max(2, season))
    last, previous = array[-1], array[-2]
    yoy = None
    if season > 1 and len(array) > season:
        yoy = safe_div(float(last - array[-1 - season]), abs(float(array[-1 - season])))
    recent = min(len(array) // 2, season if season > 1 else 3)
    recent_growth = None
    if recent >= 1 and len(array) >= recent * 2:
        now, before = float(array[-recent:].sum()), float(array[-2 * recent : -recent].sum())
        recent_growth = safe_div(now - before, abs(before))
    first_full = array[: min(len(array), season if season > 1 else 3)].mean()
    last_full = array[-min(len(array), season if season > 1 else 3) :].mean()
    direction = (
        "increasing"
        if p_value < 0.05 and tau > 0
        else "decreasing"
        if p_value < 0.05 and tau < 0
        else "flat_or_noisy"
    )
    peak = int(np.argmax(array))
    trough = int(np.argmin(array))
    slope_share = safe_div(float(slope), abs(mean_level))
    is_flag = bool(measure) and frame.roles[frame.require(measure)].role == "flag"
    label, label_ar = measure_label(measure, agg, is_flag)
    return clean(
        {
            **series,
            "direction": direction,
            "kendall_tau": float(tau),
            "p_value": float(p_value),
            "theil_sen_slope_per_period": float(slope),
            "slope_ci": [float(low), float(high)],
            "slope_as_share_of_mean": slope_share,
            "last_value": float(last),
            "last_period": periods[-1],
            "previous_value": float(previous),
            "period_over_period": safe_div(float(last - previous), abs(float(previous))),
            "year_over_year": yoy,
            "recent_window": recent,
            "recent_growth": recent_growth,
            "start_to_end_change": safe_div(float(last_full - first_full), abs(float(first_full))),
            "peak": {"period": periods[peak], "value": float(array[peak])},
            "trough": {"period": periods[trough], "value": float(array[trough])},
            "volatility_cv": safe_div(float(np.std(array)), abs(mean_level)),
            "seasonality": seasonality,
            "level_shift": {**shift, "period": periods[shift["index"]]} if shift else None,
            "anomalies": anomalies,
            "chart": {
                "type": "line",
                "title": bi(f"{label} per {grain_name}", f"{label_ar} لكل فترة"),
                "x": periods,
                "series": [
                    {"name": label, "data": values},
                    {
                        "name": "trend",
                        "data": [float(intercept + slope * i) for i in index],
                        "style": "dashed",
                    },
                ],
                "markers": [
                    {"x": item["period"], "label": item["direction"]} for item in anomalies[:10]
                ],
            },
            "method": "theil_sen_slope_mann_kendall_test_additive_decomposition",
            "summary": bi(
                f"{label} is {direction.replace('_', ' ')} (Kendall τ={tau:.2f}, p={p_text(p_value)}); "
                f"latest {grain_name} change {pct(safe_div(float(last - previous), abs(float(previous))), signed=True)}.",
                f"اتجاه {label_ar}: {_direction_ar(direction)} (معامل كندال {tau:.2f}، p={p_text(p_value)})؛ "
                f"تغيّر آخر فترة {pct(safe_div(float(last - previous), abs(float(previous))), signed=True)}.",
            ),
        }
    )


def _direction_ar(direction: str) -> str:
    return {"increasing": "صاعد", "decreasing": "هابط", "flat_or_noisy": "مستقر أو متذبذب"}[
        direction
    ]


def forecast(
    frame: AnalysisFrame,
    measure: str | None,
    agg: str = "sum",
    horizon: int | None = None,
    grain: str | None = None,
    filters: list[dict[str, Any]] | None = None,
    interval: float = 0.9,
) -> dict[str, Any]:
    series = build_series(frame, measure, agg, grain, filters)
    grain_name = series["grain"]
    default_horizon = {"day": 14, "week": 8, "month": 6, "quarter": 4, "year": 2}[grain_name]
    horizon = max(1, min(int(horizon or default_horizon), 36))
    result = forecast_series(
        series["periods"],
        series["values"],
        horizon,
        seasonal_period=SEASONAL_PERIOD[grain_name],
        interval=interval,
        label=measure or "records",
        non_negative=agg in {"count", "nunique"} or _non_negative(frame, measure),
        period_step=_step_function(grain_name),
    )
    result["series_definition"] = {
        k: v for k, v in series.items() if k not in {"values", "periods"}
    }
    if result.get("status") == "completed":
        future = result["forecast"]
        history_values = series["values"]
        horizon_total = float(sum(point["value"] for point in future))
        same_window = history_values[-len(future) :]
        prior_total = float(sum(same_window)) if len(same_window) == len(future) else None
        result["outlook"] = {
            "horizon_total": horizon_total,
            "previous_window_total": prior_total,
            "expected_change": safe_div(horizon_total - prior_total, abs(prior_total))
            if prior_total
            else None,
            "lower_total": float(sum(point["lower"] for point in future)),
            "upper_total": float(sum(point["upper"] for point in future)),
        }
        result["chart"] = {
            "type": "forecast",
            "title": bi(
                f"{measure_label(measure, agg)[0]} forecast ({grain_name})",
                f"توقع {measure_label(measure, agg)[1]}",
            ),
            "x": series["periods"] + [point["period"] for point in future],
            "history": history_values,
            "forecast": [point["value"] for point in future],
            "lower": [point["lower"] for point in future],
            "upper": [point["upper"] for point in future],
        }
    return clean(result)


def _non_negative(frame: AnalysisFrame, measure: str | None) -> bool:
    if not measure:
        return True
    values = frame.numeric(frame.require(measure)).dropna()
    return bool(len(values) and (values >= 0).all())


def seasonality_profile(
    frame: AnalysisFrame, measure: str | None, agg: str = "sum"
) -> dict[str, Any]:
    """Which months / weekdays are structurally strong or weak?"""

    column = frame.time_column
    if not column:
        raise AppError(422, "time_column_required", "This dataset has no date column.")
    df = frame.df[frame.df[column].notna()]
    values = frame.numeric(measure).loc[df.index] if measure else pd.Series(1.0, index=df.index)
    output: dict[str, Any] = {"measure": measure or "records", "agg": agg}
    for name, key, labels in (
        ("month_of_year", df[column].dt.month, None),
        ("day_of_week", df[column].dt.dayofweek, ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]),
    ):
        grouped = pd.DataFrame({"k": key, "v": values}).groupby("k")["v"]
        table = grouped.sum() if agg in {"sum", "count"} else grouped.mean()
        if table.size < 2:
            continue
        if agg in {"sum", "count"} and name == "month_of_year":
            # Normalise by the number of distinct years seen in each month.
            years = df.groupby(df[column].dt.month)[column].apply(lambda s: s.dt.year.nunique())
            table = table / years
        if agg in {"sum", "count"} and name == "day_of_week":
            weeks = df.groupby(df[column].dt.dayofweek)[column].apply(
                lambda s: s.dt.to_period("W").nunique()
            )
            table = table / weeks
        mean = float(table.mean()) or 1.0
        output[name] = [
            {
                "key": int(k),
                "label": labels[int(k)] if labels else pd.Timestamp(2000, int(k), 1).strftime("%b"),
                "value": float(v),
                "index": float(v) / mean,
            }
            for k, v in table.items()
        ]
    return clean(output)
