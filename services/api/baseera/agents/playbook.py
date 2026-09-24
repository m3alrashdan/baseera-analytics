"""The specialists' playbook: what a senior analyst runs on any new dataset, and how
each result becomes a finding a business reader can act on.

Every specialist here is deterministic. With a language model configured the chief
analyst adds its own investigation and writing on top, but this playbook alone
produces a complete, defensible analysis.
"""

from __future__ import annotations

from typing import Any

from .common import bi, fmt, measure_label, p_text, pct
from .frame import AnalysisFrame
from .toolkit.stats import benjamini_hochberg
from .workspace import Workspace, metric

MONTHS_AR = [
    "يناير",
    "فبراير",
    "مارس",
    "أبريل",
    "مايو",
    "يونيو",
    "يوليو",
    "أغسطس",
    "سبتمبر",
    "أكتوبر",
    "نوفمبر",
    "ديسمبر",
]
MONTHS_EN = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
GRAIN_AR = {
    "day": "اليوم",
    "week": "الأسبوع",
    "month": "الشهر",
    "quarter": "الربع",
    "year": "السنة",
}


def _kpi_agg(frame: AnalysisFrame, measure: str | None) -> str:
    if not measure:
        return "count"
    return "sum" if frame.roles[measure].additive else "mean"


def _business_dimensions(frame: AnalysisFrame, limit: int = 5) -> list[str]:
    return [
        d
        for d in frame.dimensions
        if frame.roles[d].distinct_count <= 40 and "ordinal_scale" not in frame.roles[d].notes
    ][:limit]


# ------------------------------------------------------------------ data engineer
def data_engineer(ws: Workspace) -> dict[str, Any] | None:
    frame = ws.frame
    ws.emit(
        "data_engineer",
        "status",
        bi("Reading the schema and auditing quality", "قراءة البنية وتدقيق الجودة"),
    )
    evidence_id, health = ws.run("data_engineer", "describe_dataset")
    if health is None:
        return None
    schema = health["schema"]
    time_range = schema.get("time_range")
    grain = health["readiness"].get("grain")
    parts_en = [f"{frame.row_count:,} records × {len(frame.df.columns)} columns"]
    parts_ar = [f"{frame.row_count:,} سجل × {len(frame.df.columns)} عمود"]
    if time_range:
        parts_en.append(f"from {time_range['start']} to {time_range['end']} (analysed by {grain})")
        parts_ar.append(
            f"من {time_range['start']} إلى {time_range['end']} (بتحليل على مستوى {GRAIN_AR.get(grain or '', grain)})"
        )
    focus = frame.primary_kpi or frame.outcome
    if focus:
        parts_en.append(f"primary focus: {focus}")
        parts_ar.append(f"محور التحليل الرئيسي: {focus}")
    ws.add(
        agent="data_engineer",
        kind="schema",
        title=bi("What this dataset is", "ما هي هذه البيانات"),
        summary=bi("; ".join(parts_en) + ".", "؛ ".join(parts_ar) + "."),
        importance=0.35,
        confidence=0.9,
        evidence_id=evidence_id,
        metrics=[
            metric("Records", "السجلات", frame.row_count),
            metric("Measures", "المقاييس", len(frame.measures)),
            metric("Dimensions", "الأبعاد", len(frame.dimensions)),
            metric("Quality score", "درجة الجودة", health.get("score"), "score"),
        ],
        details=[
            bi(
                f"Measures: {', '.join(frame.measures) or '—'}",
                f"المقاييس: {'، '.join(frame.measures) or '—'}",
            ),
            bi(
                f"Dimensions: {', '.join(frame.dimensions) or '—'}",
                f"الأبعاد: {'، '.join(frame.dimensions) or '—'}",
            ),
            bi(
                f"Entities: {', '.join(frame.entities) or '—'}",
                f"الكيانات: {'، '.join(frame.entities) or '—'}",
            ),
            bi(
                f"Outcome flags: {', '.join(frame.flags) or '—'}",
                f"مؤشرات النتائج: {'، '.join(frame.flags) or '—'}",
            ),
        ],
        evidence={"n": frame.row_count},
        tags=["schema"],
    )
    issues = [i for i in health["issues"] if i["severity"] in {"high", "medium"}]
    column_issues = health["column_issues"]
    if issues or column_issues:
        worst = "high" if any(i["severity"] == "high" for i in issues) else "medium"
        ws.add(
            agent="data_engineer",
            kind="data_quality",
            title=bi("Data quality needs attention", "جودة البيانات تحتاج إلى معالجة"),
            summary=bi(
                f"Quality score {health.get('score')}/100. "
                + "; ".join(i["title"]["en"] for i in issues[:3] + column_issues[:2])
                + ".",
                f"درجة الجودة {health.get('score')}/100. "
                + "؛ ".join(i["title"]["ar"] for i in issues[:3] + column_issues[:2])
                + ".",
            ),
            importance=0.75 if worst == "high" else 0.5,
            confidence=0.9,
            evidence_id=evidence_id,
            details=[i["impact"] for i in issues[:4]] + [c["title"] for c in column_issues[:4]],
            evidence={"n": frame.row_count, "severity": worst},
            tags=["quality", worst],
        )
    return health


