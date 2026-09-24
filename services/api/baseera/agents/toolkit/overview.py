"""Data health and headline KPIs: the first two pages of any analyst's report."""

from __future__ import annotations

from typing import Any

import pandas as pd

from ..common import bi, clean, fmt, pct, safe_div
from ..frame import AnalysisFrame
from .timeseries import SEASONAL_PERIOD, build_series, choose_grain

ISSUE_TEXT = {
    "duplicate_rows": (
        "{count} fully duplicated rows",
        "{count} صفًا مكررًا بالكامل",
        "Totals are overstated until duplicates are removed.",
        "المجاميع مضخّمة حتى تُزال التكرارات.",
    ),
    "duplicate_business_keys": (
        "{count} repeated business keys",
        "{count} مفتاح عمل مكرر",
        "Records that should be unique repeat; counts may be inflated.",
        "سجلات يُفترض أنها فريدة تتكرر؛ قد تكون الأعداد مضخّمة.",
    ),
    "missing_values": (
        "{count} missing cells",
        "{count} خلية مفقودة",
        "Averages and models use only complete values.",
        "المتوسطات والنماذج تعتمد على القيم المكتملة فقط.",
    ),
    "ambiguous_dates": (
        "{count} dates where day and month cannot be told apart",
        "{count} تاريخًا لا يمكن فيه تمييز اليوم من الشهر",
        "Time series may be misordered until the date convention is confirmed.",
        "قد تكون السلاسل الزمنية مرتبة خطأً حتى يُؤكد نمط التاريخ.",
    ),
    "mixed_date_formats": (
        "{count} columns mixing date formats",
        "{count} عمود يخلط بين صيغ تاريخ",
        "Some dates may be parsed incorrectly.",
        "قد تُقرأ بعض التواريخ بشكل خاطئ.",
    ),
}


def data_health(frame: AnalysisFrame) -> dict[str, Any]:
    profile = frame.profile
    issues: list[dict[str, Any]] = []
    for key, (en, ar, impact_en, impact_ar) in ISSUE_TEXT.items():
        count = int(profile.get("quality_issues", {}).get(key, {}).get("count", 0) or 0)
        if not count:
            continue
        share = count / max(
            1, frame.row_count * (len(frame.df.columns) if key == "missing_values" else 1)
        )
        severity = "high" if share > 0.05 else "medium" if share > 0.01 else "low"
        issues.append(
            {
                "issue": key,
                "count": count,
                "share": share,
                "severity": severity,
                "title": bi(en.format(count=f"{count:,}"), ar.format(count=f"{count:,}")),
                "impact": bi(impact_en, impact_ar),
            }
        )
    column_issues = []
    for name, role in frame.roles.items():
        if role.missing_rate >= 0.2 and role.role not in {"empty"}:
            column_issues.append(
                {
                    "column": name,
                    "issue": "high_missing_rate",
                    "missing_rate": role.missing_rate,
                    "title": bi(
                        f"{name}: {pct(role.missing_rate)} missing",
                        f"{name}: {pct(role.missing_rate)} مفقودة",
                    ),
                }
            )
        if role.role in {"constant", "empty"}:
            column_issues.append(
                {
                    "column": name,
                    "issue": role.role,
                    "title": bi(
                        f"{name} carries no information ({role.role})",
                        f"{name} لا يحمل معلومات ({'ثابت' if role.role == 'constant' else 'فارغ'})",
                    ),
                }
            )
        if "day_month_ambiguous" in role.notes:
            column_issues.append(
                {
                    "column": name,
                    "issue": "day_month_ambiguous",
                    "title": bi(
                        f"{name}: day/month order is ambiguous",
                        f"{name}: ترتيب اليوم والشهر ملتبس",
                    ),
                }
            )
    readiness = _readiness(frame)
    quality = profile.get("quality", {})
    return clean(
        {
            "score": quality.get("score"),
            "grade": quality.get("grade"),
            "rows": frame.row_count,
            "columns": len(frame.df.columns),
            "truncated": frame.truncated,
            "issues": issues,
            "column_issues": column_issues[:20],
            "recommended_cleaning": profile.get("recommended_steps", [])[:12],
            "readiness": readiness,
            "schema": frame.schema_summary(),
            "method": "full_profile_quality_scoring",
        }
    )


def _readiness(frame: AnalysisFrame) -> dict[str, Any]:
    periods = 0
    grain = None
    if frame.time_column:
        try:
            grain = choose_grain(frame)
            periods = len(build_series(frame, None, "count", grain)["periods"])
        except Exception:  # noqa: BLE001 - readiness is advisory
            periods = 0
    rows = frame.row_count
    checks = {
        "trend_analysis": frame.time_column is not None and periods >= 4,
        "forecasting": frame.time_column is not None and periods >= 12,
        "seasonal_forecasting": grain is not None and periods >= 2 * SEASONAL_PERIOD[grain],
        "driver_analysis": bool(frame.primary_kpi or frame.flags) and rows >= 60,
        "segmentation": len(frame.measures) >= 2 and rows >= 60,
        "customer_analytics": bool(frame.entities) and frame.time_column is not None,
        "group_comparison": bool(frame.dimensions) and bool(frame.measures),
    }
    return {"periods": periods, "grain": grain, "checks": checks}


