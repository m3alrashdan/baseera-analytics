"""Small shared helpers: bilingual text, JSON safety and number formatting."""

from __future__ import annotations

import math
from datetime import date, datetime
from typing import Any

import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits

Bilingual = dict[str, str]


def bi(en: str, ar: str) -> Bilingual:
    return {"en": en, "ar": ar}


def clean(value: Any, digits: int = 6) -> Any:
    """Convert numpy/pandas values into JSON-safe Python values."""

    if value is None:
        return None
    if isinstance(value, dict):
        return {str(k): clean(v, digits) for k, v in value.items()}
    if isinstance(value, list | tuple | set):
        return [clean(v, digits) for v in value]
    if isinstance(value, np.ndarray):
        return [clean(v, digits) for v in value.tolist()]
    if isinstance(value, bool | np.bool_):
        return bool(value)
    if isinstance(value, int | np.integer):
        return int(value)
    if isinstance(value, float | np.floating):
        number = float(value)
        if math.isnan(number) or math.isinf(number):
            return None
        return round(number, digits)
    if isinstance(value, pd.Timestamp):
        if pd.isna(value):
            return None
        return value.isoformat()
    if isinstance(value, datetime | date):
        return value.isoformat()
    if value is pd.NaT:
        return None
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value if isinstance(value, str) else str(value)


def fmt(value: float | int | None, digits: int = 1) -> str:
    """Human formatting with thousands separators and compact suffixes."""

    if value is None:
        return "—"
    number = float(value)
    if math.isnan(number):
        return "—"
    magnitude = abs(number)
    if magnitude >= 1_000_000_000:
        return f"{number / 1_000_000_000:,.{digits}f}B"
    if magnitude >= 1_000_000:
        return f"{number / 1_000_000:,.{digits}f}M"
    if magnitude >= 10_000:
        return f"{number / 1_000:,.{digits}f}K"
    if magnitude >= 100 or float(number).is_integer():
        return f"{number:,.0f}"
    return f"{number:,.{max(digits, 2)}f}"


def pct(value: float | None, digits: int = 1, signed: bool = False) -> str:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "—"
    sign = "+" if signed else ""
    return f"{value * 100:{sign}.{digits}f}%"


def safe_div(numerator: float, denominator: float) -> float | None:
    if denominator == 0 or denominator is None or numerator is None:
        return None
    result = numerator / denominator
    return None if math.isnan(result) or math.isinf(result) else result


def confidence_label(score: float) -> str:
    if score >= 0.75:
        return "high"
    if score >= 0.5:
        return "medium"
    return "low"


def measure_label(measure: str | None, agg: str = "sum", is_flag: bool = False) -> tuple[str, str]:
    """How a measure reads in each language, including record counts and rates."""

    if not measure:
        return "records", "السجلات"
    if is_flag and agg == "mean":
        return f"{measure} rate", f"نسبة {measure}"
    if agg == "mean":
        return f"average {measure}", f"متوسط {measure}"
    return measure, measure


def p_text(value: float | None) -> str:
    """A p- or q-value as a reader expects it."""

    if value is None:
        return "—"
    if value < 0.001:
        return "<0.001"
    return f"{value:.3f}"


_native_limit: Any = None


def limit_native_threads() -> None:
    """Pin OpenMP and BLAS pools to one thread for this process's analysis workload.

    The analyst team fits many small models inside a server that also serves requests.
    Multi-threaded OpenMP (gradient boosting, k-means) spin-waits for cores; under any
    CPU contention a 3-second fit was measured taking 99 seconds, while a single thread
    fits the same model in under 3 seconds. The limit is applied once and kept.
    """

    global _native_limit
    if _native_limit is None:
        _native_limit = threadpool_limits(limits=1)