# ------------------------------------------------------------------- statistician
def statistician(ws: Workspace) -> None:
    frame = ws.frame
    ws.emit("statistician", "status", bi("Measuring the headline numbers", "قياس الأرقام الرئيسية"))
    evidence_id, kpis = ws.run("statistician", "headline_kpis")
    if kpis:
        cards = kpis["cards"]
        ws.add(
            agent="statistician",
            kind="kpi",
            title=bi("Headline numbers", "الأرقام الرئيسية"),
            summary=kpis["summary"]
            if kpis["summary"]["en"]
            else bi(f"{frame.row_count:,} records analysed.", f"تم تحليل {frame.row_count:,} سجل."),
            importance=0.6,
            confidence=0.95,
            evidence_id=evidence_id,
            metrics=[
                metric(
                    card["measure"],
                    card["measure"],
                    card["value"],
                    "percent"
                    if card.get("is_rate")
                    else "money"
                    if card.get("is_money")
                    else "number",
                    card.get("yoy_change", card.get("change")),
                )
                for card in cards[:8]
            ],
            evidence={"n": frame.row_count},
            tags=["kpi"],
        )
    focus = frame.primary_kpi
    # Where is the total concentrated?
    for dimension in frame.entities[:1] + _business_dimensions(frame, 2):
        evidence_id, result = ws.run(
            "statistician", "concentration", {"measure": focus, "dimension": dimension}, quiet=True
        )
        if not result or result["members"] < 3:
            continue
        top_share = result["top_share"]
        share_80 = result["members_for_80pct_share"]
        # The largest member must hold at least twice its even share, or 80% of the total
        # must sit in a fifth of the members; three channels splitting 40/35/25 is normal.
        notable = (top_share >= max(0.25, 2 / result["members"])) or (
            result["members"] >= 10 and share_80 <= 0.2
        )
        if not notable:
            continue
        label = focus or bi("records", "السجلات")["en"]
        ws.add(
            agent="statistician",
            kind="concentration",
            title=bi(
                f"{label} is concentrated in few {dimension} values",
                f"{label} متركّز في عدد قليل من {dimension}",
            ),
            summary=result["summary"],
            importance=0.55 + min(0.3, top_share / 2),
            confidence=0.85,
            evidence_id=evidence_id,
            metrics=[
                metric("Largest member share", "حصة الأكبر", top_share, "percent"),
                metric("Top 3 share", "حصة أعلى 3", result["top3_share"], "percent"),
                metric("Members making 80%", "عدد من يشكلون 80%", result["members_for_80pct"]),
            ],
            chart=result["chart"],
            evidence={"n": result["members"], "dimension": dimension, "top_share": top_share},
            tags=["concentration", dimension],
        )
    # Which dimensions really separate the KPI (or outcome)? Tested together, BH-corrected.
    target = focus or frame.outcome
    if target:
        tests: list[dict[str, Any]] = []
        for dimension in _business_dimensions(frame, 5):
            evidence_id, result = ws.run(
                "statistician",
                "compare_groups",
                {"measure": target, "dimension": dimension},
                quiet=True,
            )
            if result:
                tests.append(
                    {"evidence_id": evidence_id, "p_value": result["p_value"], "result": result}
                )
        benjamini_hochberg(tests)
        material = [
            t
            for t in tests
            if t["significant"] and t["result"]["effect_magnitude"] in {"medium", "large", "small"}
        ]
        material.sort(key=lambda t: -t["result"]["effect_size"])
        for test in material[:2]:
            r = test["result"]
            is_rate = frame.roles[target].role == "flag" or frame.roles[target].is_rate
            value_fmt = pct if is_rate else fmt
            top, bottom = r["groups"][0], r["groups"][-1]
            ws.add(
                agent="statistician",
                kind="group_difference",
                title=bi(
                    f"{target} differs materially by {r['dimension']}",
                    f"{target} يختلف بوضوح حسب {r['dimension']}",
                ),
                summary=bi(
                    f"{top['group']} averages {value_fmt(top['mean'])} vs {value_fmt(bottom['mean'])} "
                    f"for {bottom['group']} ({r['effect_magnitude']} effect, {r['method'].replace('_', ' ')}, "
                    f"q={p_text(test['q_value'])}).",
                    f"متوسط {top['group']} يبلغ {value_fmt(top['mean'])} مقابل {value_fmt(bottom['mean'])} "
                    f"لـ{bottom['group']} (أثر {_magnitude_ar(r['effect_magnitude'])}، q={p_text(test['q_value'])}).",
                ),
                importance=0.45
                + {"large": 0.3, "medium": 0.2, "small": 0.05}[r["effect_magnitude"]],
                confidence=0.8,
                evidence_id=test["evidence_id"],
                metrics=[
                    metric(
                        f"Best: {top['group']}",
                        f"الأعلى: {top['group']}",
                        top["mean"],
                        "percent" if is_rate else "number",
                    ),
                    metric(
                        f"Lowest: {bottom['group']}",
                        f"الأدنى: {bottom['group']}",
                        bottom["mean"],
                        "percent" if is_rate else "number",
                    ),
                    metric("Effect size", "حجم الأثر", r["effect_size"], "ratio"),
                ],
                chart=r["chart"],
                evidence={
                    "n": sum(g["n"] for g in r["groups"]),
                    "p_value": test["q_value"],
                    "effect_magnitude": r["effect_magnitude"],
                    "dimension": r["dimension"],
                    "top_group": top["group"],
                    "bottom_group": bottom["group"],
                    "gap": r["gap"],
                },
                tags=["segment_gap", r["dimension"]],
            )
    # Relationships worth knowing, skipping trivially linked money outcomes.
    if len(frame.measures) + len(frame.flags) >= 2:
        evidence_id, result = ws.run("statistician", "correlations", {}, quiet=True)
        if result:
            pairs = [
                p
                for p in result["top_pairs"]
                if not (
                    frame.roles[p["a"]].kpi_score >= 0.75 and frame.roles[p["b"]].kpi_score >= 0.75
                )
            ][:4]
            if pairs:
                ws.add(
                    agent="statistician",
                    kind="correlation",
                    title=bi("Measures that move together", "مقاييس تتحرك معًا"),
                    summary=bi(
                        "; ".join(
                            f"{p['a']} ↔ {p['b']} ({p['direction']}, ρ={p['r']:.2f})" for p in pairs
                        )
                        + ".",
                        "؛ ".join(
                            f"{p['a']} ↔ {p['b']} ({'طردي' if p['direction'] == 'positive' else 'عكسي'}، ρ={p['r']:.2f})"
                            for p in pairs
                        )
                        + ".",
                    ),
                    importance=0.4 + 0.2 * abs(pairs[0]["r"]),
                    confidence=0.75,
                    evidence_id=evidence_id,
                    chart=result["chart"],
                    evidence={"n": pairs[0]["n"], "p_value": pairs[0]["q_value"]},
                    caveats=[result["caveat"]],
                    tags=["correlation"],
                )


