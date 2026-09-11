"use client";

import { useMemo, useState } from "react";
import {
  ArrowRight,
  Check,
  ChevronRight,
  CircleAlert,
  Clock3,
  Database,
  FileJson2,
  FileSpreadsheet,
  Filter,
  History,
  Link2,
  LockKeyhole,
  Play,
  RotateCcw,
  Search,
  Server,
  ShieldCheck,
  TableProperties,
  Upload,
  WandSparkles,
  X,
} from "lucide-react";
import type { Locale, QualityIssue } from "@/lib/contracts";
import { apiRequest, postJson, uploadDataset } from "@/lib/api";
import { demoQualityIssues } from "@/lib/demo-data";
import { formatNumber } from "@/lib/i18n";
import { ResourceState } from "./resource-state";
import { UploadStudio } from "./upload-studio";

const catalogRows = [
  {
    name: "sales_orders",
    description: "Approved sales orders and return adjustments",
    owner: "Finance data",
    rows: 18426,
    columns: 18,
    coverage: "Jul 2024–Jun 2026",
    status: "Published",
    version: "v17",
  },
  {
    name: "support_cases",
    description: "Case lifecycle timestamps, queue, and SLA policy",
    owner: "Customer operations",
    rows: 9428,
    columns: 24,
    coverage: "Jul 2024–Jun 2026",
    status: "Published",
    version: "v9",
  },
  {
    name: "project_tasks",
    description: "Planned and actual effort with dependencies",
    owner: "Delivery PMO",
    rows: 3241,
    columns: 21,
    coverage: "Jan 2025–Jun 2026",
    status: "Published",
    version: "v12",
  },
  {
    name: "employee_assignments",
    description: "Effective-dated role and project allocations",
    owner: "People operations",
    rows: 386,
    columns: 12,
    coverage: "Jul 2024–Jun 2026",
    status: "Restricted",
    version: "v8",
  },
  {
    name: "supplier_deliveries",
    description: "Purchase order promises and receipt events",
    owner: "Procurement",
    rows: 1687,
    columns: 16,
    coverage: "Sep 2024–Jun 2026",
    status: "Stale",
    version: "v6",
  },
];

export function SourcesScreen({
  locale,
  workspace,
}: {
  locale: Locale;
  workspace?: string;
}) {
  const ar = locale === "ar";
  const [tab, setTab] = useState<"files" | "database" | "application">("files");
  return (
    <div className="stack-page">
      <header className="page-header">
        <div>
          <p className="eyebrow">
            {ar ? "الإدخال والمزامنة" : "Ingestion & synchronization"}
          </p>
          <h1>{ar ? "مصادر البيانات" : "Data sources"}</h1>
          <p>
            {ar
              ? "اربط البيانات بصلاحية قراءة واضحة، ثم راجع المخطط والتغطية قبل النشر."
              : "Connect with explicit read scope, then review schema and coverage before publishing."}
          </p>
        </div>
        <span className="badge badge--demo">
          {workspace === "demo"
            ? ar
              ? "مصادر تجريبية خيالية"
              : "Fictional demo sources"
            : ar
              ? "مساحة الشركة"
              : "Company workspace"}
        </span>
      </header>
      <div
        className="segmented"
        role="tablist"
        aria-label={ar ? "أنواع المصادر" : "Source types"}
      >
        {(["files", "database", "application"] as const).map((id) => (
          <button
            role="tab"
            aria-selected={tab === id}
            key={id}
            onClick={() => setTab(id)}
          >
            {id === "files"
              ? ar
                ? "رفع ملفات"
                : "Upload files"
              : id === "database"
                ? ar
                  ? "قواعد البيانات"
                  : "Connect database"
                : ar
                  ? "تطبيقات الشركة"
                  : "Connect application"}
          </button>
        ))}
      </div>
      {tab === "files" ? (
        <UploadStudio locale={locale} upload={uploadDataset} />
      ) : tab === "database" ? (
        <ConnectorGrid locale={locale} type="database" />
      ) : (
        <ConnectorGrid locale={locale} type="application" />
      )}
      <section className="source-health">
        <header className="panel-heading">
          <div>
            <p className="eyebrow">{ar ? "حالة فعلية" : "Observed state"}</p>
            <h2>{ar ? "آخر نشاط للمصادر" : "Recent source activity"}</h2>
          </div>
        </header>
        <div className="timeline">
          <TimelineItem
            status="success"
            title={
              ar ? "اكتملت مزامنة فواتير ERP" : "ERP invoice sync completed"
            }
            detail={
              ar
                ? "١٨٬٤٢٦ صفًا مقبولًا · ٣٧ معزولًا · نقطة التحقق محفوظة"
                : "18,426 accepted · 37 quarantined · checkpoint saved"
            }
            time={ar ? "منذ ١٨ دقيقة" : "18 minutes ago"}
          />
          <TimelineItem
            status="warning"
            title={ar ? "تغير مخطط الموردين" : "Supplier schema drift detected"}
            detail={
              ar
                ? "الحقل promised_date تغيّر نوعه؛ بقي الإصدار ٦ منشورًا."
                : "promised_date changed type; published v6 remains active."
            }
            time={ar ? "منذ ساعتين" : "2 hours ago"}
          />
          <TimelineItem
            status="neutral"
            title={
              ar ? "تمت مقاطعة مزامنة المشاريع" : "Project sync interrupted"
            }
            detail={
              ar
                ? "يمكن الاستئناف من الصفحة ٤٢ دون إعادة السجلات."
                : "Resumable from page 42 without duplicating records."
            }
            time={ar ? "أمس" : "Yesterday"}
          />
        </div>
      </section>
    </div>
  );
}

