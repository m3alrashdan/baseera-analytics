"""Reviewed, auditable cleaning.

Every step records what it touched and what it could not touch. Nothing is repaired
silently: a cell the engine cannot interpret stays as it is and is reported, because a
reviewer approving a new dataset version has to be able to defend each change later.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from . import arabic as ar
from .errors import AppError
from .profiling import (
    as_number,
    coerce_boolean,
    coerce_number,
    detect_date_format,
    normalize_digits,
    parse_date_value,
    profile_dataset,
)

# A control total that moves by less than this, relative to its own magnitude, is
# treated as floating-point noise rather than a real change to the books.
CONTROL_TOTAL_TOLERANCE = 1e-9

COLUMN_SCOPED = {
    "trim_whitespace",
    "collapse_whitespace",
    "standardize_case",
    "cast_number",
    "cast_boolean",
    "parse_date",
    "replace_missing",
    "fill_missing_statistic",
    "drop_missing_rows",
    "drop_column",
    "rename_column",
    "map_values",
    "clip_outliers",
    "filter_rows",
    "normalize_digits",
    "deduplicate",
    "round_number",
}
STEP_KINDS = COLUMN_SCOPED | {"drop_duplicate_rows"}


def _quantile(ordered: list[float], fraction: float) -> float:
    """Linear-interpolation quantile over an already-sorted list."""
    if not ordered:
        return 0.0
    position = fraction * (len(ordered) - 1)
    low, high = math.floor(position), math.ceil(position)
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


_WHITESPACE_RUN = re.compile(r"\s{2,}")
_INVISIBLE = re.compile(r"[​‎‏﻿­]")


@dataclass(slots=True)
class StepEffect:
    """One entry in the cleaning log."""

    index: int
    kind: str
    columns: list[str]
    options: dict[str, Any] = field(default_factory=dict)
    cells_changed: int = 0
    rows_dropped: int = 0
    cells_unresolved: int = 0
    unresolved_examples: list[str] = field(default_factory=list)
    samples: list[dict[str, Any]] = field(default_factory=list)
    detail: dict[str, Any] = field(default_factory=dict)

    def record(self, column: str, before: Any, after: Any) -> None:
        if len(self.samples) < 5:
            self.samples.append({"column": column, "before": before, "after": after})

    def unresolved(self, value: Any) -> None:
        self.cells_unresolved += 1
        text = str(value)
        if len(self.unresolved_examples) < 5 and text not in self.unresolved_examples:
            self.unresolved_examples.append(text)

    def as_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "kind": self.kind,
            "columns": self.columns,
            "options": self.options,
            "cells_changed": self.cells_changed,
            "rows_dropped": self.rows_dropped,
            "cells_unresolved": self.cells_unresolved,
            "unresolved_examples": self.unresolved_examples,
            "samples": self.samples,
            "detail": self.detail,
            "no_effect": self.cells_changed == 0 and self.rows_dropped == 0,
        }


def _require_columns(step: dict[str, Any], columns: list[str], index: int) -> list[str]:
    selected = step.get("columns", [])
    if not isinstance(selected, list) or any(not isinstance(c, str) for c in selected):
        raise AppError(
            422,
            "invalid_recipe",
            f"Step {index + 1}: columns must be a list of column names.",
            details={"step_index": index, "available_columns": columns},
        )
    unknown = [c for c in selected if c not in columns]
    if unknown:
        raise AppError(
            422,
            "unknown_column",
            f"Step {index + 1} references {', '.join(repr(c) for c in unknown)}, "
            "which is not a column in this dataset version.",
            details={
                "step_index": index,
                "unknown_columns": unknown,
                "available_columns": columns,
                "did_you_mean": {
                    c: [k for k in columns if k.casefold() == c.casefold().strip()] for c in unknown
                },
            },
        )
    if not selected:
        raise AppError(
            422,
            "invalid_recipe",
            f"Step {index + 1} ({step.get('kind')}) needs at least one column. "
            "A step with no column would change nothing.",
            details={"step_index": index, "available_columns": columns},
        )
    return selected


def _apply_step(
    step: dict[str, Any], index: int, rows: list[dict[str, Any]], columns: list[str]
) -> tuple[list[dict[str, Any]], list[str], StepEffect]:
    if not isinstance(step, dict):
        raise AppError(422, "invalid_recipe", f"Step {index + 1} must be an object.")
    kind = step.get("kind")
    if kind not in STEP_KINDS:
        raise AppError(
            422,
            "unsupported_cleaning_step",
            f"Step {index + 1}: {kind!r} is not a supported cleaning step.",
            details={"step_index": index, "supported_steps": sorted(STEP_KINDS)},
        )
    selected = _require_columns(step, columns, index) if kind in COLUMN_SCOPED else list(columns)
    effect = StepEffect(index=index, kind=str(kind), columns=selected)

    def edit(transform: Any) -> None:
        """Apply a cell transform across the selected columns, logging every change."""
        for row in rows:
            for column in selected:
                before = row.get(column)
                after = transform(before, column, effect)
                if after is not _UNCHANGED and after != before:
                    effect.cells_changed += 1
                    effect.record(column, before, after)
                    row[column] = after

    if kind == "trim_whitespace":
        edit(lambda v, c, e: _INVISIBLE.sub("", v).strip() if isinstance(v, str) else _UNCHANGED)
    elif kind == "collapse_whitespace":
        edit(
            lambda v, c, e: (
                _WHITESPACE_RUN.sub(" ", _INVISIBLE.sub("", v)).strip()
                if isinstance(v, str)
                else _UNCHANGED
            )
        )
    elif kind == "normalize_digits":
        edit(lambda v, c, e: normalize_digits(v) if isinstance(v, str) else _UNCHANGED)
    elif kind == "standardize_case":
        mode = step.get("case", "lower")
        if mode not in {"lower", "upper", "title"}:
            raise AppError(
                422,
                "invalid_recipe",
                f"Step {index + 1}: case must be lower, upper or title.",
                details={"step_index": index},
            )
        effect.options["case"] = mode
        casers = {"lower": str.lower, "upper": str.upper, "title": str.title}
        edit(lambda v, c, e: casers[mode](v) if isinstance(v, str) else _UNCHANGED)
    elif kind == "cast_number":
        repairs: Counter[str] = Counter()

        def cast(value: Any, column: str, e: StepEffect) -> Any:
            if value is None or value == "":
                return _UNCHANGED
            number, note = coerce_number(value)
            if number is None:
                e.unresolved(value)
                return _UNCHANGED
            if note:
                repairs[note] += 1
            return number

        edit(cast)
        effect.detail["notations_repaired"] = dict(repairs)
    elif kind == "round_number":
        digits = step.get("digits", 2)
        if not isinstance(digits, int) or not 0 <= digits <= 10:
            raise AppError(
                422,
                "invalid_recipe",
                f"Step {index + 1}: digits must be an integer 0-10.",
                details={"step_index": index},
            )
        effect.options["digits"] = digits

        def rounder(value: Any, column: str, e: StepEffect) -> Any:
            number = as_number(value)
            if number is None:
                if value not in (None, ""):
                    e.unresolved(value)
                return _UNCHANGED
            return round(number, digits)

        edit(rounder)
    elif kind == "cast_boolean":

        def to_bool(value: Any, column: str, e: StepEffect) -> Any:
            if value is None or value == "":
                return _UNCHANGED
            result = coerce_boolean(value)
            if result is None:
                e.unresolved(value)
                return _UNCHANGED
            return result

        edit(to_bool)
    elif kind == "parse_date":
        pattern = step.get("format")
        if not pattern:
            detected, name, ambiguous = detect_date_format(
                [row.get(c) for c in selected for row in rows]
            )
            if detected is None:
                raise AppError(
                    422,
                    "date_format_not_detected",
                    f"Step {index + 1}: no single date format explains these values. "
                    "Supply an explicit format.",
                    details={"step_index": index, "columns": selected},
                )
            if ambiguous and not step.get("day_first_confirmed"):
                raise AppError(
                    409,
                    "ambiguous_date_order",
                    f"Step {index + 1}: every value fits both day/month and month/day order. "
                    "Confirm which the source system writes before parsing.",
                    details={"step_index": index, "detected_format": name, "columns": selected},
                )
            pattern = detected
            effect.detail["format_detected"] = name
        effect.options["format"] = pattern

        def to_date(value: Any, column: str, e: StepEffect) -> Any:
            if value is None or value == "":
                return _UNCHANGED
            parsed = parse_date_value(value, str(pattern))
            if parsed is None:
                e.unresolved(value)
                return _UNCHANGED
            return parsed

        edit(to_date)
    elif kind == "replace_missing":
        if "value" not in step:
            raise AppError(
                422,
                "invalid_recipe",
                f"Step {index + 1}: a replacement value is required.",
                details={"step_index": index},
            )
        replacement = step["value"]
        if replacement is None or (isinstance(replacement, str) and replacement.strip() == ""):
            raise AppError(
                422,
                "empty_replacement_value",
                f"Step {index + 1}: replacing missing values with an empty value changes nothing. "
                "Give a real value, or use drop_missing_rows or fill_missing_statistic.",
                details={"step_index": index},
            )
        # Keep the column's own type: a numeric column must not gain a text cell.
        typed = replacement
        if isinstance(replacement, str):
            for column in selected:
                present = [row.get(column) for row in rows]
                numeric = [as_number(v) for v in present if v not in (None, "")]
                if numeric and all(n is not None for n in numeric):
                    number, _ = coerce_number(replacement)
                    if number is None:
                        raise AppError(
                            422,
                            "replacement_type_mismatch",
                            f"Step {index + 1}: column {column!r} holds numbers, but "
                            f"{replacement!r} is not a number. A text value here would break "
                            "every metric that reads this column.",
                            details={"step_index": index, "column": column},
                        )
                    typed = number
                    effect.detail["coerced_replacement_to_number"] = True
                    break
        effect.options["value"] = typed
        edit(lambda v, c, e: typed if v is None or v == "" else _UNCHANGED)
    elif kind == "fill_missing_statistic":
        statistic = step.get("statistic", "median")
        if statistic not in {"mean", "median", "mode"}:
            raise AppError(
                422,
                "invalid_recipe",
                f"Step {index + 1}: statistic must be mean, median or mode.",
                details={"step_index": index},
            )
        effect.options["statistic"] = statistic
        fills: dict[str, Any] = {}
        for column in selected:
            present = [row.get(column) for row in rows if row.get(column) not in (None, "")]
            if statistic == "mode":
                counted = Counter(str(v) for v in present).most_common(1)
                fills[column] = counted[0][0] if counted else None
            else:
                numbers = [n for n in (as_number(v) for v in present) if n is not None]
                if len(numbers) != len(present) or not numbers:
                    raise AppError(
                        422,
                        "statistic_requires_numbers",
                        f"Step {index + 1}: {statistic} needs a fully numeric column; "
                        f"{column!r} is not. Cast it to a number first, or use mode.",
                        details={"step_index": index, "column": column},
                    )
                ordered = sorted(numbers)
                fills[column] = (
                    round(math.fsum(ordered) / len(ordered), 10)
                    if statistic == "mean"
                    else ordered[len(ordered) // 2]
                    if len(ordered) % 2
                    else round(
                        (ordered[len(ordered) // 2 - 1] + ordered[len(ordered) // 2]) / 2, 10
                    )
                )
        effect.detail["fill_values"] = fills
        # Imputed values are model output, not measurements: record them prominently.
        effect.detail["imputation_warning"] = (
            "Imputed cells are estimates. Any metric over this column now mixes measured "
            "and estimated values."
        )
        edit(
            lambda v, c, e: (
                fills[c] if (v is None or v == "") and fills[c] is not None else _UNCHANGED
            )
        )
    elif kind == "drop_missing_rows":
        keep, dropped = [], 0
        for row in rows:
            if any(row.get(c) in (None, "") for c in selected):
                dropped += 1
                effect.record(selected[0], {c: row.get(c) for c in selected}, None)
            else:
                keep.append(row)
        effect.rows_dropped = dropped
        rows = keep
    elif kind in {"deduplicate", "drop_duplicate_rows"}:
        keys = selected if kind == "deduplicate" else list(columns)
        keep_mode = step.get("keep", "first")
        if keep_mode not in {"first", "last"}:
            raise AppError(
                422,
                "invalid_recipe",
                f"Step {index + 1}: keep must be first or last.",
                details={"step_index": index},
            )
        effect.options["keep"] = keep_mode
        effect.columns = keys
        iterable = rows if keep_mode == "first" else list(reversed(rows))
        seen: set[tuple[str, ...]] = set()
        kept: list[dict[str, Any]] = []
        removed: Counter[str] = Counter()
        for row in iterable:
            signature = tuple(str(row.get(c)) for c in keys)
            if signature in seen:
                effect.rows_dropped += 1
                removed[" | ".join(signature)] += 1
                continue
            seen.add(signature)
            kept.append(row)
        rows = kept if keep_mode == "first" else list(reversed(kept))
        effect.detail["removed_key_examples"] = [
            {"key": k, "extra_copies": c} for k, c in removed.most_common(5)
        ]
    elif kind == "map_values":
        mapping = step.get("mapping")
        if not isinstance(mapping, dict) or not mapping:
            raise AppError(
                422,
                "invalid_recipe",
                f"Step {index + 1}: mapping must be a non-empty object of old -> new values.",
                details={"step_index": index},
            )
        effect.options["mapping"] = mapping
        edit(lambda v, c, e: mapping.get(str(v), _UNCHANGED) if v is not None else _UNCHANGED)
    elif kind == "clip_outliers":
        method = step.get("method", "iqr")
        if method not in {"iqr", "percentile", "absolute"}:
            raise AppError(
                422,
                "invalid_recipe",
                f"Step {index + 1}: method must be iqr, percentile or absolute.",
                details={"step_index": index},
            )
        effect.options["method"] = method
        bounds: dict[str, tuple[float, float]] = {}
        for column in selected:
            numbers = sorted(
                n for n in (as_number(row.get(column)) for row in rows) if n is not None
            )
            if not numbers:
                raise AppError(
                    422,
                    "clip_requires_numbers",
                    f"Step {index + 1}: {column!r} has no numeric values to bound.",
                    details={"step_index": index, "column": column},
                )
            if method == "absolute":
                low = float(step.get("lower", numbers[0]))
                high = float(step.get("upper", numbers[-1]))
            elif method == "iqr":
                q1, q3 = _quantile(numbers, 0.25), _quantile(numbers, 0.75)
                factor = float(step.get("factor", 1.5))
                low, high = q1 - factor * (q3 - q1), q3 + factor * (q3 - q1)
            else:
                low = _quantile(numbers, float(step.get("lower", 0.01)))
                high = _quantile(numbers, float(step.get("upper", 0.99)))
            bounds[column] = (low, high)
        effect.detail["bounds"] = {
            k: {"lower": round(v[0], 6), "upper": round(v[1], 6)} for k, v in bounds.items()
        }
        effect.detail["clipping_warning"] = (
            "Clipping keeps the row but rewrites the measurement. Sums and averages over this "
            "column no longer reproduce the source system."
        )

        def clip(value: Any, column: str, e: StepEffect) -> Any:
            number = as_number(value)
            if number is None:
                return _UNCHANGED
            low, high = bounds[column]
            return min(max(number, low), high)

        edit(clip)
    elif kind == "filter_rows":
        operator = step.get("operator")
        target = step.get("value")
        allowed = {"eq", "ne", "gt", "gte", "lt", "lte", "in", "not_in", "contains", "not_null"}
        if operator not in allowed:
            raise AppError(
                422,
                "invalid_recipe",
                f"Step {index + 1}: operator must be one of {', '.join(sorted(allowed))}.",
                details={"step_index": index},
            )
        column = selected[0]
        effect.options.update({"operator": operator, "value": target, "column": column})

        def keeps(row: dict[str, Any]) -> bool:
            value = row.get(column)
            if operator == "not_null":
                return value not in (None, "")
            if operator in {"in", "not_in"}:
                members = {str(v) for v in (target if isinstance(target, list) else [target])}
                return (str(value) in members) is (operator == "in")
            if operator == "contains":
                return isinstance(value, str) and str(target) in value
            # Numbers compare numerically; anything else falls back to text comparison.
            left: Any = as_number(value)
            right: Any = as_number(target)
            if left is None or right is None:
                left, right = str(value), str(target)
            return {
                "eq": left == right,
                "ne": left != right,
                "gt": left > right,
                "gte": left >= right,
                "lt": left < right,
                "lte": left <= right,
            }[operator]

        kept = [row for row in rows if keeps(row)]
        effect.rows_dropped = len(rows) - len(kept)
        rows = kept
    elif kind == "drop_column":
        columns = [c for c in columns if c not in selected]
        for row in rows:
            for column in selected:
                row.pop(column, None)
        effect.detail["columns_removed"] = selected
    elif kind == "rename_column":
        renames = step.get("names")
        if not isinstance(renames, dict) or set(renames) != set(selected):
            raise AppError(
                422,
                "invalid_recipe",
                f"Step {index + 1}: names must map every selected column to its new name.",
                details={"step_index": index, "columns": selected},
            )
        collisions = [v for v in renames.values() if v in columns and v not in selected]
        if collisions or len(set(renames.values())) != len(renames):
            raise AppError(
                422,
                "duplicate_column_name",
                f"Step {index + 1}: renaming would produce duplicate column names.",
                details={"step_index": index, "collisions": collisions},
            )
        columns = [renames.get(c, c) for c in columns]
        for row in rows:
            for old, new in renames.items():
                row[new] = row.pop(old, None)
        effect.detail["renames"] = renames

    return rows, columns, effect


class _Unchanged:
    __slots__ = ()

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return "<unchanged>"


_UNCHANGED = _Unchanged()


def control_totals(rows: list[dict[str, Any]], columns: list[str]) -> dict[str, Any]:
    """Sum every column that reads as numeric, and say how much could not be read.

    The unparsable count is the point: a total computed over a column where a third of
    the cells silently fell out is not a control total, and the reviewer must see that.
    """
    totals: dict[str, Any] = {}
    for column in columns:
        present = [row.get(column) for row in rows if row.get(column) not in (None, "")]
        if not present:
            continue
        strict = [as_number(v) for v in present]
        parsed = [v for v in strict if v is not None]
        if not parsed or len(parsed) < len(present) * 0.5:
            continue
        totals[column] = {
            "sum": round(math.fsum(parsed), 6),
            "count": len(parsed),
            "unreadable_cells": len(present) - len(parsed),
        }
    return totals


def _compare_totals(
    before: dict[str, Any], after: dict[str, Any]
) -> tuple[list[dict[str, Any]], bool]:
    """Diff two control-total sets and say whether a human has to look."""
    changes: list[dict[str, Any]] = []
    material = False
    for column in sorted(set(before) | set(after)):
        left = before.get(column)
        right = after.get(column)
        left_sum = left["sum"] if left else None
        right_sum = right["sum"] if right else None
        if left is None or right is None or left_sum is None or right_sum is None:
            changes.append(
                {
                    "column": column,
                    "before": left_sum,
                    "after": right_sum,
                    "difference": None,
                    "relative_difference": None,
                    "note": "column_became_unreadable_as_a_number"
                    if right_sum is None
                    else "column_became_readable_as_a_number",
                    "material": True,
                }
            )
            material = True
            continue
        difference = right_sum - left_sum
        scale = max(abs(left_sum), abs(right_sum), 1.0)
        relative = difference / scale
        # A cast that makes previously unreadable cells countable is expected to move the
        # total. It is reported as explained rather than as an unreconciled discrepancy.
        recovered = left["unreadable_cells"] - right["unreadable_cells"]
        is_material = abs(relative) > CONTROL_TOTAL_TOLERANCE
        changes.append(
            {
                "column": column,
                "before": left_sum,
                "after": right_sum,
                "difference": round(difference, 6),
                "relative_difference": round(relative, 9),
                "unreadable_before": left["unreadable_cells"],
                "unreadable_after": right["unreadable_cells"],
                "cells_recovered": recovered,
                "note": "difference_explained_by_newly_readable_cells"
                if recovered > 0 and is_material
                else "unchanged"
                if not is_material
                else "unexplained_change",
                "material": is_material,
            }
        )
        material = material or is_material
    return changes, material


def summarize(
    effects: list[StepEffect],
    before_profile: dict[str, Any],
    after_profile: dict[str, Any],
    total_changes: list[dict[str, Any]],
) -> dict[str, Any]:
    """Write the cleaning log a reviewer reads, in both interface languages."""

    def en(number: int, singular: str, plural: str | None = None) -> str:
        """English agreement: "1 row", "4 rows"."""
        return f"{number:,} {singular if number == 1 else (plural or singular + 's')}"

    english: list[str] = []
    arabic: list[str] = []
    for effect in effects:
        columns_en = ", ".join(effect.columns) or "—"
        columns_ar = ar.joined(effect.columns)
        n, dropped, stuck = effect.cells_changed, effect.rows_dropped, effect.cells_unresolved
        cells_ar = ar.count(n, ar.CELL)
        rows_ar = ar.count(dropped, ar.ROW)
        stuck_ar = ar.count(stuck, ar.CELL)
        notation_names = {
            "group_separator_comma": ("thousands separators", "فواصل الآلاف"),
            "group_separator_period": ("period thousands separators", "نقاط الآلاف"),
            "decimal_comma": ("comma decimal marks", "الفاصلة العشرية"),
            "currency_symbol": ("currency symbols", "رموز العملة"),
            "percent_sign": ("percent signs", "علامات النسبة"),
            "parenthesis_negative": ("negatives written in parentheses", "السالب بين قوسين"),
            "trailing_minus": ("trailing minus signs", "إشارة السالب اللاحقة"),
            "embedded_whitespace": ("spaces inside numbers", "المسافات داخل الأرقام"),
        }
        repaired = list(effect.detail.get("notations_repaired", {}))
        readable = sorted(
            {
                name
                for token in repaired
                for part in token.split("+")
                for name in [notation_names.get(part, (part, part))[0]]
            }
        )
        readable_ar = sorted(
            {
                name
                for token in repaired
                for part in token.split("+")
                for name in [notation_names.get(part, (part, part))[1]]
            }
        )
        notations = ", ".join(readable)
        notations_ar = ar.joined(readable_ar)
        case_mode = effect.options.get("case")
        case_ar = {
            "lower": "الأحرف الصغيرة",
            "upper": "الأحرف الكبيرة",
            "title": "أول حرف كبير",
        }.get(str(case_mode), str(case_mode))
        statistic_ar = {"mean": "المتوسط", "median": "الوسيط", "mode": "المنوال"}.get(
            str(effect.options.get("statistic")), ""
        )
        phrases: dict[str, tuple[str, str]] = {
            "trim_whitespace": (
                f"Removed leading, trailing and invisible characters from "
                f"{en(n, 'cell')} in {columns_en}.",
                f"أُزيلت المسافات الطرفية والمحارف غير المرئية من {cells_ar} في {columns_ar}.",
            ),
            "collapse_whitespace": (
                f"Collapsed repeated internal spaces in {en(n, 'cell')} in {columns_en}.",
                f"دُمجت المسافات الداخلية المتكررة في {cells_ar} في {columns_ar}.",
            ),
            "normalize_digits": (
                f"Converted Arabic-Indic digits to ASCII in {en(n, 'cell')} in {columns_en}.",
                f"حُوّلت الأرقام العربية-الهندية إلى لاتينية في {cells_ar} في {columns_ar}.",
            ),
            "standardize_case": (
                f"Standardized letter case to {case_mode} in {en(n, 'cell')} in {columns_en}, "
                "merging spellings that differed only by case.",
                f"وُحّدت حالة الأحرف إلى {case_ar} في {cells_ar} في {columns_ar}، "
                "فاندمجت القيم التي اختلفت في حالة الأحرف فقط.",
            ),
            "cast_number": (
                f"Converted {en(n, 'text cell')} in {columns_en} to numbers"
                + (f", repairing {notations}" if notations else "")
                + (
                    f". {en(stuck, 'cell')} could not be read as a number and was left unchanged."
                    if stuck == 1
                    else f". {stuck:,} cells could not be read as numbers and were left unchanged."
                    if stuck
                    else "."
                ),
                f"حُوّلت {cells_ar} في {columns_ar} من نص إلى رقم"
                + (f"، مع إصلاح {notations_ar}" if notations_ar else "")
                + (f". لم تُقرأ {stuck_ar} كقيمة رقمية فتُركت كما هي." if stuck else "."),
            ),
            "round_number": (
                f"Rounded {en(n, 'value')} in {columns_en} to "
                f"{effect.options.get('digits')} decimal places.",
                f"قُرّبت {ar.count(n, ar.VALUE)} في {columns_ar} إلى "
                f"{effect.options.get('digits')} منزلة عشرية.",
            ),
            "cast_boolean": (
                f"Converted {en(n, 'cell')} in {columns_en} to true/false values."
                + (
                    f" {en(stuck, 'cell')} was not recognisable as a boolean."
                    if stuck == 1
                    else f" {stuck:,} cells were not recognisable as booleans."
                    if stuck
                    else ""
                ),
                f"حُوّلت {cells_ar} في {columns_ar} إلى قيم صح/خطأ."
                + (f" لم يُتعرّف على {stuck_ar} كقيمة منطقية." if stuck else ""),
            ),
            "parse_date": (
                f"Parsed {en(n, 'cell')} in {columns_en} into ISO 8601 dates using the pattern "
                f"{effect.options.get('format')}."
                + (
                    f" {en(stuck, 'cell')} did not match the pattern and was left unchanged."
                    if stuck
                    else ""
                ),
                f"حُلّلت {cells_ar} في {columns_ar} إلى تواريخ ISO 8601 بالنمط "
                f"{effect.options.get('format')}."
                + (f" لم تطابق {stuck_ar} النمط فتُركت كما هي." if stuck else ""),
            ),
            "replace_missing": (
                f"Filled {en(n, 'missing cell')} in {columns_en} with "
                f"{effect.options.get('value')!r}.",
                f"عُبّئت {cells_ar} كانت فارغة في {columns_ar} بالقيمة "
                f"{effect.options.get('value')!r}.",
            ),
            "fill_missing_statistic": (
                f"Imputed {en(n, 'missing cell')} in {columns_en} with the column "
                f"{effect.options.get('statistic')} ({effect.detail.get('fill_values')}). "
                "These cells are estimates, not measurements.",
                f"عُوّضت {cells_ar} كانت فارغة في {columns_ar} بقيمة "
                f"{statistic_ar} للعمود "
                f"({effect.detail.get('fill_values')}). هذه الخلايا تقديرات وليست قياسات.",
            ),
            "drop_missing_rows": (
                f"Removed {en(dropped, 'row')} that had no value in {columns_en}.",
                f"حُذف {rows_ar} بسبب غياب القيمة في {columns_ar}.",
            ),
            "deduplicate": (
                f"Removed {en(dropped, 'duplicate row')}, keeping the "
                f"{effect.options.get('keep')} occurrence of each {columns_en} key.",
                f"حُذف {rows_ar} بسبب تكرار المفتاح {columns_ar}، مع إبقاء الظهور "
                f"{'الأول' if effect.options.get('keep') == 'first' else 'الأخير'} "
                f"لكل مفتاح.",
            ),
            "drop_duplicate_rows": (
                f"Removed {en(dropped, 'row')} identical across every column.",
                f"حُذف {rows_ar} بسبب التطابق التام في جميع الأعمدة.",
            ),
            "map_values": (
                f"Recoded {en(n, 'cell')} in {columns_en} through an explicit value mapping.",
                f"أُعيد ترميز {cells_ar} في {columns_ar} عبر خريطة قيم صريحة.",
            ),
            "clip_outliers": (
                f"Bounded {en(n, 'extreme value')} in {columns_en} to "
                f"{effect.detail.get('bounds')}. The rows were kept but the measurements "
                "were rewritten.",
                f"حُصرت {ar.count(n, ar.VALUE)} متطرفة القيمة في {columns_ar} ضمن الحدود "
                f"{effect.detail.get('bounds')}. أُبقيت الصفوف لكن أُعيدت كتابة القياسات.",
            ),
            "filter_rows": (
                f"Removed {en(dropped, 'row')} where {effect.options.get('column')} "
                f"{effect.options.get('operator')} {effect.options.get('value')!r} "
                "was not satisfied.",
                f"حُذف {rows_ar} بسبب عدم تحقق الشرط {effect.options.get('column')} "
                f"{effect.options.get('operator')} {effect.options.get('value')!r}.",
            ),
            "drop_column": (
                f"Removed the columns {columns_en} from the dataset.",
                f"حُذفت الأعمدة {columns_ar} من مجموعة البيانات.",
            ),
            "rename_column": (
                f"Renamed columns: {effect.detail.get('renames')}.",
                f"أُعيدت تسمية الأعمدة: {effect.detail.get('renames')}.",
            ),
        }
        line_en, line_ar = phrases.get(
            effect.kind,
            (f"Applied {effect.kind} to {columns_en}.", f"طُبّقت {effect.kind} على {columns_ar}."),
        )
        english.append(f"{effect.index + 1}. {line_en}")
        arabic.append(f"{effect.index + 1}. {line_ar}")

    before_score = (before_profile.get("quality") or {}).get("score")
    after_score = (after_profile.get("quality") or {}).get("score")
    unexplained = [c for c in total_changes if c.get("note") == "unexplained_change"]
    explained = [
        c for c in total_changes if c.get("note") == "difference_explained_by_newly_readable_cells"
    ]
    changed_cells = sum(e.cells_changed for e in effects)
    removed_rows = sum(e.rows_dropped for e in effects)
    direction = (
        "improved"
        if (after_score or 0) > (before_score or 0)
        else "fell"
        if (after_score or 0) < (before_score or 0)
        else "held"
    )
    direction_ar = {"improved": "ارتفعت", "fell": "انخفضت", "held": "ثبتت"}[direction]

    headline_en = (
        f"{en(len(effects), 'cleaning step')} changed "
        + (en(changed_cells, "cell") if changed_cells else "no cells")
        + " and removed "
        + (en(removed_rows, "row") if removed_rows else "no rows")
        + f". Data quality {direction} from {before_score} to {after_score} out of 100."
    )
    # Passive constructions keep the counted nouns in the nominative at every count,
    # which avoids the case marking a template cannot get right.
    changed_phrase = (
        f"تغيّرت {ar.count(changed_cells, ar.CELL)}" if changed_cells else "لم تتغيّر أي خلية"
    )
    removed_phrase = f"وحُذف {ar.count(removed_rows, ar.ROW)}" if removed_rows else "ولم يُحذف أي صف"
    headline_ar = (
        f"طُبّقت {ar.count(len(effects), ar.STEP)}، ف{changed_phrase} {removed_phrase}. "
        f"{direction_ar} جودة البيانات من {before_score} إلى {after_score} من 100."
    )
    caveats_en: list[str] = []
    caveats_ar: list[str] = []
    if unexplained:
        names_en = ", ".join(c["column"] for c in unexplained)
        caveats_en.append(
            f"Control totals changed for {names_en} without a matching recovery of "
            "unreadable cells. Confirm this is intended before publishing."
        )
        caveats_ar.append(
            f"تغيّرت المجاميع الرقابية لـ {ar.joined([c['column'] for c in unexplained])} "
            "دون استرجاع مقابل لخلايا غير مقروءة. أكّد أن هذا مقصود قبل النشر."
        )
    if explained:
        names_en = ", ".join(c["column"] for c in explained)
        caveats_en.append(
            f"Totals moved for {names_en} because cells that previously could not be read "
            "as numbers now count. The source file did not change."
        )
        caveats_ar.append(
            f"تغيّرت مجاميع {ar.joined([c['column'] for c in explained])} لأن خلايا لم تكن "
            "تُقرأ كأرقام صارت تُحتسب الآن. الملف الأصلي لم يتغيّر."
        )
    stuck_total = sum(e.cells_unresolved for e in effects)
    if stuck_total:
        caveats_en.append(
            f"{en(stuck_total, 'cell')} could not be interpreted by the steps you chose and "
            "were left exactly as they were."
        )
        caveats_ar.append(
            f"تعذّر تفسير {ar.count(stuck_total, ar.CELL)} بالخطوات المختارة فتُركت كما هي."
        )
    for effect in effects:
        if effect.detail.get("imputation_warning"):
            caveats_en.append(effect.detail["imputation_warning"])
            caveats_ar.append(
                "الخلايا المعوّضة تقديرات؛ أي مقياس على هذا العمود يخلط قياسات بتقديرات."
            )
        if effect.detail.get("clipping_warning"):
            caveats_en.append(effect.detail["clipping_warning"])
            caveats_ar.append(
                "الحصر يُبقي الصف لكنه يعيد كتابة القياس؛ لن تطابق المجاميع النظام المصدر."
            )
    no_effect = [e for e in effects if e.cells_changed == 0 and e.rows_dropped == 0]
    if no_effect:
        labels = ", ".join(f"step {e.index + 1} ({e.kind})" for e in no_effect)
        caveats_en.append(f"These steps changed nothing: {labels}. Remove them or fix the column.")
        caveats_ar.append(
            "لم تُحدث هذه الخطوات أي تغيير: "
            + ar.joined([f"الخطوة {e.index + 1} ({e.kind})" for e in no_effect])
            + ". احذفها أو صحّح العمود المستهدف."
        )
    remaining = [
        {"column": name, "issue": key, "count": value}
        for name, profile in after_profile.get("column_profiles", {}).items()
        for key, value in (
            ("missing_cells", profile.get("null_count", 0)),
            ("unreadable_numbers", profile.get("numeric_parse", {}).get("unparsable", 0)),
            ("case_variants", profile.get("text", {}).get("case_variant_groups", 0)),
            ("untrimmed", profile.get("text", {}).get("untrimmed_count", 0)),
        )
        if value
    ]
    return {
        "headline": {"en": headline_en, "ar": headline_ar},
        "steps": {"en": english, "ar": arabic},
        "caveats": {"en": caveats_en, "ar": caveats_ar},
        "totals": {
            "steps": len(effects),
            "cells_changed": changed_cells,
            "rows_removed": removed_rows,
            "cells_unresolved": stuck_total,
        },
        "quality_before": before_profile.get("quality"),
        "quality_after": after_profile.get("quality"),
        "remaining_issues": sorted(remaining, key=lambda item: -item["count"])[:20],
        "next_recommended_steps": after_profile.get("recommended_steps", [])[:8],
    }


def run_recipe(
    source_rows: list[dict[str, Any]], columns: list[str], recipe: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[str], dict[str, Any]]:
    """Execute a reviewed recipe and return the rows, the surviving columns, and the log."""
    steps = recipe.get("steps")
    if not isinstance(steps, list) or not steps:
        raise AppError(422, "invalid_recipe", "At least one cleaning step is required")
    if len(steps) > 40:
        raise AppError(
            422,
            "recipe_too_long",
            "A recipe is limited to 40 steps.",
            details={"steps": len(steps)},
        )
    rows = [dict(row) for row in source_rows]
    working = list(columns)
    effects: list[StepEffect] = []
    for index, step in enumerate(steps):
        rows, working, effect = _apply_step(step, index, rows, working)
        effects.append(effect)

    before_profile = profile_dataset(source_rows, columns)
    after_profile = profile_dataset(rows, working)
    before_totals = control_totals(source_rows, columns)
    after_totals = control_totals(rows, working)
    total_changes, material = _compare_totals(before_totals, after_totals)
    dropped_rows = sum(e.rows_dropped for e in effects)
    structural = [e for e in effects if e.kind in {"drop_column", "rename_column"}]

    preview = {
        # Legacy shape, kept so stored previews and existing consumers keep working.
        "before": {"row_count": len(source_rows), "column_count": len(columns)},
        "after": {"row_count": len(rows), "column_count": len(working)},
        "changed_cells": sum(e.cells_changed for e in effects),
        "dropped_rows": dropped_rows,
        "reconciliation": {
            "revenue_before": (before_totals.get("revenue") or {}).get("sum", 0.0),
            "revenue_after": (after_totals.get("revenue") or {}).get("sum", 0.0),
            "revenue_difference": round(
                (after_totals.get("revenue") or {}).get("sum", 0.0)
                - (before_totals.get("revenue") or {}).get("sum", 0.0),
                10,
            ),
        },
        "requires_review": bool(dropped_rows or material or structural),
        "unresolved_issues": after_profile["quality_issues"],
        # Analyst detail.
        "columns_before": columns,
        "columns_after": working,
        "control_totals": {
            "before": before_totals,
            "after": after_totals,
            "changes": total_changes,
            "tolerance": CONTROL_TOTAL_TOLERANCE,
        },
        "review_reasons": [
            *(["rows_removed"] if dropped_rows else []),
            *(["control_total_changed"] if material else []),
            *(["column_set_changed"] if structural else []),
        ],
        "steps": [e.as_dict() for e in effects],
        "summary": summarize(effects, before_profile, after_profile, total_changes),
        "profile_after": after_profile,
    }
    return rows, working, preview