def _magnitude_ar(magnitude: str) -> str:
    return {"large": "كبير", "medium": "متوسط", "small": "صغير", "negligible": "ضئيل"}.get(
        magnitude, magnitude
    )


# --------------------------------------------------------------------- forecaster
def forecaster(ws: Workspace) -> None:
    frame = ws.frame
    if not frame.time_column:
        ws.emit(
            "forecaster",
            "status",
            bi(
                "No date column: time analysis skipped",
                "لا يوجد عمود تاريخ: تم تخطي التحليل الزمني",
            ),
        )
        return
    ws.emit(
        "forecaster",
        "status",
        bi("Reading the trend and building the forecast", "قراءة الاتجاه وبناء التنبؤ"),
    )
    measure = frame.primary_kpi
    agg = _kpi_agg(frame, measure)
    label, label_ar = measure_label(measure, agg)
    evidence_id, trend = ws.run("forecaster", "trend", {"measure": measure, "agg": agg})
    if trend:
        direction = trend["direction"]
        growth = trend.get("year_over_year")
        if growth is None:
            growth = trend.get("recent_growth")
        importance = (
            0.6 + (0.2 if direction != "flat_or_noisy" else 0) + min(0.15, abs(growth or 0))
        )
        grain = trend["grain"]
        text_en = trend["summary"]["en"]
        text_ar = trend["summary"]["ar"]
        if trend.get("year_over_year") is not None:
            text_en += f" Year over year: {pct(trend['year_over_year'], signed=True)}."
            text_ar += f" مقارنة بالعام السابق: {pct(trend['year_over_year'], signed=True)}."
        if trend.get("level_shift"):
            shift = trend["level_shift"]
            text_en += f" A structural level shift occurred around {shift['period']}."
            text_ar += f" حدث تحول هيكلي في المستوى قرابة {shift['period']}."
        ws.add(
            agent="forecaster",
            kind="trend",
            title=bi(
                f"{label} trend: {direction.replace('_', ' ')}",
                f"اتجاه {label_ar}: {_direction_ar(direction)}",
            ),
            summary=bi(text_en, text_ar),
            importance=importance,
            confidence=0.85 if trend["p_value"] < 0.05 else 0.55,
            evidence_id=evidence_id,
            metrics=[
                metric(
                    f"Latest {grain}",
                    f"آخر {GRAIN_AR.get(grain, grain)}",
                    trend["last_value"],
                    "number",
                    trend.get("period_over_period"),
                ),
                metric("Year over year", "مقارنة سنوية", trend.get("year_over_year"), "percent"),
                metric("Recent growth", "النمو الأخير", trend.get("recent_growth"), "percent"),
                metric("Volatility (CV)", "التذبذب", trend.get("volatility_cv"), "ratio"),
            ],
            chart=trend["chart"],
            evidence={
                "n": len(trend["periods"]),
                "p_value": trend["p_value"],
                "direction": direction,
                "yoy": trend.get("year_over_year"),
            },
            tags=["trend", direction],
        )
        seasonality = trend.get("seasonality") or {}
        if seasonality.get("is_seasonal"):
            s_id, profile = ws.run(
                "forecaster",
                "seasonality_profile",
                {"measure": measure, "agg": "sum" if agg != "mean" else "mean"},
                quiet=True,
            )
            months = (profile or {}).get("month_of_year") or []
            if months:
                ranked = sorted(months, key=lambda m: -m["index"])
                peaks = ranked[:2]
                lows = ranked[-2:]
                ws.add(
                    agent="forecaster",
                    kind="seasonality",
                    title=bi(f"{label} is seasonal", f"{label_ar} موسمي"),
                    summary=bi(
                        f"Peaks in {', '.join(MONTHS_EN[m['key'] - 1] for m in peaks)} "
                        f"({pct(peaks[0]['index'] - 1, signed=True)} vs an average month); "
                        f"weakest in {', '.join(MONTHS_EN[m['key'] - 1] for m in lows)}.",
                        f"الذروة في {' و'.join(MONTHS_AR[m['key'] - 1] for m in peaks)} "
                        f"({pct(peaks[0]['index'] - 1, signed=True)} عن الشهر المتوسط)؛ "
                        f"والأضعف في {' و'.join(MONTHS_AR[m['key'] - 1] for m in lows)}.",
                    ),
                    importance=0.55,
                    confidence=0.8,
                    evidence_id=s_id,
                    chart={
                        "type": "bar",
                        "title": bi("Seasonal index by month", "المؤشر الموسمي حسب الشهر"),
                        "x": [MONTHS_EN[m["key"] - 1] for m in months],
                        "x_ar": [MONTHS_AR[m["key"] - 1] for m in months],
                        "series": [{"name": "index", "data": [m["index"] for m in months]}],
                        "reference": 1.0,
                    },
                    evidence={
                        "n": len(trend["periods"]),
                        "strength": seasonality.get("seasonal_strength"),
                    },
                    tags=["seasonality"],
                )
    if measure is None and frame.outcome:
        o_id, o_trend = ws.run("forecaster", "trend", {"measure": frame.outcome, "agg": "mean"})
        if o_trend:
            ws.add(
                agent="forecaster",
                kind="trend",
                title=bi(
                    f"{frame.outcome} rate over time: {o_trend['direction'].replace('_', ' ')}",
                    f"نسبة {frame.outcome} عبر الزمن: {_direction_ar(o_trend['direction'])}",
                ),
                summary=bi(
                    f"{frame.outcome} rate by {o_trend['grain']} of {frame.time_column}: latest "
                    f"{pct(o_trend['last_value'])}, peak {pct(o_trend['peak']['value'])} in "
                    f"{o_trend['peak']['period']}, lowest {pct(o_trend['trough']['value'])} in "
                    f"{o_trend['trough']['period']} (Kendall τ={o_trend['kendall_tau']:.2f}, "
                    f"p={p_text(o_trend['p_value'])}).",
                    f"نسبة {frame.outcome} حسب {GRAIN_AR.get(o_trend['grain'], o_trend['grain'])} من {frame.time_column}: "
                    f"آخر قيمة {pct(o_trend['last_value'])}، والأعلى {pct(o_trend['peak']['value'])} في "
                    f"{o_trend['peak']['period']}، والأدنى {pct(o_trend['trough']['value'])} في "
                    f"{o_trend['trough']['period']} (كندال {o_trend['kendall_tau']:.2f}، p={p_text(o_trend['p_value'])}).",
                ),
                importance=0.65 + (0.15 if o_trend["direction"] != "flat_or_noisy" else 0),
                confidence=0.8 if o_trend["p_value"] < 0.05 else 0.55,
                evidence_id=o_id,
                chart=o_trend["chart"],
                evidence={
                    "n": len(o_trend["periods"]),
                    "p_value": o_trend["p_value"],
                    "direction": o_trend["direction"],
                },
                tags=["trend", "outcome"],
            )
    evidence_id, forecast = ws.run("forecaster", "forecast", {"measure": measure, "agg": agg})
    if forecast and forecast.get("status") == "completed":
        outlook = forecast.get("outlook", {})
        backtest = forecast.get("backtest", {})
        model = forecast.get("model", {})
        horizon = len(forecast["forecast"])
        grain = forecast["series_definition"]["grain"]
        change = outlook.get("expected_change")
        wape = backtest.get("wape")
        ws.add(
            agent="forecaster",
            kind="forecast",
            title=bi(
                f"Outlook: next {horizon} {grain}s of {label}",
                f"التوقعات: {label_ar} للفترات الـ{horizon} القادمة",
            ),
            summary=bi(
                f"Expected {label} over the next {horizon} {grain}s: {fmt(outlook.get('horizon_total'))} "
                f"(range {fmt(outlook.get('lower_total'))}–{fmt(outlook.get('upper_total'))}), "
                f"{pct(change, signed=True)} vs the last {horizon}. Model: {model.get('label', {}).get('en')}; "
                f"holdout error {pct(wape)}"
                + (
                    "; beats the naive benchmark."
                    if model.get("beats_benchmark")
                    else "; does not beat the naive benchmark."
                ),
                f"المتوقع لـ{label_ar} في الفترات الـ{horizon} القادمة: {fmt(outlook.get('horizon_total'))} "
                f"(المدى {fmt(outlook.get('lower_total'))}–{fmt(outlook.get('upper_total'))})، "
                f"أي {pct(change, signed=True)} مقارنة بآخر {horizon} فترات. النموذج: {model.get('label', {}).get('ar')}؛ "
                f"خطأ الاختبار {pct(wape)}"
                + (
                    "؛ ويتفوق على المعيار البسيط."
                    if model.get("beats_benchmark")
                    else "؛ ولا يتفوق على المعيار البسيط."
                ),
            ),
            importance=0.7 + min(0.2, abs(change or 0)),
            confidence=0.8,
            evidence_id=evidence_id,
            metrics=[
                metric(
                    "Forecast total",
                    "إجمالي المتوقع",
                    outlook.get("horizon_total"),
                    "number",
                    change,
                ),
                metric("Low (interval)", "الحد الأدنى", outlook.get("lower_total")),
                metric("High (interval)", "الحد الأعلى", outlook.get("upper_total")),
                metric("Holdout WAPE", "خطأ الاختبار", wape, "percent"),
            ],
            chart=forecast.get("chart"),
            evidence={
                "n": model.get("history_periods"),
                "wape": wape,
                "beats_benchmark": model.get("beats_benchmark"),
                "expected_change": change,
                "interval": forecast.get("interval_level"),
            },
            tags=["forecast"],
        )
    elif forecast:
        ws.emit(
            "forecaster",
            "warning",
            bi("Forecast not possible", "التنبؤ غير ممكن"),
            {"reason": forecast.get("reason"), "reason_ar": forecast.get("reason_ar")},
        )