function ConnectorGrid({
  locale,
  type,
}: {
  locale: Locale;
  type: "database" | "application";
}) {
  const ar = locale === "ar";
  const entries =
    type === "database"
      ? [
          {
            name: "PostgreSQL",
            state: "ready",
            text: ar
              ? "اكتشاف ومراجعة وقراءة كاملة/تزايدية."
              : "Discovery, preview, full and incremental read.",
          },
          {
            name: "MySQL",
            state: "config",
            text: ar
              ? "المحوّل متاح؛ يحتاج بيانات اعتماد واختبار اتصال."
              : "Adapter available; credentials and connection test required.",
          },
          {
            name: "SQL Server",
            state: "config",
            text: ar
              ? "المحوّل متاح؛ لم يُختبر في هذه المساحة."
              : "Adapter available; not verified in this workspace.",
          },
        ]
      : [
          {
            name: "Bounded REST",
            state: "ready",
            text: ar
              ? "نقاط نهاية معتمدة، ترقيم صفحات وحدود طلبات."
              : "Allow-listed endpoints, pagination, and rate limits.",
          },
          {
            name: "Odoo",
            state: "config",
            text: ar
              ? "يحتاج عنوان خادم وبيانات اعتماد للقراءة فقط."
              : "Requires server URL and read-only credentials.",
          },
          {
            name: "Google Sheets",
            state: "unsupported",
            text: ar
              ? "غير مدعوم في هذا الإصدار. صدّر CSV أو XLSX."
              : "Unsupported in this release. Export CSV or XLSX.",
          },
        ];
  return (
    <div className="connector-grid">
      {entries.map((item) => (
        <article className="connector-card" key={item.name}>
          <span className="connector-icon">
            {type === "database" ? <Server /> : <Link2 />}
          </span>
          <div>
            <h2>{item.name}</h2>
            <p>{item.text}</p>
            <span
              className={`badge badge--${item.state === "ready" ? "ready" : item.state === "config" ? "warning" : "neutral"}`}
            >
              {item.state === "ready"
                ? ar
                  ? "جاهز للتهيئة"
                  : "Ready to configure"
                : item.state === "config"
                  ? ar
                    ? "يحتاج إعدادًا"
                    : "Needs configuration"
                  : ar
                    ? "غير مدعوم"
                    : "Unsupported"}
            </span>
          </div>
          {item.state !== "unsupported" ? (
            <button
              type="button"
              className="button button--secondary"
              onClick={() =>
                alert(
                  ar
                    ? "افتح نموذج الاتصال الآمن بعد توفير بيانات الاعتماد."
                    : "Secure connection form requires workspace credentials.",
                )
              }
            >
              {ar ? "تهيئة" : "Configure"}
            </button>
          ) : null}
        </article>
      ))}
    </div>
  );
}

