"""Descriptive statistics, relationships and hypothesis tests an analyst would run.

Each test chooses its method from the data (normality and group sizes), reports an
effect size next to the p-value (a significant but tiny effect is not a business
finding), and states its sample size. Batches of tests are corrected for multiple
comparisons with Benjamini-Hochberg before anything is called significant.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats as sps

from ...errors import AppError
from ..common import bi, clean, fmt, pct, safe_div
from ..frame import AnalysisFrame

MIN_GROUP = 8


def describe(frame: AnalysisFrame, columns: list[str] | None = None) -> dict[str, Any]:
    names = [frame.require(c) for c in columns] if columns else frame.measures[:12]
    numeric: list[dict[str, Any]] = []
    categorical: list[dict[str, Any]] = []
    for name in names:
        role = frame.roles[name].role
        series = frame.df[name]
        if role in {"measure", "flag"} or pd.api.types.is_numeric_dtype(series):
            values = pd.to_numeric(series, errors="coerce").dropna()
            if values.empty:
                continue
            q1, q3 = values.quantile([0.25, 0.75])
            iqr = q3 - q1
            outliers = int(((values < q1 - 1.5 * iqr) | (values > q3 + 1.5 * iqr)).sum())
            numeric.append(
                {
                    "column": name,
                    "count": int(values.count()),
                    "missing": int(series.isna().sum()),
                    "sum": float(values.sum()),
                    "mean": float(values.mean()),
                    "median": float(values.median()),
                    "std": float(values.std()) if len(values) > 1 else 0.0,
                    "min": float(values.min()),
                    "p05": float(values.quantile(0.05)),
                    "p25": float(q1),
                    "p75": float(q3),
                    "p95": float(values.quantile(0.95)),
                    "max": float(values.max()),
                    "skew": float(values.skew()) if len(values) > 2 else None,
                    "kurtosis": float(values.kurt()) if len(values) > 3 else None,
                    "cv": safe_div(float(values.std()), abs(float(values.mean())))
                    if len(values) > 1
                    else None,
                    "outliers_iqr": outliers,
                    "zeros": int((values == 0).sum()),
                    "negatives": int((values < 0).sum()),
                }
            )
        else:
            counts = series.dropna().astype(str).value_counts()
            present = int(counts.sum())
            categorical.append(
                {
                    "column": name,
                    "count": present,
                    "missing": int(series.isna().sum()),
                    "distinct": int(counts.size),
                    "top": [
                        {"value": str(k), "count": int(v), "share": v / present if present else 0}
                        for k, v in counts.head(10).items()
                    ],
                }
            )
    return clean({"numeric": numeric, "categorical": categorical, "method": "descriptive"})


def distribution(frame: AnalysisFrame, column: str, bins: int = 20) -> dict[str, Any]:
    name = frame.require(column)
    values = frame.numeric(name).dropna()
    if len(values) < 5:
        raise AppError(422, "insufficient_data", f"{name!r} has too few numeric values.")
    counts, edges = np.histogram(values, bins=min(bins, max(5, int(math.sqrt(len(values))))))
    sample = values.sample(min(len(values), 5000), random_state=7) if len(values) > 5000 else values
    normal_p = float(sps.normaltest(sample).pvalue) if len(sample) >= 20 else None
    skew = float(values.skew())
    shape = (
        "right_skewed"
        if skew > 1
        else "left_skewed"
        if skew < -1
        else "moderately_skewed"
        if abs(skew) > 0.5
        else "roughly_symmetric"
    )
    labels = [f"{fmt(edges[i])}–{fmt(edges[i + 1])}" for i in range(len(counts))]
    return clean(
        {
            "column": name,
            "n": int(len(values)),
            "shape": shape,
            "skew": skew,
            "normality_p": normal_p,
            "is_normal": normal_p is not None and normal_p > 0.05,
            "histogram": [
                {"bin": labels[i], "low": edges[i], "high": edges[i + 1], "count": int(c)}
                for i, c in enumerate(counts)
            ],
            "chart": {
                "type": "bar",
                "title": bi(f"Distribution of {name}", f"توزيع {name}"),
                "x": labels,
                "series": [{"name": "count", "data": [int(c) for c in counts]}],
            },
            "method": "histogram_and_dagostino_pearson_normality",
        }
    )


def correlations(
    frame: AnalysisFrame, columns: list[str] | None = None, method: str = "spearman"
) -> dict[str, Any]:
    names = [frame.require(c) for c in columns] if columns else (frame.measures + frame.flags)[:12]
    names = [n for n in names if pd.api.types.is_numeric_dtype(frame.df[n])]
    if len(names) < 2:
        raise AppError(422, "insufficient_data", "At least two numeric columns are needed.")
    if method not in {"spearman", "pearson", "kendall"}:
        method = "spearman"
    data = frame.df[names].apply(pd.to_numeric, errors="coerce")
    matrix = data.corr(method=method, min_periods=10)
    pairs: list[dict[str, Any]] = []
    for i, left in enumerate(names):
        for right in names[i + 1 :]:
            joined = data[[left, right]].dropna()
            n = len(joined)
            if n < 10 or joined[left].std() == 0 or joined[right].std() == 0:
                continue
            if method == "pearson":
                result = sps.pearsonr(joined[left], joined[right])
            elif method == "kendall":
                result = sps.kendalltau(joined[left], joined[right])
            else:
                result = sps.spearmanr(joined[left], joined[right])
            coefficient = float(result[0])
            pairs.append(
                {
                    "a": left,
                    "b": right,
                    "r": coefficient,
                    "p_value": float(result[1]),
                    "n": n,
                    "strength": _strength(abs(coefficient)),
                    "direction": "positive" if coefficient > 0 else "negative",
                }
            )
    _benjamini_hochberg(pairs)
    pairs.sort(key=lambda item: -abs(item["r"]))
    return clean(
        {
            "method": method,
            "columns": names,
            "matrix": [[matrix.loc[a, b] for b in names] for a in names],
            "pairs": pairs,
            "top_pairs": [p for p in pairs if p["significant"] and abs(p["r"]) >= 0.3][:8],
            "chart": {
                "type": "heatmap",
                "title": bi("Correlation matrix", "مصفوفة الارتباط"),
                "x": names,
                "y": names,
                "values": [[matrix.loc[a, b] for b in names] for a in names],
            },
            "caveat": bi(
                "Correlation shows that two measures move together, not that one causes the other.",
                "الارتباط يعني أن المقياسين يتحركان معًا، ولا يعني أن أحدهما يسبب الآخر.",
            ),
        }
    )


def _strength(value: float) -> str:
    if value >= 0.7:
        return "very_strong"
    if value >= 0.5:
        return "strong"
    if value >= 0.3:
        return "moderate"
    if value >= 0.1:
        return "weak"
    return "negligible"


def _benjamini_hochberg(items: list[dict[str, Any]], alpha: float = 0.05) -> None:
    """Mark ``significant`` and ``q_value`` in place using the BH procedure."""

    if not items:
        return
    order = sorted(range(len(items)), key=lambda i: items[i]["p_value"])
    m = len(items)
    q_values = [0.0] * m
    running = 1.0
    for rank in range(m, 0, -1):
        index = order[rank - 1]
        running = min(running, items[index]["p_value"] * m / rank)
        q_values[index] = running
    for index, item in enumerate(items):
        item["q_value"] = q_values[index]
        item["significant"] = q_values[index] < alpha


def compare_groups(
    frame: AnalysisFrame,
    measure: str,
    dimension: str,
    max_groups: int = 12,
) -> dict[str, Any]:
    """Do the groups of a dimension differ on a measure, and by how much?"""

    measure = frame.require(measure)
    dimension = frame.require(dimension)
    values = frame.numeric(measure)
    groups = frame.df[dimension].astype("object")
    data = pd.DataFrame({"g": groups, "v": values}).dropna()
    if data.empty:
        raise AppError(422, "insufficient_data", "No rows have both values.")
    counts = data["g"].astype(str).value_counts()
    keep = counts[counts >= MIN_GROUP].index[:max_groups]
    data = data[data["g"].astype(str).isin(keep)]
    data["g"] = data["g"].astype(str)
    if data["g"].nunique() < 2:
        raise AppError(
            422,
            "insufficient_data",
            f"{dimension!r} needs at least two groups with {MIN_GROUP}+ rows each.",
        )
    summary = (
        data.groupby("g")["v"]
        .agg(["count", "mean", "median", "std", "sum"])
        .sort_values("mean", ascending=False)
    )
    samples = [data.loc[data["g"] == g, "v"].to_numpy() for g in summary.index]
    normal = all(
        len(s) < 5000 and (len(s) < 20 or sps.shapiro(s[:500]).pvalue > 0.05) for s in samples
    )
    overall_mean = float(data["v"].mean())
    if len(samples) == 2:
        if normal:
            test = sps.ttest_ind(samples[0], samples[1], equal_var=False)
            method = "welch_t_test"
        else:
            test = sps.mannwhitneyu(samples[0], samples[1], alternative="two-sided")
            method = "mann_whitney_u"
        pooled = math.sqrt((np.var(samples[0], ddof=1) + np.var(samples[1], ddof=1)) / 2)
        effect = (np.mean(samples[0]) - np.mean(samples[1])) / pooled if pooled else 0.0
        effect_name = "cohens_d"
        effect_size = abs(float(effect))
        magnitude = (
            "large"
            if effect_size >= 0.8
            else "medium"
            if effect_size >= 0.5
            else "small"
            if effect_size >= 0.2
            else "negligible"
        )
    else:
        if normal:
            test = sps.f_oneway(*samples)
            method = "one_way_anova"
        else:
            test = sps.kruskal(*samples)
            method = "kruskal_wallis"
        grand = data["v"].mean()
        between = sum(len(s) * (np.mean(s) - grand) ** 2 for s in samples)
        total = float(((data["v"] - grand) ** 2).sum())
        effect_size = float(between / total) if total else 0.0
        effect_name = "eta_squared"
        magnitude = (
            "large"
            if effect_size >= 0.14
            else "medium"
            if effect_size >= 0.06
            else "small"
            if effect_size >= 0.01
            else "negligible"
        )
    p_value = float(test.pvalue)
    top, bottom = summary.index[0], summary.index[-1]
    gap = float(summary.loc[top, "mean"] - summary.loc[bottom, "mean"])
    return clean(
        {
            "measure": measure,
            "dimension": dimension,
            "method": method,
            "p_value": p_value,
            "significant": p_value < 0.05,
            "effect_size": effect_size,
            "effect_metric": effect_name,
            "effect_magnitude": magnitude,
            "overall_mean": overall_mean,
            "groups": [
                {
                    "group": str(g),
                    "n": int(row["count"]),
                    "mean": float(row["mean"]),
                    "median": float(row["median"]),
                    "std": float(row["std"]) if not pd.isna(row["std"]) else None,
                    "sum": float(row["sum"]),
                    "vs_overall": safe_div(float(row["mean"]) - overall_mean, abs(overall_mean)),
                }
                for g, row in summary.iterrows()
            ],
            "top_group": str(top),
            "bottom_group": str(bottom),
            "gap": gap,
            "gap_ratio": safe_div(
                float(summary.loc[top, "mean"]), float(summary.loc[bottom, "mean"])
            ),
            "excluded_small_groups": int(counts[counts < MIN_GROUP].size),
            "chart": {
                "type": "bar",
                "title": bi(
                    f"Average {measure} by {dimension}", f"متوسط {measure} حسب {dimension}"
                ),
                "x": [str(g) for g in summary.index],
                "series": [{"name": f"mean {measure}", "data": summary["mean"].tolist()}],
                "reference": overall_mean,
            },
        }
    )


def association(frame: AnalysisFrame, a: str, b: str) -> dict[str, Any]:
    """Chi-square test of independence between two categorical columns, with Cramér's V."""

    a, b = frame.require(a), frame.require(b)
    data = frame.df[[a, b]].dropna().astype(str)
    top_a = data[a].value_counts().index[:15]
    top_b = data[b].value_counts().index[:15]
    data = data[data[a].isin(top_a) & data[b].isin(top_b)]
    table = pd.crosstab(data[a], data[b])
    if table.shape[0] < 2 or table.shape[1] < 2:
        raise AppError(422, "insufficient_data", "Both columns need at least two categories.")
    chi2, p_value, dof, expected = sps.chi2_contingency(table)
    n = int(table.to_numpy().sum())
    v = math.sqrt(chi2 / (n * (min(table.shape) - 1))) if n else 0.0
    residuals = (table - expected) / np.sqrt(expected)
    stacked = residuals.stack().sort_values(key=lambda s: -s.abs())
    return clean(
        {
            "a": a,
            "b": b,
            "method": "chi_square_independence",
            "chi2": chi2,
            "dof": dof,
            "p_value": p_value,
            "significant": p_value < 0.05,
            "cramers_v": v,
            "strength": _strength(v),
            "n": n,
            "low_expected_cells": int((expected < 5).sum()),
            "notable_combinations": [
                {
                    a: str(idx[0]),
                    b: str(idx[1]),
                    "observed": int(table.loc[idx[0], idx[1]]),
                    "expected": float(
                        expected[table.index.get_loc(idx[0]), table.columns.get_loc(idx[1])]
                    ),
                    "direction": "over" if val > 0 else "under",
                    "std_residual": float(val),
                }
                for idx, val in stacked.head(6).items()
            ],
        }
    )