def _direction_ar(direction: str) -> str:
    return {"increasing": "صاعد", "decreasing": "هابط", "flat_or_noisy": "مستقر أو متذبذب"}.get(
        direction, direction
    )


# ----------------------------------------------------------------------- detective
def detective(ws: Workspace, readiness: dict[str, Any] | None) -> None:
    frame = ws.frame
    ws.emit(
        "detective",
        "status",
        bi("Explaining changes and hunting anomalies", "تفسير التغيرات وتعقب الحالات الشاذة"),
    )
    measure = frame.primary_kpi
    agg = _kpi_agg(frame, measure)
    label, label_ar = measure_label(measure, agg)
    if frame.time_column:
        periods = (readiness or {}).get("periods", 0)
        grain = (readiness or {}).get("grain")
        comparisons: list[dict[str, Any]] = []
        # Compare like with like: with a year of history, a month is compared with the
        # same month last year so seasonality is not mistaken for a problem.
        if grain == "month" and periods >= 15:
            comparisons.append({"grain": "quarter", "compare": "year_ago"})
        if grain == "month" and periods >= 13:
            comparisons.append({"grain": "month", "compare": "year_ago"})
        elif grain == "week" and periods >= 56:
            comparisons.append({"grain": "week", "compare": "year_ago"})
        else:
            comparisons.append({"grain": grain, "compare": "previous"})
        for spec in comparisons[:2]:
            evidence_id, change = ws.run(
                "detective",
                "explain_change",
                {
                    "measure": measure,
                    "agg": agg,
                    "grain": spec["grain"],
                    "compare": spec["compare"],
                },
            )
            if not change or not change.get("change"):
                continue
            relative = change.get("relative_change") or 0.0
            path = change.get("root_cause_path") or []
            counter = change.get("counter_movement")
            noise = change.get("noise") or {}
            normal = bool(noise.get("within_normal_range"))
            first_breakdown = change["breakdowns"][0] if change["breakdowns"] else None
            importance = 0.55 + min(0.35, abs(relative) * 1.5) - (0.2 if normal else 0.0)
            title_en = (
                f"Why {label} {'rose' if change['change'] > 0 else 'fell'}: "
                f"{change['period_before']} → {change['period_after']}"
            )
            title_ar = (
                f"لماذا {'ارتفع' if change['change'] > 0 else 'انخفض'} {label_ar}: "
                f"{change['period_before']} ← {change['period_after']}"
            )
            summary = dict(change["summary"])
            if noise:
                summary["en"] += (
                    " This is within the normal range of such changes for this series."
                    if normal
                    else f" This is unusual for this series (z={noise['z_score']:.1f} against "
                    f"{noise['comparable_changes']} comparable changes)."
                )
                summary["ar"] += (
                    " ويقع هذا ضمن المدى المعتاد لمثل هذه التغيرات في هذه السلسلة."
                    if normal
                    else f" وهذا غير معتاد لهذه السلسلة (z={noise['z_score']:.1f} مقارنة بـ"
                    f"{noise['comparable_changes']} تغيرات مماثلة)."
                )
            ws.add(
                agent="detective",
                kind="change",
                title=bi(title_en, title_ar),
                summary=summary,
                importance=importance,
                confidence=0.85,
                evidence_id=evidence_id,
                metrics=[
                    metric(
                        change["period_before"], change["period_before"], change["value_before"]
                    ),
                    metric(
                        change["period_after"],
                        change["period_after"],
                        change["value_after"],
                        "number",
                        relative,
                    ),
                    metric("Change", "التغيّر", change["change"]),
                ],
                chart=change.get("chart"),
                details=[
                    bi(
                        f"{m['member']}: {fmt(m['delta'])} ({pct(m['share_of_change'])} of the change)",
                        f"{m['member']}: {fmt(m['delta'])} ({pct(m['share_of_change'])} من التغيّر)",
                    )
                    for m in (first_breakdown["members"][:5] if first_breakdown else [])
                ],
                evidence={
                    "n": frame.row_count,
                    "relative_change": relative,
                    "root_cause_path": path,
                    "counter_movement": counter,
                    "dimension": first_breakdown["dimension"] if first_breakdown else None,
                    "compare": spec["compare"],
                    "within_normal_range": normal if noise else None,
                },
                tags=["change", spec["compare"]],
            )
        grain_for_anomalies = "week" if grain in {"week", "month"} else grain
        evidence_id, result = ws.run(
            "detective",
            "series_anomalies",
            {"measure": measure, "agg": agg, "grain": grain_for_anomalies},
            quiet=True,
        )
        if result and result["count"]:
            flags = sorted(result["anomalies"], key=lambda a: -abs(a["robust_z"]))[:4]
            ws.add(
                agent="detective",
                kind="anomaly_period",
                title=bi(
                    f"Unusual {grain_for_anomalies}s in {label}",
                    f"فترات غير اعتيادية في {label_ar}",
                ),
                summary=bi(
                    f"{result['count']} {grain_for_anomalies}(s) deviate sharply from their local level: "
                    + ", ".join(
                        f"{a['period']} ({fmt(a['value'])} vs ~{fmt(a['local_median'])})"
                        for a in flags
                    )
                    + ".",
                    f"{result['count']} فترة تنحرف بحدة عن مستواها المحلي: "
                    + "، ".join(
                        f"{a['period']} ({fmt(a['value'])} مقابل ~{fmt(a['local_median'])})"
                        for a in flags
                    )
                    + ".",
                ),
                importance=0.45 + min(0.2, 0.05 * result["count"]),
                confidence=0.75,
                evidence_id=evidence_id,
                chart=result["chart"],
                evidence={"n": len(result["periods"]), "count": result["count"]},
                tags=["anomaly"],
            )
    if frame.measures:
        evidence_id, result = ws.run("detective", "record_anomalies", {}, quiet=True)
        if result and result["top_records"]:
            extreme = [
                r
                for r in result["top_records"]
                if any(abs(x["robust_z"]) >= 8 for x in r["reasons"])
            ]
            share_value = None
            if measure and extreme:
                total = float(frame.numeric(measure).sum()) or 1.0
                share_value = (
                    sum(
                        float(frame.numeric(measure).iloc[r["row"]])
                        for r in extreme
                        if r["row"] < len(frame.df)
                    )
                    / total
                )
            examples = result["top_records"][:3]
            ws.add(
                agent="detective",
                kind="anomaly_records",
                title=bi(
                    f"{len(extreme) or result['flagged']} records look like errors or exceptional events",
                    f"{len(extreme) or result['flagged']} سجلًا تبدو أخطاء إدخال أو أحداثًا استثنائية",
                ),
                summary=bi(
                    result["summary"]["en"]
                    + (f" {len(extreme)} are extreme (>8 robust deviations)" if extreme else "")
                    + (f", together {pct(share_value)} of {measure}." if share_value else ".")
                    + " Example: "
                    + "; ".join(
                        f"row {r['row']}: "
                        + ", ".join(
                            f"{x['column']}={fmt(x['value'])} (typical {fmt(x['typical'])})"
                            for x in r["reasons"][:2]
                        )
                        for r in examples
                    ),
                    result["summary"]["ar"]
                    + (f" منها {len(extreme)} متطرفة جدًا" if extreme else "")
                    + (f"، وتمثل معًا {pct(share_value)} من {measure}." if share_value else ".")
                    + " مثال: "
                    + "؛ ".join(
                        f"الصف {r['row']}: "
                        + "، ".join(
                            f"{x['column']}={fmt(x['value'])} (المعتاد {fmt(x['typical'])})"
                            for x in r["reasons"][:2]
                        )
                        for r in examples
                    ),
                ),
                importance=0.5 + (0.2 if extreme else 0) + min(0.2, (share_value or 0) * 3),
                confidence=0.75,
                evidence_id=evidence_id,
                metrics=[
                    metric("Flagged records", "سجلات مرصودة", result["flagged"]),
                    metric("Extreme records", "سجلات متطرفة", len(extreme)),
                    metric(f"Share of {measure}", f"الحصة من {measure}", share_value, "percent"),
                ],
                evidence={
                    "n": result["records_scanned"],
                    "extreme": len(extreme),
                    "value_share": share_value,
                },
                tags=["anomaly", "data_quality"],
            )


