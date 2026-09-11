"""Deterministic deep column profiling.

The profile is the analyst's first read of a file: what each column really holds,
how badly it is malformed, and which repairs are worth proposing. Everything here
is pure and reproducible so the same upload always yields the same findings.
"""

from __future__ import annotations

import math
import re
import statistics
import unicodedata
from collections import Counter
from datetime import date, datetime
from typing import Any

IDENTIFIER_NAMES = {"id", "identifier", "order_id", "customer_id", "source_id"}

ARABIC_INDIC = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
# Single-character symbols only. The multi-character currency abbreviations live in the
# alternation below: several contain a literal "." which, inside a character class, would
# silently strip every decimal point in the file.
CURRENCY_SYMBOLS = "$€£¥₹﷼"
CURRENCY_WORDS = (
    "د.إ",
    "ر.س",
    "د.ك",
    "د.ب",
    "ر.ق",
    "ج.م",
    "د.أ",
    "ل.س",
    "د.ع",
    "JOD",
    "SAR",
    "AED",
    "USD",
    "EUR",
    "GBP",
    "KWD",
    "QAR",
    "EGP",
    "OMR",
    "BHD",
    "دينار",
    "ريال",
    "درهم",
    "جنيه",
    "دولار",
    "يورو",
)
# Thousands grouping: ASCII comma, apostrophe, underscore, NBSP, narrow NBSP, Arabic thousands.
_NUMBER_NOISE = re.compile("[\\s\u00a0\u202f\u066c,'_]")
_ARABIC_DECIMAL = "\u066b"
_CURRENCY_STRIP = re.compile(
    "|".join([*(re.escape(word) for word in CURRENCY_WORDS), f"[{re.escape(CURRENCY_SYMBOLS)}]"]),
    re.I,
)
_PERCENT = re.compile(r"^\s*-?[\d.,\s]+\s*%\s*$")
_PARENS_NEGATIVE = re.compile(r"^\s*\((.+)\)\s*$")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$")
_PHONE = re.compile(r"^[+()\d][\d\s()+\-]{6,}$")
_BOOLEAN_WORDS = {
    "true": True,
    "false": False,
    "yes": True,
    "no": False,
    "y": True,
    "n": False,
    "1": True,
    "0": False,
    "نعم": True,
    "لا": False,
    "صح": True,
    "خطأ": False,
}

# Ordered most-specific first; the first pattern that parses every sampled value wins.
DATE_PATTERNS: tuple[tuple[str, str], ...] = (
    ("%Y-%m-%dT%H:%M:%S", "iso_datetime"),
    ("%Y-%m-%d %H:%M:%S", "iso_datetime_space"),
    ("%Y-%m-%d", "iso_date"),
    ("%Y/%m/%d", "ymd_slash"),
    ("%d-%m-%Y", "dmy_dash"),
    ("%m-%d-%Y", "mdy_dash"),
    ("%d/%m/%Y", "dmy_slash"),
    ("%m/%d/%Y", "mdy_slash"),
    ("%d.%m.%Y", "dmy_dot"),
    ("%d %b %Y", "day_month_name"),
    ("%b %d, %Y", "month_name_day"),
)
_SLASH_OR_DASH_DATE = re.compile(r"^\s*(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})\s*$")


def normalize_digits(text: str) -> str:
    """Map Arabic-Indic digits onto ASCII and the Arabic decimal mark onto a period."""
    return text.translate(ARABIC_INDIC).replace(_ARABIC_DECIMAL, ".")


