"""Why did it change? Contribution analysis between two periods.

For additive measures (sum, count) the change in the total is exactly the sum of the
changes of the members of any dimension, so each member's contribution is exact. For
averages the change is split into a *mix* effect (the weights moved) and a *rate*
effect (the members' own averages moved), which is how an analyst separates "we sold
more of the cheap product" from "every product got cheaper".

The analysis then drills one level deeper inside the largest contributor, producing
a root-cause path such as "Revenue −12% ← Region = North (−70% of the change) ←
Channel = Online (−80% of North's change)".
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from ...errors import AppError
from ..common import bi, clean, fmt, measure_label, pct, safe_div
from ..frame import AnalysisFrame
from .query import add_period, apply_filters
from .timeseries import SEASONAL_PERIOD, build_series


def _period_rows(frame: AnalysisFrame, df: pd.DataFrame, grain: str, label: str) -> pd.DataFrame:
    assert frame.time_column is not None
    labels = add_period(df, frame.time_column, grain)
    return df[labels == label]


def _total(frame: AnalysisFrame, df: pd.DataFrame, measure: str | None, agg: str) -> float:
    if agg == "count" or not measure:
        return float(len(df))
    values = frame.numeric(measure).loc[df.index]
    return float(values.sum() if agg == "sum" else values.mean())


def _contributions(
    frame: AnalysisFrame,
    before: pd.DataFrame,
    after: pd.DataFrame,
    measure: str | None,
    agg: str,
    dimension: str,
) -> dict[str, Any]:
    key_before = before[dimension].astype(str).where(before[dimension].notna(), "(missing)")
    key_after = after[dimension].astype(str).where(after[dimension].notna(), "(missing)")
    if agg == "count" or not measure:
        a = key_before.value_counts()
        b = key_after.value_counts()
        members = a.index.union(b.index)
        a, b = a.reindex(members, fill_value=0), b.reindex(members, fill_value=0)
        delta = (b - a).astype(float)
        table = pd.DataFrame({"before": a, "after": b, "delta": delta})
    elif agg == "sum":
        va = frame.numeric(measure).loc[before.index]
        vb = frame.numeric(measure).loc[after.index]
        a = va.groupby(key_before).sum()
        b = vb.groupby(key_after).sum()
        members = a.index.union(b.index)
        a, b = a.reindex(members, fill_value=0.0), b.reindex(members, fill_value=0.0)
        table = pd.DataFrame({"before": a, "after": b, "delta": b - a})
    else:
        va = frame.numeric(measure).loc[before.index]
        vb = frame.numeric(measure).loc[after.index]
        ma, mb = va.groupby(key_before).mean(), vb.groupby(key_after).mean()
        wa = key_before.value_counts(normalize=True)
        wb = key_after.value_counts(normalize=True)
        members = ma.index.union(mb.index)
        ma, mb = ma.reindex(members), mb.reindex(members)
        wa, wb = wa.reindex(members, fill_value=0.0), wb.reindex(members, fill_value=0.0)
        base = ma.fillna(mb).fillna(0.0)
        mix = (wb - wa) * base
        rate = wb * (mb.fillna(base) - base)
        table = pd.DataFrame(
            {"before": ma, "after": mb, "mix": mix, "rate": rate, "delta": mix + rate}
        )
    total_delta = float(table["delta"].sum())
    table["share_of_change"] = table["delta"] / total_delta if total_delta else 0.0
    table = table.sort_values("delta", key=lambda s: -s.abs())
    # Surprise: how much the member mix itself moved (Jensen-Shannon divergence between
    # the before and after shares). A dimension whose mix did not move cannot explain a
    # change, however large its members are.
    weights_before = table["before"].clip(lower=0).fillna(0.0)
    weights_after = table["after"].clip(lower=0).fillna(0.0)
    if agg == "mean":
        weights_before = key_before.value_counts().reindex(table.index, fill_value=0).astype(float)
        weights_after = key_after.value_counts().reindex(table.index, fill_value=0).astype(float)
    surprise = _js_divergence(weights_before.to_numpy(), weights_after.to_numpy())
    same_sign = table[(table["delta"] * total_delta) > 0]
    moved = float(table["delta"].abs().sum()) or 1.0
    concentration = float(same_sign["delta"].abs().head(2).sum() / moved) if len(same_sign) else 0.0
    before_values = table["before"].astype(float)
    table["member_change"] = (table["delta"] / before_values.abs()).where(before_values != 0)
    return {
        "dimension": dimension,
        "total_delta": total_delta,
        "surprise": surprise,
        "concentration": concentration,
        "explanatory_power": surprise * (0.5 + concentration),
        "members": [
            {
                "member": str(member),
                **{k: row[k] for k in table.columns},
            }
            for member, row in table.head(12).iterrows()
        ],
    }


def _noise_check(
    values: list[float], periods: list[str], before: str, after: str
) -> dict[str, Any] | None:
    """Is this change unusual compared with the series' own history of such changes?"""

    import numpy as np

    if before not in periods or after not in periods:
        return None
    lag = periods.index(after) - periods.index(before)
    if lag <= 0:
        return None
    history = [
        (values[i] - values[i - lag]) / abs(values[i - lag])
        for i in range(lag, periods.index(after))
        if values[i - lag]
    ]
    if len(history) < 4:
        return None
    current_base = values[periods.index(before)]
    if not current_base:
        return None
    current = (values[periods.index(after)] - current_base) / abs(current_base)
    spread = float(np.std(history))
    z = (current - float(np.mean(history))) / spread if spread > 0 else 0.0
    return {
        "comparable_changes": len(history),
        "typical_change": float(np.mean(history)),
        "typical_spread": spread,
        "z_score": z,
        "within_normal_range": abs(z) < 1.5,
    }