# ------------------------------------------------------------------ data scientist
def data_scientist(ws: Workspace) -> list[dict[str, Any]]:
    """Returns driver results so the strategist can size levers."""

    frame = ws.frame
    ws.emit(
        "data_scientist",
        "status",
        bi("Modelling drivers and segments", "نمذجة العوامل المؤثرة والشرائح"),
    )
    targets: list[str] = []
    if frame.primary_kpi:
        targets.append(frame.primary_kpi)
    profit_like = next(
        (m for m in frame.measures if frame.roles[m].kpi_score == 0.95 and m != frame.primary_kpi),
        None,
    )
    if profit_like:
        targets.append(profit_like)
    if frame.outcome:
        targets.append(frame.outcome)
    driver_results: list[dict[str, Any]] = []
    for target in targets[:3]:
        evidence_id, result = ws.run("data_scientist", "key_drivers", {"target": target})
        if not result or not result["drivers"]:
            continue
        driver_results.append({"evidence_id": evidence_id, "result": result})
        model = result["model"]
        top = result["drivers"][:4]
        is_outcome = result["task"] == "classification"

        def describe(d: dict[str, Any], lang: str, is_outcome: bool = is_outcome) -> str:
            if d["kind"] == "categorical":
                if lang == "en":
                    return f"{d['feature']} (highest for {d.get('best_category')}, lowest for {d.get('worst_category')})"
                return f"{d['feature']} (الأعلى عند {d.get('best_category')} والأدنى عند {d.get('worst_category')})"
            size = pct(d.get("effect_range")) if is_outcome else fmt(d.get("effect_range"))
            if lang == "en":
                return f"{d['feature']} ({d.get('direction')}; P10→P90 moves the {'rate' if is_outcome else 'average'} by {size})"
            arrow = "طردي" if d.get("direction") == "positive" else "عكسي"
            return f"{d['feature']} ({arrow}؛ الانتقال من المئين 10 إلى 90 يغيّر {'النسبة' if is_outcome else 'المتوسط'} بمقدار {size})"

        excluded = [e["column"] for e in result.get("excluded_features", [])]
        dominance = result.get("dominance")
        dominance_en = dominance_ar = ""
        if dominance and dominance["drivers_without"]:
            rest = ", ".join(d["feature"] for d in dominance["drivers_without"][:3])
            dominance_en = (
                f" {dominance['feature']} alone carries {pct(dominance['share'])} of the explanation; "
                f"confirm it is known before {target} happens (not recorded after it). Without it the "
                f"model scores {dominance['model_without']['cv_score']:.2f} and the next drivers are {rest}."
            )
            dominance_ar = (
                f" يستحوذ {dominance['feature']} وحده على {pct(dominance['share'])} من التفسير؛ "
                f"تأكد أنه معروف قبل حدوث {target} (لا يُسجَّل بعده). بدونه يسجل النموذج "
                f"{dominance['model_without']['cv_score']:.2f} وأهم العوامل التالية: {'، '.join(d['feature'] for d in dominance['drivers_without'][:3])}."
            )
        ws.add(
            agent="data_scientist",
            kind="drivers",
            title=bi(f"What drives {target}", f"ما الذي يحرّك {target}"),
            summary=bi(
                f"{result['summary']['en']} Top levers: "
                + "; ".join(describe(d, "en") for d in top)
                + "."
                + (
                    f" Excluded as sibling outcomes/identities: {', '.join(excluded)}."
                    if excluded
                    else ""
                )
                + dominance_en,
                f"{result['summary']['ar']} أهم العوامل: "
                + "؛ ".join(describe(d, "ar") for d in top)
                + "."
                + (
                    f" استُبعدت كنتائج موازية أو متطابقات حسابية: {'، '.join(excluded)}."
                    if excluded
                    else ""
                )
                + dominance_ar,
            ),
            importance=0.6
            + (
                0.25
                if model["quality"] == "strong"
                else 0.1
                if model["quality"] == "moderate"
                else 0
            ),
            confidence={"strong": 0.85, "moderate": 0.65, "weak": 0.4}[model["quality"]],
            evidence_id=evidence_id,
            metrics=[
                metric("Model fit (CV)", "جودة النموذج", model["cv_score"], "ratio"),
                metric("Metric", "المقياس", model["metric"], "text"),
                *[metric(d["feature"], d["feature"], d["share"], "percent") for d in top[:3]],
            ],
            chart=result["chart"],
            evidence={
                "n": result["rows_used"],
                "model_quality": model["quality"],
                "cv_score": model["cv_score"],
                "target": target,
            },
            caveats=[result["caveat"]],
            tags=["drivers", target],
        )
    if len(frame.measures) >= 2:
        evidence_id, result = ws.run("data_scientist", "segment", {})
        if result:
            largest_value = max(result["segments"], key=lambda s: s.get("share_of_primary_kpi", 0))
            ws.add(
                agent="data_scientist",
                kind="segments",
                title=bi(f"{result['k']} natural segments", f"{result['k']} شرائح طبيعية"),
                summary=bi(
                    result["summary"]["en"]
                    + f" Most valuable: {largest_value['name']['en']} ({pct(largest_value['share'])} of records, "
                    f"{pct(largest_value.get('share_of_primary_kpi'))} of {result['primary_kpi']}).",
                    result["summary"]["ar"]
                    + f" الأعلى قيمة: {largest_value['name']['ar']} ({pct(largest_value['share'])} من السجلات، "
                    f"و{pct(largest_value.get('share_of_primary_kpi'))} من {result['primary_kpi']}).",
                ),
                importance=0.45 + (0.15 if result["separation"] != "weak" else 0),
                confidence=0.75 if result["separation"] != "weak" else 0.5,
                evidence_id=evidence_id,
                chart=result["chart"],
                details=[
                    bi(
                        f"{s['name']['en']}: {pct(s['share'])} of records, {pct(s.get('share_of_primary_kpi'))} of {result['primary_kpi']}",
                        f"{s['name']['ar']}: {pct(s['share'])} من السجلات، {pct(s.get('share_of_primary_kpi'))} من {result['primary_kpi']}",
                    )
                    for s in result["segments"]
                ],
                evidence={"n": result["records"], "silhouette": result["silhouette"]},
                tags=["segments"],
            )
    if frame.entities and frame.time_column:
        evidence_id, result = ws.run("data_scientist", "customer_value_tiers", {})
        if result:
            tiers = {t["tier"]: t for t in result["tiers"]}
            champions = tiers.get("champions")
            at_risk = tiers.get("at_risk")
            ws.add(
                agent="data_scientist",
                kind="customers",
                title=bi(
                    f"{result['entity']} value tiers (RFM)", f"شرائح قيمة {result['entity']} (RFM)"
                ),
                summary=bi(
                    result["summary"]["en"]
                    + (
                        f" Champions are {pct(champions['share_of_entities'])} of {result['entity']} but "
                        f"{pct(champions['share_of_value'])} of value."
                        if champions
                        else ""
                    ),
                    result["summary"]["ar"]
                    + (
                        f" «الأبطال» يمثلون {pct(champions['share_of_entities'])} من {result['entity']} لكن "
                        f"{pct(champions['share_of_value'])} من القيمة."
                        if champions
                        else ""
                    ),
                ),
                importance=0.55 + (0.15 if at_risk and at_risk["share_of_value"] > 0.05 else 0),
                confidence=0.8,
                evidence_id=evidence_id,
                chart=result["chart"],
                metrics=[
                    metric(
                        "At-risk value",
                        "القيمة المعرضة للفقدان",
                        at_risk["value"] if at_risk else 0.0,
                        "money",
                    ),
                    metric(
                        "At-risk entities",
                        "المعرضون للفقدان",
                        at_risk["entities"] if at_risk else 0,
                    ),
                    metric(
                        "Champions' share of value",
                        "حصة الأبطال من القيمة",
                        champions["share_of_value"] if champions else None,
                        "percent",
                    ),
                ],
                evidence={
                    "n": result["entities"],
                    "at_risk_value": at_risk["value"] if at_risk else 0.0,
                    "at_risk_entities": at_risk["entities"] if at_risk else 0,
                    "at_risk_share": at_risk["share_of_value"] if at_risk else 0.0,
                },
                tags=["customers", "rfm"],
            )
        evidence_id, result = ws.run("data_scientist", "cohort_retention", {}, quiet=True)
        if result and result.get("period_1_retention") is not None:
            retention = result["period_1_retention"]
            ws.add(
                agent="data_scientist",
                kind="retention",
                title=bi("Repeat behaviour by cohort", "تكرار التعامل حسب الدفعة"),
                summary=result["summary"],
                importance=0.45 + (0.2 if retention < 0.2 else 0),
                confidence=0.7,
                evidence_id=evidence_id,
                chart=result["chart"],
                metrics=[
                    metric(
                        "Next-period retention", "الاحتفاظ في الفترة التالية", retention, "percent"
                    )
                ],
                evidence={"n": sum(c["size"] for c in result["cohorts"]), "retention": retention},
                tags=["retention"],
            )
    return driver_results