function TimelineItem({
  status,
  title,
  detail,
  time,
}: {
  status: string;
  title: string;
  detail: string;
  time: string;
}) {
  return (
    <article className="timeline-item">
      <span className={`timeline-marker timeline-marker--${status}`} />
      <div>
        <h3>{title}</h3>
        <p>{detail}</p>
      </div>
      <time>{time}</time>
    </article>
  );
}

export function CatalogScreen({ locale }: { locale: Locale }) {
  const ar = locale === "ar";
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState(catalogRows[0]);
  const rows = useMemo(
    () =>
      catalogRows.filter((row) =>
        `${row.name} ${row.description} ${row.owner}`
          .toLowerCase()
          .includes(query.toLowerCase()),
      ),
    [query],
  );
  return (
    <div className="stack-page">
      <header className="page-header">
        <div>
          <p className="eyebrow">
            {ar ? "المعنى والنسب" : "Meaning & lineage"}
          </p>
          <h1>{ar ? "دليل البيانات" : "Data catalog"}</h1>
          <p>
            {ar
              ? "ابحث في مجموعات البيانات والأعمدة والتعريفات والمالكين."
              : "Search datasets, columns, definitions, and owners."}
          </p>
        </div>
        <button className="button button--secondary">
          <History size={16} />
          {ar ? "سجل الإصدارات" : "Version history"}
        </button>
      </header>
      <div className="catalog-layout">
        <section className="catalog-main">
          <label className="search-field" htmlFor="catalog-search">
            <Search size={17} aria-hidden="true" />
            <span className="sr-only">
              {ar ? "ابحث في الدليل" : "Search catalog"}
            </span>
            <input
              id="catalog-search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder={
                ar
                  ? "ابحث باسم الجدول أو المالك أو المصطلح…"
                  : "Search table, owner, or business term…"
              }
            />
          </label>
          <div className="table-scroll" tabIndex={0}>
            <table>
              <thead>
                <tr>
                  <th>{ar ? "مجموعة البيانات" : "Dataset"}</th>
                  <th>{ar ? "المالك" : "Owner"}</th>
                  <th>{ar ? "الصفوف" : "Rows"}</th>
                  <th>{ar ? "التغطية" : "Coverage"}</th>
                  <th>{ar ? "الحالة" : "Status"}</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr
                    key={row.name}
                    className={selected.name === row.name ? "selected" : ""}
                  >
                    <th scope="row">
                      <button
                        className="table-link"
                        onClick={() => setSelected(row)}
                      >
                        <bdi>{row.name}</bdi>
                        <span>{row.description}</span>
                      </button>
                    </th>
                    <td>{row.owner}</td>
                    <td>{formatNumber(row.rows, locale, 0)}</td>
                    <td>{row.coverage}</td>
                    <td>
                      <span
                        className={`badge badge--${row.status === "Published" ? "ready" : row.status === "Stale" ? "warning" : "neutral"}`}
                      >
                        {row.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
        <aside
          className="catalog-detail"
          aria-label={ar ? "تفاصيل مجموعة البيانات" : "Dataset details"}
        >
          <p className="eyebrow">{ar ? "النطاق المحدد" : "Selected scope"}</p>
          <h2>
            <bdi>{selected.name}</bdi>
          </h2>
          <p>{selected.description}</p>
          <dl className="compact-dl">
            <div>
              <dt>{ar ? "الإصدار المنشور" : "Published version"}</dt>
              <dd>{selected.version}</dd>
            </div>
            <div>
              <dt>{ar ? "الأعمدة" : "Columns"}</dt>
              <dd>{selected.columns}</dd>
            </div>
            <div>
              <dt>{ar ? "السجلات المرفوضة" : "Rejected records"}</dt>
              <dd>37</dd>
            </div>
            <div>
              <dt>{ar ? "آخر تحديث ناجح" : "Last successful refresh"}</dt>
              <dd>{ar ? "٣٠ يونيو ٢٠٢٦، ١٠:٤٢" : "30 Jun 2026, 10:42"}</dd>
            </div>
          </dl>
          <button className="button button--primary button--wide">
            {ar ? "افتح مستكشف الصفوف" : "Open row explorer"}
            <ArrowRight size={16} />
          </button>
        </aside>
      </div>
    </div>
  );
}