def headline_kpis(frame: AnalysisFrame, limit: int = 6) -> dict[str, Any]:
    cards: list[dict[str, Any]] = []
    grain = choose_grain(frame) if frame.time_column else None
    measures = frame.measures[:limit]
    for measure in measures:
        values = frame.numeric(measure).dropna()
        if values.empty:
            continue
        role = frame.roles[measure]
        agg = "sum" if role.additive else "mean"
        total = float(values.mean() if agg == "mean" else values.sum())
        card: dict[str, Any] = {
            "measure": measure,
            "label": bi(
                measure if agg == "sum" else f"Average {measure}",
                measure if agg == "sum" else f"متوسط {measure}",
            ),
            "agg": agg,
            "value": total,
            "mean_per_record": float(values.mean()),
            "is_money": role.is_money,
            "is_rate": role.is_rate,
            "rate_scale": role.rate_scale,
            "is_primary": measure == frame.primary_kpi,
        }
        if grain:
            try:
                series = build_series(frame, measure, agg, grain)
                vals = series["values"]
                if len(vals) >= 2:
                    card.update(
                        {
                            "grain": grain,
                            "last_period": series["periods"][-1],
                            "last_value": vals[-1],
                            "previous_value": vals[-2],
                            "change": safe_div(vals[-1] - vals[-2], abs(vals[-2])),
                            "sparkline": vals[-24:],
                        }
                    )
                    season = SEASONAL_PERIOD[grain]
                    if len(vals) > season and season > 1:
                        card["year_ago_value"] = vals[-1 - season]
                        card["yoy_change"] = safe_div(
                            vals[-1] - vals[-1 - season], abs(vals[-1 - season])
                        )
            except Exception:  # noqa: BLE001 - a KPI card without history is still useful
                pass
        cards.append(card)
    cards.append(
        {
            "measure": "records",
            "label": bi("Records", "السجلات"),
            "agg": "count",
            "value": float(frame.row_count),
        }
    )
    for entity in frame.entities[:2]:
        cards.append(
            {
                "measure": f"distinct {entity}",
                "label": bi(f"Distinct {entity}", f"عدد {entity} المختلفة"),
                "agg": "nunique",
                "value": float(frame.df[entity].nunique()),
            }
        )
    for flag in frame.flags[:2]:
        rate = frame.numeric(flag).mean()
        if not pd.isna(rate):
            cards.append(
                {
                    "measure": f"{flag} rate",
                    "label": bi(f"{flag} rate", f"نسبة {flag}"),
                    "agg": "mean",
                    "value": float(rate),
                    "is_rate": True,
                    "rate_scale": 1.0,
                    "is_primary": flag == frame.outcome and frame.primary_kpi is None,
                }
            )
    primary = next((c for c in cards if c.get("is_primary")), None)
    summary_en = summary_ar = ""
    if primary and primary["agg"] == "mean" and primary.get("is_rate"):
        value = pct(primary["value"] / primary.get("rate_scale", 1.0))
        summary_en = f"{primary['label']['en']}: {value}"
        summary_ar = f"{primary['label']['ar']}: {value}"
    elif primary and primary["agg"] == "mean":
        summary_en = f"Average {primary['measure']} is {fmt(primary['value'])} per record"
        summary_ar = f"متوسط {primary['measure']} يبلغ {fmt(primary['value'])} لكل سجل"
    elif primary:
        summary_en = f"{primary['measure']} totals {fmt(primary['value'])}"
        summary_ar = f"إجمالي {primary['measure']} يبلغ {fmt(primary['value'])}"
    if primary and primary.get("yoy_change") is not None:
        summary_en += (
            f"; the latest {primary['grain']} ({primary['last_period']}) is "
            f"{pct(primary['yoy_change'], signed=True)} vs the same {primary['grain']} a year earlier"
        )
        summary_ar += (
            f"؛ وآخر فترة ({primary['last_period']}) "
            f"{pct(primary['yoy_change'], signed=True)} مقارنة بالفترة نفسها من العام السابق"
        )
    elif primary and primary.get("change") is not None:
        summary_en += (
            f"; the latest {primary['grain']} ({primary['last_period']}) moved "
            f"{pct(primary['change'], signed=True)} vs the previous one"
        )
        summary_ar += (
            f"؛ وتغيّرت آخر فترة ({primary['last_period']}) بنسبة "
            f"{pct(primary['change'], signed=True)} عن سابقتها"
        )
    if primary:
        summary_en += "."
        summary_ar += "."
    return clean(
        {
            "cards": cards,
            "time_range": frame.time_range(),
            "grain": grain,
            "summary": bi(summary_en, summary_ar),
            "method": "aggregate_totals_and_period_comparison",
        }
    )