# --------------------------------------------------------------------- strategist
def size_levers(ws: Workspace, driver_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """What-if on the strongest numeric lever of each driver model."""

    ws.emit(
        "strategist",
        "status",
        bi("Sizing the levers with what-if scenarios", "تقدير أثر الروافع بسيناريوهات «ماذا لو»"),
    )
    scenarios: list[dict[str, Any]] = []
    for item in driver_results:
        result = item["result"]
        if result["model"]["quality"] == "weak":
            continue
        target_role = ws.frame.roles.get(result["target"])
        money_target = bool(target_role and target_role.kpi_score >= 0.75)

        def actionable(d: dict[str, Any], money_target: bool = money_target) -> bool:
            role = ws.frame.roles.get(d["feature"])
            if d["kind"] != "numeric" or role is None or role.role != "measure":
                return False
            # Price and quantity are arithmetic components of a money target: holding
            # everything else fixed while moving them tells you nothing about demand.
            return not (money_target and role.kpi_score in {0.55, 0.7, 0.65})

        dominance = result.get("dominance")
        pool = dominance["drivers_without"] if dominance else result["drivers"]
        lever = next((d for d in pool if actionable(d) and (d.get("share") or 0) >= 0.05), None)
        if lever is None:
            continue
        good_direction = -1 if result["task"] == "classification" else 1
        # Move the lever 20% in the direction that improves the target.
        step = 20.0 if (lever["direction"] == "positive") == (good_direction > 0) else -20.0
        arguments: dict[str, Any] = {
            "target": result["target"],
            "changes": [{"column": lever["feature"], "percent_change": step}],
        }
        if dominance:
            # Size levers without a feature that may be a consequence of the outcome.
            arguments["exclude"] = [dominance["feature"]]
        evidence_id, scenario = ws.run("strategist", "what_if", arguments)
        if not scenario:
            continue
        scenarios.append(
            {"evidence_id": evidence_id, "scenario": scenario, "lever": lever, "step": step}
        )
        is_outcome = scenario["task"] == "classification"
        delta = scenario["change_per_record"]
        total = scenario.get("total_change_over_rows")
        ws.add(
            agent="strategist",
            kind="what_if",
            title=bi(
                f"If {lever['feature']} changes {step:+.0f}%: effect on {result['target']}",
                f"لو تغيّر {lever['feature']} بنسبة {step:+.0f}%: الأثر على {result['target']}",
            ),
            summary=bi(
                f"Modelled {result['target']}: {pct(scenario['baseline_mean']) if is_outcome else fmt(scenario['baseline_mean'])} → "
                f"{pct(scenario['scenario_mean']) if is_outcome else fmt(scenario['scenario_mean'])} "
                + (
                    f"({delta * 100:+.1f} percentage points)."
                    if is_outcome
                    else f"per record ({pct(scenario['relative_change'], signed=True)}; ≈{fmt(total)} across all records)."
                ),
                f"القيمة المقدّرة لـ{result['target']}: {pct(scenario['baseline_mean']) if is_outcome else fmt(scenario['baseline_mean'])} ← "
                f"{pct(scenario['scenario_mean']) if is_outcome else fmt(scenario['scenario_mean'])} "
                + (
                    f"({delta * 100:+.1f} نقطة مئوية)."
                    if is_outcome
                    else f"لكل سجل ({pct(scenario['relative_change'], signed=True)}؛ ≈{fmt(total)} على جميع السجلات)."
                ),
            ),
            importance=0.55 + min(0.3, abs(scenario.get("relative_change") or 0) * 2),
            confidence=0.6 if not scenario["extrapolating"] else 0.4,
            evidence_id=evidence_id,
            evidence={
                "n": scenario["rows"],
                "relative_change": scenario.get("relative_change"),
                "delta": delta,
                "total": total,
                "lever": lever["feature"],
                "step": step,
                "target": result["target"],
            },
            caveats=[scenario["caveat"]],
            tags=["what_if", lever["feature"]],
        )
    return scenarios