type CleaningStage = "issues" | "preview" | "applying" | "published";

export function QualityScreen({
  locale,
  workspace,
}: {
  locale: Locale;
  workspace?: string;
}) {
  const ar = locale === "ar";
  const [issues, setIssues] = useState<QualityIssue[]>(() =>
    demoQualityIssues(locale),
  );
  const [selectedId, setSelectedId] = useState(issues[0].id);
  const [stage, setStage] = useState<CleaningStage>("issues");
  const [problem, setProblem] = useState("");
  const [confirmVersion, setConfirmVersion] = useState("");
  const selected = issues.find((item) => item.id === selectedId) ?? issues[0];
  const versionId = workspace === "demo" ? "dv_demo_raw_01" : "dv_current";
  async function preview() {
    setProblem("");
    try {
      await postJson(`/api/v1/dataset-versions/${versionId}/cleaning/preview`, {
        issue_ids: issues.filter((i) => i.accepted).map((i) => i.id),
        recipe_name: "reviewed-import-cleanup",
      });
      setStage("preview");
    } catch (error) {
      if (workspace === "demo") setStage("preview");
      else
        setProblem(error instanceof Error ? error.message : "Preview failed");
    }
  }
  async function apply() {
    if (confirmVersion !== "raw-v1") return;
    setStage("applying");
    setProblem("");
    try {
      await postJson(
        `/api/v1/dataset-versions/${versionId}/cleaning/apply`,
        {
          expected_version: "raw-v1",
          issue_ids: issues.filter((i) => i.accepted).map((i) => i.id),
        },
        "raw-v1",
      );
      setStage("published");
    } catch (error) {
      setStage("preview");
      setProblem(error instanceof Error ? error.message : "Apply failed");
    }
  }
  if (stage === "published")
    return (
      <div className="stack-page">
        <header className="page-header">
          <div>
            <p className="eyebrow">
              {ar ? "إصدار منشور" : "Published version"}
            </p>
            <h1>
              {ar
                ? "اكتمل التنظيف والتحقق"
                : "Cleaning and validation complete"}
            </h1>
            <p>
              {ar
                ? "تم إنشاء cleaned-v2؛ بقي raw-v1 دون تعديل ويمكن إرجاع مؤشر النشر إليه."
                : "cleaned-v2 was created; raw-v1 remains immutable and can be republished."}
            </p>
          </div>
          <span className="badge badge--ready">
            <Check />
            {ar ? "متصالح" : "Reconciled"}
          </span>
        </header>
        <Reconciliation locale={locale} />
        <div className="action-row">
          <button
            className="button button--secondary"
            onClick={() => setStage("preview")}
          >
            <RotateCcw size={16} />
            {ar ? "راجع الوصفة" : "Review recipe"}
          </button>
          <button className="button button--primary">
            {ar ? "افتح التحليل بالإصدار الجديد" : "Analyze cleaned version"}
            <ArrowRight size={16} />
          </button>
        </div>
      </div>
    );
  return (
    <div className="stack-page">
      <header className="page-header">
        <div>
          <p className="eyebrow">
            {ar ? "orders_dirty.xlsx · raw-v1" : "orders_dirty.xlsx · raw-v1"}
          </p>
          <h1>{ar ? "استوديو جودة البيانات" : "Data quality studio"}</h1>
          <p>
            {ar
              ? "راجع المشكلات والتغييرات والأثر على الإجماليات قبل إنشاء إصدار جديد."
              : "Review issues, transformations, and control totals before creating a new version."}
          </p>
        </div>
        <span className="badge badge--warning">
          {ar ? "٤ مشكلات · ٦٤٦ صفًا متأثرًا" : "4 issues · 646 affected rows"}
        </span>
      </header>
      {workspace === "demo" ? (
        <div className="truth-banner">
          <CircleAlert size={17} />
          {ar
            ? "مراجعة بيانات خيالية بتاريخ ٣٠ يونيو ٢٠٢٦. التطبيق الفعلي يتطلب API متاحًا."
            : "Fictional review dated 30 Jun 2026. Applying requires the API to be available."}
        </div>
      ) : null}
      <ol
        className="stepper"
        aria-label={ar ? "مراحل التنظيف" : "Cleaning stages"}
      >
        <li className="done">
          <Check />
          {ar ? "ملف أصلي" : "Original profile"}
        </li>
        <li className={stage === "issues" ? "current" : "done"}>
          {stage !== "issues" ? <Check /> : <span>2</span>}
          {ar ? "مراجعة القواعد" : "Review rules"}
        </li>
        <li
          className={
            stage === "preview" || stage === "applying" ? "current" : ""
          }
        >
          <span>3</span>
          {ar ? "معاينة وتطبيق" : "Preview & apply"}
        </li>
        <li>
          <span>4</span>
          {ar ? "تحقق ونشر" : "Validate & publish"}
        </li>
      </ol>
      {problem ? (
        <ResourceState
          locale={locale}
          status="error"
          compact
          reason={problem}
          onRetry={stage === "issues" ? preview : apply}
        />
      ) : null}
      {stage === "issues" ? (
        <div className="quality-layout">
          <section className="issue-list" aria-labelledby="issues-heading">
            <header>
              <h2 id="issues-heading">
                {ar ? "المشكلات المكتشفة" : "Detected issues"}
              </h2>
              <span>
                {issues.filter((i) => i.accepted).length}/{issues.length}{" "}
                {ar ? "مقبولة" : "accepted"}
              </span>
            </header>
            {issues.map((issue) => (
              <button
                key={issue.id}
                className={selectedId === issue.id ? "selected" : ""}
                onClick={() => setSelectedId(issue.id)}
              >
                <input
                  type="checkbox"
                  checked={issue.accepted}
                  onChange={(event) => {
                    event.stopPropagation();
                    setIssues((all) =>
                      all.map((i) =>
                        i.id === issue.id
                          ? { ...i, accepted: event.target.checked }
                          : i,
                      ),
                    );
                  }}
                  aria-label={`${issue.accepted ? (ar ? "رفض" : "Reject") : ar ? "قبول" : "Accept"} ${issue.title}`}
                />
                <div>
                  <span
                    className={`badge badge--${issue.severity === "high" ? "danger" : issue.severity === "medium" ? "warning" : "neutral"}`}
                  >
                    {issue.severity}
                  </span>
                  <h3>{issue.title}</h3>
                  <p>
                    <bdi>{issue.field}</bdi> ·{" "}
                    {formatNumber(issue.count, locale, 0)}{" "}
                    {ar ? "صفًا" : "rows"}
                  </p>
                </div>
                <ChevronRight aria-hidden="true" />
              </button>
            ))}
          </section>
          <section className="issue-detail">
            <div className="issue-detail__head">
              <span className="issue-icon">
                <WandSparkles />
              </span>
              <div>
                <p className="eyebrow">
                  {ar ? "قاعدة مقترحة" : "Proposed rule"}
                </p>
                <h2>{selected.title}</h2>
              </div>
            </div>
            <dl className="detail-dl">
              <div>
                <dt>{ar ? "الحقل" : "Field"}</dt>
                <dd>
                  <code>{selected.field}</code>
                </dd>
              </div>
              <div>
                <dt>{ar ? "مثال" : "Example"}</dt>
                <dd>
                  <bdi>{selected.example}</bdi>
                </dd>
              </div>
              <div>
                <dt>{ar ? "المعالجة" : "Treatment"}</dt>
                <dd>{selected.treatment}</dd>
              </div>
              <div>
                <dt>{ar ? "لماذا" : "Rationale"}</dt>
                <dd>{selected.rationale}</dd>
              </div>
            </dl>
            <div className="protected-note">
              <LockKeyhole size={17} />
              <p>
                <b>{ar ? "ضمان المصالحة" : "Reconciliation guard"}</b>
                <br />
                {ar
                  ? "لن تتحول المعرّفات ذات الصفر البادئ إلى أرقام، ولن تُحذف المرتجعات السالبة المشروعة."
                  : "Leading-zero IDs stay text and legitimate negative returns are retained."}
              </p>
            </div>
          </section>
        </div>
      ) : (
        <CleaningPreview
          locale={locale}
          confirmVersion={confirmVersion}
          setConfirmVersion={setConfirmVersion}
          applying={stage === "applying"}
          onBack={() => setStage("issues")}
          onApply={apply}
        />
      )}
      {stage === "issues" ? (
        <div className="sticky-review-bar">
          <div>
            <strong>
              {ar
                ? "وصفة reviewed-import-cleanup"
                : "Recipe reviewed-import-cleanup"}
            </strong>
            <span>
              {ar
                ? `${issues.filter((i) => i.accepted).length} قواعد · لا تعديل للأصل raw-v1`
                : `${issues.filter((i) => i.accepted).length} rules · raw-v1 remains unchanged`}
            </span>
          </div>
          <button
            className="button button--primary"
            onClick={preview}
            disabled={!issues.some((i) => i.accepted)}
          >
            <Play size={16} />
            {ar ? "إنشاء معاينة" : "Generate preview"}
          </button>
        </div>
      ) : null}
    </div>
  );
}