def as_number(value: Any) -> float | None:
    """Strict numeric read: only what ``float()`` already accepts."""
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _separator_convention(text: str) -> tuple[str, str | None]:
    """Decide which of "." and "," groups digits and which one is the decimal mark.

    A file may use either convention and sometimes both appear in one cell. The
    rightmost separator is the decimal mark when both are present; a lone separator
    followed by exactly three digits, or repeated, is grouping.
    """
    has_dot, has_comma = "." in text, "," in text
    if has_dot and has_comma:
        if text.rfind(".") > text.rfind(","):
            return text.replace(",", ""), "group_separator_comma"
        return text.replace(".", "").replace(",", "."), "decimal_comma"
    if has_comma:
        parts = text.split(",")
        if len(parts) > 2 or (len(parts) == 2 and len(parts[1]) == 3):
            return text.replace(",", ""), "group_separator_comma"
        return text.replace(",", "."), "decimal_comma"
    if has_dot and text.count(".") > 1:
        return text.replace(".", ""), "group_separator_period"
    return text, None


def coerce_number(value: Any) -> tuple[float | None, str | None]:
    """Tolerant numeric read.

    Returns the value plus the notation that had to be repaired, so the cleaning
    log can state exactly what was reinterpreted rather than silently rewriting it.
    """
    if value is None or isinstance(value, bool):
        return None, None
    if isinstance(value, (int, float)):
        number = float(value)
        return (number, None) if math.isfinite(number) else (None, None)
    if not isinstance(value, str):
        return None, None
    text = normalize_digits(value.strip())
    if not text:
        return None, None
    notes: list[str] = []
    percent = bool(_PERCENT.match(text))
    if percent:
        text = text.replace("%", "").strip()
        notes.append("percent_sign")
    stripped = _CURRENCY_STRIP.sub("", text).strip()
    if stripped != text:
        notes.append("currency_symbol")
        text = stripped
    negative = False
    parens = _PARENS_NEGATIVE.match(text)
    if parens:
        text = parens.group(1).strip()
        negative = True
        notes.append("parenthesis_negative")
    if text.endswith("-"):
        text = text[:-1].strip()
        negative = True
        notes.append("trailing_minus")
    text, convention = _separator_convention(text)
    if convention:
        notes.append(convention)
    condensed = _NUMBER_NOISE.sub("", text)
    if condensed != text:
        notes.append("embedded_whitespace")
    try:
        number = float(condensed)
    except (TypeError, ValueError):
        return None, None
    if not math.isfinite(number):
        return None, None
    if negative:
        number = -abs(number)
    if percent:
        number = number / 100.0
    return number, ("+".join(notes) if notes else None)


