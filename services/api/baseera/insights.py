"""Findings written the way a consultant writes them.

Every finding separates four things a reader is entitled to keep apart:

``observation``      arithmetic over the data, reproducible and not arguable
``interpretation``   what it most likely means, stated as a reading rather than a fact
``recommendation``   the action it implies
``limitation``       what the finding does not establish

Nothing here calls a model. The findings are deterministic, so the same data always
produces the same analysis and a buyer can audit any number back to its rows.
"""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from collections.abc import Callable
from typing import Any

import numpy as np

from . import arabic as ar
from .profiling import coerce_number, parse_date_value

SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}

# Below this many rows, most inference is noise. Findings that need scale say so.
MIN_ROWS_FOR_INFERENCE = 30


def _finding(
    identifier: str,
    kind: str,
    severity: str,
    confidence: str,
    title: tuple[str, str],
    observation: tuple[str, str],
    interpretation: tuple[str, str],
    recommendation: tuple[str, str],
    limitation: tuple[str, str],
    evidence: dict[str, Any],
    chart: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "id": identifier,
        "kind": kind,
        "severity": severity,
        "confidence": confidence,
        "title": {"en": title[0], "ar": title[1]},
        "observation": {"en": observation[0], "ar": observation[1]},
        "interpretation": {"en": interpretation[0], "ar": interpretation[1]},
        "recommendation": {"en": recommendation[0], "ar": recommendation[1]},
        "limitation": {"en": limitation[0], "ar": limitation[1]},
        "evidence": evidence,
        "chart": chart,
    }


def _numeric_columns(rows: list[dict[str, Any]], profile: dict[str, Any]) -> list[str]:
    return [
        name
        for name, column in profile.get("column_profiles", {}).items()
        if column.get("semantic_type") in {"number", "number_text"}
        and column.get("numeric", {}).get("std_dev", 0) is not None
    ]