function CleaningPreview({
  locale,
  confirmVersion,
  setConfirmVersion,
  applying,
  onBack,
  onApply,
}: {
  locale: Locale;
  confirmVersion: string;
  setConfirmVersion: (v: string) => void;
  applying: boolean;
  onBack: () => void;
  onApply: () => void;
}) {
  const ar = locale === "ar";
  return (
    <div className="preview-stack">
      <div className="comparison-grid">
        <ProfileCard
          locale={locale}
          title={ar ? "قبل · raw-v1" : "Before · raw-v1"}
          rows="18,891"
          accepted="18,428"
          quarantined="37"
          duplicate="428"
          quality="72 / 100"
        />
        <ProfileCard
          locale={locale}
          title={
            ar ? "بعد · cleaned-v2 (معاينة)" : "After · cleaned-v2 (preview)"
          }
          rows="18,463"
          accepted="18,426"
          quarantined="37"
          duplicate="0"
          quality="91 / 100"
          positive
        />
      </div>
      <Reconciliation locale={locale} />
      <section className="diff-panel">
        <header className="panel-heading">
          <div>
            <p className="eyebrow">{ar ? "عينة تغييرات" : "Change sample"}</p>
            <h2>{ar ? "الصفوف المتأثرة" : "Affected rows"}</h2>
          </div>
          <span className="badge">
            {ar ? "معاينة ٥٠ من ٦٤٦" : "50 of 646 previewed"}
          </span>
        </header>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>{ar ? "الموقع" : "Location"}</th>
                <th>{ar ? "الحقل" : "Field"}</th>
                <th>{ar ? "قبل" : "Before"}</th>
                <th>{ar ? "بعد" : "After"}</th>
                <th>{ar ? "القاعدة" : "Rule"}</th>
              </tr>
            </thead>
            <tbody>
              <tr>
                <td>
                  <bdi>Orders!42</bdi>
                </td>
                <td>
                  <bdi>customer_id</bdi>
                </td>
                <td>
                  <bdi>00127</bdi>
                </td>
                <td>
                  <bdi>00127</bdi>
                </td>
                <td>{ar ? "محفوظ كنص" : "Preserved as text"}</td>
              </tr>
              <tr>
                <td>
                  <bdi>Returns!18</bdi>
                </td>
                <td>
                  <bdi>net_amount</bdi>
                </td>
                <td>
                  <bdi>−184.50</bdi>
                </td>
                <td>
                  <bdi>−184.50</bdi>
                </td>
                <td>{ar ? "مرتجع مشروع" : "Legitimate return"}</td>
              </tr>
              <tr>
                <td>
                  <bdi>Orders!384</bdi>
                </td>
                <td>
                  <bdi>batch_id</bdi>
                </td>
                <td>
                  <bdi>batch_2026_05_14</bdi>
                </td>
                <td>{ar ? "معزول" : "Quarantined"}</td>
                <td>{ar ? "نسخة دفعة" : "Duplicate batch"}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </section>
      <section className="approval-box">
        <div>
          <p className="eyebrow">
            {ar ? "مراجعة ذات أثر" : "Material change review"}
          </p>
          <h2>{ar ? "أنشئ إصدارًا جديدًا" : "Create a new version"}</h2>
          <p>
            {ar
              ? "اكتب raw-v1 لتأكيد إصدار المصدر. سيتم حفظ الوصفة والسجل والمجاميع الرقابية."
              : "Type raw-v1 to confirm the source version. The recipe, ledger, and control totals will be stored."}
          </p>
        </div>
        <div className="field">
          <label htmlFor="confirm-version">
            {ar ? "إصدار المصدر المتوقع" : "Expected source version"}
          </label>
          <input
            id="confirm-version"
            value={confirmVersion}
            onChange={(e) => setConfirmVersion(e.target.value)}
            placeholder="raw-v1"
          />
        </div>
        <div className="action-row">
          <button className="button button--secondary" onClick={onBack}>
            {ar ? "عودة للقواعد" : "Back to rules"}
          </button>
          <button
            className="button button--primary"
            disabled={confirmVersion !== "raw-v1" || applying}
            onClick={onApply}
          >
            {applying
              ? ar
                ? "جارٍ التطبيق…"
                : "Applying…"
              : ar
                ? "تطبيق وإنشاء cleaned-v2"
                : "Apply and create cleaned-v2"}
          </button>
        </div>
      </section>
    </div>
  );
}

