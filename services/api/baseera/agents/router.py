"""Deterministic question routing for the expert engine (no language model).

Maps a question in Arabic or English to one or more analysis tools, resolving column
and category names mentioned in the text. It is deliberately conservative: when it
cannot tell what is asked it answers with an overview and says what it can do.
"""

from __future__ import annotations

import re
from typing import Any

from .frame import AnalysisFrame

INTENTS: list[tuple[str, tuple[str, ...]]] = [
    (
        "what_if",
        (
            "what if",
            "what would happen",
            "ماذا لو",
            "لو زاد",
            "لو خفض",
            "لو قل",
            "لو ارتفع",
            "سيناريو",
        ),
    ),
    (
        "forecast",
        (
            "forecast",
            "predict",
            "projection",
            "next month",
            "next quarter",
            "next year",
            "outlook",
            "توقع",
            "تنبأ",
            "تنبؤ",
            "المستقبل",
            "القادم",
            "القادمة",
        ),
    ),
    (
        "why",
        (
            "why",
            "reason",
            "cause",
            "explain",
            "drop",
            "decline",
            "increase",
            "fell",
            "rose",
            "لماذا",
            "ليش",
            "سبب",
            "أسباب",
            "فسر",
            "انخفض",
            "تراجع",
            "ارتفع",
            "زاد",
        ),
    ),
    (
        "drivers",
        (
            "driver",
            "drives",
            "affect",
            "influence",
            "impact",
            "factor",
            "what makes",
            "يؤثر",
            "تؤثر",
            "عوامل",
            "العوامل",
            "محرك",
            "يحرك",
        ),
    ),
    (
        "segments",
        ("segment", "cluster", "group of", "personas", "شرائح", "شريحة", "تقسيم", "مجموعات"),
    ),
    (
        "customers",
        (
            "rfm",
            "loyal",
            "churn risk",
            "at risk",
            "best customers",
            "vip",
            "ولاء",
            "أفضل العملاء",
            "المعرضين",
            "كبار العملاء",
        ),
    ),
    (
        "anomalies",
        (
            "anomal",
            "outlier",
            "unusual",
            "strange",
            "fraud",
            "error",
            "شاذ",
            "شاذة",
            "غريب",
            "غير طبيعي",
            "أخطاء",
            "خطأ",
            "احتيال",
        ),
    ),
    (
        "trend",
        (
            "trend",
            "over time",
            "growth",
            "evolution",
            "اتجاه",
            "نمو",
            "عبر الزمن",
            "تطور",
            "تغير عبر",
        ),
    ),
    ("compare", ("compare", " vs ", "versus", "difference between", "قارن", "مقارنة", "الفرق بين")),
    ("correlation", ("correlat", "relationship", "related", "علاقة", "ارتباط")),
    ("quality", ("quality", "missing", "duplicate", "clean", "جودة", "مفقود", "مكرر", "تنظيف")),
    (
        "top",
        (
            "top",
            "best",
            "highest",
            "largest",
            "most",
            "worst",
            "lowest",
            "least",
            "rank",
            "أعلى",
            "أكثر",
            "أفضل",
            "أكبر",
            "أقل",
            "أسوأ",
            "ترتيب",
        ),
    ),
    (
        "summary",
        ("summary", "overview", "summarize", "tell me about", "ملخص", "لخص", "نظرة عامة", "عام"),
    ),
]


def detect_intents(question: str) -> list[str]:
    text = f" {question.casefold()} "
    found = [name for name, words in INTENTS if any(word in text for word in words)]
    return found or ["summary"]


def _normalize(text: str) -> str:
    return re.sub(r"[\s_\-]+", " ", text.casefold()).strip()


def mentioned_columns(frame: AnalysisFrame, question: str) -> list[str]:
    text = _normalize(question)
    hits: list[tuple[int, str]] = []
    for column in frame.df.columns:
        name = _normalize(str(column))
        variants = {name, name.replace(" ", "")}
        if name.startswith("ال"):
            variants.add(name[2:])
        for variant in variants:
            if variant and len(variant) >= 3 and variant in text:
                hits.append((text.index(variant), str(column)))
                break
    return [column for _, column in sorted(hits)]


def mentioned_values(frame: AnalysisFrame, question: str) -> list[dict[str, Any]]:
    """Category values named in the question, e.g. 'North' or 'الشمال'."""

    text = _normalize(question)
    filters = []
    for dimension in frame.dimensions + frame.flags:
        series = frame.df[dimension]
        if series.dtype != object:
            continue
        for value in series.dropna().astype(str).unique()[:200]:
            candidate = _normalize(value)
            if len(candidate) >= 3 and re.search(rf"(^|\W){re.escape(candidate)}($|\W)", text):
                filters.append({"column": dimension, "op": "eq", "value": value})
    return filters[:3]


def horizon_from(question: str) -> int | None:
    match = re.search(
        r"(\d{1,2})\s*(month|months|week|weeks|quarter|quarters|شهر|أشهر|اسابيع|أسابيع|أسبوع|ربع)",
        question.casefold(),
    )
    return int(match.group(1)) if match else None


def top_n(question: str) -> int:
    match = re.search(r"(?:top|أعلى|أفضل|أكبر)\s*(\d{1,3})", question.casefold())
    return int(match.group(1)) if match else 10


