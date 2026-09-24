"""A safe, typed query language over the analysis frame.

Agents never execute generated code or SQL. When they need a number that no
specialised tool provides, they describe it in this small, validated language:
filters, a time grain, group-bys, aggregations, sorting and a limit. Every column and
operator is checked against the frame before anything runs.
"""

from __future__ import annotations

import contextlib
from typing import Any

import numpy as np
import pandas as pd

from ...errors import AppError
from ..common import bi, clean
from ..frame import AnalysisFrame

FILTER_OPS = {
    "eq",
    "ne",
    "gt",
    "gte",
    "lt",
    "lte",
    "in",
    "not_in",
    "contains",
    "between",
    "is_null",
    "not_null",
}
AGGREGATIONS = {"sum", "mean", "median", "min", "max", "count", "nunique", "std", "share"}
TIME_GRAINS = {"day": "D", "week": "W-MON", "month": "M", "quarter": "Q", "year": "Y"}
MAX_RESULT_ROWS = 200


def apply_filters(frame: AnalysisFrame, filters: list[dict[str, Any]] | None) -> pd.DataFrame:
    df = frame.df
    if not filters:
        return df
    mask = pd.Series(True, index=df.index)
    for index, item in enumerate(filters[:12]):
        column = frame.require(str(item.get("column", "")))
        op = str(item.get("op", "eq"))
        if op not in FILTER_OPS:
            raise AppError(
                422,
                "invalid_filter",
                f"Filter {index + 1} uses unsupported operator {op!r}.",
                details={"supported": sorted(FILTER_OPS)},
            )
        value: Any = item.get("value")
        series = df[column]
        role = frame.roles[column].role
        if role == "time" and op not in {"is_null", "not_null"}:
            value = _as_timestamp(value) if op != "between" else [_as_timestamp(v) for v in value]
        elif pd.api.types.is_numeric_dtype(series) and op in {"gt", "gte", "lt", "lte", "between"}:
            value = [float(v) for v in value] if op == "between" else float(value)
        elif pd.api.types.is_numeric_dtype(series) and op in {"eq", "ne"}:
            with contextlib.suppress(TypeError, ValueError):
                value = float(value)
        if op == "eq":
            condition = (
                series.astype(str) == str(value) if series.dtype == object else series == value
            )
        elif op == "ne":
            condition = (
                series.astype(str) != str(value) if series.dtype == object else series != value
            )
        elif op == "gt":
            condition = series > value
        elif op == "gte":
            condition = series >= value
        elif op == "lt":
            condition = series < value
        elif op == "lte":
            condition = series <= value
        elif op == "in":
            values = [str(v) for v in (value if isinstance(value, list) else [value])]
            condition = series.astype(str).isin(values)
        elif op == "not_in":
            values = [str(v) for v in (value if isinstance(value, list) else [value])]
            condition = ~series.astype(str).isin(values)
        elif op == "contains":
            condition = series.astype(str).str.contains(str(value), case=False, regex=False)
        elif op == "between":
            if not isinstance(value, list) or len(value) != 2:
                raise AppError(422, "invalid_filter", "between needs a [low, high] pair.")
            condition = (series >= value[0]) & (series <= value[1])
        elif op == "is_null":
            condition = series.isna()
        else:
            condition = series.notna()
        mask &= condition.fillna(False).astype(bool)
    return df[mask]


def _as_timestamp(value: Any) -> pd.Timestamp:
    try:
        stamp = pd.Timestamp(str(value))
    except (ValueError, TypeError) as exc:
        raise AppError(422, "invalid_filter", f"{value!r} is not a readable date.") from exc
    if pd.isna(stamp):
        raise AppError(422, "invalid_filter", f"{value!r} is not a readable date.")
    return stamp


def period_label(stamp: pd.Timestamp, grain: str) -> str:
    if grain == "day":
        return stamp.strftime("%Y-%m-%d")
    if grain == "week":
        return (stamp - pd.Timedelta(days=stamp.weekday())).strftime("%Y-%m-%d")
    if grain == "month":
        return stamp.strftime("%Y-%m")
    if grain == "quarter":
        return f"{stamp.year}-Q{(stamp.month - 1) // 3 + 1}"
    return str(stamp.year)


def add_period(df: pd.DataFrame, time_column: str, grain: str) -> pd.Series:
    values = df[time_column]
    if grain == "week":
        start = values - pd.to_timedelta(values.dt.weekday, unit="D")
        return start.dt.strftime("%Y-%m-%d")
    if grain == "day":
        return values.dt.strftime("%Y-%m-%d")
    if grain == "month":
        return values.dt.strftime("%Y-%m")
    if grain == "quarter":
        return values.dt.year.astype("Int64").astype(str) + "-Q" + values.dt.quarter.astype(str)
    return values.dt.year.astype("Int64").astype(str)


