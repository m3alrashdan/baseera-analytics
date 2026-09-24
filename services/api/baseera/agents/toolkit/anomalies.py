"""Anomalies in time and in records.

* In time: robust local-level deviations (MAD z-scores) on the aggregated series.
* In records: an Isolation Forest over the numeric measures, with an explanation of
  *why* each flagged record is unusual (which of its values sit furthest from typical,
  in robust z-score terms). A flag without a reason is not actionable.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from ...errors import AppError
from ...forecasting import detect_anomalies
from ..common import bi, clean
from ..frame import AnalysisFrame
from .timeseries import SEASONAL_PERIOD, build_series


def series_anomalies(
    frame: AnalysisFrame,
    measure: str | None,
    agg: str = "sum",
    grain: str | None = None,
    filters: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    series = build_series(frame, measure, agg, grain, filters)
    flags = detect_anomalies(
        series["periods"], series["values"], max(2, SEASONAL_PERIOD[series["grain"]])
    )
    return clean(
        {
            **{k: v for k, v in series.items() if k not in {"values"}},
            "anomalies": flags,
            "count": len(flags),
            "method": "rolling_median_with_mad_robust_z_threshold_3.5",
            "chart": {
                "type": "line",
                "title": bi("Unusual periods", "فترات غير اعتيادية"),
                "x": series["periods"],
                "series": [{"name": measure or "records", "data": series["values"]}],
                "markers": [{"x": f["period"], "label": f["direction"]} for f in flags],
            },
        }
    )


def record_anomalies(
    frame: AnalysisFrame,
    columns: list[str] | None = None,
    contamination: float = 0.01,
    top: int = 15,
) -> dict[str, Any]:
    names = [frame.require(c) for c in columns] if columns else frame.measures[:10]
    names = [n for n in names if pd.api.types.is_numeric_dtype(frame.df[n])]
    if not names:
        raise AppError(422, "insufficient_data", "Record anomalies need numeric measures.")
    data = frame.df[names].apply(pd.to_numeric, errors="coerce")
    usable = data.dropna(thresh=max(1, len(names) // 2))
    if len(usable) < 50:
        raise AppError(422, "insufficient_data", "At least 50 records are needed.")
    medians = usable.median()
    mads = (usable - medians).abs().median() * 1.4826
    mads = mads.replace(0, np.nan).fillna(usable.std().replace(0, 1.0)).fillna(1.0)
    filled = usable.fillna(medians)
    robust = (filled - medians) / mads
    contamination = float(min(max(contamination, 0.001), 0.1))
    model = IsolationForest(
        n_estimators=200, contamination=contamination, random_state=20260630, n_jobs=1
    )
    sample = robust if len(robust) <= 50_000 else robust.sample(50_000, random_state=1)
    model.fit(sample.to_numpy())
    scores = -model.score_samples(robust.to_numpy())
    flagged = model.predict(robust.to_numpy()) == -1
    order = np.argsort(-scores)
    context_columns = [
        c for c in [frame.time_column, *frame.dimensions[:3], *frame.entities[:1]] if c
    ]
    records: list[dict[str, Any]] = []
    for position in order[:top]:
        if not flagged[position]:
            continue
        index = robust.index[position]
        deviations = robust.loc[index].abs().sort_values(ascending=False)
        reasons = [
            {
                "column": column,
                "value": float(filled.loc[index, column]),
                "typical": float(medians[column]),
                "robust_z": float(robust.loc[index, column]),
            }
            for column in deviations.index[:3]
            if abs(robust.loc[index, column]) >= 2.5
        ]
        record = {
            "row": int(index),
            "score": float(scores[position]),
            "reasons": reasons,
            "context": {c: frame.df.loc[index, c] for c in context_columns},
        }
        records.append(record)
    return clean(
        {
            "columns": names,
            "records_scanned": int(len(robust)),
            "flagged": int(flagged.sum()),
            "flagged_share": float(flagged.mean()),
            "top_records": records,
            "method": "isolation_forest_on_robust_scaled_measures",
            "summary": bi(
                f"{int(flagged.sum())} of {len(robust)} records "
                f"({flagged.mean() * 100:.1f}%) look unusual across {', '.join(names)}.",
                f"{int(flagged.sum())} من أصل {len(robust)} سجلًا "
                f"({flagged.mean() * 100:.1f}%) تبدو غير اعتيادية عبر {', '.join(names)}.",
            ),
        }
    )