def plan(frame: AnalysisFrame, question: str) -> list[tuple[str, dict[str, Any]]]:
    columns = mentioned_columns(frame, question)
    # Intent words hidden inside column names ("monthly_fee", "الرسوم_الشهرية") are not intents.
    stripped = _normalize(question)
    for column in columns:
        stripped = stripped.replace(_normalize(column), " ")
    intents = detect_intents(stripped)
    filters = mentioned_values(frame, question)
    measures = [c for c in columns if frame.roles[c].role == "measure"]
    dimensions = [c for c in columns if frame.roles[c].role in {"dimension", "entity"}]
    flags = [c for c in columns if frame.roles[c].role == "flag"]
    measure = measures[0] if measures else frame.primary_kpi
    named = flags or measures
    target: str | None = named[0] if named else (frame.outcome or frame.primary_kpi)
    agg = "sum" if measure and frame.roles[measure].additive else "mean"
    if not measure:
        agg = "count"
    filter_args = {"filters": filters} if filters else {}
    lowered = question.casefold()
    grain = next(
        (
            g
            for g, words in (
                ("quarter", ("quarter", "ربع")),
                ("week", ("week", "أسبوع", "اسبوع", "أسابيع")),
                ("month", ("month", "شهر", "أشهر")),
                ("year", ("year", "annual", "سنة", "سنوي", "عام")),
            )
            if any(word in lowered for word in words)
        ),
        None,
    )
    year_ago = bool(
        re.search(
            r"year over year|yoy|last year|same period|العام الماضي|السنة الماضية|نفس الفترة",
            lowered,
        )
    )
    grain_args = {"grain": grain} if grain and grain != "year" else {}
    steps: list[tuple[str, dict[str, Any]]] = []
    for intent in intents[:2]:
        if intent == "forecast" and frame.time_column:
            steps.append(
                (
                    "forecast",
                    {
                        "measure": measure,
                        "agg": agg,
                        "horizon": horizon_from(question),
                        **grain_args,
                        **filter_args,
                    },
                )
            )
        elif intent == "why" and frame.time_column:
            steps.append(
                (
                    "explain_change",
                    {
                        "measure": measure,
                        "agg": agg,
                        "compare": "year_ago" if year_ago else "previous",
                        **grain_args,
                        **filter_args,
                    },
                )
            )
        elif intent == "drivers" and target:
            steps.append(("key_drivers", {"target": target, **filter_args}))
        elif intent == "what_if":
            numeric = [c for c in columns if frame.roles[c].role in {"measure", "flag"}]
            # The last numeric column named is usually the lever ("what if discount drops"),
            # the target is another named measure/outcome or the dataset's focus.
            lever = numeric[-1] if numeric else None
            target = next(
                (c for c in numeric if c != lever),
                frame.primary_kpi or frame.outcome,
            )
            if lever == target:
                lever = None
            percent = re.search(r"([-+]?\d{1,3})\s*(%|٪|percent|بالمئة|في المئة)", question)
            if lever and target:
                change = float(percent.group(1)) if percent else 10.0
                if (
                    re.search(r"reduce|decrease|cut|lower|خفض|تقليل|قلل|نقص", question.casefold())
                    and change > 0
                ):
                    change = -change
                steps.append(
                    (
                        "what_if",
                        {
                            "target": target,
                            "changes": [{"column": lever, "percent_change": change}],
                        },
                    )
                )
            elif target:
                steps.append(("key_drivers", {"target": target}))
        elif intent == "segments":
            steps.append(("segment", filter_args))
        elif intent == "customers" and frame.entities and frame.time_column:
            steps.append(("customer_value_tiers", {}))
        elif intent == "anomalies":
            steps.append(("record_anomalies", {}))
            if frame.time_column:
                steps.append(("series_anomalies", {"measure": measure, "agg": agg, **filter_args}))
        elif intent == "trend" and frame.time_column:
            steps.append(("trend", {"measure": measure, "agg": agg, **grain_args, **filter_args}))
        elif intent == "compare" and dimensions and (measure or target):
            steps.append(
                ("compare_groups", {"measure": measure or target, "dimension": dimensions[0]})
            )
        elif intent == "correlation":
            steps.append(("correlations", {"columns": measures} if len(measures) >= 2 else {}))
        elif intent == "quality":
            steps.append(("describe_dataset", {}))
        elif intent == "top":
            dimension = (
                dimensions[0] if dimensions else (frame.dimensions[0] if frame.dimensions else None)
            )
            if dimension:
                desc = not re.search(r"worst|lowest|least|أقل|أسوأ|أدنى", question.casefold())
                metric = (
                    {"column": measure, "agg": agg, "as": "value"}
                    if measure
                    else {"agg": "count", "as": "value"}
                )
                steps.append(
                    (
                        "query_data",
                        {
                            "group_by": [dimension],
                            "metrics": [metric, {"agg": "count", "as": "records"}],
                            "sort": {"by": "value", "desc": desc},
                            "limit": top_n(question),
                            **filter_args,
                        },
                    )
                )
        elif intent == "summary":
            steps.append(("headline_kpis", {}))
            if dimensions and measure:
                steps.append(
                    (
                        "query_data",
                        {
                            "group_by": dimensions[:1],
                            "metrics": [{"column": measure, "agg": agg, "as": "value"}],
                            **filter_args,
                        },
                    )
                )
    if not steps:
        steps.append(("headline_kpis", {}))
    return steps[:3]