def _categorical_columns(profile: dict[str, Any], row_count: int) -> list[str]:
    return [
        name
        for name, column in profile.get("column_profiles", {}).items()
        if column.get("semantic_type") in {"categorical", "text", "boolean"}
        and 1 < column.get("distinct_count", 0) <= max(2, min(60, row_count // 3))
    ]


def _dimension_columns(profile: dict[str, Any], row_count: int) -> list[str]:
    """Columns worth grouping by when asking where a total is concentrated.

    Wider than the plain categorical gate: customer and product columns carry many
    distinct values and are exactly where concentration risk lives. A column that is
    nearly unique per row is excluded, because grouping by it says nothing.
    """
    return [
        name
        for name, column in profile.get("column_profiles", {}).items()
        if column.get("semantic_type") in {"categorical", "text", "boolean", "identifier"}
        and 1 < column.get("distinct_count", 0) <= min(500, max(4, row_count // 2))
        and column.get("distinct_rate", 1.0) < 0.9
    ]


def _date_columns(profile: dict[str, Any]) -> list[str]:
    return [
        name
        for name, column in profile.get("column_profiles", {}).items()
        if column.get("temporal", {}).get("detected_format")
    ]


def _values(rows: list[dict[str, Any]], column: str) -> list[float]:
    return [n for n in (coerce_number(row.get(column))[0] for row in rows) if n is not None]


def _quality_findings(profile: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    quality = profile.get("quality") or {}
    score = quality.get("score")
    grade = quality.get("grade")
    counts = quality.get("counts", {})
    if score is None:
        return findings

    severity = (
        "critical" if score < 50 else "high" if score < 75 else "medium" if score < 90 else "info"
    )
    grade_ar = {
        "ready": "جاهزة",
        "usable_with_caveats": "قابلة للاستخدام مع تحفظات",
        "repair_required": "تحتاج إصلاحًا",
        "not_fit_for_reporting": "غير صالحة للتقارير",
    }.get(str(grade), str(grade))
    dimensions = quality.get("dimensions", {})
    weakest = min(dimensions, key=lambda k: dimensions[k]) if dimensions else None
    weakest_ar = {
        "completeness": "الاكتمال",
        "uniqueness": "التفرّد",
        "validity": "الصلاحية",
        "consistency": "الاتساق",
        "plausibility": "المعقولية",
    }.get(str(weakest), str(weakest))
    findings.append(
        _finding(
            "quality.score",
            "data_quality",
            severity,
            "high",
            ("Data quality assessment", "تقييم جودة البيانات"),
            (
                f"Quality scores {score}/100 ({grade}). Of {counts.get('cells', 0):,} cells, "
                f"{counts.get('missing_cells', 0):,} are empty, "
                f"{counts.get('invalid_cells', 0):,} cannot be read as their column's type, and "
                f"{counts.get('duplicate_rows', 0):,} rows are exact duplicates. "
                f"The weakest dimension is {weakest} at "
                f"{dimensions.get(weakest, 0):.0%}.",
                f"تبلغ الجودة {score}/100 ({grade_ar}). من أصل "
                f"{ar.count(int(counts.get('cells', 0)), ar.CELL)}، هناك "
                f"{ar.count(int(counts.get('missing_cells', 0)), ar.CELL)} فارغة، و"
                f"{ar.count(int(counts.get('invalid_cells', 0)), ar.CELL)} لا تُقرأ بنوع عمودها، و"
                f"{ar.count(int(counts.get('duplicate_rows', 0)), ar.ROW)} مكررة تمامًا. "
                f"أضعف بُعد هو {weakest_ar} عند {dimensions.get(weakest, 0):.0%}.",
            ),
            (
                "Reporting built on this file inherits these defects. Duplicates inflate "
                "counts and sums; unreadable cells drop silently out of averages, which "
                "understates totals without producing an error."
                if severity in {"critical", "high"}
                else "The file is usable for reporting once the flagged repairs are reviewed.",
                "أي تقرير مبني على هذا الملف يرث هذه العيوب. التكرارات تضخّم الأعداد "
                "والمجاميع، والخلايا غير المقروءة تسقط بصمت من المتوسطات فتقلّل المجاميع "
                "دون إظهار أي خطأ."
                if severity in {"critical", "high"}
                else "الملف صالح للتقارير بعد مراجعة الإصلاحات المقترحة.",
            ),
            (
                "Apply the proposed cleaning steps, review the reconciliation, and publish "
                "a cleaned version before any figure leaves this workspace.",
                "طبّق خطوات التنظيف المقترحة وراجع المطابقة وانشر إصدارًا منظّفًا قبل خروج "
                "أي رقم من مساحة العمل.",
            ),
            (
                "The score measures form, not truth. A perfectly formatted file can still "
                "record the wrong thing.",
                "يقيس المؤشر الشكل لا الصحة. قد يسجّل ملف سليم التنسيق معلومة خاطئة تمامًا.",
            ),
            {"score": score, "grade": grade, "dimensions": dimensions, "counts": counts},
            {"type": "radar", "series": dimensions},
        )
    )

    for name, column in profile.get("column_profiles", {}).items():
        temporal = column.get("temporal", {})
        if temporal.get("mixed_formats"):
            formats = temporal.get("formats_found", {})
            findings.append(
                _finding(
                    f"quality.mixed_dates.{name}",
                    "data_quality",
                    "high",
                    "high",
                    (
                        f"{name} mixes date conventions",
                        f"يخلط العمود {name} بين تقاليد التاريخ",
                    ),
                    (
                        f"{name} contains {len(formats)} different date formats: "
                        + ", ".join(f"{k} ({v:,})" for k, v in formats.items())
                        + ".",
                        f"يحتوي {name} على {len(formats)} أنماط تاريخ مختلفة: "
                        + ar.joined([f"{k} ({v:,})" for k, v in formats.items()])
                        + ".",
                    ),
                    (
                        "This usually means the column was assembled from more than one "
                        "source system, or edited by hand. No single parsing rule is "
                        "correct for all of it, so any period grouping is currently wrong "
                        "for part of the file.",
                        "يعني هذا غالبًا أن العمود جُمع من أكثر من نظام مصدر أو حُرِّر يدويًا. "
                        "لا توجد قاعدة تحليل واحدة صحيحة للجميع، لذا أي تجميع زمني الآن "
                        "خاطئ لجزء من الملف.",
                    ),
                    (
                        "Split the column by source, confirm each convention with the "
                        "system owner, then normalise to ISO 8601.",
                        "افصل العمود حسب المصدر، وأكّد كل تقليد مع مالك النظام، ثم وحّده "
                        "إلى ISO 8601.",
                    ),
                    (
                        "Detection reads the written form only; it cannot recover the "
                        "intended date where day and month are both below thirteen.",
                        "يقرأ الاكتشاف الشكل المكتوب فقط، ولا يمكنه استرجاع التاريخ المقصود "
                        "عندما يكون اليوم والشهر كلاهما أقل من ثلاثة عشر.",
                    ),
                    {
                        "column": name,
                        "formats": formats,
                        "ambiguous_cells": temporal.get("ambiguous_cells", 0),
                    },
                    {"type": "bar", "series": formats},
                )
            )
        parse = column.get("numeric_parse", {})
        if parse.get("unparsable") and column.get("semantic_type") == "number_text":
            share = parse["unparsable"] / max(1, column.get("present_count", 1))
            findings.append(
                _finding(
                    f"quality.unreadable_numbers.{name}",
                    "data_quality",
                    "critical" if share > 0.1 else "high",
                    "high",
                    (
                        f"{name} holds numbers stored as text",
                        f"يحتفظ {name} بأرقام مخزّنة كنص",
                    ),
                    (
                        f"{parse['tolerant_parsable']:,} values in {name} are numeric but "
                        "written as text ("
                        + (", ".join(parse.get("repairs_required", {})) or "mixed notation")
                        + "), "
                        f"and {parse['unparsable']:,} ({share:.0%}) cannot be read as a "
                        "number at all. Examples: "
                        + ", ".join(parse.get("unparsable_examples", [])[:3])
                        + ".",
                        f"هناك {parse['tolerant_parsable']:,} قيمة في {name} رقمية لكنها "
                        f"مكتوبة كنص، و{parse['unparsable']:,} ({share:.0%}) لا تُقرأ كرقم "
                        "إطلاقًا. أمثلة: "
                        + ar.joined(parse.get("unparsable_examples", [])[:3])
                        + ".",
                    ),
                    (
                        "Spreadsheet tools drop text cells out of SUM and AVERAGE without "
                        "warning. Any total already computed over this column is "
                        "understated, and the shortfall is invisible in the result.",
                        "تُسقط أدوات الجداول الخلايا النصية من دوال الجمع والمتوسط دون "
                        "تحذير. أي مجموع حُسب على هذا العمود أقل من الحقيقة، والنقص غير "
                        "ظاهر في النتيجة.",
                    ),
                    (
                        f"Cast {name} to a number, then compare the control total before "
                        "and after. The difference is the amount previously missing from "
                        "every report.",
                        f"حوّل {name} إلى رقم، ثم قارن المجموع الرقابي قبل وبعد. الفرق هو "
                        "المبلغ الذي كان غائبًا عن كل تقرير.",
                    ),
                    (
                        "Cells that remain unreadable after the cast need a human decision; "
                        "the engine will not guess a value.",
                        "الخلايا التي تبقى غير مقروءة بعد التحويل تحتاج قرارًا بشريًا؛ "
                        "لن يخمّن المحرك أي قيمة.",
                    ),
                    {"column": name, **parse},
                    None,
                )
            )
    return findings


def _concentration_findings(
    rows: list[dict[str, Any]], profile: dict[str, Any]
) -> list[dict[str, Any]]:
    """Where the business is exposed: how few names carry the total.

    Concentration is judged against the equal-share baseline for the number of
    categories present. A raw Herfindahl index cannot fall below 1/n, so comparing it
    to a fixed threshold declares every three-category breakdown "concentrated", which
    is a tautology rather than a finding.
    """
    findings: list[dict[str, Any]] = []
    row_count = len(rows)
    measures = _numeric_columns(rows, profile)
    dimensions = _dimension_columns(profile, row_count)
    if not measures or not dimensions:
        return findings
    measure = max(
        measures,
        key=lambda name: abs(
            profile["column_profiles"][name].get("numeric", {}).get("sum", 0) or 0
        ),
    )
    for dimension in dimensions[:4]:
        totals: dict[str, float] = defaultdict(float)
        for row in rows:
            value, _ = coerce_number(row.get(measure))
            if value is None:
                continue
            totals[str(row.get(dimension))] += value
        categories = len(totals)
        # With three or fewer categories every share is large by construction and the
        # statement carries no information.
        if categories < 4:
            continue
        ordered = sorted(totals.items(), key=lambda item: -item[1])
        grand = sum(v for _, v in ordered)
        if grand <= 0:
            continue
        shares = [v / grand for _, v in ordered]
        cumulative = np.cumsum(shares)
        top_count = int(np.searchsorted(cumulative, 0.8) + 1)
        top_count = min(top_count, categories)
        top_share = float(cumulative[top_count - 1])
        herfindahl = float(sum(s**2 for s in shares))
        equal_share = 1.0 / categories
        # 0 when every category is equal, 1 when one category holds everything.
        normalized = (herfindahl - equal_share) / (1 - equal_share) if categories > 1 else 0.0
        leader, leader_value = ordered[0]
        leader_share = leader_value / grand
        remaining = categories - top_count

        # Report only when the split is materially more skewed than an even one.
        if normalized < 0.20 and leader_share < 3 * equal_share:
            continue
        severity = (
            "high"
            if normalized > 0.5 or leader_share > 0.5
            else "medium"
            if normalized > 0.3 or leader_share > 0.35
            else "low"
        )
        tail_en = (
            f"the remaining {remaining:,} carry {1 - top_share:.0%} between them"
            if remaining
            else "no category sits outside that group"
        )
        tail_ar = (
            f"وتتقاسم الـ{remaining:,} المتبقية {1 - top_share:.0%}"
            if remaining
            else "ولا توجد فئة خارج هذه المجموعة"
        )
        findings.append(
            _finding(
                f"concentration.{dimension}.{measure}",
                "concentration",
                severity,
                "high",
                (
                    f"{measure} depends on a few {dimension} values",
                    f"يعتمد {measure} على عدد قليل من قيم {dimension}",
                ),
                (
                    f"{top_count} of {categories} {dimension} values account for "
                    f"{top_share:.0%} of total {measure}, and {tail_en}. The largest, "
                    f"{leader!r}, carries {leader_share:.0%} on its own against "
                    f"{equal_share:.0%} for an even split. Normalised concentration is "
                    f"{normalized:.2f} on a 0-to-1 scale.",
                    f"تستحوذ {top_count} من {categories} قيمة في {dimension} على "
                    f"{top_share:.0%} من إجمالي {measure}، {tail_ar}. وتحمل الأكبر، "
                    f"{leader!r}، {leader_share:.0%} وحدها مقابل {equal_share:.0%} في "
                    f"التوزيع المتساوي. التركّز المعياري {normalized:.2f} على مقياس من 0 إلى 1.",
                ),
                (
                    f"This is concentration risk. Losing {leader!r} removes "
                    f"{leader_share:.0%} of {measure} in a single event"
                    + (
                        f", and the {remaining:,} smaller values would each need to grow "
                        f"by {leader_share / max(1 - leader_share, 1e-9):.0%} to replace it."
                        if remaining
                        else ", with no smaller tail available to absorb it."
                    ),
                    f"هذه مخاطرة تركّز. فقدان {leader!r} يزيل {leader_share:.0%} من "
                    f"{measure} في حدث واحد"
                    + (
                        f"، وستحتاج القيم الأصغر الـ{remaining:,} إلى النمو بنسبة "
                        f"{leader_share / max(1 - leader_share, 1e-9):.0%} لتعويضه."
                        if remaining
                        else "، ولا يوجد ذيل أصغر يمتصّه."
                    ),
                ),
                (
                    f"Set a concentration ceiling for {dimension}, track the leading share "
                    "as a standing metric, and name a retention owner for the largest "
                    "positions before the next planning cycle.",
                    f"ضع سقفًا للتركّز في {dimension}، وتابع حصة الأكبر كمقياس دائم، وعيّن "
                    "مسؤولًا بالاسم عن الاحتفاظ بأكبر المراكز قبل دورة التخطيط القادمة.",
                ),
                (
                    "Concentration describes exposure, not health. A concentrated book can "
                    "be entirely appropriate for the market being served, and this measure "
                    "says nothing about the profitability of any position.",
                    "يصف التركّز التعرّض للمخاطر لا الصحة. قد يكون التركّز مناسبًا تمامًا "
                    "للسوق المخدوم، ولا يقول هذا المقياس شيئًا عن ربحية أي مركز.",
                ),
                {
                    "dimension": dimension,
                    "measure": measure,
                    "categories": categories,
                    "top_count_for_80_percent": top_count,
                    "top_share": round(top_share, 4),
                    "leader": leader,
                    "leader_share": round(leader_share, 4),
                    "even_split_share": round(equal_share, 4),
                    "herfindahl": round(herfindahl, 4),
                    "normalised_concentration": round(normalized, 4),
                    "top_values": [
                        {"label": k, "value": round(v, 4), "share": round(v / grand, 4)}
                        for k, v in ordered[:10]
                    ],
                },
                {"type": "pareto", "dimension": dimension, "measure": measure},
            )
        )
    return findings


def _distribution_findings(
    rows: list[dict[str, Any]], profile: dict[str, Any]
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for name in _numeric_columns(rows, profile)[:6]:
        stats = profile["column_profiles"][name].get("numeric", {})
        if not stats or stats.get("outlier_count") is None:
            continue
        count = profile["column_profiles"][name].get("present_count", 0)
        outliers = int(stats.get("outlier_count", 0))
        if not outliers or count < MIN_ROWS_FOR_INFERENCE:
            continue
        share = outliers / count
        bounds = stats.get("outlier_bounds") or {}
        severity = "high" if share > 0.05 else "medium" if share > 0.01 else "low"
        findings.append(
            _finding(
                f"distribution.outliers.{name}",
                "distribution",
                severity,
                "medium",
                (f"{name} has a long tail", f"يحمل {name} ذيلًا طويلًا"),
                (
                    f"{outliers:,} of {count:,} values ({share:.1%}) in {name} fall outside "
                    f"[{bounds.get('lower', 0):,.2f}, {bounds.get('upper', 0):,.2f}]. "
                    f"The median is {stats.get('median', 0):,.2f} while the mean is "
                    f"{stats.get('mean', 0):,.2f}, and the distribution is "
                    + (
                        "symmetric."
                        if stats.get("skew_direction") == "symmetric"
                        else f"{stats.get('skew_direction')}-skewed."
                    ),
                    f"تقع {ar.count(outliers, ar.VALUE)} من أصل {count:,} ({share:.1%}) في "
                    f"{name} خارج النطاق [{bounds.get('lower', 0):,.2f}, "
                    f"{bounds.get('upper', 0):,.2f}]. الوسيط {stats.get('median', 0):,.2f} "
                    f"بينما المتوسط {stats.get('mean', 0):,.2f}.",
                ),
                (
                    f"When the mean sits away from the median, the average stops describing "
                    f"a typical case. Reporting the mean of {name} to a decision-maker will "
                    "overstate the ordinary outcome.",
                    f"عندما يبتعد المتوسط عن الوسيط يتوقف المتوسط عن وصف الحالة النمطية. "
                    f"عرض متوسط {name} على متخذ القرار سيبالغ في تقدير النتيجة المعتادة.",
                ),
                (
                    f"Report the median and an interquartile range for {name}, and review "
                    "the extreme rows individually before excluding any of them.",
                    f"اعرض الوسيط والمدى الربيعي لـ{name}، وراجع الصفوف المتطرفة فرديًا قبل "
                    "استبعاد أي منها.",
                ),
                (
                    "An outlier by this definition is a statistical distance, not an error. "
                    "The largest values are often the most important customers.",
                    "القيمة المتطرفة بهذا التعريف مسافة إحصائية لا خطأ. غالبًا ما تكون أكبر "
                    "القيم هي أهم العملاء.",
                ),
                {"column": name, **stats},
                {"type": "box", "column": name},
            )
        )
    return findings


def _relationship_findings(
    rows: list[dict[str, Any]], profile: dict[str, Any]
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    numeric = _numeric_columns(rows, profile)
    if len(numeric) < 2 or len(rows) < MIN_ROWS_FOR_INFERENCE:
        return findings
    pairs: list[tuple[str, str, float, int]] = []
    for index, left in enumerate(numeric[:8]):
        for right in numeric[index + 1 : 8]:
            paired = [
                (a, b)
                for a, b in (
                    (coerce_number(row.get(left))[0], coerce_number(row.get(right))[0])
                    for row in rows
                )
                if a is not None and b is not None
            ]
            if len(paired) < MIN_ROWS_FOR_INFERENCE:
                continue
            first = np.asarray([p[0] for p in paired], dtype=float)
            second = np.asarray([p[1] for p in paired], dtype=float)
            if float(np.std(first)) == 0 or float(np.std(second)) == 0:
                continue
            correlation = float(np.corrcoef(first, second)[0, 1])
            if math.isfinite(correlation) and abs(correlation) >= 0.6:
                pairs.append((left, right, correlation, len(paired)))
    for left, right, correlation, sample in sorted(pairs, key=lambda p: -abs(p[2]))[:3]:
        direction = "together" if correlation > 0 else "in opposite directions"
        direction_ar = "معًا" if correlation > 0 else "في اتجاهين متعاكسين"
        findings.append(
            _finding(
                f"relationship.{left}.{right}",
                "relationship",
                "info",
                "medium" if abs(correlation) < 0.85 else "high",
                (
                    f"{left} and {right} move {direction}",
                    f"يتحرك {left} و{right} {direction_ar}",
                ),
                (
                    f"Across {sample:,} rows with both values present, {left} and {right} "
                    f"have a Pearson correlation of {correlation:+.2f}, so roughly "
                    f"{correlation**2:.0%} of the variation in one is matched by variation "
                    "in the other.",
                    f"عبر {sample:,} صف تتوفر فيها القيمتان، يبلغ معامل ارتباط بيرسون بين "
                    f"{left} و{right} نحو {correlation:+.2f}، أي أن قرابة "
                    f"{correlation**2:.0%} من التباين في أحدهما يقابله تباين في الآخر.",
                ),
                (
                    "A relationship this strong is usually either a definitional link "
                    "(one column is derived from the other), a shared driver such as "
                    "volume or seasonality, or a genuine dependency worth modelling.",
                    "الارتباط بهذه القوة يكون عادة إما صلة تعريفية (أحد العمودين مشتق من "
                    "الآخر)، أو محركًا مشتركًا كالحجم أو الموسمية، أو اعتمادًا حقيقيًا "
                    "يستحق النمذجة.",
                ),
                (
                    f"Check first whether {right} is computed from {left}. If it is not, "
                    "this pair is a candidate for a driver model in the next analysis cycle.",
                    f"تحقّق أولًا مما إذا كان {right} محسوبًا من {left}. إن لم يكن، فهذا "
                    "الزوج مرشّح لنموذج محرّكات في دورة التحليل القادمة.",
                ),
                (
                    "Correlation is not causation and this test assumes a straight-line "
                    "relationship. It cannot detect a curved one, and says nothing about "
                    "which variable moves first.",
                    "الارتباط ليس سببية، وهذا الاختبار يفترض علاقة خطية، فلا يكتشف العلاقات "
                    "المنحنية ولا يحدد أي المتغيرين يتحرك أولًا.",
                ),
                {
                    "left": left,
                    "right": right,
                    "pearson_r": round(correlation, 4),
                    "r_squared": round(correlation**2, 4),
                    "sample": sample,
                },
                {"type": "scatter", "x": left, "y": right},
            )
        )
    return findings


def _missingness_findings(
    rows: list[dict[str, Any]], profile: dict[str, Any]
) -> list[dict[str, Any]]:
    """Missing data that clusters in one segment is bias, not inconvenience."""
    findings: list[dict[str, Any]] = []
    if len(rows) < MIN_ROWS_FOR_INFERENCE:
        return findings
    dimensions = _categorical_columns(profile, len(rows))
    for name, column in profile.get("column_profiles", {}).items():
        missing = int(column.get("null_count", 0))
        if not missing or missing == len(rows):
            continue
        overall = missing / len(rows)
        for dimension in dimensions[:3]:
            if dimension == name:
                continue
            grouped: dict[str, list[int]] = defaultdict(list)
            for row in rows:
                empty = row.get(name) is None or row.get(name) == ""
                grouped[str(row.get(dimension))].append(int(empty))
            rates = {
                key: sum(flags) / len(flags) for key, flags in grouped.items() if len(flags) >= 10
            }
            if len(rates) < 2:
                continue
            worst = max(rates, key=lambda k: rates[k])
            if rates[worst] < max(0.3, overall * 2.5):
                continue
            findings.append(
                _finding(
                    f"missingness.{name}.{dimension}",
                    "missingness",
                    "high",
                    "medium",
                    (
                        f"{name} is missing unevenly across {dimension}",
                        f"يغيب {name} بشكل غير متساوٍ عبر {dimension}",
                    ),
                    (
                        f"{name} is empty in {overall:.0%} of rows overall, but in "
                        f"{rates[worst]:.0%} of rows where {dimension} is {worst!r} "
                        f"({len(grouped[worst]):,} rows).",
                        f"يكون {name} فارغًا في {overall:.0%} من الصفوف إجمالًا، لكن في "
                        f"{rates[worst]:.0%} من الصفوف التي يكون فيها {dimension} هو "
                        f"{worst!r} ({len(grouped[worst]):,} صف).",
                    ),
                    (
                        "Missing values that cluster in one segment are not random. Any "
                        f"average or total that silently drops them will under-represent "
                        f"{worst!r} specifically, so a comparison between segments is "
                        "currently unfair.",
                        "القيم المفقودة المتجمّعة في شريحة واحدة ليست عشوائية. أي متوسط أو "
                        f"مجموع يُسقطها بصمت سيمثّل {worst!r} تمثيلًا ناقصًا تحديدًا، لذا "
                        "المقارنة بين الشرائح غير عادلة حاليًا.",
                    ),
                    (
                        f"Find out why {name} is not captured for {worst!r} before "
                        "comparing segments. Fix the collection path rather than imputing, "
                        "and if you must impute, do it per segment and label it.",
                        f"اعرف سبب عدم تسجيل {name} لـ{worst!r} قبل مقارنة الشرائح. أصلح "
                        "مسار الجمع بدل التعويض، وإن اضطررت للتعويض فافعله لكل شريحة "
                        "على حدة ووسمه.",
                    ),
                    (
                        "This shows association between missingness and segment, not the "
                        "reason for it. The cause is usually a process, not the data.",
                        "يُظهر هذا ارتباطًا بين الغياب والشريحة لا سببه. السبب عادة عملية "
                        "تشغيلية لا البيانات نفسها.",
                    ),
                    {
                        "column": name,
                        "dimension": dimension,
                        "overall_missing_rate": round(overall, 4),
                        "worst_segment": worst,
                        "worst_segment_rate": round(rates[worst], 4),
                        "rates": {
                            k: round(v, 4)
                            for k, v in sorted(rates.items(), key=lambda i: -i[1])[:10]
                        },
                    },
                    {
                        "type": "bar",
                        "series": {k: round(v, 4) for k, v in rates.items()},
                    },
                )
            )
            break
    return findings


def _trend_findings(rows: list[dict[str, Any]], profile: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    dates = _date_columns(profile)
    measures = _numeric_columns(rows, profile)
    if not dates or not measures:
        return findings
    date_column = dates[0]
    pattern = profile["column_profiles"][date_column]["temporal"]["strptime_pattern"]
    measure = max(
        measures,
        key=lambda name: abs(
            profile["column_profiles"][name].get("numeric", {}).get("sum", 0) or 0
        ),
    )
    buckets: dict[str, float] = defaultdict(float)
    for row in rows:
        parsed = parse_date_value(row.get(date_column), pattern)
        value, _ = coerce_number(row.get(measure))
        if parsed is None or value is None:
            continue
        buckets[parsed[:7]] += value
    if len(buckets) < 4:
        return findings
    months = sorted(buckets)
    series = np.asarray([buckets[m] for m in months], dtype=float)
    index = np.arange(len(series), dtype=float)
    slope, intercept = np.polyfit(index, series, 1)
    fitted = intercept + slope * index
    residual = series - fitted
    total_variance = float(np.var(series))
    explained = 1 - float(np.var(residual)) / total_variance if total_variance > 0 else 0.0
    average = float(np.mean(series))
    monthly_change = float(slope) / average if average else 0.0
    if abs(monthly_change) < 0.01 or explained < 0.25:
        return findings
    direction = "rising" if slope > 0 else "falling"
    direction_ar = "صاعد" if slope > 0 else "هابط"
    findings.append(
        _finding(
            f"trend.{measure}.{date_column}",
            "trend",
            "high" if abs(monthly_change) > 0.05 else "medium",
            "medium" if explained < 0.6 else "high",
            (
                f"{measure} is {direction} over time",
                f"{measure} في مسار {direction_ar} عبر الزمن",
            ),
            (
                f"Across {len(months)} months from {months[0]} to {months[-1]}, monthly "
                f"{measure} changes by {slope:+,.1f} on average, which is "
                f"{monthly_change:+.1%} of the {average:,.1f} monthly mean. A straight line "
                f"explains {explained:.0%} of the movement.",
                f"عبر {ar.count(len(months), ar.MONTH)} من {months[0]} إلى {months[-1]}، "
                f"يتغيّر {measure} الشهري بمقدار {slope:+,.1f} وسطيًا، أي "
                f"{monthly_change:+.1%} من المتوسط الشهري البالغ {average:,.1f}. يفسّر خط "
                f"مستقيم {explained:.0%} من الحركة.",
            ),
            (
                f"Continued at this rate the monthly figure moves by roughly "
                f"{monthly_change * 12:+.0%} over a year. "
                + (
                    "The line fits loosely, so treat the direction as indicative and the "
                    "rate as uncertain."
                    if explained < 0.6
                    else "The movement is steady rather than driven by one or two months."
                ),
                f"باستمرار هذا المعدل يتحرك الرقم الشهري نحو {monthly_change * 12:+.0%} خلال "
                "سنة. "
                + (
                    "ملاءمة الخط ضعيفة، فاعتبر الاتجاه استرشاديًا والمعدل غير مؤكد."
                    if explained < 0.6
                    else "الحركة مطّردة وليست ناتجة عن شهر أو شهرين."
                ),
            ),
            (
                f"Put {measure} on a monthly review with a stated target, and run a formal "
                "forecast before committing capacity or budget to the implied path.",
                f"ضع {measure} ضمن مراجعة شهرية بهدف معلن، وشغّل توقعًا رسميًا قبل التزام "
                "أي طاقة أو موازنة بالمسار المتضمَّن.",
            ),
            (
                "A fitted line describes the past only. It carries no seasonality, no "
                "uncertainty band, and no assurance that the pattern continues.",
                "يصف الخط الملائم الماضي فقط. لا يحمل موسمية ولا نطاق عدم يقين ولا ضمانًا "
                "باستمرار النمط.",
            ),
            {
                "measure": measure,
                "date_column": date_column,
                "months": len(months),
                "first_month": months[0],
                "last_month": months[-1],
                "slope_per_month": round(float(slope), 4),
                "relative_change_per_month": round(monthly_change, 4),
                "r_squared": round(explained, 4),
                "series": [{"period": m, "value": round(buckets[m], 4)} for m in months],
            },
            {"type": "line", "measure": measure, "date_column": date_column},
        )
    )
    return findings


def _segment_findings(rows: list[dict[str, Any]], profile: dict[str, Any]) -> list[dict[str, Any]]:
    """Which segment differs enough from the rest to be worth a manager's attention."""
    findings: list[dict[str, Any]] = []
    if len(rows) < MIN_ROWS_FOR_INFERENCE:
        return findings
    measures = _numeric_columns(rows, profile)
    dimensions = _categorical_columns(profile, len(rows))
    if not measures or not dimensions:
        return findings
    measure = measures[0]
    for dimension in dimensions[:3]:
        grouped: dict[str, list[float]] = defaultdict(list)
        for row in rows:
            value, _ = coerce_number(row.get(measure))
            if value is not None:
                grouped[str(row.get(dimension))].append(value)
        groups = {k: v for k, v in grouped.items() if len(v) >= 8}
        if len(groups) < 2:
            continue
        overall = float(np.mean([v for values in groups.values() for v in values]))
        spread = float(np.std([v for values in groups.values() for v in values]))
        if spread <= 0:
            continue
        scored = sorted(
            ((key, float(np.mean(values)), len(values)) for key, values in groups.items()),
            key=lambda item: -abs(item[1] - overall),
        )
        key, mean, size = scored[0]
        gap = (mean - overall) / overall if overall else 0.0
        # Standard error of the segment mean, so a small noisy group is not "a finding".
        standard_error = spread / math.sqrt(size)
        if abs(mean - overall) < 2 * standard_error or abs(gap) < 0.15:
            continue
        findings.append(
            _finding(
                f"segment.{dimension}.{measure}",
                "segment",
                "high" if abs(gap) > 0.4 else "medium",
                "high" if abs(mean - overall) > 3 * standard_error else "medium",
                (
                    f"{key} stands apart on {measure}",
                    f"تنفرد {key} في {measure}",
                ),
                (
                    f"Average {measure} for {dimension} = {key!r} is {mean:,.2f} across "
                    f"{size:,} rows, against {overall:,.2f} overall — a gap of {gap:+.0%}. "
                    f"The gap is {abs(mean - overall) / standard_error:.1f} standard errors "
                    "of that segment's mean.",
                    f"متوسط {measure} عند {dimension} = {key!r} هو {mean:,.2f} عبر "
                    f"{size:,} صف، مقابل {overall:,.2f} إجمالًا — بفارق {gap:+.0%}. "
                    f"يعادل الفارق {abs(mean - overall) / standard_error:.1f} من الخطأ "
                    "المعياري لمتوسط هذه الشريحة.",
                ),
                (
                    f"A gap this size is unlikely to be sampling noise. Either {key!r} "
                    "operates differently, serves a different mix, or is recorded "
                    "differently from the rest.",
                    f"فارق بهذا الحجم يصعب أن يكون ضجيج عيّنة. إما أن {key!r} تعمل بطريقة "
                    "مختلفة، أو تخدم مزيجًا مختلفًا، أو تُسجَّل بشكل مختلف عن البقية.",
                ),
                (
                    f"Ask the {key!r} owner what differs operationally before treating the "
                    "gap as performance. If the practice is better, document and spread it; "
                    "if it is a recording difference, fix the definition.",
                    f"اسأل مالك {key!r} عمّا يختلف تشغيليًا قبل اعتبار الفارق أداءً. إن كانت "
                    "الممارسة أفضل فوثّقها وعمّمها، وإن كان اختلاف تسجيل فصحّح التعريف.",
                ),
                (
                    "This compares one segment against the pooled rest without holding any "
                    "other factor constant. A different customer or product mix can produce "
                    "the same gap.",
                    "تقارن هذه النتيجة شريحة واحدة بالبقية مجتمعة دون تثبيت أي عامل آخر. "
                    "قد ينتج المزيج المختلف للعملاء أو المنتجات الفارق نفسه.",
                ),
                {
                    "dimension": dimension,
                    "measure": measure,
                    "segment": key,
                    "segment_mean": round(mean, 4),
                    "overall_mean": round(overall, 4),
                    "relative_gap": round(gap, 4),
                    "rows": size,
                    "standard_errors": round(abs(mean - overall) / standard_error, 2),
                    "all_segments": [
                        {"label": k, "mean": round(m, 4), "rows": n} for k, m, n in scored[:10]
                    ],
                },
                {"type": "bar", "dimension": dimension, "measure": measure},
            )
        )
    return findings


def analyze_dataset(
    rows: list[dict[str, Any]], columns: list[str], profile: dict[str, Any]
) -> dict[str, Any]:
    """Produce the full finding set for one dataset version."""
    findings: list[dict[str, Any]] = []
    producers: tuple[Callable[..., list[dict[str, Any]]], ...] = (
        _quality_findings,
        _trend_findings,
        _concentration_findings,
        _segment_findings,
        _missingness_findings,
        _distribution_findings,
        _relationship_findings,
    )
    for producer in producers:
        try:
            findings.extend(
                producer(rows, profile) if producer is not _quality_findings else producer(profile)
            )
        except (ValueError, KeyError, ZeroDivisionError, IndexError, TypeError) as error:
            # One unhealthy column must not suppress every other finding.
            findings.append(
                _finding(
                    f"engine.error.{producer.__name__}",
                    "engine",
                    "low",
                    "high",
                    ("An analysis pass could not complete", "تعذّر إكمال أحد مسارات التحليل"),
                    (
                        f"{producer.__name__} stopped with {type(error).__name__}.",
                        f"توقف {producer.__name__} بخطأ {type(error).__name__}.",
                    ),
                    (
                        "The remaining findings are unaffected; this pass is simply absent.",
                        "بقية النتائج غير متأثرة؛ هذا المسار غائب فقط.",
                    ),
                    (
                        "Report the dataset shape so the pass can be repaired.",
                        "أبلغ عن شكل البيانات لإصلاح هذا المسار.",
                    ),
                    (
                        "Absence of a finding here is not evidence that none exists.",
                        "غياب نتيجة هنا ليس دليلًا على عدم وجودها.",
                    ),
                    {"pass": producer.__name__, "error": type(error).__name__},
                )
            )
    findings.sort(key=lambda f: (SEVERITY_ORDER.get(f["severity"], 9), f["id"]))
    counts = Counter(f["severity"] for f in findings)
    return {
        "findings": findings,
        "counts": dict(counts),
        "row_count": len(rows),
        "column_count": len(columns),
        "method": "deterministic_statistical_rules_no_model_inference",
        "reproducible": True,
        "disclosure": {
            "en": (
                "Observations are arithmetic over the rows you supplied and can be "
                "reproduced exactly. Interpretations and recommendations are analyst "
                "judgement applied to those numbers, and are open to challenge."
            ),
            "ar": (
                "الملاحظات عمليات حسابية على الصفوف التي زوّدتنا بها ويمكن إعادة إنتاجها "
                "تمامًا. أما التفسيرات والتوصيات فهي اجتهاد تحليلي مبني على تلك الأرقام "
                "وقابل للنقاش."
            ),
        },
    }
