"use client";

import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle,
  Download,
  FileText,
  Info,
  Lightbulb,
  Presentation,
  Scale,
  Search,
  ShieldAlert,
} from "lucide-react";
import type { Locale } from "@/lib/contracts";
import { apiRequest, postJson, resourceStatusFromError } from "@/lib/api";
import { num } from "@/lib/viz";
import { Chart } from "./chart";
import {
  paretoOption,
  rankedBarOption,
  scatterOption,
  trendOption,
} from "@/lib/chart-options";
import { ResourceState } from "./resource-state";

type Json = Record<string, any>;
const w = (locale: Locale, en: string, ar: string) =>
  locale === "ar" ? ar : en;

const SEVERITY_LABEL: Record<string, [string, string]> = {
  critical: ["Critical", "حرج"],
  high: ["High", "مرتفع"],
  medium: ["Medium", "متوسط"],
  low: ["Low", "منخفض"],
  info: ["Context", "سياق"],
};

const KIND_LABEL: Record<string, [string, string]> = {
  data_quality: ["Data quality", "جودة البيانات"],
  concentration: ["Concentration", "التركّز"],
  trend: ["Trend", "الاتجاه"],
  segment: ["Segment", "الشريحة"],
  missingness: ["Missing data", "البيانات المفقودة"],
  distribution: ["Distribution", "التوزيع"],
  relationship: ["Relationship", "العلاقة"],
  engine: ["Engine", "المحرك"],
};

