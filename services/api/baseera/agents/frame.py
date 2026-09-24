"""The analysis frame: typed data plus the semantic model an analyst builds first.

Before any analysis a good analyst answers four questions about a table:

* Which column is *time*, and at what grain is the business measured?
* Which columns are *measures* (things you add up or average) and which of those is
  the *KPI* the business most likely cares about?
* Which columns are *dimensions* you slice by, and which are *entities* (customers,
  products) that repeat over time?
* What is noise: identifiers, free text, constants?

``AnalysisFrame`` answers them deterministically from the column profile, so every
agent downstream works from the same, inspectable semantic model.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

from ..errors import AppError
from ..ingestion import profile_rows
from ..profiling import coerce_boolean, coerce_number
from .common import clean

MAX_ANALYSIS_ROWS = 250_000
ML_SAMPLE_ROWS = 40_000

# Words that mark a column as a likely business KPI, strongest first. English words are
# matched as whole tokens ("discount" must not match "count"); Arabic as substrings.
KPI_WORDS: tuple[tuple[set[str], tuple[str, ...], float], ...] = (
    (
        {"revenue", "revenues", "sales", "turnover", "gmv", "mrr", "arr"},
        ("إيراد", "ايراد", "مبيعات"),
        1.0,
    ),
    ({"profit", "profits", "margin", "earnings", "ebitda"}, ("ربح", "أرباح", "هامش"), 0.95),
    (
        {"amount", "total", "value", "spend", "spending", "ltv", "arpu"},
        ("مبلغ", "إجمالي", "اجمالي", "قيمة", "إنفاق"),
        0.85,
    ),
    (
        {"income", "fee", "fees", "charge", "charges", "salary", "wage", "payment", "payments"},
        ("دخل", "رسوم", "راتب", "دفعة"),
        0.8,
    ),
    (
        {"cost", "costs", "expense", "expenses", "budget", "cogs"},
        ("تكلفة", "كلفة", "مصروف", "مصاريف", "ميزانية"),
        0.75,
    ),
    ({"quantity", "qty", "units", "volume"}, ("كمية", "الكمية", "وحدات"), 0.7),
    (
        {"orders", "transactions", "bookings", "visits", "sessions", "leads"},
        ("طلبات", "معاملات", "زيارات"),
        0.65,
    ),
    ({"price"}, ("سعر",), 0.55),
    ({"score", "rating", "satisfaction", "nps", "csat"}, ("تقييم", "رضا", "الرضا", "ولاء"), 0.5),
    (
        {"duration", "hours", "days", "time", "minutes", "tenure"},
        ("مدة", "ساعات", "أيام", "وقت"),
        0.45,
    ),
    ({"count", "number"}, ("عدد",), 0.4),
)
MONEY_WORDS = {
    "revenue",
    "revenues",
    "sales",
    "profit",
    "amount",
    "price",
    "cost",
    "costs",
    "expense",
    "expenses",
    "spend",
    "budget",
    "income",
    "value",
    "gmv",
    "fee",
    "fees",
    "charge",
    "salary",
    "wage",
    "payment",
    "mrr",
    "arr",
    "arpu",
    "ltv",
    "margin",
}
MONEY_AR = (
    "مبلغ",
    "إيراد",
    "ايراد",
    "مبيعات",
    "ربح",
    "سعر",
    "تكلفة",
    "مصروف",
    "دخل",
    "قيمة",
    "رسوم",
    "راتب",
)
TARGET_FLAG_PATTERNS = (
    r"churn|attrition|returned|return|cancel|default|fraud|converted|conversion|won|lost|left|"
    r"انسحاب|مرتجع|إلغاء|الغاء|تسرب|فقدان"
)
NON_MEASURE_WORDS = {
    "year",
    "month",
    "day",
    "week",
    "quarter",
    "yr",
    "zip",
    "postal",
    "postcode",
    "code",
    "phone",
    "mobile",
    "lat",
    "lon",
    "latitude",
    "longitude",
    "rank",
    "سنة",
    "السنة",
    "العام",
    "شهر",
    "الشهر",
    "يوم",
    "اليوم",
    "أسبوع",
    "ربع",
    "رمز",
    "الرمز",
    "هاتف",
    "الهاتف",
    "ترتيب",
}
# Measures a reader averages rather than adds: prices, scores, durations, rates.
AVERAGED_SCORES = {0.55, 0.5, 0.45}
ENTITY_PATTERNS = (
    r"customer|client|user|account|member|patient|student|employee|product|sku|item|store|"
    r"supplier|vendor|subscriber|عميل|زبون|مستخدم|حساب|منتج|صنف|متجر|مورد|موظف|مشترك"
)


def _tokens(name: str) -> set[str]:
    return {token for token in re.split(r"[^0-9a-z]+", name.casefold()) if token}


def _words(name: str) -> set[str]:
    """Whole words in any script, split on spaces, underscores and punctuation."""

    return {token for token in re.split(r"[\s_\-./()]+", name.casefold()) if token}


def _non_measure_name(name: str) -> bool:
    return bool(_words(name) & NON_MEASURE_WORDS)


def is_money(name: str) -> bool:
    lowered = name.casefold()
    return bool(_tokens(name) & MONEY_WORDS) or any(word in lowered for word in MONEY_AR)


@dataclass(slots=True)
class ColumnRole:
    name: str
    semantic_type: str
    role: str  # time | measure | dimension | entity | identifier | flag | text | constant | empty
    missing_rate: float
    distinct_count: int
    kpi_score: float = 0.0
    is_money: bool = False
    is_rate: bool = False
    rate_scale: float = 1.0  # 1 for 0-1 ratios, 100 for percentage points
    additive: bool = True
    unique_key: bool = False
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return clean(
            {
                "name": self.name,
                "semantic_type": self.semantic_type,
                "role": self.role,
                "missing_rate": self.missing_rate,
                "distinct_count": self.distinct_count,
                "kpi_score": self.kpi_score,
                "is_money": self.is_money,
                "is_rate": self.is_rate,
                "rate_scale": self.rate_scale,
                "additive": self.additive,
                "notes": self.notes,
            }
        )


@dataclass(slots=True)
class AnalysisFrame:
    df: pd.DataFrame
    profile: dict[str, Any]
    roles: dict[str, ColumnRole]
    time_column: str | None
    measures: list[str]
    dimensions: list[str]
    entities: list[str]
    flags: list[str]
    primary_kpi: str | None
    outcome: str | None
    row_count: int
    truncated: bool = False
    cache: dict[str, Any] = field(default_factory=dict)

    # ----------------------------------------------------------------- accessors
    def column(self, name: str) -> pd.Series:
        if name not in self.df.columns:
            raise AppError(
                422,
                "unknown_column",
                f"{name!r} is not a column in this dataset.",
                details={"available_columns": list(self.df.columns)},
            )
        return self.df[name]

    def require(self, name: str | None, role: set[str] | None = None) -> str:
        if not name:
            raise AppError(422, "column_required", "A column name is required for this tool.")
        resolved = self.resolve(name)
        if resolved is None:
            raise AppError(
                422,
                "unknown_column",
                f"{name!r} is not a column in this dataset.",
                details={"available_columns": list(self.df.columns)},
            )
        if role and self.roles[resolved].role not in role:
            raise AppError(
                422,
                "column_role_mismatch",
                f"{resolved!r} is a {self.roles[resolved].role} column; this tool needs "
                f"{' or '.join(sorted(role))}.",
                details={"column": resolved, "role": self.roles[resolved].role},
            )
        return resolved

    def resolve(self, name: str) -> str | None:
        """Match a column name leniently (case, spaces, underscores)."""

        if name in self.df.columns:
            return name
        wanted = _normalize(name)
        for column in self.df.columns:
            if _normalize(column) == wanted:
                return str(column)
        return None

    def numeric(self, name: str) -> pd.Series:
        series = self.column(name)
        if pd.api.types.is_numeric_dtype(series):
            return series.astype(float)
        if pd.api.types.is_bool_dtype(series):
            return series.astype(float)
        return pd.to_numeric(series, errors="coerce")

    def ml_sample(self, size: int = ML_SAMPLE_ROWS) -> pd.DataFrame:
        if len(self.df) <= size:
            return self.df
        return self.df.sample(n=size, random_state=20260630)

    def schema_summary(self) -> dict[str, Any]:
        """Compact semantic model, suitable to show a user or a language model."""

        return clean(
            {
                "rows": self.row_count,
                "columns": len(self.df.columns),
                "truncated_to_rows": len(self.df) if self.truncated else None,
                "time_column": self.time_column,
                "time_range": self.time_range(),
                "primary_kpi": self.primary_kpi,
                "outcome": self.outcome,
                "measures": self.measures,
                "dimensions": self.dimensions,
                "entities": self.entities,
                "flags": self.flags,
                "columns_detail": [role.as_dict() for role in self.roles.values()],
                "quality_score": self.profile.get("quality", {}).get("score"),
            }
        )

    def time_range(self) -> dict[str, Any] | None:
        if not self.time_column:
            return None
        values = self.df[self.time_column].dropna()
        if values.empty:
            return None
        start, end = values.min(), values.max()
        return {
            "start": start.date().isoformat(),
            "end": end.date().isoformat(),
            "days": int((end - start).days) + 1,
        }

    def dimension_values(self, column: str, limit: int = 12) -> list[str]:
        counts = self.df[column].dropna().astype(str).value_counts()
        return [str(value) for value in counts.index[:limit]]


def _normalize(name: str) -> str:
    return re.sub(r"[\s_\-]+", "", str(name)).casefold()


def _kpi_score(name: str) -> float:
    lowered = name.casefold()
    tokens = _tokens(name)
    for english, arabic, score in KPI_WORDS:
        if tokens & english or any(word in lowered for word in arabic):
            return score
    return 0.2


def build_frame(
    rows: list[dict[str, Any]],
    columns: list[str],
    profile: dict[str, Any] | None = None,
) -> AnalysisFrame:
    """Type the rows and build the semantic model."""

    if not rows or not columns:
        raise AppError(
            422, "insufficient_data", "The dataset has no rows to analyze.", details={"rows": 0}
        )
    total_rows = len(rows)
    truncated = total_rows > MAX_ANALYSIS_ROWS
    if truncated:
        rows = rows[:MAX_ANALYSIS_ROWS]
    profile = profile or profile_rows(rows, columns)
    column_profiles: dict[str, Any] = profile.get("column_profiles", {})

    data: dict[str, Any] = {}
    roles: dict[str, ColumnRole] = {}
    for name in columns:
        info = column_profiles.get(name, {})
        semantic = str(info.get("semantic_type", "text"))
        raw = [row.get(name) for row in rows]
        missing_rate = float(info.get("missing_rate", 0.0) or 0.0)
        distinct = int(info.get("distinct_count", 0) or 0)
        role = ColumnRole(name, semantic, "text", missing_rate, distinct)
        lowered = name.casefold()

        if semantic == "empty" or distinct == 0:
            role.role = "empty"
            data[name] = pd.Series([None] * len(rows), dtype="object")
        elif semantic == "date" or (
            semantic in {"text", "categorical", "identifier"}
            and info.get("temporal", {}).get("parsable", 0)
            >= 0.9 * max(1, info.get("present_count", 0))
        ):
            data[name] = _parse_dates(raw, info)
            role.role = "time" if data[name].notna().mean() > 0.5 else "text"
            if info.get("temporal", {}).get("day_month_ambiguous"):
                role.notes.append("day_month_ambiguous")
        elif semantic == "boolean":
            data[name] = pd.Series(
                [coerce_boolean(v) if v not in (None, "") else None for v in raw], dtype="object"
            ).map(lambda v: None if v is None else float(bool(v)))
            data[name] = pd.to_numeric(data[name], errors="coerce")
            role.role = "flag"
        elif semantic in {"number", "number_text"}:
            numbers = [coerce_number(v)[0] if v not in (None, "") else None for v in raw]
            series = pd.to_numeric(pd.Series(numbers, dtype="object"), errors="coerce")
            data[name] = series
            unique = series.dropna().unique()
            is_binary = len(unique) == 2 and set(np.round(unique, 6)) <= {0.0, 1.0}
            integer_like = bool(len(unique)) and bool(np.all(np.mod(unique, 1) == 0))
            if is_binary:
                role.role = "flag"
            elif _non_measure_name(name) or (
                integer_like and len(unique) <= 7 and len(series.dropna()) > 30
            ):
                # Years, codes and short ordinal scales are sliced by, not summed.
                role.role = "dimension"
                if not _non_measure_name(name):
                    role.notes.append("ordinal_scale")
                data[name] = series.map(lambda v: None if pd.isna(v) else f"{v:g}")
            else:
                role.role = "measure"
                role.kpi_score = _kpi_score(name)
                role.is_money = is_money(name)
                non_null = series.dropna()
                percent_name = bool(re.search(r"rate|ratio|pct|percent|share|نسبة|معدل", lowered))
                bounded_unit = bool(
                    not non_null.empty and non_null.between(0, 1).all() and non_null.std() > 0
                )
                role.is_rate = percent_name or bounded_unit
                if (
                    role.is_rate
                    and not bounded_unit
                    and not non_null.empty
                    and non_null.max() <= 100
                ):
                    role.rate_scale = 100.0
                elif role.is_rate and not bounded_unit:
                    role.is_rate = False
                role.additive = not role.is_rate and (
                    role.kpi_score not in AVERAGED_SCORES and role.kpi_score >= 0.6
                )
        elif semantic == "identifier":
            data[name] = pd.Series([None if v in (None, "") else str(v) for v in raw])
            unique = bool(info.get("is_unique"))
            role.unique_key = unique
            # A key that never repeats identifies the row itself (an entity table such as
            # a customer list); one that repeats is an entity the rows are about.
            role.role = (
                "entity" if re.search(ENTITY_PATTERNS, lowered) and not unique else "identifier"
            )
        else:
            values = pd.Series([None if v in (None, "") else str(v).strip() for v in raw])
            data[name] = values
            present = max(1, int(values.notna().sum()))
            if info.get("is_constant"):
                role.role = "constant"
            elif re.search(TARGET_FLAG_PATTERNS, lowered) and distinct == 2:
                role.role = "flag"
                positive = _positive_label(values)
                data[name] = values.map(
                    lambda v, p=positive: None if v is None else float(str(v) == p)
                )
            elif info.get("is_unique") and present > 20:
                role.role = "identifier"
                role.unique_key = True
            elif re.search(ENTITY_PATTERNS, lowered) and distinct > 20 and distinct < present:
                role.role = "entity"
            elif distinct <= max(2, min(60, present // 3)) or (
                semantic == "categorical" and distinct <= 200
            ):
                role.role = "dimension"
            elif distinct < present * 0.5 and distinct <= 5000:
                role.role = "entity" if re.search(ENTITY_PATTERNS, lowered) else "dimension"
            else:
                role.role = "text"
        if info.get("is_constant") and role.role in {"measure", "dimension"}:
            role.role = "constant"
        roles[name] = role

    df = pd.DataFrame(data, columns=columns)
    time_columns = [name for name, role in roles.items() if role.role == "time"]
    time_column = _choose_time_column(df, time_columns)
    measures = sorted(
        (name for name, role in roles.items() if role.role == "measure"),
        key=lambda name: (-roles[name].kpi_score, columns.index(name)),
    )
    dimensions = [name for name, role in roles.items() if role.role == "dimension"]
    # High-cardinality dimensions are less useful to slice by; keep the readable ones first.
    dimensions.sort(key=lambda name: (roles[name].distinct_count > 30, roles[name].distinct_count))
    entities = [name for name, role in roles.items() if role.role == "entity"]
    flags = [name for name, role in roles.items() if role.role == "flag"]
    outcome = next(
        (name for name in flags if re.search(TARGET_FLAG_PATTERNS, name.casefold())), None
    )
    primary_kpi = _choose_primary_kpi(df, measures, roles)
    entity_table = any(
        role.unique_key and re.search(ENTITY_PATTERNS, name.casefold())
        for name, role in roles.items()
    )
    if outcome and primary_kpi and (entity_table or roles[primary_kpi].kpi_score < 0.75):
        # A table of customers (one row each) with a churn/attrition flag is about that
        # outcome, not about whichever number happens to vary most. Transaction tables
        # (orders with a "returned" flag) keep their money KPI as the focus.
        primary_kpi = None
    return AnalysisFrame(
        df=df,
        profile=profile,
        roles=roles,
        time_column=time_column,
        measures=measures,
        dimensions=dimensions,
        entities=entities,
        flags=flags,
        primary_kpi=primary_kpi,
        outcome=outcome,
        row_count=total_rows,
        truncated=truncated,
    )


def _positive_label(values: pd.Series) -> str:
    labels = sorted(values.dropna().astype(str).unique())
    positive_words = r"^(yes|y|true|1|churned|returned|cancel+ed|left|won|converted|نعم)$"
    for label in labels:
        if re.search(positive_words, label.strip().casefold()):
            return label
    counts = values.dropna().astype(str).value_counts()
    return str(counts.index[-1])  # the rarer class is usually the event of interest


def _parse_dates(raw: list[Any], info: dict[str, Any]) -> pd.Series:
    pattern = info.get("temporal", {}).get("strptime_pattern")
    parsed: list[datetime | None] = []
    for value in raw:
        if value in (None, ""):
            parsed.append(None)
            continue
        text = str(value).strip()
        result: datetime | None = None
        if pattern:
            try:
                result = datetime.strptime(text, pattern)
            except ValueError:
                result = None
        if result is None:
            try:
                stamp = pd.Timestamp(text)
                result = None if pd.isna(stamp) else stamp.to_pydatetime().replace(tzinfo=None)
            except (ValueError, TypeError, OverflowError):
                result = None
        parsed.append(result)
    return pd.to_datetime(pd.Series(parsed, dtype="object"), errors="coerce")


def _choose_time_column(df: pd.DataFrame, candidates: list[str]) -> str | None:
    if not candidates:
        return None
    preferred = r"order|transaction|sale|invoice|created|date|تاريخ|طلب"

    def score(name: str) -> tuple[int, float, int]:
        series = df[name]
        return (
            1 if re.search(preferred, name.casefold()) else 0,
            float(series.notna().mean()),
            int(series.nunique()),
        )

    return max(candidates, key=score)


def _choose_primary_kpi(
    df: pd.DataFrame, measures: list[str], roles: dict[str, ColumnRole]
) -> str | None:
    if not measures:
        return None

    def score(name: str) -> float:
        series = df[name].dropna()
        coverage = len(series) / max(1, len(df))
        variability = 0.0
        if len(series) > 1 and series.mean() != 0:
            variability = min(1.0, float(series.std() / abs(series.mean())))
        return roles[name].kpi_score * 2 + coverage + 0.3 * variability

    return max(measures, key=score)