function ProfileCard({
  locale,
  title,
  rows,
  accepted,
  quarantined,
  duplicate,
  quality,
  positive,
}: {
  locale: Locale;
  title: string;
  rows: string;
  accepted: string;
  quarantined: string;
  duplicate: string;
  quality: string;
  positive?: boolean;
}) {
  const ar = locale === "ar";
  return (
    <article
      className={`profile-card${positive ? " profile-card--positive" : ""}`}
    >
      <header>
        <h2>{title}</h2>
        {positive ? (
          <span className="badge badge--ready">
            <Check />
            {ar ? "متحقق" : "Validated"}
          </span>
        ) : (
          <span className="badge badge--warning">
            {ar ? "أصلي" : "Original"}
          </span>
        )}
      </header>
      <dl>
        <div>
          <dt>{ar ? "الصفوف المكتشفة" : "Rows discovered"}</dt>
          <dd>{rows}</dd>
        </div>
        <div>
          <dt>{ar ? "المقبولة" : "Accepted"}</dt>
          <dd>{accepted}</dd>
        </div>
        <div>
          <dt>{ar ? "المعزولة" : "Quarantined"}</dt>
          <dd>{quarantined}</dd>
        </div>
        <div>
          <dt>{ar ? "المكررة" : "Duplicates"}</dt>
          <dd>{duplicate}</dd>
        </div>
        <div>
          <dt>{ar ? "نتيجة القواعد" : "Rule score"}</dt>
          <dd>{quality}</dd>
        </div>
      </dl>
    </article>
  );
}

