"""Deterministic writing: the executive summary a senior analyst would open with.

Used on its own when no language model is configured, and as the reference the model's
own writing is checked against when one is.
"""

from __future__ import annotations

from typing import Any

from .common import bi

KIND_ORDER = [
    "kpi",
    "trend",
    "change",
    "forecast",
    "drivers",
    "customers",
    "concentration",
    "group_difference",
    "seasonality",
    "anomaly_records",
    "data_quality",
    "what_if",
    "segments",
    "retention",
    "anomaly_period",
    "correlation",
]


def rank(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        findings,
        key=lambda f: -(f["importance"] * (0.5 + 0.5 * f["confidence_score"])),
    )


def executive_summary(
    frame_info: dict[str, Any],
    findings: list[dict[str, Any]],
    recommendations: list[dict[str, Any]],
) -> dict[str, str]:
    by_kind: dict[str, dict[str, Any]] = {}
    for finding in rank(findings):
        by_kind.setdefault(finding["kind"], finding)
    time_range = frame_info.get("time_range")
    scope_en = f"This analysis covers {frame_info.get('rows', 0):,} records"
    scope_ar = f"يغطي هذا التحليل {frame_info.get('rows', 0):,} سجل"
    if time_range:
        scope_en += f" from {time_range['start']} to {time_range['end']}"
        scope_ar += f" من {time_range['start']} إلى {time_range['end']}"
    scope_en += "."
    scope_ar += "."
    en = [scope_en]
    ar = [scope_ar]
    for kind in ("kpi", "trend", "change", "forecast", "drivers", "customers"):
        chosen = by_kind.get(kind)
        if chosen:
            en.append(chosen["summary"]["en"])
            ar.append(chosen["summary"]["ar"])
    risks = [
        by_kind[k] for k in ("data_quality", "anomaly_records", "concentration") if k in by_kind
    ]
    if risks:
        en.append("Watch-outs: " + " ".join(r["title"]["en"] + "." for r in risks[:2]))
        ar.append("تنبيهات: " + " ".join(r["title"]["ar"] + "." for r in risks[:2]))
    if recommendations:
        top = recommendations[:3]
        en.append(
            "Priorities: " + "; ".join(f"({r['priority']}) {r['title']['en']}" for r in top) + "."
        )
        ar.append(
            "الأولويات: " + "؛ ".join(f"({r['priority']}) {r['title']['ar']}" for r in top) + "."
        )
    return {"en": "\n\n".join(en), "ar": "\n\n".join(ar)}


SECTIONS = [
    (
        "overview",
        ("Data & headline numbers", "البيانات والأرقام الرئيسية"),
        {"schema", "kpi", "data_quality"},
    ),
    (
        "performance",
        ("Performance & trends", "الأداء والاتجاهات"),
        {"trend", "seasonality", "anomaly_period"},
    ),
    (
        "why",
        ("What changed and why", "ما الذي تغيّر ولماذا"),
        {"change", "group_difference", "concentration", "correlation"},
    ),
    ("outlook", ("Forecast & outlook", "التنبؤ والتوقعات"), {"forecast"}),
    (
        "drivers",
        ("Drivers, segments & customers", "العوامل المؤثرة والشرائح والعملاء"),
        {"drivers", "segments", "customers", "retention"},
    ),
    ("risks", ("Anomalies & risks", "الحالات الشاذة والمخاطر"), {"anomaly_records"}),
    ("scenarios", ("Scenarios", "السيناريوهات"), {"what_if"}),
    ("investigation", ("Chief analyst's investigation", "تحقيق كبير المحللين"), {"investigation"}),
]


def sections(findings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    for key, (en, ar), kinds in SECTIONS:
        members = [f["id"] for f in findings if f["kind"] in kinds]
        if members:
            output.append({"id": key, "title": bi(en, ar), "findings": members})
    return output


def key_insights(findings: list[dict[str, Any]], limit: int = 6) -> list[str]:
    ranked = [f for f in rank(findings) if f["kind"] not in {"schema"}]
    return [f["id"] for f in ranked[:limit]]
