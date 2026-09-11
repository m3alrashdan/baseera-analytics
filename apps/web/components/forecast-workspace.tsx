"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Activity,
  AlertTriangle,
  CircleHelp,
  Play,
  Target,
  TrendingUp,
} from "lucide-react";
import type { Locale } from "@/lib/contracts";
import { apiRequest, postJson, resourceStatusFromError } from "@/lib/api";
import { num } from "@/lib/viz";
import { Chart } from "./chart";
import { forecastOption, rankedBarOption } from "@/lib/chart-options";
import { ResourceState } from "./resource-state";

type Json = Record<string, any>;
const w = (locale: Locale, en: string, ar: string) =>
  locale === "ar" ? ar : en;

export function ForecastWorkspace({ locale }: { locale: Locale }) {
  const ar = locale === "ar";
  const [metrics, setMetrics] = useState<Json[]>([]);
  const [metricId, setMetricId] = useState("net_revenue");
  const [horizon, setHorizon] = useState(6);
  const [interval, setInterval] = useState(0.9);
  const [result, setResult] = useState<Json | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  useEffect(() => {
    apiRequest<{ items: Json[] }>("/api/v1/forecasts/metrics")
      .then((value) => setMetrics(value.items))
      .catch(() => setMetrics([]));
  }, []);

  const run = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      setResult(
        await postJson<Json>("/api/v1/forecasts", {
          metric_id: metricId,
          horizon,
          interval,
        }),
      );
    } catch (cause) {
      setError(cause);
      setResult(null);
    } finally {
      setBusy(false);
    }
  }, [metricId, horizon, interval]);

  const definition = metrics.find((item) => item.metric_id === metricId);
  const unit = definition?.unit as string | undefined;

  return (
    <div className="stack-page forecast">
      <header className="page-header">
        <div>
          <p className="eyebrow">{w(locale, "Outlook", "النظرة المستقبلية")}</p>
          <h1>{w(locale, "Forecast a metric", "توقّع مقياسًا")}</h1>
          <p>
            {w(
              locale,
              "The model is selected, its interval calibrated, and its accuracy measured on three separate windows of history, so the reported error is out of sample.",
              "يُختار النموذج ويُعاير فاصله وتُقاس دقته على ثلاث نوافذ منفصلة من التاريخ، فتكون الأخطاء المُبلَّغة خارج العيّنة.",
            )}
          </p>
        </div>
      </header>

      <section className="live-form panel">
        <label>
          {w(locale, "Metric", "المقياس")}
          <select
            value={metricId}
            onChange={(event) => setMetricId(event.target.value)}
          >
            {metrics.map((item) => (
              <option key={item.metric_id} value={item.metric_id}>
                {item.label?.[locale] ?? item.metric_id}
              </option>
            ))}
          </select>
        </label>
        <label>
          {w(locale, "Months ahead", "الأشهر القادمة")}
          <input
            type="number"
            min={1}
            max={24}
            value={horizon}
            onChange={(event) => setHorizon(Number(event.target.value))}
          />
        </label>
        <label>
          {w(locale, "Interval", "الفاصل")}
          <select
            value={String(interval)}
            onChange={(event) => setInterval(Number(event.target.value))}
          >
            <option value="0.8">80%</option>
            <option value="0.9">90%</option>
            <option value="0.95">95%</option>
          </select>
        </label>
        <button
          type="button"
          className="button button--primary"
          onClick={run}
          disabled={busy || horizon < 1 || horizon > 24}
        >
          <Play size={16} />
          {busy
            ? w(locale, "Running…", "جارٍ التشغيل…")
            : w(locale, "Run", "شغّل")}
        </button>
      </section>

      {error != null && (
        <ResourceState
          locale={locale}
          status={resourceStatusFromError(error)}
          reason={error instanceof Error ? error.message : String(error)}
          compact
        />
      )}

      {result && <ForecastResult locale={locale} result={result} unit={unit} />}
    </div>
  );
}

