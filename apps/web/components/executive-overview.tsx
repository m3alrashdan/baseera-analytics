"use client";

import { useState } from "react";
import {
  AlertCircle,
  ArrowDownRight,
  ArrowUpRight,
  CalendarClock,
  CheckCircle2,
  Minus,
  Sparkles,
} from "lucide-react";
import type { Locale, MetricResult, OverviewResponse } from "@/lib/contracts";
import { formatCompactNumber, formatDate, formatNumber, t } from "@/lib/i18n";
import { ChartPanel } from "./chart-panel";
import { EvidenceDrawer, type EvidenceRecord } from "./evidence-drawer";
import { ResourceState } from "./resource-state";

interface ExecutiveOverviewProps {
  locale: Locale;
  data: OverviewResponse;
  offline?: boolean;
}

function metricEvidence(
  metric: MetricResult,
  data: OverviewResponse,
): EvidenceRecord {
  return {
    metricId: metric.id,
    resultId: metric.result_id,
    definition: metric.definition,
    scope: data.period.label,
    source: metric.source,
    freshness: metric.freshness,
    warning: metric.warning,
  };
}

export function ExecutiveOverview({
  locale,
  data,
  offline,
}: ExecutiveOverviewProps) {
  const [evidence, setEvidence] = useState<EvidenceRecord | null>(null);
  const ar = locale === "ar";
  if (data.status === "empty")
    return (
      <ResourceState
        locale={locale}
        status="empty"
        reason={
          ar
            ? "اربط مصدرًا أو ارفع ملفًا لإنشاء أول نظرة تنفيذية."
            : "Connect a source or upload a file to create the first executive view."
        }
      />
    );
  return (
    <div className="overview-page">
      <header className="page-header page-header--overview">
        <div>
          <p className="eyebrow">
            {ar
              ? "موجز القيادة · نطاق متحقق"
              : "Leadership brief · verified scope"}
          </p>
          <h1>{t(locale, "overview.title")}</h1>
          <p>{data.company.name}</p>
        </div>
        <div className="page-header__meta">
          <span className="badge badge--demo">
            {data.company.demo
              ? t(locale, "demo.label")
              : ar
                ? "مساحة شركة"
                : "Company workspace"}
          </span>
          <span>
            <CalendarClock size={15} aria-hidden="true" /> {data.period.label}
          </span>
        </div>
      </header>
      {offline ? (
        <div className="truth-banner" role="status">
          <AlertCircle size={17} aria-hidden="true" />
          {t(locale, "demo.offline")}
        </div>
      ) : null}
      <section
        className="executive-brief"
        aria-labelledby="executive-brief-heading"
      >
        <div className="brief-mark" aria-hidden="true">
          <Sparkles />
        </div>
        <div>
          <p className="eyebrow">{t(locale, "overview.brief")}</p>
          <h2 id="executive-brief-heading">{data.brief}</h2>
          <p>
            {ar
              ? "المؤشرات أدناه مرتبطة بتعاريف معتمدة وسجل نتائج قابل لإعادة الإنتاج."
              : "The metrics below bind to approved definitions and reproducible result records."}
          </p>
        </div>
        <button
          className="button button--secondary"
          type="button"
          onClick={() =>
            document
              .getElementById("attention-panel")
              ?.scrollIntoView({ behavior: "smooth" })
          }
        >
          {ar ? "راجع الاستثناءات" : "Review exceptions"}
        </button>
      </section>
      <section
        className="kpi-grid"
        aria-label={ar ? "المؤشرات الرئيسية" : "Key performance indicators"}
      >
        {data.metrics.length ? (
          data.metrics.map((metric) => {
            const change = metric.change;
            const TrendIcon =
              metric.trend === "up"
                ? ArrowUpRight
                : metric.trend === "down"
                  ? ArrowDownRight
                  : Minus;
            return (
              <article className="kpi-card" key={metric.id}>
                <div className="kpi-card__top">
                  <span>{metric.name}</span>
                  <span className={`trend trend--${metric.trend}`}>
                    <TrendIcon size={15} aria-hidden="true" />
                    {change == null
                      ? "—"
                      : `${change > 0 ? "+" : ""}${formatNumber(change, locale)}%`}
                  </span>
                </div>
                <p className="kpi-card__value">
                  <bdi>
                    {metric.value == null
                      ? "—"
                      : metric.unit === "ratio"
                        ? formatNumber(metric.value * 100, locale)
                        : formatCompactNumber(metric.value, locale)}
                  </bdi>{" "}
                  <small>
                    <bdi>{metric.unit === "ratio" ? "%" : metric.unit}</bdi>
                  </small>
                </p>
                <div className="kpi-card__foot">
                  <span>{metric.freshness}</span>
                  <button
                    className="evidence-button"
                    type="button"
                    onClick={() => setEvidence(metricEvidence(metric, data))}
                    aria-label={`${ar ? "فحص الدليل لـ" : "Inspect evidence for"} ${metric.name}`}
                  >
                    {t(locale, "action.inspect")}
                  </button>
                </div>
              </article>
            );
          })
        ) : (
          <ResourceState
            locale={locale}
            status="empty"
            compact
            reason={
              ar
                ? "لا توجد مؤشرات مسموحة في هذا النطاق."
                : "No permitted metrics exist in this scope."
            }
          />
        )}
      </section>
      <div className="overview-grid">
        <ChartPanel
          locale={locale}
          title={t(locale, "overview.trend")}
          description={
            ar
              ? "صافي الإيرادات الشهري مقابل الشهر نفسه من العام السابق"
              : "Monthly net revenue against the same month of the previous year"
          }
          unit={data.company.currency}
          source={
            data.metrics[0]?.source ??
            (ar ? "لا يوجد مصدر متاح" : "No source available")
          }
          data={data.trend.map((row) => ({
            label: row.period,
            value: row.current,
            comparison: row.comparison,
          }))}
          onPointSelect={(point) =>
            data.metrics[0] &&
            setEvidence({
              ...metricEvidence(data.metrics[0], data),
              scope: `${data.period.label} · ${point.label}`,
            })
          }
        />
        <section
          className="attention-panel"
          id="attention-panel"
          aria-labelledby="attention-heading"
        >
          <header>
            <p className="eyebrow">
              {ar ? "استثناءات مرصودة" : "Observed exceptions"}
            </p>
            <h2 id="attention-heading">{t(locale, "overview.attention")}</h2>
          </header>
          <div className="attention-list">
            {data.attention.length ? (
              data.attention.map((item, index) => (
                <article key={item.id}>
                  <span
                    className={`severity-dot severity-dot--${item.severity}`}
                    aria-label={item.severity}
                  />
                  <div>
                    <span className="attention-index">
                      {String(index + 1).padStart(2, "0")}
                    </span>
                    <h3>{item.title}</h3>
                    <p>{item.detail}</p>
                  </div>
                </article>
              ))
            ) : (
              <p className="empty-inline">
                {ar
                  ? "لا توجد استثناءات مؤكدة."
                  : "No verified exceptions in scope."}
              </p>
            )}
          </div>
        </section>
      </div>
      <div className="lower-grid">
        <ChartPanel
          locale={locale}
          kind="bar"
          title={t(locale, "overview.departments")}
          description={
            ar
              ? "الطلب كنسبة من الطاقة المتاحة"
              : "Demand as a share of available capacity"
          }
          unit="%"
          data={data.departments.map((row) => ({
            label: row.name,
            value: row.value,
            comparison: row.target,
          }))}
        />
        <section className="action-panel" aria-labelledby="action-heading">
          <header className="panel-heading">
            <div>
              <p className="eyebrow">{ar ? "حلقة القرار" : "Decision loop"}</p>
              <h2 id="action-heading">{t(locale, "overview.actions")}</h2>
            </div>
          </header>
          <ul className="action-list">
            {!data.actions.length ? (
              <li>
                {ar
                  ? "لا توجد إجراءات مراجعة مرتبطة بهذا الملخص."
                  : "No reviewed actions are linked to this summary."}
              </li>
            ) : null}
            {data.actions.map((action) => (
              <li key={action.id}>
                <CheckCircle2 size={18} aria-hidden="true" />
                <div>
                  <b>{action.title}</b>
                  <span>
                    {action.owner} · {formatDate(action.due, locale)}
                  </span>
                </div>
                <span className="badge">{action.status}</span>
              </li>
            ))}
          </ul>
        </section>
      </div>
      <EvidenceDrawer
        locale={locale}
        evidence={evidence}
        open={Boolean(evidence)}
        onClose={() => setEvidence(null)}
      />
    </div>
  );
}
