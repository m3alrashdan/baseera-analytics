"""The quality reviewer: nothing ships unchallenged.

Two jobs:

``review``          Re-grade each finding's confidence against the standards a senior
                    reviewer applies: sample size, statistical significance after
                    correction, effect size, forecast skill versus a naive benchmark,
                    data quality, and the difference between association and cause.
``verify_numbers``  Extract every figure a language model wrote and check it against
                    the numbers the deterministic tools actually produced. A figure that
                    cannot be traced to evidence is reported, never silently published.
"""

from __future__ import annotations

import math
import re
from typing import Any

from .common import bi, confidence_label

ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹٫٬", "01234567890123456789.,")
NUMBER = re.compile(
    r"(?<![\w.])([-+−]?\d{1,3}(?:,\d{3})+(?:\.\d+)?|[-+−]?\d+(?:\.\d+)?)\s*"
    r"(%|٪|k\b|K\b|m\b|M\b|bn\b|B\b|ألف|مليون|مليار)?",
)
CAUSAL_PHRASES = (
    r"\bcauses?\b",
    r"\bcaused\b",
    r"\bleads? to\b",
    r"\bresults? in\b",
    r"\bbecause of\b",
    "يسبب",
    "تسبب",
    "يؤدي إلى",
    "أدى إلى",
    "بسبب",
)


def collect_numbers(value: Any, bag: set[float] | None = None) -> set[float]:
    """Every numeric leaf in a result tree."""

    bag = set() if bag is None else bag
    if isinstance(value, bool):
        return bag
    if isinstance(value, int | float):
        if not (isinstance(value, float) and (math.isnan(value) or math.isinf(value))):
            bag.add(float(value))
    elif isinstance(value, dict):
        for item in value.values():
            collect_numbers(item, bag)
    elif isinstance(value, list | tuple):
        for item in value:
            collect_numbers(item, bag)
    elif isinstance(value, str):
        # Numbers embedded in deterministic summaries count as evidence too.
        for number, suffix in _extract(value):
            bag.add(_scaled(number, suffix))
    return bag


def _extract(text: str) -> list[tuple[float, str]]:
    normalized = text.translate(ARABIC_DIGITS).replace("−", "-")
    found = []
    for match in NUMBER.finditer(normalized):
        raw = match.group(1).replace(",", "").replace("+", "")
        try:
            found.append((float(raw), (match.group(2) or "").strip()))
        except ValueError:
            continue
    return found


def _scaled(number: float, suffix: str) -> float:
    scale = {
        "k": 1e3,
        "K": 1e3,
        "ألف": 1e3,
        "m": 1e6,
        "M": 1e6,
        "مليون": 1e6,
        "bn": 1e9,
        "B": 1e9,
        "مليار": 1e9,
    }.get(suffix, 1.0)
    return number * scale


def _matches(candidate: float, evidence: set[float], percent: bool) -> bool:
    targets = [candidate]
    if percent:
        targets.append(candidate / 100)
    for target in targets:
        tolerance = max(abs(target) * 0.02, 0.051 if abs(target) < 10 else 0.5)
        for known in evidence:
            if abs(known - target) <= tolerance:
                return True
            # Percentage points written from a ratio (0.123 -> 12.3) or a rate.
            if percent is False and abs(known * 100 - target) <= tolerance:
                return True
    return False


def verify_numbers(
    text: str, evidence: set[float], ignore: set[float] | None = None
) -> dict[str, Any]:
    ignore = ignore or set()
    checked = 0
    unverified: list[str] = []
    for number, suffix in _extract(text):
        percent = suffix in {"%", "٪"}
        value = _scaled(number, suffix)
        # Years, small ordinals and list numbering are language, not claims.
        if (
            not percent
            and not suffix
            and (
                (1900 <= value <= 2100 and float(value).is_integer())
                or (abs(value) <= 12 and float(value).is_integer())
            )
        ):
            continue
        if value in ignore:
            continue
        checked += 1
        if not _matches(value, evidence, percent):
            label = f"{number:g}{suffix}"
            if label not in unverified:
                unverified.append(label)
    causal = [p for p in CAUSAL_PHRASES if re.search(p, text, flags=re.IGNORECASE)]
    return {
        "numbers_checked": checked,
        "unverified": unverified[:20],
        "verified_share": (checked - len(unverified)) / checked if checked else 1.0,
        "causal_language": causal,
        "passed": not unverified,
    }