def _js_divergence(p: Any, q: Any) -> float:
    import numpy as np

    p = np.asarray(p, dtype=float)
    q = np.asarray(q, dtype=float)
    if p.sum() <= 0 or q.sum() <= 0:
        return 0.0
    p, q = p / p.sum(), q / q.sum()
    m = (p + q) / 2

    def kl(a: Any, b: Any) -> float:
        mask = a > 0
        return float(np.sum(a[mask] * np.log2(a[mask] / b[mask])))

    return max(0.0, 0.5 * kl(p, m) + 0.5 * kl(q, m))


def explain_change(
    frame: AnalysisFrame,
    measure: str | None,
    agg: str = "sum",
    grain: str | None = None,
    period_before: str | None = None,
    period_after: str | None = None,
    compare: str = "previous",
    dimensions: list[str] | None = None,
    filters: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if not frame.time_column:
        raise AppError(422, "time_column_required", "Explaining a change needs a date column.")
    if agg not in {"sum", "count", "mean"}:
        raise AppError(422, "invalid_aggregation", "Use sum, count or mean.")
    if measure:
        measure = frame.require(measure)
    series = build_series(frame, measure, agg if agg != "mean" else "mean", grain, filters)
    periods = series["periods"]
    grain = series["grain"]
    if len(periods) < 2:
        raise AppError(422, "insufficient_data", "At least two periods are needed.")
    if not period_after:
        period_after = periods[-1]
    if not period_before:
        position = periods.index(period_after) if period_after in periods else len(periods) - 1
        lag = SEASONAL_PERIOD[grain] if compare == "year_ago" else 1
        if position - lag < 0:
            raise AppError(
                422,
                "insufficient_data",
                f"No comparison period {lag} step(s) before {period_after}.",
            )
        period_before = periods[position - lag]
    noise = _noise_check(series["values"], periods, period_before, period_after)
    df = apply_filters(frame, filters)
    df = df[df[frame.time_column].notna()]
    before = _period_rows(frame, df, grain, period_before)
    after = _period_rows(frame, df, grain, period_after)
    if before.empty and after.empty:
        raise AppError(422, "insufficient_data", "Neither period has rows.")
    total_before = _total(frame, before, measure, agg)
    total_after = _total(frame, after, measure, agg)
    change = total_after - total_before
    relative = safe_div(change, abs(total_before))
    candidates = (
        [frame.require(d) for d in dimensions]
        if dimensions
        else [
            d
            for d in frame.dimensions
            if frame.roles[d].distinct_count <= 60 and "ordinal_scale" not in frame.roles[d].notes
        ][:6]
    )
    breakdowns = [_contributions(frame, before, after, measure, agg, dim) for dim in candidates]
    breakdowns.sort(key=lambda item: -abs(item["explanatory_power"]))
    path: list[dict[str, Any]] = []
    if breakdowns and change:
        first = breakdowns[0]
        top = first["members"][0] if first["members"] else None
        if top:
            path.append(
                {
                    "dimension": first["dimension"],
                    "member": top["member"],
                    "delta": top["delta"],
                    "share_of_parent_change": top["share_of_change"],
                    "member_change": top.get("member_change"),
                }
            )
            others = [d for d in candidates if d != first["dimension"]]
            inner_before = before[before[first["dimension"]].astype(str) == top["member"]]
            inner_after = after[after[first["dimension"]].astype(str) == top["member"]]
            nested = [
                _contributions(frame, inner_before, inner_after, measure, agg, dim)
                for dim in others
            ]
            nested.sort(key=lambda item: -abs(item["explanatory_power"]))
            if nested and nested[0]["members"]:
                inner = nested[0]["members"][0]
                path.append(
                    {
                        "dimension": nested[0]["dimension"],
                        "member": inner["member"],
                        "delta": inner["delta"],
                        "share_of_parent_change": inner["share_of_change"],
                    }
                )
    counter: dict[str, Any] | None = None
    if breakdowns and change:
        opposite = [m for m in breakdowns[0]["members"] if m["delta"] * change < 0]
        if opposite:
            counter = {
                "dimension": breakdowns[0]["dimension"],
                "member": opposite[0]["member"],
                "delta": opposite[0]["delta"],
                "member_change": opposite[0].get("member_change"),
            }
    label, label_ar = measure_label(measure, agg)
    direction_en = "rose" if change > 0 else "fell" if change < 0 else "did not change"
    direction_ar = "ارتفع" if change > 0 else "انخفض" if change < 0 else "لم يتغير"
    path_en = " → ".join(
        f"{step['dimension']} = {step['member']} ({pct(step['share_of_parent_change'])} of the change)"
        for step in path
    )
    path_ar = " ← ".join(
        f"{step['dimension']} = {step['member']} ({pct(step['share_of_parent_change'])} من التغيّر)"
        for step in path
    )
    top_breakdown = breakdowns[0] if breakdowns else None
    chart = None
    if top_breakdown:
        members = top_breakdown["members"][:10]
        chart = {
            "type": "waterfall",
            "title": bi(
                f"What moved {label}: {period_before} → {period_after}",
                f"ما الذي حرّك {label_ar}: {period_before} ← {period_after}",
            ),
            "x": [period_before, *[m["member"] for m in members], period_after],
            "start": total_before,
            "deltas": [m["delta"] for m in members],
            "other": change - sum(m["delta"] for m in members) if agg != "mean" else 0.0,
            "end": total_after,
        }
    return clean(
        {
            "measure": label,
            "agg": agg,
            "grain": grain,
            "period_before": period_before,
            "period_after": period_after,
            "compare": compare,
            "value_before": total_before,
            "value_after": total_after,
            "change": change,
            "relative_change": relative,
            "breakdowns": breakdowns,
            "root_cause_path": path,
            "counter_movement": counter,
            "noise": noise,
            "chart": chart,
            "method": "additive_contribution_analysis"
            if agg != "mean"
            else "mix_rate_decomposition",
            "summary": bi(
                f"{label} {direction_en} from {fmt(total_before)} to {fmt(total_after)} "
                f"({pct(relative, signed=True)}) between {period_before} and {period_after}."
                + (f" Largest driver: {path_en}." if path else "")
                + (
                    f" Moving the other way: {counter['dimension']} = {counter['member']} "
                    f"({fmt(counter['delta'])})."
                    if counter
                    else ""
                ),
                f"{direction_ar} {label_ar} من {fmt(total_before)} إلى {fmt(total_after)} "
                f"({pct(relative, signed=True)}) بين {period_before} و{period_after}."
                + (f" أكبر مسبّب: {path_ar}." if path else "")
                + (
                    f" وفي الاتجاه المعاكس: {counter['dimension']} = {counter['member']} "
                    f"({fmt(counter['delta'])})."
                    if counter
                    else ""
                ),
            ),
        }
    )