function Reconciliation({ locale }: { locale: Locale }) {
  const ar = locale === "ar";
  return (
    <section className="reconciliation">
      <div>
        <ShieldCheck />
        <span>
          <b>{ar ? "مصالحة المجموع" : "Control-total reconciliation"}</b>
          <small>
            {ar
              ? "صافي الإيراد بعد حذف الدفعة المكررة"
              : "Net revenue after duplicate batch removal"}
          </small>
        </span>
      </div>
      <dl>
        <div>
          <dt>{ar ? "قبل" : "Before"}</dt>
          <dd>
            <bdi>JOD 1,889,124.50</bdi>
          </dd>
        </div>
        <div>
          <dt>{ar ? "دفعة مكررة" : "Duplicate batch"}</dt>
          <dd className="negative">
            <bdi>−JOD 46,624.50</bdi>
          </dd>
        </div>
        <div>
          <dt>{ar ? "بعد" : "After"}</dt>
          <dd>
            <bdi>JOD 1,842,500.00</bdi>
          </dd>
        </div>
        <div>
          <dt>{ar ? "فرق غير مفسر" : "Unexplained delta"}</dt>
          <dd className="positive">
            <bdi>JOD 0.00</bdi>
          </dd>
        </div>
      </dl>
    </section>
  );
}