def concentration(frame: AnalysisFrame, measure: str | None, dimension: str) -> dict[str, Any]:
    """How concentrated is a total across the members of a dimension (Pareto / HHI)?"""

    dimension = frame.require(dimension)
    data = frame.df
    if measure:
        measure = frame.require(measure)
        totals = (
            pd.DataFrame({"k": data[dimension].astype(str), "v": frame.numeric(measure)})
            .dropna()
            .groupby("k")["v"]
            .sum()
        )
    else:
        totals = data[dimension].dropna().astype(str).value_counts()
    totals = totals[totals > 0].sort_values(ascending=False)
    if totals.empty:
        raise AppError(422, "insufficient_data", "Nothing positive to concentrate.")
    grand = float(totals.sum())
    shares = totals / grand
    cumulative = shares.cumsum()
    members_for_80 = int((cumulative < 0.8).sum() + 1)
    hhi = float((shares**2).sum())
    top = totals.head(15)
    return clean(
        {
            "measure": measure or "row_count",
            "dimension": dimension,
            "members": int(len(totals)),
            "total": grand,
            "top_share": float(shares.iloc[0]),
            "top3_share": float(shares.head(3).sum()),
            "top10pct_share": float(shares.head(max(1, len(shares) // 10)).sum()),
            "members_for_80pct": members_for_80,
            "members_for_80pct_share": members_for_80 / len(totals),
            "hhi": hhi,
            "concentration_level": "high" if hhi > 0.25 else "moderate" if hhi > 0.15 else "low",
            "top_members": [
                {"member": str(k), "value": float(v), "share": float(shares[k])}
                for k, v in top.items()
            ],
            "chart": {
                "type": "pareto",
                "title": bi(
                    f"{measure or 'Rows'} by {dimension}", f"{measure or 'السجلات'} حسب {dimension}"
                ),
                "x": [str(k) for k in top.index],
                "series": [
                    {"name": measure or "count", "data": top.tolist()},
                    {"name": "cumulative_share", "data": cumulative.head(15).tolist()},
                ],
            },
            "method": "pareto_and_herfindahl_index",
            "summary": bi(
                f"Top {members_for_80} of {len(totals)} {dimension} values hold 80% of "
                f"{measure or 'rows'}; the largest holds {pct(float(shares.iloc[0]))}.",
                f"أعلى {members_for_80} من أصل {len(totals)} قيمة في {dimension} تستحوذ على 80% من "
                f"{measure or 'السجلات'}؛ وأكبرها يستحوذ على {pct(float(shares.iloc[0]))}.",
            ),
        }
    )


def benjamini_hochberg(items: list[dict[str, Any]], alpha: float = 0.05) -> list[dict[str, Any]]:
    """Public wrapper used by agents correcting a batch of tests."""

    _benjamini_hochberg(items, alpha)
    return items
