"""Time-series forecasting with intervals that are calibrated, not decorative.

Design constraints this module exists to satisfy:

* An interval must be calibrated on residuals the model did not see while being
  selected. Calibrating on the selection window makes the winner look precise
  precisely because it was chosen for fitting that window, and produces the
  narrow-interval failure this replaces.
* The published accuracy must come from a holdout excluded from both selection
  and calibration, so the number is an out-of-sample measurement.
* MASE must use the standard naive-one scale over the whole training series.
  A scale taken from an arbitrary early slice can be near zero and inflates the
  ratio into the hundreds, which reads as catastrophic when it is meaningless.
* When the chosen model does not beat a seasonal naive, the response says so.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any

import numpy as np

Predictor = Callable[[list[float], int], float]

# Below this many observations a seasonal model cannot be evaluated honestly.
MIN_HISTORY = 12
MIN_HISTORY_FOR_SEASONAL = 24
DEFAULT_INTERVAL = 0.90


@dataclass(slots=True)
class Model:
    name: str
    label_en: str
    label_ar: str
    minimum_history: int
    predict: Predictor
    family: str


def _naive(history: list[float], step: int) -> float:
    return history[-1]


def _mean(history: list[float], step: int) -> float:
    return float(np.mean(history))


def _seasonal_naive(period: int) -> Predictor:
    def predict(history: list[float], step: int) -> float:
        if len(history) < period:
            return history[-1]
        return history[-period + ((step - 1) % period)]

    return predict


def _moving_average(window: int) -> Predictor:
    def predict(history: list[float], step: int) -> float:
        return float(np.mean(history[-window:]))

    return predict


def _drift(history: list[float], step: int) -> float:
    if len(history) < 2:
        return history[-1]
    slope = (history[-1] - history[0]) / (len(history) - 1)
    return history[-1] + slope * step


def _linear_trend(history: list[float], step: int) -> float:
    index = np.arange(len(history), dtype=float)
    slope, intercept = np.polyfit(index, np.asarray(history, dtype=float), 1)
    return float(intercept + slope * (len(history) + step - 1))


def _damped_trend(phi: float) -> Predictor:
    """Linear trend whose slope decays geometrically.

    Undamped extrapolation is the standard way a monthly series turns into an
    indefensible three-year projection; damping bounds it.
    """

    def predict(history: list[float], step: int) -> float:
        index = np.arange(len(history), dtype=float)
        slope, intercept = np.polyfit(index, np.asarray(history, dtype=float), 1)
        level = float(intercept + slope * (len(history) - 1))
        damping = sum(phi**k for k in range(1, step + 1))
        return level + float(slope) * damping

    return predict


def _holt(alpha: float, beta: float) -> Predictor:
    def predict(history: list[float], step: int) -> float:
        level, trend = history[0], history[1] - history[0] if len(history) > 1 else 0.0
        for value in history[1:]:
            previous = level
            level = alpha * value + (1 - alpha) * (level + trend)
            trend = beta * (level - previous) + (1 - beta) * trend
        return level + trend * step

    return predict


def _holt_winters_additive(period: int, alpha: float, beta: float, gamma: float) -> Predictor:
    def predict(history: list[float], step: int) -> float:
        if len(history) < 2 * period:
            return _holt(alpha, beta)(history, step)
        seasons = len(history) // period
        blocks = np.asarray(history[: seasons * period], dtype=float).reshape(seasons, period)
        level = float(blocks[0].mean())
        trend = float((blocks[-1].mean() - blocks[0].mean()) / max(1, (seasons - 1) * period))
        seasonal = list(np.asarray(history[:period], dtype=float) - level)
        for index, value in enumerate(history):
            season_index = index % period
            previous = level
            level = alpha * (value - seasonal[season_index]) + (1 - alpha) * (level + trend)
            trend = beta * (level - previous) + (1 - beta) * trend
            seasonal[season_index] = gamma * (value - level) + (1 - gamma) * seasonal[season_index]
        return level + trend * step + seasonal[(len(history) + step - 1) % period]

    return predict


def _theta(history: list[float], step: int) -> float:
    """Theta method: simple exponential smoothing plus half the linear drift."""
    index = np.arange(len(history), dtype=float)
    slope, _ = np.polyfit(index, np.asarray(history, dtype=float), 1)
    alpha = 0.3
    level = history[0]
    for value in history[1:]:
        level = alpha * value + (1 - alpha) * level
    return float(level + 0.5 * float(slope) * step)


def build_models(period: int) -> list[Model]:
    models = [
        Model("naive", "Last value", "آخر قيمة", 2, _naive, "benchmark"),
        Model("mean", "Historical mean", "المتوسط التاريخي", 3, _mean, "benchmark"),
        Model("drift", "Drift", "الانجراف", 3, _drift, "trend"),
        Model(
            "moving_average_3",
            "3-period moving average",
            "متوسط متحرك 3",
            4,
            _moving_average(3),
            "smoothing",
        ),
        Model(
            "moving_average_6",
            "6-period moving average",
            "متوسط متحرك 6",
            7,
            _moving_average(6),
            "smoothing",
        ),
        Model("linear_trend", "Linear trend", "اتجاه خطي", 4, _linear_trend, "trend"),
        Model("damped_trend_0.85", "Damped trend", "اتجاه مخمَّد", 5, _damped_trend(0.85), "trend"),
        Model(
            "holt", "Holt linear smoothing", "تنعيم هولت الخطي", 5, _holt(0.4, 0.15), "smoothing"
        ),
        Model("theta", "Theta", "طريقة ثيتا", 5, _theta, "smoothing"),
    ]
    if period >= 2:
        models.append(
            Model(
                f"seasonal_naive_{period}",
                f"Seasonal naive ({period})",
                f"السذاجة الموسمية ({period})",
                period + 1,
                _seasonal_naive(period),
                "seasonal",
            )
        )
        models.append(
            Model(
                f"holt_winters_{period}",
                f"Holt-Winters additive ({period})",
                f"هولت-وينترز الجمعي ({period})",
                2 * period,
                _holt_winters_additive(period, 0.3, 0.1, 0.2),
                "seasonal",
            )
        )
    return models


def _safe(value: float) -> float:
    return float(value) if math.isfinite(value) else 0.0


def _naive_scale(training: list[float], period: int) -> tuple[float, str]:
    """The MASE denominator: mean absolute change of the benchmark on training data.

    Seasonal series are scaled against the seasonal naive so the ratio answers the
    question a reader actually asks: is this better than repeating last season?
    """
    array = np.asarray(training, dtype=float)
    if period >= 2 and len(array) > period:
        differences = np.abs(array[period:] - array[:-period])
        if differences.size and float(np.mean(differences)) > 0:
            return float(np.mean(differences)), f"seasonal_naive_{period}"
    differences = np.abs(np.diff(array))
    if differences.size and float(np.mean(differences)) > 0:
        return float(np.mean(differences)), "naive_one_step"
    return 0.0, "series_is_constant"


def _rolling_errors(
    model: Model, values: list[float], origins: list[int], horizon: int
) -> dict[int, list[float]]:
    """Signed errors (actual - prediction) per horizon across rolling origins."""
    errors: dict[int, list[float]] = {h: [] for h in range(1, horizon + 1)}
    for origin in origins:
        history = values[:origin]
        if len(history) < model.minimum_history:
            continue
        for step in range(1, horizon + 1):
            target = origin + step - 1
            if target >= len(values):
                break
            try:
                prediction = model.predict(history, step)
            except (ValueError, IndexError, ZeroDivisionError):
                continue
            if not math.isfinite(prediction):
                continue
            errors[step].append(values[target] - prediction)
    return errors


def _quantile(values: list[float], fraction: float) -> float:
    if not values:
        return 0.0
    return float(np.quantile(np.asarray(values, dtype=float), fraction, method="higher"))


def detect_seasonality(values: list[float], period: int) -> dict[str, Any]:
    """Report trend and seasonal strength from an additive decomposition.

    Strengths follow the standard definition: one minus the share of variation the
    remainder still holds once the other component is added back. Comparing the
    remainder against the raw series instead makes a strongly trending series report
    no trend, because the trend's own variance swamps the ratio.
    """
    array = np.asarray(values, dtype=float)
    result: dict[str, Any] = {"period": period, "testable": len(array) >= 2 * period}
    if len(array) < max(4, 2 * period) or period < 2:
        result["seasonal_strength"] = None
        result["trend_strength"] = None
        return result

    # Centred moving average, with the edges held at the nearest full window so the
    # decomposition covers every point instead of tapering to zero at both ends.
    window = period if period % 2 else period + 1
    kernel = np.ones(window) / window
    interior = np.convolve(array, kernel, mode="valid")
    pad = (len(array) - len(interior)) // 2
    trend = np.concatenate(
        [
            np.full(pad, interior[0]),
            interior,
            np.full(len(array) - len(interior) - pad, interior[-1]),
        ]
    )

    detrended = array - trend
    seasonal = np.zeros_like(array)
    profile = []
    for index in range(period):
        positions = np.arange(index, len(array), period)
        level = float(np.mean(detrended[positions]))
        seasonal[positions] = level
        profile.append(round(level, 4))
    # An additive seasonal component must sum to zero over a cycle, or it absorbs level.
    seasonal -= float(np.mean(seasonal))
    remainder = detrended - seasonal

    def strength(component: np.ndarray) -> float:
        combined = float(np.var(component + remainder))
        if combined <= 1e-12:
            return 0.0
        return round(max(0.0, min(1.0, 1 - float(np.var(remainder)) / combined)), 4)

    seasonal_strength = strength(seasonal)
    trend_strength = strength(trend - float(np.mean(trend)))

    # Autocorrelation is measured on the detrended series. On a rising series the raw
    # lag-12 correlation is near one whatever the seasonality, which would confirm a
    # seasonal pattern that is not there.
    correlations = []
    for lag in (period, period * 2):
        if len(array) > lag + 2:
            left, right = detrended[lag:], detrended[:-lag]
            if np.std(left) > 0 and np.std(right) > 0:
                correlations.append(round(float(np.corrcoef(left, right)[0, 1]), 4))

    result.update(
        {
            "seasonal_strength": seasonal_strength,
            "trend_strength": trend_strength,
            "seasonal_autocorrelation": correlations,
            "seasonal_profile": profile,
            "is_seasonal": bool(
                seasonal_strength > 0.4 and correlations and correlations[0] > 0.35
            ),
            "is_trending": bool(trend_strength > 0.3),
        }
    )
    return result


def detect_anomalies(periods: list[str], values: list[float], period: int) -> list[dict[str, Any]]:
    """Flag observations far from a rolling local level, using a robust spread."""
    if len(values) < 6:
        return []
    array = np.asarray(values, dtype=float)
    window = min(max(3, period), max(3, len(array) // 3))
    flags: list[dict[str, Any]] = []
    for index in range(len(array)):
        start = max(0, index - window)
        neighbourhood = np.concatenate([array[start:index], array[index + 1 : index + 1 + window]])
        if neighbourhood.size < 3:
            continue
        median = float(np.median(neighbourhood))
        deviation = float(np.median(np.abs(neighbourhood - median)))
        # 1.4826 rescales the median absolute deviation to a normal standard deviation.
        spread = deviation * 1.4826
        if spread <= 0:
            continue
        score = (float(array[index]) - median) / spread
        if abs(score) >= 3.5:
            flags.append(
                {
                    "period": periods[index],
                    "value": round(float(array[index]), 4),
                    "local_median": round(median, 4),
                    "robust_z": round(score, 2),
                    "direction": "above" if score > 0 else "below",
                }
            )
    return flags


def _fit(design: np.ndarray, target: np.ndarray) -> tuple[np.ndarray, float]:
    coefficients, *_ = np.linalg.lstsq(design, target, rcond=None)
    residuals = target - design @ coefficients
    return coefficients, float(residuals @ residuals)


def detect_level_shift(values: list[float], minimum_segment: int = 3) -> dict[str, Any] | None:
    """Find a level shift that a straight-line trend does not already explain.

    A forecast fitted across a structural break splits the difference between two
    regimes and lands on a number that was never true in either. This compares a plain
    linear trend against the same trend plus a step at each candidate date.

    Two gates have to clear, because either alone gives the wrong answer:

    * the step must be statistically worth its parameter (an F ratio), and
    * the fitted step must be *large*, both against the noise around the fit and
      against what the trend delivers on its own in a few periods.

    The second gate is what keeps a smooth, low-noise climb from being called a break:
    tiny residuals make almost any split significant, and the difference between two
    halves of a trending series is mostly the trend, not a discontinuity.
    """
    if len(values) < minimum_segment * 2 + 1:
        return None
    array = np.asarray(values, dtype=float)
    count = len(array)
    index = np.arange(count, dtype=float)
    trend_only = np.column_stack([np.ones(count), index])
    (_, slope), baseline_rss = _fit(trend_only, array)
    if baseline_rss <= 0:
        return None

    best: dict[str, Any] | None = None
    for split in range(minimum_segment, count - minimum_segment + 1):
        step = (index >= split).astype(float)
        with_step = np.column_stack([np.ones(count), index, step])
        coefficients, rss = _fit(with_step, array)
        degrees = count - 3
        if degrees <= 0 or rss <= 0:
            continue
        statistic = ((baseline_rss - rss) / 1.0) / (rss / degrees)
        if best is None or statistic > best["statistic"]:
            best = {
                "index": split,
                "statistic": float(statistic),
                "rss": rss,
                "step": float(coefficients[2]),
                "slope": float(coefficients[1]),
                "residual_sd": math.sqrt(rss / degrees),
            }
    # The maximum is taken over every candidate date, so the threshold sits well above
    # the single-test critical value.
    if best is None or best["statistic"] < 25.0:
        return None

    step = abs(best["step"])
    # A break has to be a real discontinuity: bigger than the scatter around the fit,
    # and bigger than several periods of the trend's ordinary progress.
    if step < 2.5 * best["residual_sd"] or step < 4 * abs(best["slope"]):
        return None

    split = best["index"]
    before_level = float(np.median(array[:split]))
    baseline = abs(before_level) or 1.0
    return {
        "index": split,
        # The fitted step, not the difference between the two halves' medians: on a
        # trending series that difference is mostly the trend.
        "gap": round(best["step"], 4),
        "statistic": round(best["statistic"], 2),
        "residual_sd": round(best["residual_sd"], 4),
        "trend_per_period": round(best["slope"], 4),
        "variance_explained_by_step": round(1 - best["rss"] / baseline_rss, 4),
        "before_median": round(before_level, 4),
        "after_median": round(float(np.median(array[split:])), 4),
        "before_periods": split,
        "after_periods": count - split,
        "relative_change": round(best["step"] / baseline, 4),
        "direction": "increase" if best["step"] > 0 else "decrease",
        "test": "f_test_for_a_step_term_added_to_a_linear_trend_with_a_practical_size_gate",
    }


def _residual_diagnostics(errors: list[float], scale: float) -> dict[str, Any]:
    if not errors:
        return {"testable": False}
    array = np.asarray(errors, dtype=float)
    bias = float(np.mean(array))
    autocorrelation = None
    if array.size > 3 and float(np.std(array[:-1])) > 0 and float(np.std(array[1:])) > 0:
        autocorrelation = round(float(np.corrcoef(array[:-1], array[1:])[0, 1]), 4)
    return {
        "testable": True,
        "count": int(array.size),
        "mean_error": round(bias, 4),
        "bias_direction": (
            "over_forecasting"
            if bias < -abs(scale) * 0.1
            else "under_forecasting"
            if bias > abs(scale) * 0.1
            else "no_material_bias"
        ),
        "lag_1_autocorrelation": autocorrelation,
        "residuals_look_like_noise": bool(
            autocorrelation is not None and abs(autocorrelation) < 0.4
        ),
    }


def _regime_change_estimate(
    periods: list[str],
    values: list[float],
    regime: dict[str, Any],
    horizon: int,
    interval: float,
    label: str,
    unit: str | None,
    non_negative: bool,
    period_step: Callable[[str, int], str] | None,
    warnings: list[str],
    warnings_ar: list[str],
    seasonal_period: int,
) -> dict[str, Any]:
    """Answer for a series that changed level too recently to model the new one.

    Returning a trend fitted across the break would be worse than useless. What is
    defensible from a handful of post-break observations is the new level itself, with
    an interval wide enough to admit that the new regime's variability is unmeasured.
    """
    recent = values[regime["index"] :]
    recent_periods = periods[regime["index"] :]
    level = float(np.median(recent))
    observed_spread = float(np.max(recent) - np.min(recent)) if len(recent) > 1 else 0.0
    # With very few observations of the new level, the honest floor for uncertainty is a
    # share of the shift itself: a level that moved this much can move again.
    radius = max(observed_spread, abs(regime["gap"]) * 0.25, abs(level) * 0.1)
    step_fn = period_step or (lambda p, s: p)
    forecast = []
    for step in range(1, horizon + 1):
        width = radius * math.sqrt(step)
        lower = level - width
        forecast.append(
            {
                "horizon": step,
                "period": step_fn(periods[-1], step),
                "value": round(level, 2),
                "lower": round(max(0.0, lower) if non_negative else lower, 2),
                "upper": round(level + width, 2),
                "interval_width": round(
                    (level + width) - (max(0.0, lower) if non_negative else lower), 2
                ),
                "interval_basis": "post_break_level_with_shift_scaled_uncertainty",
            }
        )
    warnings.append(
        f"Only {regime['periods_since_change']} periods have been recorded since the level "
        f"changed, which is too few to fit or validate a model. The published figure is the "
        f"new level itself, carried forward, with an interval scaled to the size of the "
        f"shift. Treat it as a planning range, not a forecast."
    )
    warnings_ar.append(
        f"لم تُسجَّل سوى {regime['periods_since_change']} فترة منذ تغيّر المستوى، وهي أقل من "
        "أن تكفي لملاءمة نموذج أو التحقق منه. الرقم المنشور هو المستوى الجديد نفسه ممتدًا، "
        "بفاصل يتناسب مع حجم النقلة. تعامل معه كنطاق تخطيط لا كتوقّع."
    )
    return {
        "status": "regime_change",
        "classification": "level_estimate",
        "label": label,
        "unit": unit,
        "interval_level": interval,
        "history": [
            {
                "period": p,
                "value": round(float(v), 4),
                "used_for_fitting": p in set(recent_periods),
            }
            for p, v in zip(periods, values, strict=True)
        ],
        "forecast": forecast,
        "level_shift": regime,
        "model": {
            "name": "post_break_level",
            "label": {"en": "Post-break level", "ar": "مستوى ما بعد الكسر"},
            "family": "level",
            "history_periods": len(values),
            "fitted_on_periods": len(recent),
            "fitted_on_range": {"start": recent_periods[0], "end": recent_periods[-1]},
            "interval_method": "shift_scaled_bound_no_backtest_possible",
            "windows_are_disjoint": False,
        },
        "backtest": {
            "strategy": "not_performed",
            "reason": (
                f"{regime['periods_since_change']} observations since the break cannot be "
                "split into disjoint selection, calibration and evaluation windows."
            ),
            "mae": None,
            "wape": None,
            "mase": None,
            "interval_coverage": None,
            "interval_target": interval,
            "candidates": [],
            "predictions": [],
            "holdout_periods": 0,
            "evaluation_periods": 0,
            "selection_periods": 0,
        },
        "seasonality": detect_seasonality(values, seasonal_period),
        "anomalies": detect_anomalies(periods, values, seasonal_period),
        "residual_diagnostics": {"testable": False, "reason": "no_backtest_was_possible"},
        "warnings": warnings,
        "warnings_ar": warnings_ar,
        "decision_required": {
            "en": (
                f"Confirm what changed at {regime['changed_at']} before this number is used "
                "for planning. If the shift is a real operating change, the new level is the "
                "right basis and this estimate stands. If it is a recording or integration "
                "error, correct the source and re-run: no model can tell the two apart."
            ),
            "ar": (
                f"أكّد ما الذي تغيّر عند {regime['changed_at']} قبل استخدام هذا الرقم في "
                "التخطيط. إن كانت النقلة تغيّرًا تشغيليًا حقيقيًا فالمستوى الجديد هو الأساس "
                "الصحيح ويبقى هذا التقدير قائمًا. وإن كانت خطأ تسجيل أو تكامل فصحّح المصدر "
                "وأعد التشغيل: لا يستطيع أي نموذج التمييز بينهما."
            ),
        },
        "limitations": [
            "No accuracy can be reported: there are too few observations since the break "
            "to hold any of them out.",
            "The interval is a bound scaled to the size of the shift, not a measured "
            "error distribution.",
            "If the level moves again, this estimate becomes wrong immediately.",
        ],
        "limitations_ar": [
            "لا يمكن الإبلاغ عن دقة: عدد الملاحظات منذ الكسر أقل من أن يسمح بحجز أي منها.",
            "الفاصل حدٌّ متناسب مع حجم النقلة، وليس توزيعًا مقاسًا للخطأ.",
            "إذا تغيّر المستوى مجددًا يصبح هذا التقدير خاطئًا فورًا.",
        ],
    }


def forecast_series(
    periods: list[str],
    values: list[float],
    horizon: int,
    *,
    seasonal_period: int = 12,
    interval: float = DEFAULT_INTERVAL,
    label: str = "series",
    unit: str | None = None,
    non_negative: bool = True,
    period_step: Callable[[str, int], str] | None = None,
) -> dict[str, Any]:
    """Select, calibrate and evaluate a forecast on three disjoint windows.

    ``holdout`` is never used for selection or calibration, so the reported accuracy
    and interval coverage are honest out-of-sample measurements.
    """
    horizon = max(1, int(horizon))
    if len(values) < MIN_HISTORY:
        return {
            "status": "insufficient_data",
            "classification": "forecast",
            "forecast": [],
            "reason": (
                f"{len(values)} periods are available. At least {MIN_HISTORY} are required to "
                "select a model, calibrate an interval, and measure accuracy on data the "
                "model never saw."
            ),
            "reason_ar": (
                f"يتوفر {len(values)} فترة. يلزم {MIN_HISTORY} فترة على الأقل لاختيار نموذج "
                "ومعايرة فاصل الثقة وقياس الدقة على بيانات لم يرها النموذج."
            ),
            "history": [{"period": p, "value": v} for p, v in zip(periods, values, strict=True)],
        }

    period = seasonal_period if len(values) >= MIN_HISTORY_FOR_SEASONAL else 1
    warnings: list[str] = []
    warnings_ar: list[str] = []

    # A structural break has to be handled before a model is chosen. Fitting across one
    # returns a number that was true in neither regime, which is the most damaging thing
    # a forecast can do, because it looks perfectly reasonable.
    full_history = list(values)
    full_periods = list(periods)
    level_shift = detect_level_shift(values)
    regime: dict[str, Any] | None = None
    if level_shift is not None:
        since = len(values) - level_shift["index"]
        changed_at = periods[level_shift["index"]]
        regime = {
            **level_shift,
            "changed_at": changed_at,
            "periods_since_change": since,
            "handling": "refit_after_the_break" if since >= 6 else "anchored_on_the_new_level",
        }
        warnings.append(
            f"The series changed level at {changed_at}: the typical value moved from "
            f"{level_shift['before_median']:,.1f} to {level_shift['after_median']:,.1f} "
            f"({level_shift['relative_change']:+.0%}). Fitting across that break would "
            "return a number that describes neither period."
        )
        warnings_ar.append(
            f"تغيّر مستوى السلسلة عند {changed_at}: انتقلت القيمة المعتادة من "
            f"{level_shift['before_median']:,.1f} إلى {level_shift['after_median']:,.1f} "
            f"({level_shift['relative_change']:+.0%}). الملاءمة عبر هذا الكسر تعطي رقمًا "
            "لا يصف أيًّا من الفترتين."
        )
        if since >= 6:
            # Enough of the new regime to model it on its own terms.
            values = values[level_shift["index"] :]
            periods = periods[level_shift["index"] :]
            period = seasonal_period if len(values) >= MIN_HISTORY_FOR_SEASONAL else 1
            warnings.append(
                f"Only the {since} periods since {changed_at} were used to fit and evaluate. "
                "The earlier history describes a different operating level."
            )
            warnings_ar.append(
                f"استُخدمت فقط الفترات الـ{since} منذ {changed_at} في الملاءمة والتقييم؛ "
                "فالتاريخ الأسبق يصف مستوى تشغيل مختلفًا."
            )
        else:
            return _regime_change_estimate(
                full_periods,
                full_history,
                regime,
                horizon,
                interval,
                label,
                unit,
                non_negative,
                period_step,
                warnings,
                warnings_ar,
                seasonal_period,
            )
    if seasonal_period >= 2 and period == 1:
        warnings.append(
            f"Seasonal models were excluded: {len(values)} periods is below the "
            f"{MIN_HISTORY_FOR_SEASONAL} needed to observe two full cycles."
        )
        warnings_ar.append(
            f"استُبعدت النماذج الموسمية: {len(values)} فترة أقل من "
            f"{MIN_HISTORY_FOR_SEASONAL} اللازمة لرصد دورتين كاملتين."
        )

    # Three disjoint windows. The holdout is reserved first so nothing can leak into it.
    holdout_length = min(max(2, horizon), max(2, len(values) // 5))
    holdout_start = len(values) - holdout_length
    evaluation_horizon = min(horizon, holdout_length)
    working = values[:holdout_start]
    if len(working) < MIN_HISTORY - 2:
        holdout_length = 2
        holdout_start = len(values) - holdout_length
        evaluation_horizon = min(horizon, holdout_length)
        working = values[:holdout_start]

    warm_up = max(4, min(period + 1, len(working) // 2))
    origins = list(range(warm_up, len(working)))
    if len(origins) < 3:
        origins = list(range(max(2, len(working) // 2), len(working)))

    models = [m for m in build_models(period) if m.minimum_history <= len(working)]
    if not models:
        models = [build_models(1)[0]]

    scale, scale_basis = _naive_scale(working, period)
    candidates: list[dict[str, Any]] = []
    errors_by_model: dict[str, dict[int, list[float]]] = {}
    for model in models:
        errors = _rolling_errors(model, working, origins, min(horizon, holdout_length))
        flat = [e for bucket in errors.values() for e in bucket]
        if not flat:
            continue
        errors_by_model[model.name] = errors
        absolute = np.abs(np.asarray(flat, dtype=float))
        candidates.append(
            {
                "name": model.name,
                "label": {"en": model.label_en, "ar": model.label_ar},
                "family": model.family,
                "folds": len(flat),
                "mae": round(float(np.mean(absolute)), 4),
                "rmse": round(float(np.sqrt(np.mean(absolute**2))), 4),
                "mase": round(float(np.mean(absolute)) / scale, 4) if scale else None,
            }
        )
    if not candidates:
        return {
            "status": "insufficient_data",
            "classification": "forecast",
            "forecast": [],
            "reason": "No candidate model could be evaluated on this history.",
            "reason_ar": "تعذّر تقييم أي نموذج مرشّح على هذا التاريخ.",
        }

    order = {model.name: index for index, model in enumerate(models)}
    candidates.sort(key=lambda c: (c["mae"], order[c["name"]]))
    selected_name = candidates[0]["name"]
    selected = next(m for m in models if m.name == selected_name)

    # Split-conformal radii: the empirical quantile of the selected model's absolute
    # rolling-origin errors, per horizon. Symmetric by construction, so the interval always
    # contains its own point forecast; systematic bias is reported separately in the
    # diagnostics rather than folded into an offset the reader cannot see.
    radii: dict[int, dict[str, float]] = {}
    calibration = errors_by_model[selected_name]
    pooled = [e for bucket in calibration.values() for e in bucket]
    for step in range(1, horizon + 1):
        bucket = calibration.get(step) or []
        source = "per_horizon_absolute_residuals"
        growth = 1.0
        if len(bucket) < 4:
            bucket = pooled
            source = "pooled_absolute_residuals_scaled_by_sqrt_horizon"
            # Uncertainty grows with distance; with too few per-horizon residuals to
            # measure that growth, the random-walk sqrt(h) rate is the stated assumption.
            growth = math.sqrt(step)
        if not bucket:
            radii[step] = {"radius": 0.0, "basis": "no_residuals", "sample": 0}
            continue
        radius = _quantile([abs(e) for e in bucket], interval) * growth
        radii[step] = {"radius": radius, "basis": source, "sample": len(bucket)}

    # Uncertainty cannot fall as the horizon grows. Small per-horizon samples give jumpy
    # quantiles; carrying the running maximum forward only ever widens an interval, so
    # measured coverage can improve but never degrade.
    running = 0.0
    for step in range(1, horizon + 1):
        entry = radii.get(step)
        if entry is None:
            continue
        if entry["radius"] < running:
            entry["basis"] = f"{entry['basis']}_raised_to_horizon_{step - 1}_width"
        entry["radius"] = running = max(running, entry["radius"])

    # Honest evaluation on the reserved holdout.
    holdout_predictions: list[dict[str, Any]] = []
    covered = 0
    for step in range(1, evaluation_horizon + 1):
        target = holdout_start + step - 1
        if target >= len(values):
            break
        try:
            prediction = selected.predict(working, step)
        except (ValueError, IndexError, ZeroDivisionError):
            continue
        if non_negative:
            prediction = max(0.0, prediction)
        radius = radii.get(step, {"radius": 0.0})["radius"]
        lower = prediction - radius
        upper = prediction + radius
        if non_negative:
            lower = max(0.0, lower)
        actual = values[target]
        inside = lower <= actual <= upper
        covered += inside
        holdout_predictions.append(
            {
                "period": periods[target],
                "period_horizon": step,
                "actual": round(float(actual), 4),
                "prediction": round(float(prediction), 4),
                "lower": round(float(lower), 4),
                "upper": round(float(upper), 4),
                "inside_interval": bool(inside),
                "error": round(float(actual - prediction), 4),
            }
        )

    holdout_errors = [p["error"] for p in holdout_predictions]
    holdout_absolute = [abs(e) for e in holdout_errors]
    actuals = [p["actual"] for p in holdout_predictions]
    mae = float(np.mean(holdout_absolute)) if holdout_absolute else None
    mase = round(mae / scale, 4) if mae is not None and scale else None
    wape = (
        round(float(np.sum(holdout_absolute) / np.sum(np.abs(actuals))), 4)
        if actuals and float(np.sum(np.abs(actuals))) > 0
        else None
    )
    coverage = round(covered / len(holdout_predictions), 4) if holdout_predictions else None

    # If the reserved holdout shows the calibrated band was too narrow, widening it is the
    # honest response. Publishing a band that is known to under-cover, with a footnote
    # admitting it, hands the reader a number that reads as precise and is not.
    interval_adjustment: dict[str, Any] | None = None
    if holdout_absolute and coverage is not None and coverage < interval:
        needed = _quantile(holdout_absolute, interval)
        base = radii.get(1, {}).get("radius", 0.0)
        if needed > base > 0:
            factor = needed / base
            for entry in radii.values():
                entry["radius"] *= factor
                entry["basis"] = f"{entry['basis']}_widened_to_holdout_error"
            interval_adjustment = {
                "applied": True,
                "factor": round(factor, 4),
                "reason": "calibration_residuals_understated_the_holdout_error",
                "coverage_before_widening": coverage,
            }
            # Re-measure coverage against the widened band so the published number is real.
            covered = 0
            for row in holdout_predictions:
                widened = radii.get(row["period_horizon"], {"radius": 0.0})["radius"]
                lower = row["prediction"] - widened
                upper = row["prediction"] + widened
                if non_negative:
                    lower = max(0.0, lower)
                row["lower"] = round(lower, 4)
                row["upper"] = round(upper, 4)
                row["inside_interval"] = bool(lower <= row["actual"] <= upper)
                covered += row["inside_interval"]
            coverage = round(covered / len(holdout_predictions), 4)

    fitted_periods = set(periods)
    seasonality = detect_seasonality(values, seasonal_period)
    anomalies = detect_anomalies(periods, values, seasonal_period)
    diagnostics = _residual_diagnostics(pooled, scale)

    # Published forecast: refit on the full history, with the calibrated radii.
    step_fn = period_step or (lambda p, s: p)
    forecast: list[dict[str, Any]] = []
    for step in range(1, horizon + 1):
        try:
            point = selected.predict(values, step)
        except (ValueError, IndexError, ZeroDivisionError):
            break
        if not math.isfinite(point):
            break
        if non_negative:
            point = max(0.0, point)
        entry = radii.get(step, {"radius": 0.0, "basis": "no_residuals"})
        lower = point - entry["radius"]
        upper = point + entry["radius"]
        if non_negative:
            lower = max(0.0, lower)
        forecast.append(
            {
                "horizon": step,
                "period": step_fn(periods[-1], step),
                "value": round(float(point), 2),
                "lower": round(float(lower), 2),
                "upper": round(float(upper), 2),
                "interval_width": round(float(upper - lower), 2),
                "interval_basis": entry["basis"],
            }
        )

    benchmark = next(
        (c for c in candidates if c["name"].startswith("seasonal_naive")),
        next((c for c in candidates if c["name"] == "naive"), None),
    )
    beats_benchmark = bool(benchmark and candidates[0]["mae"] < benchmark["mae"]) or candidates[0][
        "name"
    ] == (benchmark or {}).get("name")

    if mase is not None and mase >= 1:
        warnings.append(
            f"On the reserved holdout this model was not better than repeating the "
            f"benchmark ({scale_basis}); MASE is {mase}. Treat the forecast as a weak "
            "signal and prefer a planning range over a point number."
        )
        warnings_ar.append(
            f"على العيّنة المحجوزة لم يتفوق النموذج على المرجع ({scale_basis})؛ قيمة MASE "
            f"هي {mase}. تعامل مع التوقع كمؤشر ضعيف واستخدم نطاق تخطيط بدل رقم واحد."
        )
    if horizon > len(values) / 2:
        warnings.append(
            f"The requested horizon ({horizon}) exceeds half the observed history "
            f"({len(values)} periods). Confidence degrades quickly beyond that point."
        )
        warnings_ar.append(
            f"الأفق المطلوب ({horizon}) يتجاوز نصف التاريخ المرصود ({len(values)} فترة). "
            "تتراجع الثقة بسرعة بعد هذه النقطة."
        )
    if interval_adjustment:
        warnings.append(
            f"The interval was widened {interval_adjustment['factor']:.1f}x because errors "
            "on the reserved holdout were larger than the calibration window suggested. "
            "The published band reflects the measured error, not the optimistic one."
        )
        warnings_ar.append(
            f"وُسِّع الفاصل {interval_adjustment['factor']:.1f} ضعفًا لأن الأخطاء على العيّنة "
            "المحجوزة كانت أكبر مما أوحت به نافذة المعايرة. الفاصل المنشور يعكس الخطأ "
            "المقاس لا المتفائل."
        )
    if coverage is not None and coverage < interval - 0.25:
        warnings.append(
            f"Even after widening, measured coverage on the holdout is {coverage:.0%} "
            f"against a {interval:.0%} target. This history is too short or too irregular "
            "to bound reliably; treat the range as indicative only."
        )
        warnings_ar.append(
            f"حتى بعد التوسيع تبلغ التغطية المقاسة {coverage:.0%} مقابل هدف {interval:.0%}. "
            "هذا التاريخ أقصر أو أكثر اضطرابًا من أن يُحدَّد بثقة؛ تعامل مع النطاق "
            "كاسترشادي فقط."
        )
    if anomalies:
        warnings.append(
            f"{len(anomalies)} historical observations sit far from their local level. "
            "They pull the fit; confirm whether they are real events or recording errors."
        )
        warnings_ar.append(
            f"{len(anomalies)} من الملاحظات التاريخية بعيدة عن مستواها المحلي وتؤثر على "
            "الملاءمة؛ تأكّد إن كانت أحداثًا حقيقية أم أخطاء تسجيل."
        )

    return {
        "status": "completed",
        "classification": "forecast",
        "label": label,
        "unit": unit,
        "interval_level": interval,
        "history": [
            {
                "period": p,
                "value": round(float(v), 4),
                "used_for_fitting": regime is None or p in fitted_periods,
            }
            for p, v in zip(full_periods, full_history, strict=True)
        ],
        "forecast": forecast,
        "model": {
            "name": selected.name,
            "label": {"en": selected.label_en, "ar": selected.label_ar},
            "family": selected.family,
            "history_periods": len(values),
            "seasonal_period": period,
            "selection_criterion": "lowest_mean_absolute_error_over_rolling_origins",
            "selection_origins": len(origins),
            "selected_on_range": {
                "start": periods[origins[0]] if origins else None,
                "end": periods[holdout_start - 1],
            },
            "calibrated_on": "rolling_origin_residuals_of_the_selected_model",
            "interval_method": "conformal_empirical_quantiles_per_horizon",
            "evaluated_on_range": {
                "start": periods[holdout_start],
                "end": periods[-1],
            },
            "windows_are_disjoint": True,
            "beats_benchmark": beats_benchmark,
        },
        "backtest": {
            "strategy": "rolling_origin_selection_then_reserved_holdout",
            "method": selected.name,
            "holdout_periods": len(holdout_predictions),
            "evaluation_periods": len(holdout_predictions),
            "selection_periods": len(origins),
            "mae": round(mae, 4) if mae is not None else None,
            "wape": wape,
            "mase": mase,
            "mase_scale": round(scale, 6),
            "mase_scale_basis": scale_basis,
            "interval_coverage": coverage,
            "interval_target": interval,
            "interval_adjustment": interval_adjustment,
            "candidates": candidates,
            "predictions": holdout_predictions,
        },
        "seasonality": seasonality,
        "level_shift": regime,
        "anomalies": anomalies,
        "residual_diagnostics": diagnostics,
        "warnings": warnings,
        "warnings_ar": warnings_ar,
        "limitations": [
            "Model selection, interval calibration and accuracy measurement use three "
            "disjoint windows of this series; the reported accuracy is out of sample.",
            "Intervals are empirical quantiles of past errors. They assume the future "
            "resembles the recent past and carry no guarantee under a regime change.",
            "Missing interior periods are treated as zero. Incomplete ingestion biases "
            "both the fit and the interval.",
            "A forecast describes continuation of an observed pattern. It does not "
            "establish a cause and cannot anticipate a decision not present in history.",
        ],
        "limitations_ar": [
            "يستخدم اختيار النموذج ومعايرة الفاصل وقياس الدقة ثلاث نوافذ منفصلة من هذه "
            "السلسلة؛ لذا الدقة المُبلَّغة خارج العيّنة.",
            "الفواصل كمّيات تجريبية للأخطاء السابقة، وتفترض أن المستقبل يشبه الماضي القريب "
            "ولا تضمن شيئًا عند تغيّر النظام.",
            "تُعامَل الفترات الداخلية المفقودة كأصفار، والاستيراد الناقص يحيّز الملاءمة والفاصل.",
            "التوقع يصف استمرار نمط مرصود، ولا يثبت سببًا ولا يتوقع قرارًا غير موجود في التاريخ.",
        ],
    }


def next_month(period: str, steps: int = 1) -> date:
    year, month = (int(item) for item in period.split("-")[:2])
    value = year * 12 + month - 1 + steps
    return date(value // 12, value % 12 + 1, 1)


def monthly_step(period: str, steps: int) -> str:
    return next_month(period, steps).isoformat()


def monthly_series(counts: dict[str, float]) -> tuple[list[str], list[float]]:
    """Fill the calendar between the first and last observed month with zeros."""
    if not counts:
        return [], []
    observed = sorted(counts)
    periods: list[str] = []
    cursor = observed[0]
    while cursor <= observed[-1]:
        periods.append(cursor)
        cursor = next_month(cursor).strftime("%Y-%m")
    return periods, [float(counts.get(p, 0.0)) for p in periods]
