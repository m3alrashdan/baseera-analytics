"""What drives a KPI, how predictable is it, and what if we change a lever?

The data-scientist agent's core tool. It:

1. Builds a feature matrix from measures, low-cardinality dimensions and calendar
   features, excluding identifiers and free text.
2. Guards against *definitional leakage*: when the target is (almost) an arithmetic
   identity of other columns (profit = revenue − cost), those columns would "explain"
   everything and teach nothing. They are reported as the identity and excluded.
3. Runs a model tournament (regularised linear vs gradient boosting) with 5-fold
   cross-validation and compares against a naive baseline, so a model that does not
   beat the baseline is reported as such.
4. Ranks drivers by grouped permutation importance on held-out data, and gives each
   a direction and a size in the KPI's own units (average effect of moving a
   numeric driver from its 10th to 90th percentile, or of each category).
5. Answers what-if questions by re-scoring the data with a lever changed. These are
   model-based associations, labelled as such; they are not causal estimates.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LinearRegression, LogisticRegression, Ridge
from sklearn.metrics import mean_absolute_error, r2_score, roc_auc_score
from sklearn.model_selection import KFold, StratifiedKFold, cross_val_score, train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from ...errors import AppError
from ..common import bi, clean, confidence_label, fmt, limit_native_threads, pct, safe_div
from ..frame import AnalysisFrame
from .query import apply_filters

MAX_CATEGORIES = 12
MIN_ROWS = 60


@dataclass(slots=True)
class FeatureSpace:
    X: pd.DataFrame
    groups: dict[str, list[str]]  # original column -> encoded columns
    kinds: dict[str, str]  # original column -> numeric | categorical | calendar
    categories: dict[str, list[str]]


@dataclass(slots=True)
class FittedModel:
    target: str
    task: str  # regression | classification
    model: Any
    space: FeatureSpace
    y: pd.Series
    cv_score: float
    baseline_score: float
    metric: str
    candidates: list[dict[str, Any]]
    excluded: list[dict[str, Any]]
    positive_label: str | None


def _encode(frame: AnalysisFrame, df: pd.DataFrame, features: list[str]) -> FeatureSpace:
    columns: dict[str, pd.Series] = {}
    groups: dict[str, list[str]] = {}
    kinds: dict[str, str] = {}
    categories: dict[str, list[str]] = {}
    for name in features:
        role = frame.roles[name].role
        if role in {"measure", "flag"}:
            columns[name] = pd.to_numeric(df[name], errors="coerce")
            groups[name] = [name]
            kinds[name] = "numeric"
        elif role == "dimension":
            values = df[name].astype(str).where(df[name].notna(), "(missing)")
            top = values.value_counts().index[:MAX_CATEGORIES].tolist()
            values = values.where(values.isin(top), "(other)")
            levels = sorted(values.unique().tolist())
            categories[name] = levels
            encoded = []
            for level in levels[1:] if len(levels) > 1 else levels:
                key = f"{name}={level}"
                columns[key] = (values == level).astype(float)
                encoded.append(key)
            groups[name] = encoded
            kinds[name] = "categorical"
        elif role == "time":
            stamp = df[name]
            month_key, dow_key, trend_key = f"{name}:month", f"{name}:weekday", f"{name}:trend"
            columns[month_key] = stamp.dt.month.astype(float)
            columns[dow_key] = stamp.dt.dayofweek.astype(float)
            start = stamp.min()
            columns[trend_key] = (stamp - start).dt.days.astype(float)
            groups[f"{name} (season)"] = [month_key]
            groups[f"{name} (weekday)"] = [dow_key]
            groups[f"{name} (trend)"] = [trend_key]
            kinds[f"{name} (season)"] = "calendar"
            kinds[f"{name} (weekday)"] = "calendar"
            kinds[f"{name} (trend)"] = "calendar"
    X = pd.DataFrame(columns, index=df.index)
    return FeatureSpace(X=X, groups=groups, kinds=kinds, categories=categories)


def _default_features(frame: AnalysisFrame, target: str) -> tuple[list[str], list[dict[str, Any]]]:
    """Candidate levers for a target, leaving out sibling outcomes.

    When the target is a money KPI (revenue), other money KPIs (profit, cost, amount)
    are outcomes of the same transaction, not levers. Explaining revenue with profit is
    true and useless, so those are excluded by default and reported as such.
    """

    target_role = frame.roles[target]
    money_target = target_role.role == "measure" and target_role.kpi_score >= 0.75
    excluded: list[dict[str, Any]] = []
    features: list[str] = []
    for measure in frame.measures:
        if measure == target:
            continue
        role = frame.roles[measure]
        if money_target and role.kpi_score >= 0.75 and role.kpi_score != 0.55:
            excluded.append({"column": measure, "reason": "sibling_outcome_measure"})
            continue
        features.append(measure)
    features += [f for f in frame.flags if f != target]
    features += [d for d in frame.dimensions if frame.roles[d].distinct_count <= 60 and d != target]
    if frame.time_column:
        features.append(frame.time_column)
    return features[:40], excluded


def _leakage_guard(
    X: pd.DataFrame, y: pd.Series, space: FeatureSpace, task: str
) -> list[dict[str, Any]]:
    """Find numeric features that define the target arithmetically."""

    if task != "regression":
        return []
    numeric = [g for g, kind in space.kinds.items() if kind == "numeric"]
    if not numeric:
        return []
    data = pd.concat([X[numeric], y.rename("__target__")], axis=1).dropna()
    if len(data) < 30:
        return []
    excluded: list[dict[str, Any]] = []
    for name in numeric:
        if data[name].std() == 0:
            continue
        corr = abs(float(np.corrcoef(data[name], data["__target__"])[0, 1]))
        if corr >= 0.985:
            excluded.append({"column": name, "reason": "near_duplicate_of_target", "r": corr})
    remaining = [n for n in numeric if n not in {e["column"] for e in excluded}]
    if len(remaining) >= 2:
        model = LinearRegression().fit(data[remaining], data["__target__"])
        fit = r2_score(data["__target__"], model.predict(data[remaining]))
        if fit >= 0.995:
            scaled = np.abs(model.coef_) * data[remaining].std().to_numpy()
            order = np.argsort(-scaled)
            for index in order[:3]:
                if scaled[index] > 0.05 * scaled.max():
                    excluded.append(
                        {
                            "column": remaining[index],
                            "reason": "part_of_arithmetic_identity",
                            "identity_r2": float(fit),
                        }
                    )
    return excluded


def fit_model(
    frame: AnalysisFrame,
    target: str,
    features: list[str] | None = None,
    filters: list[dict[str, Any]] | None = None,
) -> FittedModel:
    limit_native_threads()
    target = frame.require(target)
    cache_key = f"model::{target}::{sorted(features or [])}::{filters!r}"
    cached = frame.cache.get(cache_key)
    if cached is not None:
        return cached
    df = apply_filters(frame, filters)
    if len(df) > 20_000:
        df = df.sample(20_000, random_state=20260630)
    role = frame.roles[target].role
    positive_label: str | None = None
    if role in {"measure"}:
        task = "regression"
        y = pd.to_numeric(df[target], errors="coerce")
    elif role == "flag":
        task = "classification"
        y = pd.to_numeric(df[target], errors="coerce")
        positive_label = "1"
    elif role == "dimension" and 2 <= frame.roles[target].distinct_count <= 10:
        task = "classification"
        values = df[target].astype(str).where(df[target].notna())
        positive_label = values.value_counts().index[-1] if values.notna().any() else None
        y = (values == positive_label).astype(float).where(values.notna())
    else:
        raise AppError(
            422,
            "unsupported_target",
            f"{target!r} is a {role} column; choose a numeric measure or a yes/no outcome.",
        )
    sibling_exclusions: list[dict[str, Any]] = []
    if features:
        chosen = [frame.require(f) for f in features]
    else:
        chosen, sibling_exclusions = _default_features(frame, target)
    chosen = [f for f in chosen if f != target]
    space = _encode(frame, df, chosen)
    mask = y.notna()
    X, y = space.X[mask], y[mask]
    if len(y) < MIN_ROWS:
        raise AppError(
            422, "insufficient_data", f"{len(y)} usable rows; driver analysis needs {MIN_ROWS}+."
        )
    if task == "classification" and (y.sum() < 10 or (len(y) - y.sum()) < 10):
        raise AppError(422, "insufficient_data", "Each outcome needs at least 10 examples.")
    excluded = _leakage_guard(X, y, space, task)
    for item in excluded:
        for encoded in space.groups.pop(item["column"], []):
            X = X.drop(columns=encoded)
        space.kinds.pop(item["column"], None)
    space.X = X
    if X.shape[1] == 0:
        raise AppError(422, "insufficient_data", "No usable features remain for this target.")

    candidates: list[dict[str, Any]] = []
    folds = 3 if len(y) > 8000 else 5
    if task == "regression":
        cv = KFold(n_splits=folds, shuffle=True, random_state=20260630)
        metric = "r2"
        models = {
            "ridge_regression": make_pipeline(
                SimpleImputer(strategy="median"), StandardScaler(), Ridge(alpha=1.0)
            ),
            "gradient_boosting": HistGradientBoostingRegressor(
                max_iter=150, learning_rate=0.08, random_state=20260630
            ),
        }
        baseline = 0.0
    else:
        cv = StratifiedKFold(n_splits=folds, shuffle=True, random_state=20260630)
        metric = "roc_auc"
        models = {
            "logistic_regression": make_pipeline(
                SimpleImputer(strategy="median"),
                StandardScaler(),
                LogisticRegression(max_iter=2000),
            ),
            "gradient_boosting": HistGradientBoostingClassifier(
                max_iter=150, learning_rate=0.08, random_state=20260630
            ),
        }
        baseline = 0.5
    best_name, best_score = "", -np.inf
    for name, model in models.items():
        scores = cross_val_score(model, X, y, cv=cv, scoring=metric, n_jobs=1)
        score = float(np.mean(scores))
        candidates.append(
            {"model": name, "cv_mean": score, "cv_std": float(np.std(scores)), "folds": folds}
        )
        if score > best_score:
            best_name, best_score = name, score
    final = models[best_name]
    final.fit(X, y)
    fitted = FittedModel(
        target=target,
        task=task,
        model=final,
        space=space,
        y=y,
        cv_score=best_score,
        baseline_score=baseline,
        metric=metric,
        candidates=candidates,
        excluded=sibling_exclusions + excluded,
        positive_label=positive_label,
    )
    fitted_name = best_name
    fitted.candidates = [{**c, "selected": c["model"] == fitted_name} for c in candidates]
    frame.cache[cache_key] = fitted
    return fitted


def _score(fitted: FittedModel, X: pd.DataFrame, y: pd.Series) -> float:
    if fitted.task == "regression":
        return float(r2_score(y, fitted.model.predict(X)))
    probabilities = fitted.model.predict_proba(X)[:, 1]
    return float(roc_auc_score(y, probabilities))


def _predict_mean(fitted: FittedModel, X: pd.DataFrame) -> float:
    if fitted.task == "regression":
        return float(np.mean(fitted.model.predict(X)))
    return float(np.mean(fitted.model.predict_proba(X)[:, 1]))


def key_drivers(
    frame: AnalysisFrame,
    target: str,
    features: list[str] | None = None,
    filters: list[dict[str, Any]] | None = None,
    top: int = 8,
) -> dict[str, Any]:
    fitted = fit_model(frame, target, features, filters)
    X, y = fitted.space.X, fitted.y
    stratify = y if fitted.task == "classification" else None
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.25, random_state=20260630, stratify=stratify
    )
    evaluator = replace(fitted, model=_clone_fit(fitted.model, X_train, y_train))
    reference = _score(evaluator, X_test, y_test)
    rng = np.random.default_rng(20260630)
    importances: list[dict[str, Any]] = []
    for group, encoded in fitted.space.groups.items():
        drops = []
        for _ in range(3):
            shuffled = X_test.copy()
            permutation = rng.permutation(len(shuffled))
            shuffled[encoded] = shuffled[encoded].to_numpy()[permutation]
            drops.append(reference - _score(evaluator, shuffled, y_test))
        importances.append({"feature": group, "importance": float(np.mean(drops))})
    positive_total = sum(max(0.0, item["importance"]) for item in importances) or 1.0
    importances.sort(key=lambda item: -item["importance"])
    drivers: list[dict[str, Any]] = []
    target_mean = float(y.mean())
    for item in importances[:top]:
        group = item["feature"]
        if item["importance"] <= 0:
            continue
        effect = _effect(fitted, group)
        drivers.append(
            {
                **item,
                "share": max(0.0, item["importance"]) / positive_total,
                "kind": fitted.space.kinds.get(group, "numeric"),
                **effect,
            }
        )
    dominance: dict[str, Any] | None = None
    if drivers and drivers[0]["share"] > 0.6 and not features and drivers[0]["kind"] != "calendar":
        # One feature explaining nearly everything is either the real story or a leak
        # (recorded after the outcome, or part of its definition). Show what remains
        # without it, so the reader can judge.
        dominant = drivers[0]["feature"]
        remaining = [f for f in _default_features(frame, fitted.target)[0] if f != dominant]
        try:
            second = key_drivers(frame, fitted.target, remaining, filters, top)
            dominance = {
                "feature": dominant,
                "share": drivers[0]["share"],
                "model_without": second["model"],
                "drivers_without": [
                    {
                        k: d.get(k)
                        for k in (
                            "feature",
                            "share",
                            "direction",
                            "kind",
                            "effect_range",
                            "best_category",
                            "worst_category",
                        )
                    }
                    for d in second["drivers"][:5]
                ],
            }
        except AppError:
            dominance = None
    lift = fitted.cv_score - fitted.baseline_score
    quality = (
        "strong"
        if (fitted.task == "regression" and fitted.cv_score >= 0.6)
        or (fitted.task == "classification" and fitted.cv_score >= 0.8)
        else "moderate"
        if (fitted.task == "regression" and fitted.cv_score >= 0.3)
        or (fitted.task == "classification" and fitted.cv_score >= 0.68)
        else "weak"
    )
    confidence_score = {"strong": 0.85, "moderate": 0.65, "weak": 0.35}[quality]
    unit = "probability" if fitted.task == "classification" else "units"
    top_names = ", ".join(d["feature"] for d in drivers[:3]) or "—"
    return clean(
        {
            "target": fitted.target,
            "task": fitted.task,
            "positive_label": fitted.positive_label,
            "rows_used": int(len(y)),
            "target_mean": target_mean,
            "model": {
                "selected": next(c["model"] for c in fitted.candidates if c.get("selected")),
                "metric": fitted.metric,
                "cv_score": fitted.cv_score,
                "baseline": fitted.baseline_score,
                "lift_over_baseline": lift,
                "holdout_score": reference,
                "quality": quality,
                "candidates": fitted.candidates,
            },
            "excluded_features": fitted.excluded,
            "drivers": drivers,
            "dominance": dominance,
            "confidence": confidence_label(confidence_score),
            "effect_unit": unit,
            "chart": {
                "type": "bar_horizontal",
                "title": bi(f"What drives {fitted.target}", f"ما الذي يحرّك {fitted.target}"),
                "x": [d["feature"] for d in drivers],
                "series": [{"name": "share_of_explained", "data": [d["share"] for d in drivers]}],
            },
            "method": "model_tournament_5fold_cv_grouped_permutation_importance",
            "caveat": bi(
                "Drivers are associations learned from historical data, not proof of cause. "
                "Validate the top levers with a controlled test before large decisions.",
                "العوامل المؤثرة ارتباطات مستخلصة من البيانات التاريخية وليست دليلًا على السببية. "
                "تحقّق من أهم العوامل بتجربة مضبوطة قبل القرارات الكبيرة.",
            ),
            "summary": bi(
                f"The model explains {fitted.target} with {fitted.metric}={fitted.cv_score:.2f} "
                f"({quality}); the strongest drivers are {top_names}.",
                f"يفسّر النموذج {fitted.target} بمقياس {fitted.metric}={fitted.cv_score:.2f} "
                f"({ {'strong': 'قوي', 'moderate': 'متوسط', 'weak': 'ضعيف'}[quality] })؛ "
                f"وأقوى العوامل: {top_names}.",
            ),
        }
    )


def _clone_fit(model: Any, X: pd.DataFrame, y: pd.Series) -> Any:
    from sklearn.base import clone

    return clone(model).fit(X, y)


def _effect(fitted: FittedModel, group: str) -> dict[str, Any]:
    X = fitted.space.X
    sample = X if len(X) <= 4000 else X.sample(4000, random_state=3)
    encoded = fitted.space.groups[group]
    kind = fitted.space.kinds.get(group, "numeric")
    if kind == "categorical":
        name = group
        levels = fitted.space.categories.get(name, [])
        effects: list[dict[str, Any]] = []
        for level in levels:
            shifted = sample.copy()
            shifted[encoded] = 0.0
            key = f"{name}={level}"
            if key in shifted.columns:
                shifted[key] = 1.0
            effects.append({"category": level, "predicted_mean": _predict_mean(fitted, shifted)})
        effects.sort(key=lambda item: -item["predicted_mean"])
        spread = effects[0]["predicted_mean"] - effects[-1]["predicted_mean"] if effects else 0.0
        return {
            "best_category": effects[0]["category"] if effects else None,
            "worst_category": effects[-1]["category"] if effects else None,
            "effect_range": spread,
            "category_effects": effects[:12],
            "direction": "categorical",
        }
    column = encoded[0]
    values = sample[column].dropna()
    if values.empty or values.nunique() < 2:
        return {"direction": "flat", "effect_range": 0.0}
    low, high = float(values.quantile(0.1)), float(values.quantile(0.9))
    if low == high:
        low, high = float(values.min()), float(values.max())
    grid = np.linspace(low, high, 7)
    curve = []
    for point in grid:
        shifted = sample.copy()
        shifted[column] = point
        curve.append({"x": float(point), "y": _predict_mean(fitted, shifted)})
    effect = curve[-1]["y"] - curve[0]["y"]
    monotone = all(b["y"] >= a["y"] for a, b in zip(curve, curve[1:], strict=False)) or all(
        b["y"] <= a["y"] for a, b in zip(curve, curve[1:], strict=False)
    )
    return {
        "direction": "positive" if effect > 0 else "negative" if effect < 0 else "flat",
        "low_value": low,
        "high_value": high,
        "effect_range": effect,
        "monotonic": monotone,
        "response_curve": curve,
    }


def what_if(
    frame: AnalysisFrame,
    target: str,
    changes: list[dict[str, Any]],
    filters: list[dict[str, Any]] | None = None,
    exclude: list[str] | None = None,
) -> dict[str, Any]:
    """Re-score the data with levers changed; report the modelled change in the target."""

    features = None
    if exclude:
        target_name = frame.require(target)
        features = [f for f in _default_features(frame, target_name)[0] if f not in set(exclude)]
    fitted = fit_model(frame, target, features, filters)
    X = fitted.space.X
    scenario = X.copy()
    applied: list[dict[str, Any]] = []
    for change in changes[:6]:
        column = frame.require(str(change.get("column", "")))
        if column not in fitted.space.groups:
            raise AppError(
                422,
                "lever_not_in_model",
                f"{column!r} is not a usable driver of {fitted.target}.",
                details={"available": list(fitted.space.groups)},
            )
        encoded = fitted.space.groups[column]
        if fitted.space.kinds[column] == "categorical":
            level = str(change.get("set_to", ""))
            if level not in fitted.space.categories.get(column, []):
                raise AppError(
                    422,
                    "unknown_category",
                    f"{level!r} is not a modelled value of {column!r}.",
                    details={"values": fitted.space.categories.get(column, [])},
                )
            scenario[encoded] = 0.0
            key = f"{column}={level}"
            if key in scenario.columns:
                scenario[key] = 1.0
            applied.append({"column": column, "set_to": level})
        else:
            if "percent_change" in change:
                factor = 1 + float(change["percent_change"]) / 100
                scenario[encoded[0]] = scenario[encoded[0]] * factor
                applied.append(
                    {"column": column, "percent_change": float(change["percent_change"])}
                )
            elif "set_to" in change:
                scenario[encoded[0]] = float(change["set_to"])
                applied.append({"column": column, "set_to": float(change["set_to"])})
            elif "add" in change:
                scenario[encoded[0]] = scenario[encoded[0]] + float(change["add"])
                applied.append({"column": column, "add": float(change["add"])})
            else:
                raise AppError(422, "invalid_change", "Use percent_change, set_to or add.")
    base = _predict_mean(fitted, X)
    after = _predict_mean(fitted, scenario)
    delta = after - base
    rows = len(X)
    observed_range = {
        column: {
            "min": float(X[fitted.space.groups[column][0]].min()),
            "max": float(X[fitted.space.groups[column][0]].max()),
        }
        for column in {a["column"] for a in applied}
        if fitted.space.kinds.get(column) == "numeric"
    }
    extrapolating = any(
        float(scenario[fitted.space.groups[c][0]].max()) > r["max"] * 1.05
        or float(scenario[fitted.space.groups[c][0]].min()) < r["min"] * 0.95
        for c, r in observed_range.items()
    )
    unit = "probability" if fitted.task == "classification" else "per_record"
    return clean(
        {
            "target": fitted.target,
            "task": fitted.task,
            "changes": applied,
            "baseline_mean": base,
            "scenario_mean": after,
            "change_per_record": delta,
            "relative_change": safe_div(delta, abs(base)),
            "total_change_over_rows": delta * rows if fitted.task == "regression" else None,
            "rows": rows,
            "unit": unit,
            "model_quality": {"metric": fitted.metric, "cv_score": fitted.cv_score},
            "extrapolating": extrapolating,
            "method": "counterfactual_rescoring_with_fitted_model",
            "caveat": bi(
                "A model-based association estimate, not a causal forecast. Effects outside the "
                "historically observed range are extrapolations.",
                "تقدير قائم على ارتباطات النموذج وليس توقعًا سببيًا. التأثيرات خارج المدى الذي "
                "رُصد تاريخيًا استقراء غير مضمون.",
            ),
            "summary": bi(
                f"Modelled {fitted.target}: {fmt(base)} → {fmt(after)} per record "
                f"({pct(safe_div(delta, abs(base)), signed=True)}).",
                f"القيمة المقدّرة لـ{fitted.target}: {fmt(base)} ← {fmt(after)} لكل سجل "
                f"({pct(safe_div(delta, abs(base)), signed=True)}).",
            ),
        }
    )


def model_errors(fitted: FittedModel) -> dict[str, float]:
    if fitted.task == "regression":
        predictions = fitted.model.predict(fitted.space.X)
        return {"in_sample_mae": float(mean_absolute_error(fitted.y, predictions))}
    return {}