export function OnboardingScreen({ locale }: { locale: Locale }) {
  const ar = locale === "ar";
  return (
    <div className="onboarding">
      <div className="onboarding__intro">
        <span className="brand-mark brand-mark--large">ب</span>
        <p className="eyebrow">{ar ? "مساحة نظيفة" : "Clean workspace"}</p>
        <h1>
          {ar ? "ابنِ أول نتيجة موثوقة" : "Build your first trusted result"}
        </h1>
        <p>
          {ar
            ? "ابدأ بسياق الشركة ثم مصدر بيانات وصياغة معنى المؤشرات. لن نضيف بيانات تجريبية هنا."
            : "Start with company context, a source, and metric meaning. No demo records will be added here."}
        </p>
      </div>
      <ol className="onboarding-steps">
        <li className="current">
          <span>1</span>
          <div>
            <b>{ar ? "سياق الشركة" : "Company context"}</b>
            <p>
              {ar
                ? "المنطقة الزمنية، العملة، وبداية الأسبوع"
                : "Timezone, currency, and week start"}
            </p>
          </div>
        </li>
        <li>
          <span>2</span>
          <div>
            <b>{ar ? "مصدر البيانات" : "Data source"}</b>
            <p>
              {ar ? "ملف أو اتصال قراءة فقط" : "File or read-only connection"}
            </p>
          </div>
        </li>
        <li>
          <span>3</span>
          <div>
            <b>{ar ? "المعنى والصلاحيات" : "Meaning & access"}</b>
            <p>
              {ar
                ? "المعرّفات والتعاريف والنطاق"
                : "Identifiers, definitions, and scope"}
            </p>
          </div>
        </li>
        <li>
          <span>4</span>
          <div>
            <b>{ar ? "أول لوحة" : "First dashboard"}</b>
            <p>
              {ar
                ? "نتائج متصالحة مرتبطة بالدليل"
                : "Reconciled, evidence-bound results"}
            </p>
          </div>
        </li>
      </ol>
      <form className="setup-form">
        <div className="field">
          <label htmlFor="company-name">
            {ar ? "اسم الشركة" : "Company name"}
          </label>
          <input
            id="company-name"
            placeholder={ar ? "مثال: شركة المدار" : "e.g. Al-Madar Company"}
          />
        </div>
        <div className="field-row">
          <div className="field">
            <label htmlFor="timezone">
              {ar ? "المنطقة الزمنية" : "Reporting timezone"}
            </label>
            <select id="timezone" defaultValue="Asia/Amman">
              <option>Asia/Amman</option>
              <option>Asia/Riyadh</option>
              <option>UTC</option>
            </select>
          </div>
          <div className="field">
            <label htmlFor="currency">{ar ? "العملة" : "Currency"}</label>
            <select id="currency" defaultValue="JOD">
              <option>JOD</option>
              <option>SAR</option>
              <option>USD</option>
            </select>
          </div>
        </div>
        <button className="button button--primary" type="button">
          {ar ? "حفظ ومتابعة" : "Save and continue"}
          <ArrowRight size={16} />
        </button>
      </form>
    </div>
  );
}
