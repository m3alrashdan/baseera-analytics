"""Segmentation: natural groups in the records, customer value tiers and cohorts.

* ``segment``: k-means on robust-scaled measures, with k chosen by silhouette score
  (not fixed), and every segment profiled and named from what makes it different
  ("High revenue · Low discount"). An unprofiled cluster is not an insight.
* ``rfm``: recency / frequency / monetary scoring of an entity column (customers,
  accounts) into the standard actionable tiers (Champions, At risk, …).
* ``cohorts``: retention of entities by the period they first appeared.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import RobustScaler

from ...errors import AppError
from ..common import bi, clean, fmt, pct, safe_div
from ..frame import AnalysisFrame
from .query import add_period, apply_filters

SEGMENT_NAMES_AR = {"High": "مرتفع", "Low": "منخفض", "Typical": "معتاد"}


def segment(
    frame: AnalysisFrame,
    features: list[str] | None = None,
    k: int | None = None,
    filters: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if features:
        names = [frame.require(c) for c in features]
    else:
        # One money outcome is enough: revenue, cost and profit move together and would
        # otherwise make "big order" the only thing the clustering can see.
        names, money_seen = [], False
        for measure in frame.measures:
            role = frame.roles[measure]
            if role.kpi_score >= 0.75 and role.kpi_score != 0.55:
                if money_seen and measure != frame.primary_kpi:
                    continue
                money_seen = True
            names.append(measure)
        names = names[:6]
    names = [n for n in names if pd.api.types.is_numeric_dtype(frame.df[n])]
    if len(names) < 2:
        raise AppError(422, "insufficient_data", "Segmentation needs at least two measures.")
    df = apply_filters(frame, filters)
    data = df[names].apply(pd.to_numeric, errors="coerce").dropna()
    if len(data) < 60:
        raise AppError(422, "insufficient_data", "At least 60 complete records are needed.")
    # Heavy-tailed business measures (revenue, spend) cluster on scale alone unless
    # compressed; a signed log keeps order and tames the tail.
    transformed = data.apply(lambda s: np.sign(s) * np.log1p(np.abs(s)) if s.skew() > 1.5 else s)
    scaled = RobustScaler().fit_transform(transformed)
    # Clip extreme robust scores so a handful of data-entry errors cannot claim a cluster.
    scaled = np.clip(scaled, -6, 6)
    fit_index = (
        np.random.default_rng(5).choice(len(scaled), 8000, replace=False)
        if len(scaled) > 8000
        else np.arange(len(scaled))
    )
    sample_index = (
        np.random.default_rng(11).choice(len(scaled), 4000, replace=False)
        if len(scaled) > 4000
        else np.arange(len(scaled))
    )
    trials: list[dict[str, Any]] = []
    best_k, best_score, best_model = 0, -1.0, None
    options = [k] if k else list(range(2, 7))
    for candidate in options:
        if candidate < 2 or candidate >= len(data):
            continue
        model = KMeans(n_clusters=candidate, n_init=4, random_state=20260630)
        model.fit(scaled[fit_index])
        labels = model.predict(scaled)
        score = float(silhouette_score(scaled[sample_index], labels[sample_index]))
        sizes = np.bincount(labels, minlength=candidate) / len(labels)
        # Penalise a sliver cluster (rarely matters to a business) and prefer a richer
        # segmentation when it separates almost as well as a two-way split.
        adjusted = score - (0.1 if sizes.min() < 0.03 else 0.0) + 0.01 * (candidate - 2)
        trials.append({"k": candidate, "silhouette": score, "smallest_share": float(sizes.min())})
        if adjusted > best_score:
            best_k, best_score, best_model = candidate, adjusted, model
    if best_model is None:
        raise AppError(422, "insufficient_data", "No valid segmentation was found.")
    labels = best_model.predict(scaled)
    best_score = next(t["silhouette"] for t in trials if t["k"] == best_k)
    overall = data.mean()
    overall_std = data.std().replace(0, 1.0)
    segments: list[dict[str, Any]] = []
    for cluster in range(best_k):
        members = data[labels == cluster]
        means = members.mean()
        z = (means - overall) / overall_std
        order = z.abs().sort_values(ascending=False)
        traits = []
        for column in order.index[:2]:
            level = "High" if z[column] > 0.35 else "Low" if z[column] < -0.35 else "Typical"
            traits.append((level, column))
        name_en = " · ".join(f"{level} {column}" for level, column in traits)
        name_ar = " · ".join(f"{column} {SEGMENT_NAMES_AR[level]}" for level, column in traits)
        dims: dict[str, Any] = {}
        for dimension in frame.dimensions[:4]:
            values = df.loc[members.index, dimension].dropna().astype(str)
            if values.empty:
                continue
            share = values.value_counts(normalize=True)
            base = df[dimension].dropna().astype(str).value_counts(normalize=True)
            lift = (share / base.reindex(share.index)).fillna(1.0)
            top = lift.sort_values(ascending=False).index[0]
            dims[dimension] = {"value": top, "share": float(share[top]), "lift": float(lift[top])}
        segments.append(
            {
                "segment": cluster,
                "name": bi(name_en, name_ar),
                "size": int(len(members)),
                "share": float(len(members) / len(data)),
                "means": {c: float(means[c]) for c in names},
                "index_vs_overall": {
                    c: safe_div(float(means[c]), float(overall[c])) for c in names
                },
                "z_scores": {c: float(z[c]) for c in names},
                "over_represented": dims,
                "totals": {c: float(members[c].sum()) for c in names},
            }
        )
    segments.sort(key=lambda s: -s["size"])
    kpi = frame.primary_kpi if frame.primary_kpi in names else names[0]
    total_kpi = float(data[kpi].sum()) or 1.0
    for item in segments:
        item["share_of_primary_kpi"] = item["totals"][kpi] / total_kpi
    quality = "clear" if best_score >= 0.5 else "moderate" if best_score >= 0.3 else "weak"
    return clean(
        {
            "features": names,
            "k": best_k,
            "silhouette": best_score,
            "separation": quality,
            "trials": trials,
            "records": int(len(data)),
            "primary_kpi": kpi,
            "segments": segments,
            "chart": {
                "type": "scatter",
                "title": bi("Segments", "الشرائح"),
                "x_label": names[0],
                "y_label": names[1],
                "series": [
                    {
                        "name": item["name"]["en"],
                        "data": data.loc[labels == item["segment"], [names[0], names[1]]]
                        .head(400)
                        .to_numpy()
                        .tolist(),
                    }
                    for item in segments
                ],
            },
            "method": "kmeans_silhouette_selected_k_on_robust_scaled_measures",
            "summary": bi(
                f"{best_k} segments found (silhouette {best_score:.2f}, {quality} separation). "
                f"Largest: {segments[0]['name']['en']} ({pct(segments[0]['share'])} of records).",
                f"تم العثور على {best_k} شرائح (مؤشر الانفصال {best_score:.2f}). "
                f"أكبرها: {segments[0]['name']['ar']} ({pct(segments[0]['share'])} من السجلات).",
            ),
        }
    )


RFM_TIERS = [
    ("champions", "Champions", "الأبطال", lambda r, f, m: r >= 4 and f >= 4),
    ("loyal", "Loyal", "المخلصون", lambda r, f, m: f >= 4),
    ("big_spenders", "Big spenders", "كبار المنفقين", lambda r, f, m: m >= 5),
    ("promising", "Promising / new", "واعدون / جدد", lambda r, f, m: r >= 4 and f <= 2),
    ("at_risk", "At risk", "معرضون للفقدان", lambda r, f, m: r <= 2 and f >= 3),
    ("hibernating", "Hibernating / lost", "خاملون / مفقودون", lambda r, f, m: r <= 2),
    ("need_attention", "Need attention", "بحاجة لاهتمام", lambda r, f, m: True),
]


def rfm(
    frame: AnalysisFrame, entity: str | None = None, monetary: str | None = None
) -> dict[str, Any]:
    if not frame.time_column:
        raise AppError(422, "time_column_required", "RFM needs a date column.")
    entity = frame.require(entity) if entity else (frame.entities[0] if frame.entities else None)
    if not entity:
        raise AppError(422, "entity_required", "RFM needs a customer/account column.")
    monetary = frame.require(monetary) if monetary else frame.primary_kpi
    df = frame.df[[entity, frame.time_column]].copy()
    df["m"] = frame.numeric(monetary) if monetary else 1.0
    df = df.dropna(subset=[entity, frame.time_column])
    if df[entity].nunique() < 30:
        raise AppError(422, "insufficient_data", "RFM needs at least 30 distinct entities.")
    reference = df[frame.time_column].max() + pd.Timedelta(days=1)
    table = df.groupby(entity).agg(
        last=(frame.time_column, "max"),
        frequency=(frame.time_column, "count"),
        monetary=("m", "sum"),
    )
    table["recency_days"] = (reference - table["last"]).dt.days

    def score(series: pd.Series, reverse: bool = False) -> pd.Series:
        ranked = series.rank(method="first", ascending=not reverse)
        return pd.qcut(ranked, 5, labels=[1, 2, 3, 4, 5]).astype(int)

    table["R"] = score(table["recency_days"], reverse=True)
    table["F"] = score(table["frequency"])
    table["M"] = score(table["monetary"])
    tiers = []
    for _, row in table.iterrows():
        for key, _, _, rule in RFM_TIERS:
            if rule(row["R"], row["F"], row["M"]):
                tiers.append(key)
                break
    table["tier"] = tiers
    total_value = float(table["monetary"].sum()) or 1.0
    summary: list[dict[str, Any]] = []
    for key, en, ar, _ in RFM_TIERS:
        members = table[table["tier"] == key]
        if members.empty:
            continue
        summary.append(
            {
                "tier": key,
                "label": bi(en, ar),
                "entities": int(len(members)),
                "share_of_entities": len(members) / len(table),
                "value": float(members["monetary"].sum()),
                "share_of_value": float(members["monetary"].sum()) / total_value,
                "avg_recency_days": float(members["recency_days"].mean()),
                "avg_frequency": float(members["frequency"].mean()),
                "avg_value": float(members["monetary"].mean()),
            }
        )
    at_risk = next((s for s in summary if s["tier"] == "at_risk"), None)
    return clean(
        {
            "entity": entity,
            "monetary": monetary,
            "entities": int(len(table)),
            "reference_date": reference.date().isoformat(),
            "tiers": summary,
            "at_risk_value": at_risk["value"] if at_risk else 0.0,
            "chart": {
                "type": "bar",
                "title": bi("Customer value tiers (RFM)", "شرائح قيمة العملاء (RFM)"),
                "x": [s["label"]["en"] for s in summary],
                "x_ar": [s["label"]["ar"] for s in summary],
                "series": [
                    {"name": "share_of_value", "data": [s["share_of_value"] for s in summary]},
                    {
                        "name": "share_of_entities",
                        "data": [s["share_of_entities"] for s in summary],
                    },
                ],
            },
            "method": "rfm_quintile_scoring",
            "summary": bi(
                f"{len(table)} {entity} values scored; "
                + (
                    f"'At risk' holds {pct(at_risk['share_of_value'])} of value "
                    f"({fmt(at_risk['value'])})."
                    if at_risk
                    else "no at-risk tier detected."
                ),
                f"تم تقييم {len(table)} من {entity}؛ "
                + (
                    f"شريحة «معرضون للفقدان» تمثل {pct(at_risk['share_of_value'])} من القيمة "
                    f"({fmt(at_risk['value'])})."
                    if at_risk
                    else "لا توجد شريحة معرضة للفقدان."
                ),
            ),
        }
    )


def cohorts(
    frame: AnalysisFrame, entity: str | None = None, grain: str = "month"
) -> dict[str, Any]:
    if not frame.time_column:
        raise AppError(422, "time_column_required", "Cohorts need a date column.")
    entity = frame.require(entity) if entity else (frame.entities[0] if frame.entities else None)
    if not entity:
        raise AppError(422, "entity_required", "Cohorts need a customer/account column.")
    df = frame.df[[entity, frame.time_column]].dropna().copy()
    if grain not in {"month", "quarter", "week"}:
        grain = "month"
    df["period"] = add_period(df, frame.time_column, grain)
    first = df.groupby(entity)["period"].min().rename("cohort")
    df = df.join(first, on=entity)
    periods = sorted(df["period"].unique())
    position = {p: i for i, p in enumerate(periods)}
    df["age"] = df["period"].map(position) - df["cohort"].map(position)
    matrix = df.groupby(["cohort", "age"])[entity].nunique().unstack(fill_value=0)
    sizes = matrix[0] if 0 in matrix.columns else matrix.iloc[:, 0]
    retention = matrix.div(sizes, axis=0)
    retention = retention.tail(12)
    horizon = min(12, retention.shape[1])
    averages = [
        float(retention[a].iloc[: max(1, len(retention) - a)].mean())
        for a in range(horizon)
        if a in retention.columns
    ]
    return clean(
        {
            "entity": entity,
            "grain": grain,
            "cohorts": [
                {
                    "cohort": str(cohort),
                    "size": int(sizes.get(cohort, 0)),
                    "retention": [
                        float(retention.loc[cohort, a])
                        for a in range(horizon)
                        if a in retention.columns
                    ],
                }
                for cohort in retention.index
            ],
            "average_retention": averages,
            "period_1_retention": averages[1] if len(averages) > 1 else None,
            "chart": {
                "type": "heatmap",
                "title": bi("Cohort retention", "الاحتفاظ حسب الدفعة"),
                "x": [str(a) for a in range(horizon)],
                "y": [str(c) for c in retention.index],
                "values": retention.iloc[:, :horizon].to_numpy().tolist(),
            },
            "method": "first_seen_cohort_retention",
            "summary": bi(
                f"On average {pct(averages[1] if len(averages) > 1 else None)} of {entity} "
                f"return in the {grain} after their first.",
                f"في المتوسط يعود {pct(averages[1] if len(averages) > 1 else None)} من {entity} "
                "في الفترة التالية لأول ظهور.",
            ),
        }
    )
