"""The tool registry: every capability an agent may use, typed and validated.

A tool has a JSON schema (sent to the language model), an owning specialist, a
deterministic handler over the analysis frame, and a compact summariser that turns a
large result into something a model can read without blowing its context. Full
results are kept as evidence and shown to the user; the model sees the digest.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ..errors import AppError
from .frame import AnalysisFrame
from .toolkit import anomalies, drivers, overview, query, segments, stats, timeseries, variance

Handler = Callable[[AnalysisFrame, dict[str, Any]], dict[str, Any]]

FILTERS_SCHEMA: dict[str, Any] = {
    "type": "array",
    "description": "Optional row filters applied before the analysis.",
    "items": {
        "type": "object",
        "properties": {
            "column": {"type": "string"},
            "op": {
                "type": "string",
                "enum": sorted(query.FILTER_OPS),
            },
            "value": {"description": "Value, list of values, or [low, high] for between."},
        },
        "required": ["column", "op"],
    },
}
GRAIN_SCHEMA = {"type": "string", "enum": ["day", "week", "month", "quarter", "year"]}


@dataclass(frozen=True, slots=True)
class Tool:
    name: str
    agent: str
    description: str
    schema: dict[str, Any]
    handler: Handler
    title_en: str
    title_ar: str

    def spec(self) -> dict[str, Any]:
        return {"name": self.name, "description": self.description, "input_schema": self.schema}


def _obj(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {"type": "object", "properties": properties, "required": required or []}


TOOLS: dict[str, Tool] = {}


def register(tool: Tool) -> None:
    TOOLS[tool.name] = tool


register(
    Tool(
        "describe_dataset",
        "data_engineer",
        "Return the semantic model of the dataset (time column, measures, dimensions, "
        "entities, primary KPI), data-quality issues and which analyses the data supports. "
        "Call this first when you are unsure what the columns mean.",
        _obj({}),
        lambda f, a: overview.data_health(f),
        "Data health & schema",
        "صحة البيانات وبنيتها",
    )
)
register(
    Tool(
        "headline_kpis",
        "statistician",
        "Headline totals for the main measures with latest-period and year-over-year change.",
        _obj({}),
        lambda f, a: overview.headline_kpis(f),
        "Headline KPIs",
        "المؤشرات الرئيسية",
    )
)
register(
    Tool(
        "query_data",
        "statistician",
        "Run a validated aggregate query: filters, optional time_grain over the date column, "
        "up to 3 group_by columns, metrics with agg in sum|mean|median|min|max|count|nunique|"
        "std|share, sort and limit. Use for any 'how much / how many / top N / by X' question.",
        _obj(
            {
                "filters": FILTERS_SCHEMA,
                "group_by": {"type": "array", "items": {"type": "string"}, "maxItems": 3},
                "time_grain": GRAIN_SCHEMA,
                "metrics": {
                    "type": "array",
                    "items": _obj(
                        {
                            "column": {"type": "string"},
                            "agg": {"type": "string", "enum": sorted(query.AGGREGATIONS)},
                            "as": {"type": "string"},
                        },
                        ["agg"],
                    ),
                    "maxItems": 6,
                },
                "sort": _obj({"by": {"type": "string"}, "desc": {"type": "boolean"}}),
                "limit": {"type": "integer", "minimum": 1, "maximum": 200},
            }
        ),
        lambda f, a: query.run_query(f, a),
        "Data query",
        "استعلام البيانات",
    )
)
register(
    Tool(
        "describe_columns",
        "statistician",
        "Descriptive statistics (mean, median, spread, percentiles, skew, outliers) for columns.",
        _obj({"columns": {"type": "array", "items": {"type": "string"}}}),
        lambda f, a: stats.describe(f, a.get("columns")),
        "Descriptive statistics",
        "الإحصاء الوصفي",
    )
)
register(
    Tool(
        "distribution",
        "statistician",
        "Histogram, shape and normality test of one numeric column.",
        _obj({"column": {"type": "string"}}, ["column"]),
        lambda f, a: stats.distribution(f, a["column"]),
        "Distribution",
        "التوزيع",
    )
)
register(
    Tool(
        "correlations",
        "statistician",
        "Correlation matrix and significant pairs (Benjamini-Hochberg corrected) among "
        "numeric columns. method: spearman (default), pearson or kendall.",
        _obj(
            {
                "columns": {"type": "array", "items": {"type": "string"}},
                "method": {"type": "string", "enum": ["spearman", "pearson", "kendall"]},
            }
        ),
        lambda f, a: stats.correlations(f, a.get("columns"), a.get("method", "spearman")),
        "Correlations",
        "الارتباطات",
    )
)
register(
    Tool(
        "compare_groups",
        "statistician",
        "Test whether groups of a dimension differ on a measure (t-test / Mann-Whitney / "
        "ANOVA / Kruskal chosen automatically) with effect size and group means.",
        _obj(
            {"measure": {"type": "string"}, "dimension": {"type": "string"}},
            ["measure", "dimension"],
        ),
        lambda f, a: stats.compare_groups(f, a["measure"], a["dimension"]),
        "Group comparison",
        "مقارنة المجموعات",
    )
)
register(
    Tool(
        "association",
        "statistician",
        "Chi-square test and Cramér's V between two categorical columns, with the "
        "combinations that are over- or under-represented.",
        _obj({"a": {"type": "string"}, "b": {"type": "string"}}, ["a", "b"]),
        lambda f, a: stats.association(f, a["a"], a["b"]),
        "Association test",
        "اختبار الاستقلالية",
    )
)
register(
    Tool(
        "concentration",
        "statistician",
        "Pareto / Herfindahl concentration of a measure (or of row counts) across the members "
        "of a dimension or entity: top shares and how many members make 80%.",
        _obj({"measure": {"type": "string"}, "dimension": {"type": "string"}}, ["dimension"]),
        lambda f, a: stats.concentration(f, a.get("measure"), a["dimension"]),
        "Concentration (Pareto)",
        "التركّز (باريتو)",
    )
)
register(
    Tool(
        "trend",
        "forecaster",
        "Trend of a measure over time: direction and significance (Mann-Kendall), robust "
        "slope, growth rates, seasonality, level shifts and anomalous periods. agg: "
        "sum|mean|median|count|nunique. Omit measure with agg=count to trend record counts.",
        _obj(
            {
                "measure": {"type": "string"},
                "agg": {"type": "string", "enum": ["sum", "mean", "median", "count", "nunique"]},
                "grain": GRAIN_SCHEMA,
                "filters": FILTERS_SCHEMA,
            }
        ),
        lambda f, a: timeseries.trend(
            f, a.get("measure"), a.get("agg", "sum"), a.get("grain"), a.get("filters")
        ),
        "Trend analysis",
        "تحليل الاتجاه",
    )
)
register(
    Tool(
        "forecast",
        "forecaster",
        "Forecast a measure with a backtested model tournament and calibrated prediction "
        "intervals; reports holdout accuracy (WAPE, MASE) and whether it beats a naive "
        "benchmark. horizon is in periods of the grain.",
        _obj(
            {
                "measure": {"type": "string"},
                "agg": {"type": "string", "enum": ["sum", "mean", "median", "count", "nunique"]},
                "horizon": {"type": "integer", "minimum": 1, "maximum": 36},
                "grain": GRAIN_SCHEMA,
                "filters": FILTERS_SCHEMA,
                "interval": {"type": "number", "minimum": 0.5, "maximum": 0.99},
            }
        ),
        lambda f, a: timeseries.forecast(
            f,
            a.get("measure"),
            a.get("agg", "sum"),
            a.get("horizon"),
            a.get("grain"),
            a.get("filters"),
            float(a.get("interval", 0.9)),
        ),
        "Forecast",
        "التنبؤ",
    )
)
register(
    Tool(
        "seasonality_profile",
        "forecaster",
        "Month-of-year and day-of-week index of a measure (1.0 = average).",
        _obj({"measure": {"type": "string"}, "agg": {"type": "string", "enum": ["sum", "mean"]}}),
        lambda f, a: timeseries.seasonality_profile(f, a.get("measure"), a.get("agg", "sum")),
        "Seasonality profile",
        "النمط الموسمي",
    )
)
register(
    Tool(
        "explain_change",
        "detective",
        "Explain why a measure changed between two periods: exact contribution of every "
        "member of each dimension (or mix vs rate for averages) and a two-level root-cause "
        "path. compare: previous|year_ago. Periods use the grain's labels (e.g. 2026-05, "
        "2026-Q2).",
        _obj(
            {
                "measure": {"type": "string"},
                "agg": {"type": "string", "enum": ["sum", "count", "mean"]},
                "grain": GRAIN_SCHEMA,
                "period_before": {"type": "string"},
                "period_after": {"type": "string"},
                "compare": {"type": "string", "enum": ["previous", "year_ago"]},
                "dimensions": {"type": "array", "items": {"type": "string"}},
                "filters": FILTERS_SCHEMA,
            }
        ),
        lambda f, a: variance.explain_change(
            f,
            a.get("measure"),
            a.get("agg", "sum"),
            a.get("grain"),
            a.get("period_before"),
            a.get("period_after"),
            a.get("compare", "previous"),
            a.get("dimensions"),
            a.get("filters"),
        ),
        "Change explanation",
        "تفسير التغيّر",
    )
)
register(
    Tool(
        "series_anomalies",
        "detective",
        "Unusual periods in a measure's time series (robust local deviations).",
        _obj(
            {
                "measure": {"type": "string"},
                "agg": {"type": "string", "enum": ["sum", "mean", "count"]},
                "grain": GRAIN_SCHEMA,
                "filters": FILTERS_SCHEMA,
            }
        ),
        lambda f, a: anomalies.series_anomalies(
            f, a.get("measure"), a.get("agg", "sum"), a.get("grain"), a.get("filters")
        ),
        "Unusual periods",
        "الفترات غير الاعتيادية",
    )
)
register(
    Tool(
        "record_anomalies",
        "detective",
        "Unusual individual records across numeric measures (Isolation Forest) with the "
        "reason each is unusual.",
        _obj(
            {
                "columns": {"type": "array", "items": {"type": "string"}},
                "contamination": {"type": "number", "minimum": 0.001, "maximum": 0.1},
            }
        ),
        lambda f, a: anomalies.record_anomalies(
            f, a.get("columns"), float(a.get("contamination", 0.01))
        ),
        "Unusual records",
        "السجلات غير الاعتيادية",
    )
)
register(
    Tool(
        "key_drivers",
        "data_scientist",
        "What drives a target (numeric measure or yes/no outcome): cross-validated model "
        "tournament, grouped permutation importance, direction and size of each driver. "
        "Excludes sibling outcomes and arithmetic identities by default.",
        _obj(
            {
                "target": {"type": "string"},
                "features": {"type": "array", "items": {"type": "string"}},
                "filters": FILTERS_SCHEMA,
            },
            ["target"],
        ),
        lambda f, a: drivers.key_drivers(f, a["target"], a.get("features"), a.get("filters")),
        "Key drivers",
        "العوامل المؤثرة",
    )
)
register(
    Tool(
        "what_if",
        "strategist",
        "Model-based what-if: change levers (percent_change, set_to or add for numeric; "
        "set_to a category for dimensions) and see the modelled effect on the target.",
        _obj(
            {
                "target": {"type": "string"},
                "changes": {
                    "type": "array",
                    "items": _obj(
                        {
                            "column": {"type": "string"},
                            "percent_change": {"type": "number"},
                            "set_to": {},
                            "add": {"type": "number"},
                        },
                        ["column"],
                    ),
                    "minItems": 1,
                    "maxItems": 6,
                },
                "filters": FILTERS_SCHEMA,
                "exclude": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Columns to leave out of the model (e.g. recorded after the outcome).",
                },
            },
            ["target", "changes"],
        ),
        lambda f, a: drivers.what_if(
            f, a["target"], a["changes"], a.get("filters"), a.get("exclude")
        ),
        "What-if scenario",
        "سيناريو ماذا لو",
    )
)
register(
    Tool(
        "segment",
        "data_scientist",
        "Find natural segments of records (k-means with k chosen by silhouette) and profile "
        "what makes each segment different.",
        _obj(
            {
                "features": {"type": "array", "items": {"type": "string"}},
                "k": {"type": "integer", "minimum": 2, "maximum": 8},
                "filters": FILTERS_SCHEMA,
            }
        ),
        lambda f, a: segments.segment(f, a.get("features"), a.get("k"), a.get("filters")),
        "Segmentation",
        "التقسيم إلى شرائح",
    )
)
register(
    Tool(
        "customer_value_tiers",
        "data_scientist",
        "RFM (recency, frequency, monetary) tiers of an entity column such as customers: "
        "Champions, Loyal, At risk, Hibernating, with each tier's share of value.",
        _obj({"entity": {"type": "string"}, "monetary": {"type": "string"}}),
        lambda f, a: segments.rfm(f, a.get("entity"), a.get("monetary")),
        "Customer value tiers (RFM)",
        "شرائح قيمة العملاء (RFM)",
    )
)
register(
    Tool(
        "cohort_retention",
        "data_scientist",
        "Retention of entities (customers) by the period they first appeared.",
        _obj(
            {
                "entity": {"type": "string"},
                "grain": {"type": "string", "enum": ["week", "month", "quarter"]},
            }
        ),
        lambda f, a: segments.cohorts(f, a.get("entity"), a.get("grain", "month")),
        "Cohort retention",
        "الاحتفاظ حسب الدفعة",
    )
)

AGENT_TOOLS = sorted(TOOLS)


def execute(frame: AnalysisFrame, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    tool = TOOLS.get(name)
    if tool is None:
        raise AppError(422, "unknown_tool", f"{name!r} is not an available analysis tool.")
    if not isinstance(arguments, dict):
        raise AppError(422, "invalid_tool_arguments", "Tool arguments must be an object.")
    return tool.handler(frame, arguments)


# ------------------------------------------------------------------- digests for models
DROP_KEYS = {"chart", "matrix", "history", "predictions", "response_curve", "histogram", "values"}


def digest(result: dict[str, Any], limit: int = 5000) -> str:
    """A compact JSON view of a tool result for a language model."""

    def shrink(value: Any, depth: int = 0) -> Any:
        if isinstance(value, dict):
            return {
                k: shrink(v, depth + 1)
                for k, v in value.items()
                if k not in DROP_KEYS and not (k == "periods" and depth == 0)
            }
        if isinstance(value, list):
            items = value[:12] if depth < 3 else value[:5]
            shrunk = [shrink(v, depth + 1) for v in items]
            if len(value) > len(items):
                shrunk.append(f"... {len(value) - len(items)} more")
            return shrunk
        if isinstance(value, float):
            return round(value, 4)
        return value

    text = json.dumps(shrink(result), ensure_ascii=False, default=str)
    if len(text) > limit:
        text = text[:limit] + "…(truncated)"
    return text