def coerce_boolean(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return _BOOLEAN_WORDS.get(value.strip().casefold())
    return None


def classify_date_values(values: list[Any], sample: int = 2000) -> dict[str, Any]:
    """Classify each value against every known date format.

    A column that mixes conventions is a worse problem than one that is uniformly
    ambiguous, because no single parse can be correct for all of it. Both are counted.
    """
    texts = [normalize_digits(str(v).strip()) for v in values[:sample] if v not in (None, "")]
    per_format: Counter[str] = Counter()
    unmatched: list[str] = []
    ambiguous_cells = 0
    for text in texts:
        matched: str | None = None
        for pattern, name in DATE_PATTERNS:
            try:
                datetime.strptime(text, pattern)
            except ValueError:
                continue
            matched = name
            break
        if matched is None:
            if len(unmatched) < 5:
                unmatched.append(text)
            continue
        per_format[matched] += 1
        # Both components <= 12: day-first and month-first both parse, to different dates.
        match = _SLASH_OR_DASH_DATE.match(text)
        if match and int(match.group(1)) <= 12 and int(match.group(2)) <= 12:
            ambiguous_cells += 1
    return {
        "considered": len(texts),
        "per_format": dict(per_format.most_common()),
        "matched": sum(per_format.values()),
        "unmatched": len(texts) - sum(per_format.values()),
        "unmatched_examples": unmatched,
        "distinct_formats": len(per_format),
        "mixed_formats": len(per_format) > 1,
        "ambiguous_cells": ambiguous_cells,
    }


def detect_date_format(values: list[Any], sample: int = 400) -> tuple[str | None, str | None, bool]:
    """Pick the single format that parses the most sampled values.

    The third element reports day/month ambiguity: a slash date where some value has a
    first component above 12 proves day-first, otherwise the reading is a guess and the
    caller must ask rather than assume.
    """
    texts = [normalize_digits(str(v).strip()) for v in values[:sample] if v not in (None, "")]
    if not texts:
        return None, None, False
    best: tuple[int, str, str] | None = None
    for pattern, name in DATE_PATTERNS:
        parsed = 0
        for text in texts:
            try:
                datetime.strptime(text, pattern)
            except ValueError:
                continue
            parsed += 1
        if parsed and (best is None or parsed > best[0]):
            best = (parsed, pattern, name)
    if best is None or best[0] < max(1, int(len(texts) * 0.6)):
        return None, None, False
    ambiguous = False
    if best[2] in {"dmy_slash", "mdy_slash", "dmy_dash", "mdy_dash", "dmy_dot"}:
        firsts, seconds = [], []
        for text in texts:
            match = _SLASH_OR_DASH_DATE.match(text)
            if match:
                firsts.append(int(match.group(1)))
                seconds.append(int(match.group(2)))
        ambiguous = bool(firsts) and max(firsts) <= 12 and max(seconds or [0]) <= 12
    return best[1], best[2], ambiguous


def parse_date_value(value: Any, pattern: str) -> str | None:
    if value in (None, ""):
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    try:
        parsed = datetime.strptime(normalize_digits(str(value).strip()), pattern)
    except (ValueError, TypeError):
        return None
    return parsed.date().isoformat() if "%H" not in pattern else parsed.isoformat()


def _present(values: list[Any]) -> list[Any]:
    return [v for v in values if v is not None and (not isinstance(v, str) or v.strip() != "")]


def _semantic_type(name: str, present: list[Any]) -> tuple[str, dict[str, Any]]:
    """Classify a column and report how confidently, with the evidence."""
    lowered = name.strip().casefold()
    total = len(present)
    if not total:
        return "empty", {"reason": "no_present_values"}
    if lowered in IDENTIFIER_NAMES or lowered.endswith("_id") or lowered == "id":
        return "identifier", {"reason": "name_matches_identifier_convention"}

    strict = sum(as_number(v) is not None for v in present)
    tolerant = sum(coerce_number(v)[0] is not None for v in present)
    booleans = sum(coerce_boolean(v) is not None for v in present)
    emails = sum(bool(_EMAIL.match(str(v).strip())) for v in present)
    phones = sum(
        bool(_PHONE.match(str(v).strip())) and not _EMAIL.match(str(v).strip()) for v in present
    )
    pattern, _fmt, _amb = detect_date_format(present)
    dates = 0
    if pattern:
        dates = sum(parse_date_value(v, pattern) is not None for v in present)

    if booleans == total and len({coerce_boolean(v) for v in present}) <= 2:
        return "boolean", {"reason": "every_value_is_a_boolean_token"}
    if emails >= total * 0.9:
        return "email", {"match_rate": round(emails / total, 4)}
    if dates >= total * 0.9:
        return "date", {"match_rate": round(dates / total, 4), "format": _fmt}
    if strict == total:
        return "number", {"strict_parse_rate": 1.0}
    if tolerant >= total * 0.9:
        # Numbers hiding behind formatting; the repair is a cast, not a retype.
        return "number_text", {
            "strict_parse_rate": round(strict / total, 4),
            "tolerant_parse_rate": round(tolerant / total, 4),
        }
    if phones >= total * 0.9:
        return "phone", {"match_rate": round(phones / total, 4)}
    distinct = len({str(v) for v in present})
    if distinct <= max(2, min(50, total // 5)) and distinct < total:
        return "categorical", {"distinct": distinct}
    return "text", {"distinct": distinct}


LEGACY_TYPE = {
    "identifier": "identifier",
    "number": "number",
    "number_text": "text",
    "date": "date_or_datetime",
    "boolean": "boolean",
    "categorical": "text",
    "email": "text",
    "phone": "text",
    "text": "text",
    "empty": "text",
}


def _numeric_stats(numbers: list[float]) -> dict[str, Any]:
    if not numbers:
        return {}
    ordered = sorted(numbers)
    count = len(ordered)

    def quantile(q: float) -> float:
        if count == 1:
            return ordered[0]
        position = q * (count - 1)
        low = math.floor(position)
        high = math.ceil(position)
        return ordered[low] + (ordered[high] - ordered[low]) * (position - low)

    q1, q3 = quantile(0.25), quantile(0.75)
    iqr = q3 - q1
    lower_fence, upper_fence = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    outliers = [v for v in ordered if v < lower_fence or v > upper_fence] if iqr > 0 else []
    mean = statistics.fmean(ordered)
    deviation = statistics.pstdev(ordered) if count > 1 else 0.0
    return {
        "min": round(ordered[0], 6),
        "max": round(ordered[-1], 6),
        "mean": round(mean, 6),
        "median": round(quantile(0.5), 6),
        "std_dev": round(deviation, 6),
        "p25": round(q1, 6),
        "p75": round(q3, 6),
        "p95": round(quantile(0.95), 6),
        "sum": round(math.fsum(ordered), 6),
        "zero_count": sum(1 for v in ordered if v == 0),
        "negative_count": sum(1 for v in ordered if v < 0),
        "coefficient_of_variation": round(deviation / abs(mean), 4) if mean else None,
        "skew_direction": (
            "right"
            if quantile(0.5) < mean - deviation * 0.1
            else "left"
            if quantile(0.5) > mean + deviation * 0.1
            else "symmetric"
        ),
        "outlier_bounds": {"lower": round(lower_fence, 6), "upper": round(upper_fence, 6)}
        if iqr > 0
        else None,
        "outlier_count": len(outliers),
        "outlier_examples": [round(v, 6) for v in outliers[:5]],
    }


def _text_anomalies(present: list[Any]) -> dict[str, Any]:
    strings = [v for v in present if isinstance(v, str)]
    if not strings:
        return {}
    untrimmed = sum(1 for v in strings if v != v.strip())
    doubled = sum(1 for v in strings if re.search(r"\s{2,}", v.strip()))
    folded: dict[str, set[str]] = {}
    for value in strings:
        folded.setdefault(value.strip().casefold(), set()).add(value.strip())
    case_variants = {k: sorted(v) for k, v in folded.items() if len(v) > 1}
    control = sum(
        1 for v in strings if any(unicodedata.category(ch) == "Cc" or ch in "​‎‏﻿" for ch in v)
    )
    lengths = [len(v.strip()) for v in strings]
    return {
        "untrimmed_count": untrimmed,
        "internal_double_space_count": doubled,
        "case_variant_groups": len(case_variants),
        "case_variant_examples": [
            {"normalized": k, "variants": v} for k, v in list(case_variants.items())[:5]
        ],
        "control_or_invisible_character_count": control,
        "min_length": min(lengths),
        "max_length": max(lengths),
    }


def profile_column(name: str, values: list[Any]) -> dict[str, Any]:
    present = _present(values)
    total = len(values)
    missing = total - len(present)
    semantic, evidence = _semantic_type(name, present)
    distinct_keys = {str(v) for v in present}
    frequencies = Counter(str(v) for v in present)
    profile: dict[str, Any] = {
        # Legacy keys, kept stable for stored profiles and existing consumers.
        "inferred_type": LEGACY_TYPE[semantic],
        "null_count": missing,
        "distinct_count": len(distinct_keys),
        "examples": [str(v) for v in present[:5]],
        # Analyst detail.
        "semantic_type": semantic,
        "type_evidence": evidence,
        "present_count": len(present),
        "missing_rate": round(missing / total, 6) if total else 0.0,
        "distinct_rate": round(len(distinct_keys) / len(present), 6) if present else 0.0,
        "is_constant": len(distinct_keys) == 1 and len(present) > 1,
        "is_unique": bool(present) and len(distinct_keys) == len(present),
        "top_values": [
            {"value": value, "count": count, "share": round(count / len(present), 6)}
            for value, count in frequencies.most_common(10)
        ]
        if present
        else [],
    }

    numeric_candidate = semantic in {"number", "number_text"}
    if semantic == "identifier" and present:
        # An identifier that happens to be numeric is worth summarising, but "ORD-00001"
        # failing to parse as a number is not a defect — the column was never numeric.
        numeric_candidate = (
            sum(coerce_number(v)[0] is not None for v in present) >= len(present) * 0.9
        )
    if numeric_candidate:
        strict = [as_number(v) for v in present]
        tolerant = [coerce_number(v) for v in present]
        numbers = [n for n, _ in tolerant if n is not None]
        repairs = Counter(note for _, note in tolerant if note)
        profile["numeric"] = _numeric_stats(numbers)
        profile["numeric_parse"] = {
            "strict_parsable": sum(v is not None for v in strict),
            "tolerant_parsable": len(numbers),
            "unparsable": len(present) - len(numbers),
            "repairs_required": dict(repairs),
            "unparsable_examples": [
                str(v) for v, (n, _) in zip(present, tolerant, strict=True) if n is None
            ][:5],
        }
    if semantic in {"date", "text", "categorical", "identifier"}:
        pattern, fmt, ambiguous = detect_date_format(present)
        if pattern:
            classification = classify_date_values(present)
            parsed = [parse_date_value(v, pattern) for v in present]
            ordered = sorted(v for v in parsed if v)
            profile["temporal"] = {
                "detected_format": fmt,
                "strptime_pattern": pattern,
                "parsable": sum(v is not None for v in parsed),
                "unparsable": sum(v is None for v in parsed),
                "day_month_ambiguous": ambiguous or classification["ambiguous_cells"] > 0,
                "ambiguous_cells": classification["ambiguous_cells"],
                "mixed_formats": classification["mixed_formats"],
                "formats_found": classification["per_format"],
                "values_matching_no_known_format": classification["unmatched"],
                "unmatched_examples": classification["unmatched_examples"],
                "min": ordered[0] if ordered else None,
                "max": ordered[-1] if ordered else None,
            }
    if semantic in {"text", "categorical", "email", "phone", "identifier", "number_text"}:
        anomalies = _text_anomalies(present)
        if anomalies:
            profile["text"] = anomalies
    return profile


def _suggest(column: str, profile: dict[str, Any]) -> list[dict[str, Any]]:
    """Propose the repairs a reviewer should consider, never apply them."""
    suggestions: list[dict[str, Any]] = []
    text = profile.get("text", {})
    numeric_parse = profile.get("numeric_parse", {})
    temporal = profile.get("temporal", {})
    if text.get("untrimmed_count") or text.get("control_or_invisible_character_count"):
        suggestions.append(
            {
                "step": {"kind": "trim_whitespace", "columns": [column]},
                "reason": "leading_or_trailing_whitespace",
                "affected_cells": int(text.get("untrimmed_count", 0))
                + int(text.get("control_or_invisible_character_count", 0)),
            }
        )
    if text.get("internal_double_space_count"):
        suggestions.append(
            {
                "step": {"kind": "collapse_whitespace", "columns": [column]},
                "reason": "repeated_internal_spaces",
                "affected_cells": int(text["internal_double_space_count"]),
            }
        )
    if text.get("case_variant_groups"):
        suggestions.append(
            {
                "step": {"kind": "standardize_case", "columns": [column], "case": "title"},
                "reason": "same_value_recorded_in_several_letter_cases",
                "affected_cells": int(text["case_variant_groups"]),
            }
        )
    if profile.get("semantic_type") == "number_text" and numeric_parse.get("tolerant_parsable"):
        suggestions.append(
            {
                "step": {"kind": "cast_number", "columns": [column]},
                "reason": "numbers_stored_as_text_with_"
                + (",".join(numeric_parse.get("repairs_required", {})) or "mixed_notation"),
                "affected_cells": int(numeric_parse["tolerant_parsable"]),
            }
        )
    if temporal.get("mixed_formats"):
        suggestions.append(
            {
                "step": {"kind": "parse_date", "columns": [column]},
                "reason": "column_mixes_"
                + str(temporal.get("formats_found", {}))
                + "_so_one_parse_cannot_be_correct_for_every_cell",
                "affected_cells": int(temporal.get("parsable", 0)),
                "requires_human_decision": True,
            }
        )
    elif temporal.get("detected_format") and temporal["detected_format"] != "iso_date":
        suggestions.append(
            {
                "step": {
                    "kind": "parse_date",
                    "columns": [column],
                    "format": temporal["strptime_pattern"],
                },
                "reason": "dates_are_not_stored_in_iso_8601"
                + (
                    "_and_day_month_order_is_ambiguous"
                    if temporal.get("day_month_ambiguous")
                    else ""
                ),
                "affected_cells": int(temporal.get("parsable", 0)),
                "requires_human_decision": bool(temporal.get("day_month_ambiguous")),
            }
        )
    if profile.get("is_constant"):
        suggestions.append(
            {
                "step": {"kind": "drop_column", "columns": [column]},
                "reason": "column_holds_a_single_repeated_value_and_carries_no_signal",
                "affected_cells": int(profile.get("present_count", 0)),
            }
        )
    return suggestions


def _quality_score(
    rows: int,
    columns: list[str],
    profiles: dict[str, Any],
    duplicate_rows: int,
    duplicate_keys: int,
) -> dict[str, Any]:
    """Five weighted dimensions, each a plain ratio so the number can be defended."""
    if not rows or not columns:
        return {"score": None, "dimensions": {}, "grade": "not_assessable"}
    cells = rows * len(columns)
    missing = sum(int(p["null_count"]) for p in profiles.values())
    completeness = 1 - missing / cells
    uniqueness = 1 - (duplicate_rows + duplicate_keys) / max(rows, 1)
    # Only a column that is meant to hold a number or a date can have an invalid value in
    # it. Counting a text column's non-numeric cells as invalid would mark every ordinary
    # name and code in the file as a defect.
    invalid = sum(
        int(p.get("numeric_parse", {}).get("unparsable", 0))
        for p in profiles.values()
        if p.get("semantic_type") in {"number", "number_text"}
    ) + sum(
        int(p.get("temporal", {}).get("unparsable", 0))
        for p in profiles.values()
        if p.get("semantic_type") == "date"
    )
    validity = 1 - invalid / cells
    inconsistent = sum(
        int(p.get("text", {}).get("untrimmed_count", 0))
        + int(p.get("text", {}).get("internal_double_space_count", 0))
        + int(p.get("text", {}).get("case_variant_groups", 0))
        + int(p.get("text", {}).get("control_or_invisible_character_count", 0))
        for p in profiles.values()
    )
    consistency = 1 - min(1.0, inconsistent / cells)
    outliers = sum(int(p.get("numeric", {}).get("outlier_count", 0)) for p in profiles.values())
    plausibility = 1 - min(1.0, outliers / cells)
    dimensions = {
        "completeness": round(max(0.0, completeness), 4),
        "uniqueness": round(max(0.0, uniqueness), 4),
        "validity": round(max(0.0, validity), 4),
        "consistency": round(max(0.0, consistency), 4),
        "plausibility": round(max(0.0, plausibility), 4),
    }
    weights = {
        "completeness": 0.3,
        "uniqueness": 0.2,
        "validity": 0.25,
        "consistency": 0.15,
        "plausibility": 0.1,
    }
    score = round(sum(dimensions[k] * w for k, w in weights.items()) * 100, 1)
    grade = (
        "ready"
        if score >= 90
        else "usable_with_caveats"
        if score >= 75
        else "repair_required"
        if score >= 50
        else "not_fit_for_reporting"
    )
    return {
        "score": score,
        "dimensions": dimensions,
        "weights": weights,
        "grade": grade,
        "counts": {
            "cells": cells,
            "missing_cells": missing,
            "invalid_cells": invalid,
            "inconsistent_cells": inconsistent,
            "outlier_cells": outliers,
            "duplicate_rows": duplicate_rows,
            "duplicate_business_keys": duplicate_keys,
        },
    }


def profile_dataset(rows: list[dict[str, Any]], columns: list[str]) -> dict[str, Any]:
    profiles = {name: profile_column(name, [row.get(name) for row in rows]) for name in columns}

    business_key = next(
        (
            n
            for n in columns
            if n.strip().casefold() in IDENTIFIER_NAMES or n.strip().casefold().endswith("_id")
        ),
        None,
    )
    duplicate_keys = 0
    duplicate_key_examples: list[str] = []
    if business_key:
        counts = Counter(
            str(row.get(business_key)) for row in rows if row.get(business_key) not in (None, "")
        )
        duplicate_keys = sum(c - 1 for c in counts.values() if c > 1)
        duplicate_key_examples = [k for k, c in counts.most_common(5) if c > 1]

    row_signatures = Counter(tuple(str(row.get(name)) for name in columns) for row in rows)
    duplicate_rows = sum(c - 1 for c in row_signatures.values() if c > 1)

    missing_count = sum(int(p["null_count"]) for p in profiles.values())
    negative_rows = sum(
        any((n := as_number(v)) is not None and n < 0 for v in row.values()) for row in rows
    )
    ambiguous_dates = sum(
        int(p.get("temporal", {}).get("ambiguous_cells", 0)) for p in profiles.values()
    )
    mixed_format_columns = [
        name for name, p in profiles.items() if p.get("temporal", {}).get("mixed_formats")
    ]

    suggestions: list[dict[str, Any]] = []
    for name in columns:
        suggestions.extend(_suggest(name, profiles[name]))
    if duplicate_rows:
        suggestions.insert(
            0,
            {
                "step": {"kind": "deduplicate", "columns": list(columns), "keep": "first"},
                "reason": "identical_rows_repeated_across_every_column",
                "affected_cells": duplicate_rows,
            },
        )
    elif duplicate_keys and business_key:
        suggestions.insert(
            0,
            {
                "step": {"kind": "deduplicate", "columns": [business_key], "keep": "first"},
                "reason": f"business_key_{business_key}_repeats_with_differing_rows",
                "affected_cells": duplicate_keys,
                "requires_human_decision": True,
            },
        )

    return {
        "row_count": len(rows),
        "column_count": len(columns),
        "column_profiles": profiles,
        "quality_issues": {
            "duplicate_business_keys": {
                "count": duplicate_keys,
                "key": business_key,
                "examples": duplicate_key_examples,
            },
            "duplicate_rows": {"count": duplicate_rows},
            "missing_values": {"count": missing_count},
            "legitimate_negative_candidates": {
                "count": negative_rows,
                "guidance": "Review sign semantics; negative values are not removed automatically.",
            },
            "ambiguous_dates": {
                "count": ambiguous_dates,
                "guidance": "Confirm locale before parsing slash-formatted dates.",
            },
            "mixed_date_formats": {
                "count": len(mixed_format_columns),
                "columns": mixed_format_columns,
                "guidance": (
                    "These columns record dates in more than one convention. No single "
                    "parse is correct for all of them; split or repair them at the source."
                ),
            },
        },
        "quality": _quality_score(len(rows), columns, profiles, duplicate_rows, duplicate_keys),
        "business_key": business_key,
        "recommended_steps": suggestions,
        "scope": "full",
    }
