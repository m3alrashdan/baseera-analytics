"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import {
  CheckCircle2,
  Database,
  Download,
  Play,
  RefreshCw,
  Save,
  Search,
  ShieldCheck,
} from "lucide-react";
import type { Locale, UploadAccepted } from "@/lib/contracts";
import {
  apiRequest,
  postJson,
  resourceStatusFromError,
  uploadDataset,
} from "@/lib/api";
import { ResourceState } from "./resource-state";
import { UploadStudio } from "./upload-studio";
import { ChartPanel } from "./chart-panel";

type Row = Record<string, any>;
type Props = { locale: Locale };
const words = (locale: Locale, en: string, ar: string) =>
  locale === "ar" ? ar : en;

function useResource<T>(path: string) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const active = useRef<AbortController | null>(null);
  const load = useCallback(() => {
    active.current?.abort();
    const controller = new AbortController();
    active.current = controller;
    setLoading(true);
    setError(null);
    setData(null);
    apiRequest<T>(path, { signal: controller.signal })
      .then((value) => {
        if (!controller.signal.aborted) setData(value);
      })
      .catch((cause) => {
        if (!controller.signal.aborted) setError(cause);
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => active.current?.abort();
  }, [path]);
  useEffect(load, [load]);
  return { data, error, loading, reload: load };
}

function PageTitle({
  locale,
  title,
  detail,
  children,
}: Props & { title: string; detail: string; children?: React.ReactNode }) {
  return (
    <header className="page-header">
      <div>
        <p className="eyebrow">
          {words(locale, "Your connected workspace", "مساحة عملك المتصلة")}
        </p>
        <h1>{title}</h1>
        <p>{detail}</p>
      </div>
      {children}
    </header>
  );
}

function Problem({ locale, error }: Props & { error: unknown }) {
  return error ? (
    <ResourceState
      locale={locale}
      status={resourceStatusFromError(error)}
      reason={error instanceof Error ? error.message : String(error)}
      compact
    />
  ) : null;
}

function cell(value: unknown, locale: Locale): string {
  if (value == null) return "—";
  if (typeof value === "number")
    return new Intl.NumberFormat(locale === "ar" ? "ar-JO" : "en", {
      maximumFractionDigits: 3,
    }).format(value);
  if (typeof value === "boolean")
    return words(locale, value ? "Yes" : "No", value ? "نعم" : "لا");
  return Array.isArray(value)
    ? value.join(" · ")
    : typeof value === "object"
      ? JSON.stringify(value)
      : String(value);
}

export function RecordsTable({
  locale,
  rows,
  title,
}: Props & { rows: Row[]; title: string }) {
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(0);
  const [sort, setSort] = useState<{ key: string; ascending: boolean } | null>(
    null,
  );
  const columns = Array.from(new Set(rows.flatMap(Object.keys))).filter(
    (key) => !key.endsWith("_id") && key !== "id",
  );
  if (!columns.length && rows.length) columns.push(...Object.keys(rows[0]));
  const filtered = rows.filter((row) =>
    Object.values(row).some((value) =>
      cell(value, locale)
        .toLocaleLowerCase()
        .includes(search.toLocaleLowerCase()),
    ),
  );
  if (sort)
    filtered.sort((a, b) => {
      const first = a[sort.key],
        second = b[sort.key];
      const order =
        typeof first === "number" && typeof second === "number"
          ? first - second
          : cell(first, locale).localeCompare(cell(second, locale));
      return sort.ascending ? order : -order;
    });
  const pageCount = Math.max(1, Math.ceil(filtered.length / 20));
  const current = Math.min(page, pageCount - 1);
  return (
    <section className="records-panel">
      <header className="panel-heading">
        <div>
          <h2>{title}</h2>
          <p>
            {words(
              locale,
              "Search and sort the records returned within your access scope.",
              "ابحث ورتّب السجلات المعادة ضمن صلاحياتك.",
            )}
          </p>
        </div>
        <label className="live-search">
          <Search size={16} />
          <input
            aria-label={words(locale, "Search records", "ابحث في السجلات")}
            placeholder={words(locale, "Search records…", "ابحث في السجلات…")}
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
              setPage(0);
            }}
          />
        </label>
      </header>
      {!filtered.length ? (
        <ResourceState
          locale={locale}
          status="empty"
          reason={words(
            locale,
            "No matching records.",
            "لا توجد سجلات مطابقة.",
          )}
          compact
        />
      ) : (
        <div className="table-scroll">
          <table>
            <caption className="sr-only">{title}</caption>
            <thead>
              <tr>
                {columns.map((key) => (
                  <th
                    key={key}
                    aria-sort={
                      sort?.key === key
                        ? sort.ascending
                          ? "ascending"
                          : "descending"
                        : "none"
                    }
                  >
                    <button
                      className="table-sort"
                      onClick={() =>
                        setSort({
                          key,
                          ascending: sort?.key === key ? !sort.ascending : true,
                        })
                      }
                    >
                      {key.replaceAll("_", " ")}
                      {sort?.key === key ? (sort.ascending ? " ↑" : " ↓") : ""}
                    </button>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered
                .slice(current * 20, current * 20 + 20)
                .map((row, index) => (
                  <tr key={row.id ?? index}>
                    {columns.map((key) => (
                      <td key={key}>
                        <bdi>{cell(row[key], locale)}</bdi>
                      </td>
                    ))}
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      )}
      <footer className="live-pagination">
        <span>
          {filtered.length} {words(locale, "records ·", "سجلًا ·")}{" "}
          {current + 1}/{pageCount}
        </span>
        <div className="action-row">
          <button
            className="button button--secondary"
            disabled={current === 0}
            onClick={() => setPage(current - 1)}
          >
            {words(locale, "Previous", "السابق")}
          </button>
          <button
            className="button button--secondary"
            disabled={current + 1 >= pageCount}
            onClick={() => setPage(current + 1)}
          >
            {words(locale, "Next", "التالي")}
          </button>
        </div>
      </footer>
    </section>
  );
}

export function LiveCompany({ locale, module }: Props & { module: string }) {
  const titles: Record<string, [string, string]> = {
    customers: ["Customers & sales", "العملاء والمبيعات"],
    people: ["People & capacity", "الأفراد والطاقة"],
    projects: ["Project portfolio", "محفظة المشاريع"],
    operations: ["Operations", "العمليات"],
    finance: ["Costs & budgets", "التكاليف والموازنات"],
    support: ["Customer support", "دعم العملاء"],
    objectives: ["Objectives", "الأهداف"],
  };
  const { data, error, loading, reload } = useResource<{
    items: Row[];
    scope: Row;
  }>(`/api/v1/company/${module === "finance" ? "costs" : module}`);
  const title = titles[module]?.[locale === "ar" ? 1 : 0] ?? module;
  return (
    <div className="stack-page">
      <PageTitle
        locale={locale}
        title={title}
        detail={words(
          locale,
          "Company records are filtered by your organization and permitted departments.",
          "سجلات الشركة مقيّدة بمؤسستك والإدارات المسموحة.",
        )}
      >
        <button className="button button--secondary" onClick={reload}>
          <RefreshCw size={16} />
          {words(locale, "Refresh", "تحديث")}
        </button>
      </PageTitle>
      <Problem locale={locale} error={error} />
      {loading && !data ? (
        <ResourceState locale={locale} status="loading" />
      ) : data ? (
        <>
          <div className="truth-banner">
            <ShieldCheck size={17} />
            {words(
              locale,
              "Live records · up to 250 records per module. Totals below reflect the returned records.",
              "سجلات حية · حتى ٢٥٠ سجلًا لكل وحدة. الإجماليات تخص السجلات المعادة.",
            )}
          </div>
          <div className="live-summary">
            <article>
              <span>
                {words(locale, "Returned records", "السجلات المعادة")}
              </span>
              <strong>{cell(data.items.length, locale)}</strong>
            </article>
            {module === "people" &&
            data.items.length > 0 &&
            data.items.every(
              (row) =>
                typeof row.capacity_hours === "number" &&
                typeof row.workload_hours === "number",
            ) ? (
              <>
                <article>
                  <span>
                    {words(locale, "Planned capacity", "الطاقة المخططة")}
                  </span>
                  <strong>
                    {cell(
                      data.items.reduce(
                        (sum, row) => sum + Number(row.capacity_hours ?? 0),
                        0,
                      ),
                      locale,
                    )}{" "}
                    h
                  </strong>
                </article>
                <article>
                  <span>
                    {words(locale, "Assigned workload", "العمل المكلّف")}
                  </span>
                  <strong>
                    {cell(
                      data.items.reduce(
                        (sum, row) => sum + Number(row.workload_hours ?? 0),
                        0,
                      ),
                      locale,
                    )}{" "}
                    h
                  </strong>
                </article>
              </>
            ) : null}
            {module === "finance" ? (
              <>
                <article>
                  <span>
                    {words(locale, "Recorded actual", "المصروف المسجل")}
                  </span>
                  <strong>
                    {cell(
                      data.items.reduce(
                        (sum, row) => sum + Number(row.actual ?? 0),
                        0,
                      ),
                      locale,
                    )}{" "}
                    JOD
                  </strong>
                </article>
                <article>
                  <span>
                    {words(locale, "Recorded budget", "الموازنة المسجلة")}
                  </span>
                  <strong>
                    {cell(
                      data.items.reduce(
                        (sum, row) => sum + Number(row.budget ?? 0),
                        0,
                      ),
                      locale,
                    )}{" "}
                    JOD
                  </strong>
                </article>
              </>
            ) : null}
          </div>
          <RecordsTable locale={locale} rows={data.items} title={title} />
        </>
      ) : null}
    </div>
  );
}

export function LiveSources({ locale }: Props) {
  return (
    <div className="stack-page">
      <UploadStudio locale={locale} upload={uploadDataset} />
      <section className="live-next-step">
        <Database />
        <div>
          <h2>
            {words(
              locale,
              "Continue with the uploaded version",
              "تابع العمل على الإصدار المرفوع",
            )}
          </h2>
          <p>
            {words(
              locale,
              "Inspect all columns, preview your cleaning recipe, then explicitly approve a new version.",
              "افحص جميع الأعمدة وعاين خطوات التنظيف ثم وافق صراحة على إصدار جديد.",
            )}
          </p>
        </div>
        <Link
          className="button button--primary"
          href={`/${locale}/data/quality`}
        >
          {words(locale, "Inspect quality", "افحص الجودة")}
        </Link>
      </section>
      <LiveCatalog locale={locale} />
    </div>
  );
}

export function LiveCatalog({ locale }: Props) {
  const { data, error, loading, reload } = useResource<{ items: Row[] }>(
    "/api/v1/datasets",
  );
  return (
    <div className="stack-page">
      <PageTitle
        locale={locale}
        title={words(locale, "Data catalog", "دليل البيانات")}
        detail={words(
          locale,
          "Versioned datasets in your organization.",
          "مجموعات البيانات ذات الإصدارات في مؤسستك.",
        )}
      >
        <button className="button button--secondary" onClick={reload}>
          <RefreshCw size={16} />
          {words(locale, "Refresh", "تحديث")}
        </button>
      </PageTitle>
      <Problem locale={locale} error={error} />
      {loading && !data ? (
        <ResourceState locale={locale} status="loading" />
      ) : data ? (
        <RecordsTable
          locale={locale}
          rows={data.items}
          title={words(locale, "Datasets", "مجموعات البيانات")}
        />
      ) : null}
    </div>
  );
}

export function LiveQuality({ locale }: Props) {
  const [version, setVersion] = useState("");
  const [dataset, setDataset] = useState("");
  const [versionNumber, setVersionNumber] = useState(1);
  const [profile, setProfile] = useState<Row | null>(null);
  const [preview, setPreview] = useState<Row | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [kind, setKind] = useState("trim_whitespace");
  const [column, setColumn] = useState("");
  const [replacement, setReplacement] = useState("");
  const [approved, setApproved] = useState(false);
  useEffect(() => {
    try {
      const recent: UploadAccepted = JSON.parse(
        sessionStorage.getItem("baseera-last-upload") ?? "null",
      );
      if (recent) {
        setVersion(recent.version_id ?? "");
        setDataset(recent.dataset_id);
        setVersionNumber(recent.version_number ?? 1);
      }
    } catch {
      /* No remembered upload. */
    }
  }, []);
  const steps = [
    {
      kind,
      columns: column ? [column] : [],
      ...(kind === "replace_missing" ? { value: replacement } : {}),
      ...(kind === "deduplicate" ? { keep: "first" } : {}),
    },
  ];
  async function inspect() {
    setBusy(true);
    setError(null);
    setPreview(null);
    try {
      const result = await apiRequest<Row>(
        `/api/v1/dataset-versions/${encodeURIComponent(version)}/profile`,
      );
      setProfile(result);
      setColumn(Object.keys(result.column_profiles ?? {})[0] ?? "");
    } catch (cause) {
      setError(cause);
    } finally {
      setBusy(false);
    }
  }
  async function review() {
    setBusy(true);
    setError(null);
    setApproved(false);
    try {
      setPreview(
        await postJson(
          `/api/v1/dataset-versions/${encodeURIComponent(version)}/cleaning/preview`,
          { steps },
        ),
      );
    } catch (cause) {
      setError(cause);
    } finally {
      setBusy(false);
    }
  }
  async function apply() {
    setBusy(true);
    setError(null);
    try {
      const result = await postJson<Row>(
        `/api/v1/dataset-versions/${encodeURIComponent(version)}/cleaning/apply`,
        { steps, expected_version: versionNumber, approved },
      );
      const next = result.version;
      setVersion(next.id);
      setVersionNumber(next.version_number);
      setPreview(null);
      setProfile(null);
      setNotice(
        words(
          locale,
          `Version ${next.version_number} saved. The source version remains available.`,
          `حُفظ الإصدار ${next.version_number}. الإصدار الأصلي ما زال متاحًا.`,
        ),
      );
      sessionStorage.setItem(
        "baseera-last-upload",
        JSON.stringify({
          dataset_id: dataset,
          version_id: next.id,
          version_number: next.version_number,
          status: "accepted",
        }),
      );
    } catch (cause) {
      setError(cause);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="stack-page">
      <PageTitle
        locale={locale}
        title={words(locale, "Review data quality", "راجع جودة البيانات")}
        detail={words(
          locale,
          "A preview reconciles row counts and revenue before any version is written.",
          "تطابق المعاينة عدد الصفوف والإيرادات قبل كتابة أي إصدار.",
        )}
      />
      <section className="live-form panel">
        <label>
          {words(locale, "Dataset version ID", "معرّف إصدار البيانات")}
          <input
            value={version}
            onChange={(event) => {
              setVersion(event.target.value);
              setProfile(null);
              setPreview(null);
            }}
            placeholder="dataset-version-…"
            dir="ltr"
          />
        </label>
        <label>
          {words(locale, "Expected version number", "رقم الإصدار المتوقع")}
          <input
            type="number"
            min={1}
            value={versionNumber}
            onChange={(event) => setVersionNumber(Number(event.target.value))}
          />
        </label>
        <button
          className="button button--primary"
          disabled={!version || busy}
          onClick={inspect}
        >
          {words(locale, "Inspect version", "افحص الإصدار")}
        </button>
      </section>
      <Problem locale={locale} error={error} />
      {notice ? (
        <p className="success-message" role="status">
          <CheckCircle2 size={17} />
          {notice}
        </p>
      ) : null}
      {profile ? (
        <>
          <div className="live-summary">
            <article>
              <span>{words(locale, "Rows", "الصفوف")}</span>
              <strong>{cell(profile.row_count, locale)}</strong>
            </article>
            <article>
              <span>{words(locale, "Columns", "الأعمدة")}</span>
              <strong>{cell(profile.column_count, locale)}</strong>
            </article>
            <article>
              <span>{words(locale, "Inspection scope", "نطاق الفحص")}</span>
              <strong>{profile.scope}</strong>
            </article>
          </div>
          <RecordsTable
            locale={locale}
            title={words(locale, "Column profiles", "ملفات الأعمدة")}
            rows={Object.entries(profile.column_profiles ?? {}).map(
              ([name, value]) => ({ name, ...(value as Row) }),
            )}
          />
          <RecordsTable
            locale={locale}
            title={words(locale, "Quality findings", "نتائج الجودة")}
            rows={Object.entries(profile.quality_issues ?? {}).map(
              ([name, value]) => ({ name, ...(value as Row) }),
            )}
          />
          <section className="live-form panel">
            <label>
              {words(locale, "Cleaning step", "خطوة التنظيف")}
              <select
                value={kind}
                onChange={(event) => {
                  setKind(event.target.value);
                  setPreview(null);
                }}
              >
                <option value="trim_whitespace">
                  {words(locale, "Trim whitespace", "إزالة المسافات الطرفية")}
                </option>
                <option value="deduplicate">
                  {words(
                    locale,
                    "Deduplicate by key (keep first)",
                    "إزالة التكرار بالمفتاح (إبقاء الأول)",
                  )}
                </option>
                <option value="replace_missing">
                  {words(
                    locale,
                    "Replace missing values",
                    "استبدال القيم المفقودة",
                  )}
                </option>
              </select>
            </label>
            <label>
              {words(locale, "Column", "العمود")}
              <select
                value={column}
                onChange={(event) => {
                  setColumn(event.target.value);
                  setPreview(null);
                }}
              >
                {Object.keys(profile.column_profiles ?? {}).map((name) => (
                  <option key={name}>{name}</option>
                ))}
              </select>
            </label>
            {kind === "replace_missing" ? (
              <label>
                {words(locale, "Replacement value", "القيمة البديلة")}
                <input
                  value={replacement}
                  onChange={(event) => {
                    setReplacement(event.target.value);
                    setPreview(null);
                  }}
                />
              </label>
            ) : null}
            <button
              className="button button--primary"
              onClick={review}
              disabled={!column || busy}
            >
              {words(locale, "Preview changes", "عاين التغييرات")}
            </button>
          </section>
        </>
      ) : null}
      {preview ? (
        <section className="records-panel live-review">
          <h2>
            {words(locale, "Review the exact impact", "راجع الأثر الفعلي")}
          </h2>
          <RecordsTable
            locale={locale}
            title={words(locale, "Reconciliation", "المطابقة")}
            rows={[
              {
                rows_before: preview.before?.row_count,
                rows_after: preview.after?.row_count,
                changed_cells: preview.changed_cells,
                dropped_rows: preview.dropped_rows,
                ...preview.reconciliation,
              },
            ]}
          />
          <label className="checkbox-row">
            <input
              type="checkbox"
              checked={approved}
              onChange={(event) => setApproved(event.target.checked)}
            />
            {words(
              locale,
              "I reviewed the changes and approve creating an immutable new version.",
              "راجعت التغييرات وأوافق على إنشاء إصدار جديد غير قابل للتعديل.",
            )}
          </label>
          <button
            className="button button--primary"
            onClick={apply}
            disabled={!approved || busy}
          >
            <ShieldCheck size={16} />
            {words(locale, "Apply reviewed recipe", "طبّق الخطوات المراجعة")}
          </button>
        </section>
      ) : null}
    </div>
  );
}

export function LiveAnalysis({ locale }: Props) {
  const dashboards = useResource<{ items: Row[] }>("/api/v1/dashboards");
  const [dashboard, setDashboard] = useState<Row | null>(null);
  const [version, setVersion] = useState("");
  const [metric, setMetric] = useState("net_revenue");
  const [result, setResult] = useState<Row | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  useEffect(() => {
    try {
      setVersion(
        JSON.parse(sessionStorage.getItem("baseera-last-upload") ?? "null")
          ?.version_id ?? "",
      );
    } catch {}
  }, []);
  async function run() {
    setError(null);
    setResult(null);
    setBusy(true);
    try {
      if (!version.trim()) {
        const response = await postJson<{ results: Row[] }>(
          "/api/v1/assistant/query",
          { question: metric, metric_id: metric, locale },
        );
        setResult(response.results[0]);
      } else
        setResult(
          await postJson("/api/v1/metrics/query", {
            metric_id: metric,
            dataset_version_id: version,
            filters: {},
          }),
        );
    } catch (cause) {
      setError(cause);
    } finally {
      setBusy(false);
    }
  }
  async function pin() {
    if (!result) return;
    setError(null);
    try {
      const saved = await postJson<Row>("/api/v1/dashboards", {
        title: `${result.metric_id} · ${new Date().toISOString().slice(0, 10)}`,
        widgets: [{ type: "metric", result_id: result.id ?? result.result_id }],
        filters: {},
      });
      setNotice(
        words(
          locale,
          `Dashboard saved · ${saved.id}`,
          `حُفظت اللوحة · ${saved.id}`,
        ),
      );
      setDashboard(saved);
      dashboards.reload();
    } catch (cause) {
      setError(cause);
    }
  }
  return (
    <div className="stack-page">
      <PageTitle
        locale={locale}
        title={words(locale, "Analysis workspace", "مساحة التحليل")}
        detail={words(
          locale,
          "Run an approved metric against an exact dataset version, then preserve its evidence.",
          "شغّل مؤشرًا معتمدًا على إصدار محدد ثم احفظ الدليل.",
        )}
      />
      <section className="live-form panel">
        <label>
          {words(locale, "Metric", "المؤشر")}
          <select
            value={metric}
            onChange={(event) => setMetric(event.target.value)}
          >
            <option value="net_revenue">
              {words(locale, "Net revenue", "صافي الإيرادات")}
            </option>
            <option value="gross_margin">
              {words(locale, "Gross profit", "الربح الإجمالي")}
            </option>
            <option value="gross_margin_rate">
              {words(locale, "Gross margin rate", "نسبة هامش الربح")}
            </option>
          </select>
        </label>
        <label>
          {words(
            locale,
            "Dataset version ID (leave empty for company data)",
            "معرّف الإصدار (اتركه فارغًا لبيانات الشركة)",
          )}
          <input
            value={version}
            onChange={(event) => setVersion(event.target.value)}
            dir="ltr"
          />
        </label>
        <button
          className="button button--primary"
          disabled={busy}
          onClick={run}
        >
          <Play size={16} />
          {words(locale, "Run analysis", "شغّل التحليل")}
        </button>
      </section>
      <Problem locale={locale} error={error} />
      {notice ? (
        <p role="status" className="success-message">
          {notice}
        </p>
      ) : null}
      {result ? (
        <section className="records-panel live-result">
          <span className="badge badge--ready">
            {result.status ??
              result.classification ??
              words(locale, "Calculated result", "نتيجة محسوبة")}
          </span>
          <h2>{result.metric_id}</h2>
          <p className="live-result-value">
            {cell(result.value ?? result.result?.value, locale)}{" "}
            <small>{result.unit ?? result.result?.unit}</small>
          </p>
          <dl>
            {Object.entries(result)
              .filter(([key]) => !["value", "unit"].includes(key))
              .map(([key, value]) => (
                <div key={key}>
                  <dt>{key.replaceAll("_", " ")}</dt>
                  <dd>
                    <bdi>{cell(value, locale)}</bdi>
                  </dd>
                </div>
              ))}
          </dl>
          <button className="button button--primary" onClick={pin}>
            <Save size={16} />
            {words(locale, "Save to dashboard", "احفظ في لوحة")}
          </button>
        </section>
      ) : null}
      <section className="records-panel">
        <header className="panel-heading">
          <h2>{words(locale, "Saved dashboards", "اللوحات المحفوظة")}</h2>
          <button
            className="button button--secondary"
            onClick={dashboards.reload}
          >
            <RefreshCw size={15} />
            {words(locale, "Refresh", "تحديث")}
          </button>
        </header>
        <Problem locale={locale} error={dashboards.error} />
        <div className="action-row">
          {dashboards.data?.items.map((item) => (
            <button
              key={item.id}
              className="button button--secondary"
              onClick={async () => {
                setDashboard(null);
                setError(null);
                try {
                  setDashboard(
                    await apiRequest(
                      `/api/v1/dashboards/${encodeURIComponent(item.id)}`,
                    ),
                  );
                } catch (cause) {
                  setError(cause);
                }
              }}
            >
              {item.title} · v{item.version}
            </button>
          ))}
        </div>
        {dashboards.data?.items.length === 0 ? (
          <p>
            {words(
              locale,
              "Save a result to create your first dashboard.",
              "احفظ نتيجة لإنشاء لوحتك الأولى.",
            )}
          </p>
        ) : null}
        {dashboard ? (
          <div>
            <h3>
              {dashboard.title} · v{dashboard.version}
            </h3>
            <div className="live-summary">
              {dashboard.widgets.map((widget: Row, index: number) => (
                <article key={widget.result_id ?? index}>
                  <span>{widget.result?.metric_id ?? widget.type}</span>
                  <strong>
                    {cell(widget.result?.value, locale)}{" "}
                    <small>{widget.result?.unit}</small>
                  </strong>
                  <p>{widget.result?.status}</p>
                  <details>
                    <summary>{words(locale, "Evidence", "الدليل")}</summary>
                    <pre className="evidence-json" dir="ltr">
                      {JSON.stringify(
                        widget.result?.evidence ?? widget,
                        null,
                        2,
                      )}
                    </pre>
                  </details>
                </article>
              ))}
            </div>
          </div>
        ) : null}
      </section>
    </div>
  );
}

export function LiveReports({ locale }: Props) {
  const {
    data,
    reload,
    error: loadError,
  } = useResource<{ items: Row[] }>("/api/v1/reports");
  const [title, setTitle] = useState(
    words(locale, "Executive review", "مراجعة تنفيذية"),
  );
  const [text, setText] = useState("");
  const [resultId, setResultId] = useState("");
  const [report, setReport] = useState<Row | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  async function save() {
    setBusy(true);
    setError(null);
    const sections = [
      {
        type: "narrative",
        title: words(locale, "Management commentary", "تعليق الإدارة"),
        content: text,
      },
      ...(resultId ? [{ type: "metric", result_id: resultId }] : []),
    ];
    try {
      const saved = report
        ? await apiRequest<Row>(`/api/v1/reports/${report.id}`, {
            method: "PATCH",
            body: JSON.stringify({
              title,
              sections,
              expected_version: report.version,
            }),
          })
        : await postJson<Row>("/api/v1/reports", {
            title,
            language: locale,
            sections,
          });
      setReport(saved);
      reload();
    } catch (cause) {
      setError(cause);
    } finally {
      setBusy(false);
    }
  }
  async function open(id: string) {
    setError(null);
    try {
      const versions = await apiRequest<{ items: Row[] }>(
        `/api/v1/reports/${id}/versions`,
      );
      const latest = versions.items.at(-1);
      if (latest) {
        setReport(latest);
        setTitle(latest.title);
        setText(
          latest.sections?.find((section: Row) => section.type === "narrative")
            ?.content ?? "",
        );
        setResultId(
          latest.sections?.find((section: Row) => section.result_id)
            ?.result_id ?? "",
        );
      }
    } catch (cause) {
      setError(cause);
    }
  }
  return (
    <div className="stack-page">
      <PageTitle
        locale={locale}
        title={words(locale, "Report studio", "استوديو التقارير")}
        detail={words(
          locale,
          "Versioned narrative and immutable metric evidence, ready to export.",
          "سرد ذو إصدارات وأدلة مؤشرات ثابتة جاهزة للتصدير.",
        )}
      />
      <Problem locale={locale} error={error ?? loadError} />
      <div className="live-report-layout">
        <section className="panel live-editor">
          <label>
            {words(locale, "Report title", "عنوان التقرير")}
            <input
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              maxLength={240}
            />
          </label>
          <label>
            {words(locale, "Commentary", "التعليق")}
            <textarea
              rows={10}
              value={text}
              onChange={(event) => setText(event.target.value)}
              placeholder={words(
                locale,
                "Describe the decision, supporting observations, and unresolved questions…",
                "صف القرار والملاحظات الداعمة والأسئلة غير المحسومة…",
              )}
            />
          </label>
          <label>
            {words(locale, "Result ID (optional)", "معرّف نتيجة (اختياري)")}
            <input
              value={resultId}
              onChange={(event) => setResultId(event.target.value)}
              dir="ltr"
            />
          </label>
          <div className="action-row">
            <button
              className="button button--primary"
              disabled={!title.trim() || busy}
              onClick={save}
            >
              <Save size={16} />
              {words(locale, "Save version", "احفظ الإصدار")}
            </button>
            <button
              className="button button--secondary"
              onClick={() => {
                setReport(null);
                setTitle("");
                setText("");
                setResultId("");
              }}
            >
              {words(locale, "New report", "تقرير جديد")}
            </button>
          </div>
          {report ? (
            <div className="live-export">
              <p role="status">
                {words(
                  locale,
                  `Saved version ${report.version}`,
                  `الإصدار المحفوظ ${report.version}`,
                )}
              </p>
              <div className="action-row">
                {["html", "pdf", "docx", "xlsx", "csv", "json"].map(
                  (format) => (
                    <a
                      className="button button--secondary"
                      key={format}
                      href={`/api/v1/reports/${report.id}/export?format=${format}&version=${report.version}`}
                    >
                      <Download size={14} />
                      {format.toUpperCase()}
                    </a>
                  ),
                )}
              </div>
            </div>
          ) : null}
        </section>
        <aside className="records-panel live-report-list">
          <h2>{words(locale, "Saved reports", "التقارير المحفوظة")}</h2>
          {data?.items.length ? (
            data.items.map((item) => (
              <button
                key={item.id}
                className="live-list-button"
                onClick={() => open(item.id)}
              >
                <strong>{item.title}</strong>
                <span>
                  {words(locale, "Version", "الإصدار")}{" "}
                  {item.version ?? item.current_version}
                </span>
              </button>
            ))
          ) : (
            <p>
              {words(
                locale,
                "Your first saved report will appear here.",
                "سيظهر أول تقرير تحفظه هنا.",
              )}
            </p>
          )}
        </aside>
      </div>
    </div>
  );
}

export function LiveForecast({ locale }: Props) {
  const [horizon, setHorizon] = useState(6);
  const [result, setResult] = useState<Row | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  async function run() {
    setBusy(true);
    setError(null);
    try {
      setResult(
        await postJson("/api/v1/forecasts", {
          metric_id: "support_case_count",
          horizon,
        }),
      );
    } catch (cause) {
      setError(cause);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="stack-page">
      <PageTitle
        locale={locale}
        title={words(locale, "Forecast demand", "تنبأ بالطلب")}
        detail={words(
          locale,
          "A support case forecast with the model’s measured evaluation and stated limits.",
          "توقع لحالات الدعم مع تقييم النموذج المقاس وحدوده المعلنة.",
        )}
      />
      <section className="live-form panel">
        <label>
          {words(locale, "Horizon in months", "الأفق بالأشهر")}
          <input
            type="number"
            min={1}
            max={24}
            value={horizon}
            onChange={(event) => setHorizon(Number(event.target.value))}
          />
        </label>
        <button
          className="button button--primary"
          onClick={run}
          disabled={busy || horizon < 1 || horizon > 24}
        >
          <Play size={16} />
          {words(locale, "Run forecast", "شغّل التنبؤ")}
        </button>
      </section>
      <Problem locale={locale} error={error} />
      {result ? (
        <>
          <div className="truth-banner">
            {result.reason ?? result.model?.name ?? result.status}
          </div>
          {result.forecast?.length ? (
            <ChartPanel
              locale={locale}
              title={words(locale, "Support case forecast", "توقع حالات الدعم")}
              description={words(
                locale,
                "Forecast values are model estimates, not observed outcomes.",
                "القيم تقديرات للنموذج وليست نتائج مرصودة.",
              )}
              unit="cases"
              source={result.model?.name ?? "Forecast model"}
              data={result.forecast.map((row: Row) => ({
                label: String(row.period ?? row.horizon),
                value: row.value,
              }))}
            />
          ) : null}
          <RecordsTable
            locale={locale}
            title={words(
              locale,
              "Forecast values and intervals",
              "قيم التنبؤ والفواصل",
            )}
            rows={result.forecast ?? []}
          />
          <RecordsTable
            locale={locale}
            title={words(locale, "Measured backtest", "الاختبار المقاس")}
            rows={
              Array.isArray(result.backtest)
                ? result.backtest
                : [result.backtest ?? {}]
            }
          />
          {result.limitations ? (
            <ul className="live-limitations">
              {result.limitations.map((item: string) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          ) : null}
        </>
      ) : null}
    </div>
  );
}

export function LiveScenario({ locale }: Props) {
  const [inputs, setInputs] = useState({
    arrival_rate_per_hour: 12,
    service_rate_per_hour: 4,
    baseline_agents: 3,
    proposed_agents: 4,
    hours: 40,
    replications: 30,
    seed: 42,
  });
  const [result, setResult] = useState<Row | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const labels: Record<string, [string, string]> = {
    arrival_rate_per_hour: ["Arrivals per hour", "الوصول في الساعة"],
    service_rate_per_hour: [
      "Service per agent per hour",
      "الخدمة لكل موظف في الساعة",
    ],
    baseline_agents: ["Current agents", "عدد الموظفين الحالي"],
    proposed_agents: ["Proposed agents", "عدد الموظفين المقترح"],
    hours: ["Simulation hours", "ساعات المحاكاة"],
    replications: ["Replications", "التكرارات"],
    seed: ["Random seed", "بذرة العشوائية"],
  };
  async function run() {
    setBusy(true);
    setError(null);
    try {
      setResult(await postJson("/api/v1/simulations", inputs));
    } catch (cause) {
      setError(cause);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="stack-page">
      <PageTitle
        locale={locale}
        title={words(locale, "Capacity scenario lab", "مختبر سيناريو الطاقة")}
        detail={words(
          locale,
          "Compare staffing assumptions in a reproducible queue simulation.",
          "قارن افتراضات التوظيف بمحاكاة طوابير قابلة للتكرار.",
        )}
      />
      <section className="panel live-form live-form--grid">
        {Object.entries(inputs).map(([key, value]) => (
          <label key={key}>
            {labels[key][locale === "ar" ? 1 : 0]}
            <input
              type="number"
              min={key === "seed" ? 0 : 0.1}
              step={key.includes("rate") ? 0.1 : 1}
              value={value}
              onChange={(event) =>
                setInputs({ ...inputs, [key]: Number(event.target.value) })
              }
            />
          </label>
        ))}
        <button
          className="button button--primary"
          onClick={run}
          disabled={busy}
        >
          <Play size={16} />
          {words(locale, "Run and save scenario", "شغّل واحفظ السيناريو")}
        </button>
      </section>
      <Problem locale={locale} error={error} />
      {result ? (
        <>
          <div className="truth-banner">
            <CheckCircle2 size={16} />
            {words(
              locale,
              "Scenario saved. These are calculated outcomes under the assumptions below.",
              "حُفظ السيناريو. هذه نتائج محسوبة وفق الافتراضات أدناه.",
            )}
          </div>
          <RecordsTable
            locale={locale}
            title={words(locale, "Scenario comparison", "مقارنة السيناريو")}
            rows={[
              {
                scenario: words(locale, "Baseline", "الأساس"),
                ...result.baseline,
              },
              {
                scenario: words(locale, "Proposed", "المقترح"),
                ...result.proposed,
              },
            ]}
          />
          <p className="panel-note">{result.model_boundary}</p>
          <RecordsTable
            locale={locale}
            title={words(locale, "Assumptions", "الافتراضات")}
            rows={[result.assumptions]}
          />
        </>
      ) : null}
    </div>
  );
}

export function LiveDecisions({
  locale,
  approvals = false,
}: Props & { approvals?: boolean }) {
  const { data, error, reload, loading } = useResource<{ items: Row[] }>(
    "/api/v1/decisions",
  );
  const [title, setTitle] = useState("");
  const [owner, setOwner] = useState("");
  const [problem, setProblem] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  async function create() {
    setBusy(true);
    setProblem(null);
    try {
      await postJson("/api/v1/decisions", {
        title,
        owner: owner || null,
        status: "draft",
        evidence_ids: [],
      });
      setTitle("");
      reload();
    } catch (cause) {
      setProblem(cause);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="stack-page">
      <PageTitle
        locale={locale}
        title={words(
          locale,
          approvals ? "Approval review" : "Decision register",
          approvals ? "مراجعة الموافقات" : "سجل القرارات",
        )}
        detail={words(
          locale,
          "Trace decisions to their owners and review dates.",
          "تتبّع القرارات وأصحابها ومواعيد مراجعتها.",
        )}
      />
      {!approvals ? (
        <section className="panel live-form">
          <label>
            {words(locale, "Decision title", "عنوان القرار")}
            <input
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              maxLength={240}
            />
          </label>
          <label>
            {words(locale, "Owner", "صاحب القرار")}
            <input
              value={owner}
              onChange={(event) => setOwner(event.target.value)}
            />
          </label>
          <button
            className="button button--primary"
            disabled={!title.trim() || busy}
            onClick={create}
          >
            {words(locale, "Save draft", "احفظ المسودة")}
          </button>
        </section>
      ) : null}
      <Problem locale={locale} error={problem ?? error} />
      {loading && !data ? (
        <ResourceState locale={locale} status="loading" />
      ) : data ? (
        <RecordsTable
          locale={locale}
          title={words(locale, "Recorded decisions", "القرارات المسجلة")}
          rows={
            approvals
              ? data.items.filter(
                  (row) => row.status === "open" || row.status === "approved",
                )
              : data.items
          }
        />
      ) : null}
    </div>
  );
}

export function LiveAdmin({ locale }: Props) {
  const { data, error, loading } = useResource<Row>("/api/v1/capabilities");
  return (
    <div className="stack-page">
      <PageTitle
        locale={locale}
        title={words(locale, "Workspace capabilities", "قدرات مساحة العمل")}
        detail={words(
          locale,
          "Availability is read from the running service. Local AI executes through the configured Ollama model.",
          "تُقرأ الإتاحة من الخدمة الحالية. يعمل الذكاء المحلي عبر نموذج أولاما المضبوط.",
        )}
      />
      <Problem locale={locale} error={error} />
      {loading ? (
        <ResourceState locale={locale} status="loading" />
      ) : data ? (
        <RecordsTable
          locale={locale}
          title={words(locale, "Available capabilities", "القدرات المتاحة")}
          rows={
            Array.isArray(data.items)
              ? data.items
              : Object.entries(data).map(([name, value]) => ({
                  name,
                  details: value,
                }))
          }
        />
      ) : null}
    </div>
  );
}