export function AnalystWorkspace({ locale }: { locale: Locale }) {
  const ar = locale === "ar";
  const [datasets, setDatasets] = useState<Json[]>([]);
  const [datasetId, setDatasetId] = useState("");
  const [versions, setVersions] = useState<Json[]>([]);
  const [versionId, setVersionId] = useState("");
  const [insights, setInsights] = useState<Json | null>(null);
  const [busy, setBusy] = useState(false);
  const [exporting, setExporting] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [filter, setFilter] = useState<string>("all");

  useEffect(() => {
    apiRequest<{ items: Json[] }>("/api/v1/datasets")
      .then((value) => {
        setDatasets(value.items);
        if (value.items.length) setDatasetId(value.items[0].id);
      })
      .catch(setError);
  }, []);

  useEffect(() => {
    if (!datasetId) return;
    apiRequest<{ items: Json[] }>(
      `/api/v1/datasets/${encodeURIComponent(datasetId)}/versions`,
    )
      .then((value) => {
        setVersions(value.items);
        const latest = value.items[value.items.length - 1];
        if (latest) setVersionId(latest.id);
      })
      .catch(setError);
  }, [datasetId]);

  const analyze = useCallback(async () => {
    if (!versionId) return;
    setBusy(true);
    setError(null);
    try {
      setInsights(
        await postJson<Json>(
          `/api/v1/dataset-versions/${encodeURIComponent(versionId)}/insights`,
          {},
        ),
      );
    } catch (cause) {
      setError(cause);
      setInsights(null);
    } finally {
      setBusy(false);
    }
  }, [versionId]);

  useEffect(() => {
    if (versionId) void analyze();
  }, [versionId, analyze]);

  async function download(format: string) {
    setExporting(format);
    setError(null);
    try {
      const response = await fetch(
        `/api/v1/dataset-versions/${encodeURIComponent(versionId)}/brief/export`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRF-Token": (
              await apiRequest<{ csrf_token: string }>("/api/v1/auth/csrf")
            ).csrf_token,
          },
          credentials: "same-origin",
          body: JSON.stringify({ locale, format, include_forecast: true }),
        },
      );
      if (!response.ok) throw new Error(await response.text());
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `baseera-brief-${locale}.${format}`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (cause) {
      setError(cause);
    } finally {
      setExporting(null);
    }
  }

  const findings = ((insights?.findings ?? []) as Json[]).filter(
    (item) => filter === "all" || item.severity === filter,
  );
  const counts = (insights?.counts ?? {}) as Record<string, number>;

  return (
    <div className="stack-page analyst">
      <header className="page-header">
        <div>
          <p className="eyebrow">{w(locale, "Analysis", "التحليل")}</p>
          <h1>{w(locale, "What the data says", "ماذا تقول البيانات")}</h1>
          <p>
            {w(
              locale,
              "Each finding separates what was observed, how it reads, what to do, and what it does not prove. Observations are arithmetic and reproducible.",
              "تفصل كل نتيجة بين ما رُصد وكيف يُقرأ وما ينبغي فعله وما لا يثبته. الملاحظات عمليات حسابية قابلة لإعادة الإنتاج.",
            )}
          </p>
        </div>
      </header>

      <section className="live-form panel">
        <label>
          {w(locale, "Dataset", "مجموعة البيانات")}
          <select
            value={datasetId}
            onChange={(event) => setDatasetId(event.target.value)}
          >
            {datasets.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          {w(locale, "Version", "الإصدار")}
          <select
            value={versionId}
            onChange={(event) => setVersionId(event.target.value)}
          >
            {versions.map((item) => (
              <option key={item.id} value={item.id}>
                {w(locale, "Version", "إصدار")} {item.version_number} ·{" "}
                {item.kind === "raw"
                  ? w(locale, "as received", "كما وردت")
                  : w(locale, "cleaned", "منظّفة")}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          className="button button--primary"
          onClick={analyze}
          disabled={!versionId || busy}
        >
          <Search size={16} />
          {busy
            ? w(locale, "Analysing…", "جارٍ التحليل…")
            : w(locale, "Analyse", "حلّل")}
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

      {insights && (
        <>
          <section className="deliverables">
            <div>
              <h2>{w(locale, "Hand this over", "سلّم هذا العمل")}</h2>
              <p>
                {w(
                  locale,
                  "The brief covers condition, repairs, findings, outlook and limits in one document.",
                  "يغطي الموجز الحالة والإصلاحات والنتائج والتوقعات والحدود في وثيقة واحدة.",
                )}
              </p>
            </div>
            <div className="deliverables__actions">
              {(
                [
                  [
                    "pptx",
                    Presentation,
                    w(locale, "Presentation", "عرض تقديمي"),
                  ],
                  ["pdf", FileText, "PDF"],
                  ["docx", FileText, "Word"],
                  ["md", Download, "Markdown"],
                ] as const
              ).map(([format, Icon, label]) => (
                <button
                  key={format}
                  type="button"
                  className={
                    format === "pptx"
                      ? "button button--primary"
                      : "button button--secondary"
                  }
                  onClick={() => download(format)}
                  disabled={exporting !== null}
                >
                  <Icon size={16} />
                  {exporting === format
                    ? w(locale, "Preparing…", "جارٍ التجهيز…")
                    : label}
                </button>
              ))}
            </div>
          </section>

          <div className="severity-filter" role="group">
            {(
              [
                [
                  "all",
                  w(locale, "All", "الكل"),
                  Object.values(counts).reduce((a, b) => a + b, 0),
                ],
                ...(["critical", "high", "medium", "low", "info"] as const)
                  .filter((key) => counts[key])
                  .map((key) => [
                    key,
                    SEVERITY_LABEL[key][ar ? 1 : 0],
                    counts[key],
                  ]),
              ] as Array<[string, string, number]>
            ).map(([key, label, count]) => (
              <button
                key={key}
                type="button"
                className={`severity-chip severity-chip--${key}`}
                aria-pressed={filter === key}
                onClick={() => setFilter(key)}
              >
                {label}
                <b>{count}</b>
              </button>
            ))}
          </div>

          {findings.length === 0 ? (
            <section className="panel">
              <p className="muted">
                {w(
                  locale,
                  "No finding met the reporting threshold at this severity.",
                  "لم تتجاوز أي نتيجة عتبة الإبلاغ عند هذه الخطورة.",
                )}
              </p>
            </section>
          ) : (
            findings.map((finding) => (
              <FindingCard key={finding.id} locale={locale} finding={finding} />
            ))
          )}

          <p className="disclosure">
            <Scale size={15} />
            {insights.disclosure?.[ar ? "ar" : "en"]}
          </p>
        </>
      )}
    </div>
  );
}

function FindingCard({ locale, finding }: { locale: Locale; finding: Json }) {
  const ar = locale === "ar";
  const language = ar ? "ar" : "en";
  const Icon =
    finding.severity === "critical" || finding.severity === "high"
      ? ShieldAlert
      : finding.severity === "info"
        ? Info
        : AlertTriangle;
  return (
    <article className={`finding finding--${finding.severity}`}>
      <header>
        <span className="finding__severity">
          <Icon size={14} />
          {SEVERITY_LABEL[finding.severity]?.[ar ? 1 : 0] ?? finding.severity}
        </span>
        <span className="finding__kind">
          {KIND_LABEL[finding.kind]?.[ar ? 1 : 0] ?? finding.kind}
        </span>
        <h2>{finding.title?.[language]}</h2>
        <small>
          {w(locale, "Confidence", "الثقة")}:{" "}
          {finding.confidence === "high"
            ? w(locale, "high", "عالية")
            : finding.confidence === "medium"
              ? w(locale, "medium", "متوسطة")
              : w(locale, "low", "منخفضة")}
        </small>
      </header>

      <div className="finding__body">
        <p>
          <b>{w(locale, "Observed", "الملاحظة")}</b>
          {finding.observation?.[language]}
        </p>
        <p>
          <b>{w(locale, "Reading", "التفسير")}</b>
          {finding.interpretation?.[language]}
        </p>
        <p className="finding__action">
          <Lightbulb size={14} />
          <span>
            <b>{w(locale, "Action", "الإجراء")}</b>
            {finding.recommendation?.[language]}
          </span>
        </p>
        <p className="finding__limit">
          <b>{w(locale, "Limit", "الحد")}</b>
          {finding.limitation?.[language]}
        </p>
      </div>

      <FindingChart locale={locale} finding={finding} />
    </article>
  );
}

function FindingChart({ locale, finding }: { locale: Locale; finding: Json }) {
  const evidence = (finding.evidence ?? {}) as Json;
  const chart = finding.chart as Json | undefined;
  if (!chart) return null;

  if (chart.type === "pareto" && Array.isArray(evidence.top_values)) {
    return (
      <Chart
        locale={locale}
        height={280}
        option={paretoOption(
          locale,
          evidence.top_values.map((item: Json) => ({
            label: String(item.label),
            value: item.value,
          })),
          { unit: evidence.measure },
        )}
        table={{
          columns: [
            { key: "label", label: String(evidence.dimension ?? "") },
            {
              key: "value",
              label: String(evidence.measure ?? ""),
              numeric: true,
            },
            { key: "share", label: w(locale, "Share", "الحصة") },
          ],
          rows: evidence.top_values.map((item: Json) => ({
            label: item.label,
            value: item.value,
            share: `${Math.round(item.share * 1000) / 10}%`,
          })),
        }}
      />
    );
  }

  if (chart.type === "line" && Array.isArray(evidence.series)) {
    return (
      <Chart
        locale={locale}
        height={250}
        option={trendOption(
          locale,
          evidence.series.map((item: Json) => ({
            label: item.period,
            value: item.value,
          })),
          { unit: evidence.measure },
        )}
        table={{
          columns: [
            { key: "period", label: w(locale, "Period", "الفترة") },
            {
              key: "value",
              label: String(evidence.measure ?? ""),
              numeric: true,
            },
          ],
          rows: evidence.series.map((item: Json) => ({
            period: item.period,
            value: item.value,
          })),
        }}
      />
    );
  }

  if (chart.type === "bar") {
    const series = (evidence.rates ?? chart.series) as
      | Record<string, number>
      | undefined;
    const segments = evidence.all_segments as Json[] | undefined;
    const rows = segments
      ? segments.map((item) => ({
          label: String(item.label),
          value: item.mean,
          highlight: item.label === evidence.segment,
        }))
      : Object.entries(series ?? {}).map(([label, value]) => ({
          label,
          value: Number(value) * (evidence.rates ? 100 : 1),
          highlight: label === evidence.worst_segment,
        }));
    if (rows.length < 2) return null;
    return (
      <Chart
        locale={locale}
        height={Math.min(300, 60 + rows.length * 28)}
        option={rankedBarOption(locale, rows, {
          unit: evidence.rates ? "%" : String(evidence.measure ?? ""),
        })}
        table={{
          columns: [
            { key: "label", label: String(evidence.dimension ?? "") },
            {
              key: "value",
              label: w(locale, "Value", "القيمة"),
              numeric: true,
            },
          ],
          rows: rows.map((row) => ({ label: row.label, value: row.value })),
        }}
      />
    );
  }

  if (chart.type === "scatter" && evidence.pearson_r != null) {
    return null; // The raw pairs are not carried on the finding; the numbers say it.
  }

  return null;
}