export function ForecastResult({
  locale,
  result,
  unit,
}: {
  locale: Locale;
  result: Json;
  unit?: string;
}) {
  const ar = locale === "ar";
  const history = (result.history ?? []) as Json[];
  const forecast = (result.forecast ?? []) as Json[];
  const backtest = (result.backtest ?? {}) as Json;
  const shift = result.level_shift as Json | undefined;
  const warnings = (ar ? result.warnings_ar : result.warnings) ?? [];
  const limitations = (ar ? result.limitations_ar : result.limitations) ?? [];
  const decision = result.decision_required as Json | undefined;

  if (result.status === "insufficient_data") {
    return (
      <section className="panel forecast__blocked">
        <CircleHelp size={22} />
        <div>
          <h2>{w(locale, "Not enough history", "التاريخ غير كافٍ")}</h2>
          <p>{ar ? result.reason_ar : result.reason}</p>
        </div>
      </section>
    );
  }

  return (
    <>
      {shift && (
        <section className="regime-alert">
          <AlertTriangle size={20} />
          <div>
            <h2>
              {w(locale, "The series changed level", "تغيّر مستوى السلسلة")} ·{" "}
              {shift.changed_at}
            </h2>
            <p>
              {w(
                locale,
                `The typical value moved from ${num(shift.before_median, locale)} to ${num(
                  shift.after_median,
                  locale,
                )} (${shift.relative_change > 0 ? "+" : ""}${Math.round(
                  shift.relative_change * 100,
                )}%). Fitting across that break would return a number that describes neither period.`,
                `انتقلت القيمة المعتادة من ${num(shift.before_median, locale)} إلى ${num(
                  shift.after_median,
                  locale,
                )} (${shift.relative_change > 0 ? "+" : ""}${Math.round(
                  shift.relative_change * 100,
                )}%). الملاءمة عبر هذا الكسر تعطي رقمًا لا يصف أيًّا من الفترتين.`,
              )}
            </p>
            {decision && (
              <p className="regime-alert__decision">
                {decision[ar ? "ar" : "en"]}
              </p>
            )}
          </div>
        </section>
      )}

      <Chart
        locale={locale}
        title={w(locale, "History and outlook", "التاريخ والتوقع")}
        description={w(
          locale,
          "The shaded band is the calibrated interval. Projected values are model estimates, not observations.",
          "النطاق المظلل هو الفاصل المعاير. القيم المتوقعة تقديرات للنموذج وليست ملاحظات مرصودة.",
        )}
        height={340}
        option={forecastOption(
          locale,
          history.map((row) => ({
            period: row.period,
            value: row.value,
            used_for_fitting: row.used_for_fitting,
          })),
          forecast.map((row) => ({
            period: row.period,
            value: row.value,
            lower: row.lower,
            upper: row.upper,
          })),
          { unit, intervalLevel: result.interval_level },
        )}
        source={result.model?.label?.[locale] ?? result.model?.name}
        footnote={
          backtest.mase != null
            ? w(
                locale,
                `Measured on held-out data: MASE ${backtest.mase}, interval covered ${Math.round(
                  (backtest.interval_coverage ?? 0) * 100,
                )}% against a ${Math.round((backtest.interval_target ?? 0) * 100)}% target.`,
                `مقاسة على بيانات محجوزة: MASE ${backtest.mase}، وغطّى الفاصل ${Math.round(
                  (backtest.interval_coverage ?? 0) * 100,
                )}% مقابل هدف ${Math.round((backtest.interval_target ?? 0) * 100)}%.`,
              )
            : backtest.reason
        }
        table={{
          columns: [
            { key: "period", label: w(locale, "Period", "الفترة") },
            { key: "kind", label: w(locale, "Kind", "النوع") },
            {
              key: "value",
              label: w(locale, "Value", "القيمة"),
              numeric: true,
            },
            { key: "range", label: w(locale, "Interval", "الفاصل") },
          ],
          rows: [
            ...history.map((row) => ({
              period: row.period,
              kind: w(locale, "observed", "مرصود"),
              value: row.value,
              range: "—",
            })),
            ...forecast.map((row) => ({
              period: String(row.period).slice(0, 7),
              kind: w(locale, "projected", "متوقع"),
              value: row.value,
              range: `${num(row.lower, locale)} – ${num(row.upper, locale)}`,
            })),
          ],
        }}
      />

      <div className="forecast__meta">
        <section className="panel">
          <h2>
            <Target size={16} />
            {w(locale, "How well it did", "مدى جودته")}
          </h2>
          {backtest.mase != null ? (
            <>
              <dl className="metric-pairs">
                <div>
                  <dt>MASE</dt>
                  <dd className={backtest.mase < 1 ? "is-good" : "is-warn"}>
                    {backtest.mase}
                  </dd>
                  <small>
                    {backtest.mase < 1
                      ? w(
                          locale,
                          `Better than repeating the benchmark (${backtest.mase_scale_basis}).`,
                          `أفضل من تكرار المرجع (${backtest.mase_scale_basis}).`,
                        )
                      : w(
                          locale,
                          "No better than a naive forecast — treat as a weak signal.",
                          "ليس أفضل من التوقع الساذج — تعامل معه كمؤشر ضعيف.",
                        )}
                  </small>
                </div>
                <div>
                  <dt>WAPE</dt>
                  <dd>
                    {backtest.wape == null
                      ? "—"
                      : `${Math.round(backtest.wape * 1000) / 10}%`}
                  </dd>
                  <small>
                    {w(
                      locale,
                      "Average error as a share of actual volume.",
                      "متوسط الخطأ كنسبة من الحجم الفعلي.",
                    )}
                  </small>
                </div>
                <div>
                  <dt>{w(locale, "Interval coverage", "تغطية الفاصل")}</dt>
                  <dd
                    className={
                      (backtest.interval_coverage ?? 0) >=
                      (backtest.interval_target ?? 0)
                        ? "is-good"
                        : "is-warn"
                    }
                  >
                    {Math.round((backtest.interval_coverage ?? 0) * 100)}%
                  </dd>
                  <small>
                    {w(
                      locale,
                      `Target ${Math.round((backtest.interval_target ?? 0) * 100)}%. Measured on data the model never saw.`,
                      `الهدف ${Math.round((backtest.interval_target ?? 0) * 100)}%. مقاسة على بيانات لم يرها النموذج.`,
                    )}
                  </small>
                </div>
              </dl>
              {backtest.interval_adjustment && (
                <p className="note note--warn">
                  <AlertTriangle size={14} />
                  {w(
                    locale,
                    `The interval was widened ${backtest.interval_adjustment.factor}× to match the error actually measured on held-out data.`,
                    `وُسِّع الفاصل ${backtest.interval_adjustment.factor} ضعفًا ليطابق الخطأ المقاس فعليًا على البيانات المحجوزة.`,
                  )}
                </p>
              )}
            </>
          ) : (
            <p className="muted">{backtest.reason}</p>
          )}
        </section>

        <section className="panel">
          <h2>
            <Activity size={16} />
            {w(locale, "Shape of the series", "شكل السلسلة")}
          </h2>
          <dl className="metric-pairs">
            <div>
              <dt>{w(locale, "Seasonality", "الموسمية")}</dt>
              <dd>
                {result.seasonality?.seasonal_strength == null
                  ? "—"
                  : `${Math.round(result.seasonality.seasonal_strength * 100)}%`}
              </dd>
              <small>
                {result.seasonality?.is_seasonal
                  ? w(
                      locale,
                      "A repeating annual pattern is present.",
                      "يوجد نمط سنوي متكرر.",
                    )
                  : w(
                      locale,
                      "No clear repeating pattern.",
                      "لا يوجد نمط متكرر واضح.",
                    )}
              </small>
            </div>
            <div>
              <dt>{w(locale, "Trend", "الاتجاه")}</dt>
              <dd>
                {result.seasonality?.trend_strength == null
                  ? "—"
                  : `${Math.round(result.seasonality.trend_strength * 100)}%`}
              </dd>
              <small>
                {result.seasonality?.is_trending
                  ? w(
                      locale,
                      "The level is moving steadily.",
                      "المستوى يتحرك باطّراد.",
                    )
                  : w(
                      locale,
                      "The level is broadly flat.",
                      "المستوى شبه ثابت.",
                    )}
              </small>
            </div>
            <div>
              <dt>{w(locale, "Residuals", "البواقي")}</dt>
              <dd>
                {result.residual_diagnostics?.residuals_look_like_noise
                  ? w(locale, "Noise", "ضجيج")
                  : w(locale, "Structured", "منظّمة")}
              </dd>
              <small>
                {result.residual_diagnostics?.bias_direction ===
                "no_material_bias"
                  ? w(
                      locale,
                      "No systematic bias detected.",
                      "لا يوجد تحيّز منهجي.",
                    )
                  : w(
                      locale,
                      "The model leans in one direction; treat the point value with care.",
                      "يميل النموذج في اتجاه واحد؛ تعامل مع القيمة المفردة بحذر.",
                    )}
              </small>
            </div>
          </dl>
        </section>
      </div>

      {Array.isArray(backtest.candidates) && backtest.candidates.length > 1 && (
        <Chart
          locale={locale}
          title={w(locale, "Models considered", "النماذج المرشّحة")}
          description={w(
            locale,
            "Mean absolute error across rolling origins. The lowest was selected; the rest are shown so the choice can be checked.",
            "متوسط الخطأ المطلق عبر أصول متدحرجة. اختير الأقل، وتُعرض البقية للتحقق من الاختيار.",
          )}
          height={Math.min(320, 60 + backtest.candidates.length * 26)}
          option={rankedBarOption(
            locale,
            backtest.candidates.map((item: Json) => ({
              label: item.label?.[locale] ?? item.name,
              value: item.mae,
              highlight: item.name === result.model?.name,
            })),
            { unit: "MAE" },
          )}
          table={{
            columns: [
              { key: "name", label: w(locale, "Model", "النموذج") },
              { key: "mae", label: "MAE", numeric: true },
              { key: "mase", label: "MASE", numeric: true },
              {
                key: "folds",
                label: w(locale, "Folds", "الطيّات"),
                numeric: true,
              },
            ],
            rows: backtest.candidates.map((item: Json) => ({
              name: item.label?.[locale] ?? item.name,
              mae: item.mae,
              mase: item.mase,
              folds: item.folds,
            })),
          }}
        />
      )}

      {Array.isArray(result.anomalies) && result.anomalies.length > 0 && (
        <section className="panel">
          <h2>
            <TrendingUp size={16} />
            {w(locale, "Unusual observations", "ملاحظات غير معتادة")}
          </h2>
          <p className="muted">
            {w(
              locale,
              "These sit far from their neighbours and pull the fit. Confirm whether each is a real event or a recording error.",
              "تبعد هذه القيم كثيرًا عن جاراتها وتؤثر على الملاءمة. تأكّد إن كانت أحداثًا حقيقية أم أخطاء تسجيل.",
            )}
          </p>
          <ul className="anomaly-list">
            {result.anomalies.map((item: Json) => (
              <li key={item.period}>
                <b>{item.period}</b>
                <span>{num(item.value, locale)}</span>
                <small>
                  {w(
                    locale,
                    `${item.direction === "above" ? "above" : "below"} a local level of ${num(item.local_median, locale)}`,
                    `${item.direction === "above" ? "أعلى" : "أدنى"} من مستوى محلي قدره ${num(item.local_median, locale)}`,
                  )}
                </small>
              </li>
            ))}
          </ul>
        </section>
      )}

      {warnings.length > 0 && (
        <ul className="warning-list">
          {warnings.map((item: string, index: number) => (
            <li key={index}>
              <AlertTriangle size={15} />
              {item}
            </li>
          ))}
        </ul>
      )}

      {limitations.length > 0 && (
        <section className="panel limitations">
          <h2>
            {w(locale, "What this does not establish", "ما لا يثبته هذا")}
          </h2>
          <ul>
            {limitations.map((item: string, index: number) => (
              <li key={index}>{item}</li>
            ))}
          </ul>
        </section>
      )}
    </>
  );
}