def run_query(frame: AnalysisFrame, spec: dict[str, Any]) -> dict[str, Any]:
    """Execute a validated aggregate query and return rows plus a chart."""

    df = apply_filters(frame, spec.get("filters"))
    group_by = [frame.require(str(name)) for name in (spec.get("group_by") or [])[:3]]
    grain = spec.get("time_grain")
    keys: list[str] = list(group_by)
    work = df.copy()
    if grain:
        if grain not in TIME_GRAINS:
            raise AppError(
                422, "invalid_time_grain", f"time_grain must be one of {sorted(TIME_GRAINS)}."
            )
        time_column = frame.require(str(spec.get("time_column") or frame.time_column or ""))
        work = work[work[time_column].notna()]
        work["period"] = add_period(work, time_column, str(grain))
        keys = ["period", *keys]
    metrics = spec.get("metrics") or [{"agg": "count"}]
    compiled: list[tuple[str, str | None, str]] = []
    for index, metric in enumerate(metrics[:6]):
        agg = str(metric.get("agg", "sum"))
        if agg not in AGGREGATIONS:
            raise AppError(
                422,
                "invalid_aggregation",
                f"Metric {index + 1} uses unsupported aggregation {agg!r}.",
                details={"supported": sorted(AGGREGATIONS)},
            )
        column = metric.get("column")
        resolved = frame.require(str(column)) if column else None
        if agg not in {"count", "nunique"} and resolved is None:
            raise AppError(422, "column_required", f"{agg} needs a column.")
        numeric_aggregate = agg in {"sum", "mean", "median", "min", "max", "std", "share"}
        if numeric_aggregate and resolved and not pd.api.types.is_numeric_dtype(work[resolved]):
            raise AppError(
                422,
                "non_numeric_column",
                f"{resolved!r} is not numeric, so {agg} does not apply.",
            )
        alias = str(metric.get("as") or (f"{agg}_{resolved}" if resolved else agg))
        compiled.append((agg, resolved, alias))

    if keys:
        grouped = work.groupby(keys, dropna=True, sort=False)
        result = pd.DataFrame(index=grouped.size().index)
        for agg, column, alias in compiled:
            if agg == "count":
                result[alias] = grouped.size() if column is None else grouped[column].count()
            elif agg == "nunique":
                result[alias] = grouped[column].nunique()
            elif agg == "share":
                totals = grouped[column].sum()
                denominator = float(work[column].sum())
                result[alias] = totals / denominator if denominator else np.nan
            else:
                result[alias] = getattr(grouped[column], agg)()
        result = result.reset_index()
    else:
        values: dict[str, Any] = {}
        for agg, column, alias in compiled:
            if agg == "count":
                values[alias] = len(work) if column is None else int(work[column].count())
            elif agg == "nunique":
                values[alias] = int(work[column].nunique())
            elif agg == "share":
                values[alias] = 1.0
            else:
                values[alias] = getattr(work[column], agg)()
        result = pd.DataFrame([values])

    sort = spec.get("sort") or {}
    sort_by = sort.get("by")
    if grain and not sort_by:
        result = result.sort_values("period")
    elif sort_by:
        if sort_by not in result.columns:
            raise AppError(422, "invalid_sort", f"Cannot sort by {sort_by!r}.")
        result = result.sort_values(sort_by, ascending=not bool(sort.get("desc", True)))
    elif compiled and keys:
        result = result.sort_values(compiled[0][2], ascending=False)
    limit = max(1, min(int(spec.get("limit") or 50), MAX_RESULT_ROWS))
    total_groups = len(result)
    result = result.head(limit)
    records = clean(result.to_dict(orient="records"))
    chart = _chart_for(result, keys, compiled, bool(grain))
    return {
        "rows": records,
        "columns": list(result.columns),
        "row_count_filtered": int(len(work)),
        "groups_total": int(total_groups),
        "truncated": total_groups > limit,
        "spec": clean(spec),
        "chart": chart,
        "method": "validated_aggregate_query",
    }


def _chart_for(
    result: pd.DataFrame,
    keys: list[str],
    compiled: list[tuple[str, str | None, str]],
    temporal: bool,
) -> dict[str, Any] | None:
    if not keys or result.empty or not compiled:
        return None
    first_metric = compiled[0][2]
    if temporal and len(keys) == 1:
        return {
            "type": "line",
            "title": bi(first_metric, first_metric),
            "x": [str(v) for v in result["period"]],
            "series": [
                {"name": alias, "data": clean(result[alias].tolist())}
                for _, _, alias in compiled[:3]
            ],
        }
    if temporal and len(keys) == 2:
        pivot = result.pivot_table(
            index="period", columns=keys[1], values=first_metric, aggfunc="sum"
        ).sort_index()
        top = pivot.sum().sort_values(ascending=False).index[:6]
        return {
            "type": "line",
            "title": bi(first_metric, first_metric),
            "x": [str(v) for v in pivot.index],
            "series": [{"name": str(name), "data": clean(pivot[name].tolist())} for name in top],
        }
    label_column = keys[0]
    subset = result.head(20)
    return {
        "type": "bar",
        "title": bi(first_metric, first_metric),
        "x": [str(v) for v in subset[label_column]],
        "series": [{"name": first_metric, "data": clean(subset[first_metric].tolist())}],
    }