# ----------------------------------------------------------------------------- review
def review(findings: list[dict[str, Any]], health: dict[str, Any] | None) -> list[dict[str, Any]]:
    """Re-grade confidence and attach the reviewer's caveats to each finding."""

    quality = (health or {}).get("score")
    for finding in findings:
        score = float(finding.get("confidence_score", 0.7))
        caveats: list[dict[str, str]] = list(finding.get("caveats", []))
        evidence = finding.get("evidence", {})
        n = evidence.get("n")
        if isinstance(n, int | float) and n < 30:
            score -= 0.25
            caveats.append(
                bi(
                    f"Based on only {int(n)} observations.",
                    f"مبني على {int(n)} ملاحظة فقط.",
                )
            )
        p_value = evidence.get("p_value")
        if isinstance(p_value, int | float) and p_value >= 0.05:
            score -= 0.25
            caveats.append(
                bi(
                    "Not statistically significant; treat as a lead, not a conclusion.",
                    "غير دال إحصائيًا؛ عامله كمؤشر أولي لا كاستنتاج.",
                )
            )
        magnitude = evidence.get("effect_magnitude")
        if magnitude in {"negligible", "small"}:
            score -= 0.1 if magnitude == "small" else 0.2
            caveats.append(
                bi(
                    f"The effect size is {magnitude}; statistically real does not mean material.",
                    "حجم الأثر صغير؛ الدلالة الإحصائية لا تعني أهمية عملية.",
                )
            )
        if finding.get("kind") == "forecast":
            if evidence.get("beats_benchmark") is False:
                score -= 0.3
                caveats.append(
                    bi(
                        "The model did not beat a naive benchmark on the holdout; use the forecast as directional only.",
                        "لم يتفوق النموذج على المعيار البسيط في فترة الاختبار؛ استخدم التنبؤ كمؤشر اتجاه فقط.",
                    )
                )
            wape = evidence.get("wape")
            if isinstance(wape, int | float) and wape > 0.3:
                score -= 0.15
                caveats.append(
                    bi(
                        f"Holdout error (WAPE) is {wape * 100:.0f}%; plan with the interval, not the point.",
                        f"خطأ فترة الاختبار (WAPE) يبلغ {wape * 100:.0f}%؛ خطط وفق فاصل الثقة لا القيمة المفردة.",
                    )
                )
        if finding.get("kind") in {"drivers", "correlation", "what_if"}:
            caveats.append(
                bi(
                    "Association, not proven causation. Confirm with a controlled test before scaling.",
                    "ارتباط لا سببية مثبتة. أكّد بتجربة مضبوطة قبل التوسع.",
                )
            )
        if (
            isinstance(quality, int | float)
            and quality < 70
            and finding.get("kind") != "data_quality"
        ):
            score -= 0.1
            caveats.append(
                bi(
                    f"Data quality score is {quality:.0f}/100; figures may shift after cleaning.",
                    f"درجة جودة البيانات {quality:.0f}/100؛ قد تتغير الأرقام بعد التنظيف.",
                )
            )
        score = max(0.1, min(0.95, score))
        finding["confidence_score"] = round(score, 2)
        finding["confidence"] = confidence_label(score)
        finding["caveats"] = _unique(caveats)
    return findings


def _unique(items: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[str] = set()
    result = []
    for item in items:
        key = item.get("en", "")
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result
