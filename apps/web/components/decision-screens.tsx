"use client";

import { useMemo, useState } from "react";
import {
  AlertTriangle,
  ArrowRight,
  Bot,
  CalendarClock,
  Check,
  CheckCircle2,
  ChevronRight,
  CircleAlert,
  CircleDollarSign,
  Clock3,
  Copy,
  Download,
  FileCheck2,
  FileText,
  Gauge,
  GitCompareArrows,
  History,
  Info,
  LockKeyhole,
  MessageSquareText,
  Pause,
  Play,
  Plus,
  RotateCcw,
  Save,
  Settings2,
  ShieldCheck,
  SlidersHorizontal,
  Sparkles,
  UserCheck,
  UsersRound,
  X,
  XCircle,
} from "lucide-react";
import type { Locale } from "@/lib/contracts";
import { postJson } from "@/lib/api";
import { ChartPanel } from "./chart-panel";
import { ResourceState } from "./resource-state";

export function ForecastScreen({
  locale,
  workspace,
}: {
  locale: Locale;
  workspace?: string;
}) {
  const ar = locale === "ar";
  const [horizon, setHorizon] = useState("8");
  const [series, setSeries] = useState("support demand");
  const [tableOpen, setTableOpen] = useState(false);
  const data = [
    { label: "W21", value: 212 },
    { label: "W22", value: 226 },
    { label: "W23", value: 241 },
    { label: "W24", value: 258 },
    { label: "W25", value: 272 },
    { label: "W26", value: 284 },
    { label: "W27", value: 301, forecastLow: 272, forecastHigh: 331 },
    { label: "W28", value: 312, forecastLow: 277, forecastHigh: 347 },
    { label: "W29", value: 319, forecastLow: 279, forecastHigh: 359 },
    { label: "W30", value: 326, forecastLow: 281, forecastHigh: 371 },
  ];
  return (
    <div className="stack-page">
      <header className="page-header">
        <div>
          <p className="eyebrow">
            {ar ? "تنبؤ مختبر زمنيًا" : "Temporally tested forecast"}
          </p>
          <h1>{ar ? "التنبؤات والطاقة" : "Forecasts & capacity"}</h1>
          <p>
            {ar
              ? "ميّز المشاهدات عن التنبؤ وعدم اليقين، وقارن دائمًا بخط أساس."
              : "Keep observations, forecasts, and uncertainty distinct—and always compare with a baseline."}
          </p>
        </div>
        <button className="button button--primary">
          <Plus />
          {ar ? "تشغيل تنبؤ" : "Run forecast"}
        </button>
      </header>
      {workspace === "demo" ? (
        <div className="truth-banner">
          <CircleAlert />
          {ar
            ? "تشغيل خيالي محفوظ · بيانات حتى ٣٠ يونيو ٢٠٢٦ · لا يدّعي دقة على بيانات حقيقية."
            : "Stored fictional run · data through 30 Jun 2026 · no real-company accuracy claim."}
        </div>
      ) : null}
      <section className="forecast-controls">
        <label>
          <span>{ar ? "السلسلة" : "Series"}</span>
          <select value={series} onChange={(e) => setSeries(e.target.value)}>
            <option value="support demand">
              {ar ? "طلب الدعم الأسبوعي" : "Weekly support demand"}
            </option>
            <option value="project workload">
              {ar ? "عبء المشاريع" : "Project workload"}
            </option>
            <option value="net revenue">
              {ar ? "صافي الإيراد" : "Net revenue"}
            </option>
          </select>
        </label>
        <label>
          <span>{ar ? "الأفق" : "Horizon"}</span>
          <select value={horizon} onChange={(e) => setHorizon(e.target.value)}>
            <option value="4">{ar ? "٤ أسابيع" : "4 weeks"}</option>
            <option value="8">{ar ? "٨ أسابيع" : "8 weeks"}</option>
            <option value="12">{ar ? "١٢ أسبوعًا" : "12 weeks"}</option>
          </select>
        </label>
        <div>
          <span>{ar ? "الأهلية" : "Eligibility"}</span>
          <b className="badge badge--ready">
            <Check />
            {ar ? "١٠٤ أسابيع كاملة" : "104 complete weeks"}
          </b>
        </div>
        <div>
          <span>{ar ? "حداثة المصدر" : "Source freshness"}</span>
          <b>{ar ? "حتى ٣٠ يونيو ٢٠٢٦" : "Through 30 Jun 2026"}</b>
        </div>
      </section>
      <div className="forecast-layout">
        <ChartPanel
          locale={locale}
          kind="forecast"
          title={
            ar
              ? "طلب الدعم: تاريخي ومتنبأ"
              : "Support demand: observed & forecast"
          }
          description={
            ar
              ? "الخط المتصل ملاحظ حتى W26؛ المتقطع تنبؤ. فاصل ٨٠٪ موضح في الجدول."
              : "Solid values are observed through W26; dashed values are forecasts. 80% interval is available in the table."
          }
          data={data}
          unit={ar ? "حالة" : "cases"}
          source="forecast_run_demo_004 · support v9"
        />
        <aside className="forecast-summary">
          <p className="eyebrow">{ar ? "خلاصة التشغيل" : "Run summary"}</p>
          <h2>
            {ar
              ? "الطلب المرجح يتجاوز التغطية"
              : "Likely demand exceeds coverage"}
          </h2>
          <p>
            {ar
              ? "عند ٢٦٠ حالة أسبوعيًا من الطاقة الحالية، يتجاوز التنبؤ الوسيط السعة من الأسبوع ٢٧. الفاصل يتسع مع الأفق."
              : "At current capacity of 260 cases/week, the median forecast exceeds capacity from week 27. Intervals widen with horizon."}
          </p>
          <dl className="compact-dl">
            <div>
              <dt>{ar ? "النموذج المختار" : "Selected model"}</dt>
              <dd>Seasonal ETS</dd>
            </div>
            <div>
              <dt>{ar ? "خط الأساس" : "Baseline"}</dt>
              <dd>Seasonal naive</dd>
            </div>
            <div>
              <dt>WAPE</dt>
              <dd>
                <bdi>11.8% vs 15.1%</bdi>
              </dd>
            </div>
            <div>
              <dt>{ar ? "تغطية الفاصل" : "Interval coverage"}</dt>
              <dd>78.4% (target 80%)</dd>
            </div>
          </dl>
          <button
            className="button button--secondary button--wide"
            onClick={() => setTableOpen((value) => !value)}
          >
            {tableOpen
              ? ar
                ? "إخفاء الاختبار الخلفي"
                : "Hide backtest"
              : ar
                ? "عرض الاختبار الخلفي"
                : "View backtest"}
            <ChevronRight />
          </button>
        </aside>
      </div>
      {tableOpen ? (
        <section className="records-panel">
          <header className="panel-heading">
            <div>
              <p className="eyebrow">
                {ar ? "اختبار متدحرج" : "Rolling-origin backtest"}
              </p>
              <h2>{ar ? "الأداء حسب الأفق" : "Performance by horizon"}</h2>
            </div>
          </header>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>{ar ? "الأفق" : "Horizon"}</th>
                  <th>MAE</th>
                  <th>WAPE</th>
                  <th>MASE</th>
                  <th>{ar ? "تغطية ٨٠٪" : "80% coverage"}</th>
                </tr>
              </thead>
              <tbody>
                <tr>
                  <th>1 week</th>
                  <td>21.4</td>
                  <td>8.6%</td>
                  <td>0.71</td>
                  <td>81.2%</td>
                </tr>
                <tr>
                  <th>4 weeks</th>
                  <td>29.8</td>
                  <td>11.8%</td>
                  <td>0.86</td>
                  <td>78.4%</td>
                </tr>
                <tr>
                  <th>8 weeks</th>
                  <td>42.1</td>
                  <td>15.9%</td>
                  <td>1.04</td>
                  <td>74.2%</td>
                </tr>
              </tbody>
            </table>
          </div>
          <p className="panel-note">
            <Info />
            {ar
              ? "لا يتفوق النموذج على خط الأساس بعد الأسبوع الثامن؛ لذلك لا يمتد هذا التشغيل إلى ١٢ أسبوعًا."
              : "The candidate no longer beats baseline after week 8, so this run is not extended to 12 weeks."}
          </p>
        </section>
      ) : null}
    </div>
  );
}

export function ScenarioScreen({
  locale,
  workspace,
}: {
  locale: Locale;
  workspace?: string;
}) {
  const ar = locale === "ar";
  const [agents, setAgents] = useState(18);
  const [arrival, setArrival] = useState(310);
  const [hours, setHours] = useState(36);
  const [budget, setBudget] = useState(18000);
  const [saved, setSaved] = useState("");
  const [problem, setProblem] = useState("");
  const capacity = Math.round(agents * hours * 0.48);
  const feasible = capacity >= arrival;
  const utilization = Math.round((arrival / Math.max(1, capacity)) * 100);
  const wait = feasible ? Math.max(1.8, 14 * (utilization / 100) ** 4) : null;
  const chart = [
    { label: ar ? "حالي" : "Current", value: 260 },
    { label: ar ? "خط أساس" : "Baseline", value: 284 },
    { label: ar ? "مقترح" : "Proposed", value: capacity },
  ];
  async function save() {
    setProblem("");
    try {
      const response = await postJson<{ id: string }>("/api/v1/scenarios", {
        name: "Weekend support capacity",
        assumptions: { agents, arrival_rate: arrival, hours, budget },
        feasibility: feasible,
      });
      setSaved(response.id);
    } catch (error) {
      if (workspace === "demo")
        setSaved(
          ar
            ? "مسودة محلية غير محفوظة في الخادم"
            : "Local draft—not persisted to the server",
        );
      else setProblem(error instanceof Error ? error.message : "Save failed");
    }
  }
  return (
    <div className="stack-page">
      <header className="page-header">
        <div>
          <p className="eyebrow">
            {ar ? "مقارنة افتراضات" : "Assumption comparison"}
          </p>
          <h1>{ar ? "مختبر سيناريو التغطية" : "Coverage scenario lab"}</h1>
          <p>
            {ar
              ? "سيناريو محسوب، لا نتيجة ملاحظة ولا تقدير سببي. غيّر الافتراضات وافحص القيود."
              : "A calculated scenario—not an observed outcome or causal estimate. Change assumptions and inspect constraints."}
          </p>
        </div>
        <div className="action-row">
          <button
            className="button button--secondary"
            onClick={() => {
              setAgents(18);
              setArrival(310);
              setHours(36);
              setBudget(18000);
            }}
          >
            <RotateCcw />
            {ar ? "إعادة" : "Reset"}
          </button>
          <button className="button button--primary" onClick={save}>
            <Save />
            {ar ? "حفظ السيناريو" : "Save scenario"}
          </button>
        </div>
      </header>
      {workspace === "demo" ? (
        <div className="truth-banner">
          <CircleAlert />
          {ar
            ? "محاكاة خيالية ببذرة ثابتة؛ لا تمثل أثرًا سببيًا أو نتيجة مستقبلية مضمونة."
            : "Fictional fixed-seed simulation; not a causal effect or guaranteed future outcome."}
        </div>
      ) : null}
      {saved ? (
        <div className="success-message" role="status">
          <CheckCircle2 />
          {ar ? "حالة الحفظ: " : "Save status: "}
          <bdi>{saved}</bdi>
        </div>
      ) : null}
      {problem ? (
        <ResourceState
          locale={locale}
          status="error"
          compact
          reason={problem}
          onRetry={save}
        />
      ) : null}
      <div className="scenario-grid">
        <section className="assumption-panel">
          <header>
            <p className="eyebrow">
              {ar ? "الافتراضات المقترحة" : "Proposed assumptions"}
            </p>
            <h2>{ar ? "تغطية الدعم الأسبوعية" : "Weekly support coverage"}</h2>
          </header>
          <ScenarioInput
            locale={locale}
            id="agents"
            label={ar ? "الوكلاء المتاحون" : "Available agents"}
            value={agents}
            min={8}
            max={30}
            unit={ar ? "وكيل" : "agents"}
            set={setAgents}
          />
          <ScenarioInput
            locale={locale}
            id="arrivals"
            label={ar ? "الحالات الوافدة" : "Incoming cases"}
            value={arrival}
            min={180}
            max={480}
            unit={ar ? "حالة/أسبوع" : "cases/week"}
            set={setArrival}
          />
          <ScenarioInput
            locale={locale}
            id="hours"
            label={ar ? "الساعات المنتجة" : "Productive hours"}
            value={hours}
            min={20}
            max={42}
            unit={ar ? "ساعة/وكيل" : "hours/agent"}
            set={setHours}
          />
          <ScenarioInput
            locale={locale}
            id="budget"
            label={ar ? "حد الموازنة" : "Budget ceiling"}
            value={budget}
            min={8000}
            max={30000}
            step={500}
            unit="JOD"
            set={setBudget}
          />
          <div className="constraint-list">
            <h3>{ar ? "قيود صلبة" : "Hard constraints"}</h3>
            <p>
              <Check />
              {ar ? "حد ٤٢ ساعة للفرد" : "42-hour individual limit"}
            </p>
            <p>
              <Check />
              {ar
                ? "تغطية مهارة المنصة في كل وردية"
                : "Platform skill coverage each shift"}
            </p>
            <p className={budget < agents * 900 ? "failed" : ""}>
              {budget < agents * 900 ? <XCircle /> : <Check />}
              {ar ? "لا تتجاوز الموازنة" : "Stay within budget"}
            </p>
          </div>
        </section>
        <section className="scenario-results">
          <ChartPanel
            locale={locale}
            kind="bar"
            title={ar ? "الطلب والطاقة الأسبوعية" : "Weekly demand & capacity"}
            description={
              ar
                ? "الحالي والمقترح على مقياس واحد."
                : "Current and proposed on one shared scale."
            }
            data={chart}
            unit={ar ? "حالة" : "cases"}
            source="scenario_calc_demo_07"
          />
          <div
            className={`feasibility-card ${feasible && budget >= agents * 900 ? "feasible" : "infeasible"}`}
          >
            <span>
              {feasible && budget >= agents * 900 ? (
                <CheckCircle2 />
              ) : (
                <AlertTriangle />
              )}
            </span>
            <div>
              <p className="eyebrow">{ar ? "حالة الحل" : "Feasibility"}</p>
              <h2>
                {feasible && budget >= agents * 900
                  ? ar
                    ? "يوجد جدول صالح"
                    : "Feasible schedule found"
                  : ar
                    ? "القيود غير قابلة للتحقيق"
                    : "Constraints are infeasible"}
              </h2>
              <p>
                {!feasible
                  ? ar
                    ? `تنقص الطاقة ${arrival - capacity} حالة أسبوعيًا. زد الوكلاء أو الساعات أو خفّض الطلب المفترض.`
                    : `Capacity is short by ${arrival - capacity} cases/week. Add agents/hours or reduce assumed demand.`
                  : budget < agents * 900
                    ? ar
                      ? `الحد أقل من تكلفة التغطية التقديرية بمقدار ${agents * 900 - budget} د.أ.`
                      : `Budget is JOD ${agents * 900 - budget} below estimated coverage cost.`
                    : ar
                      ? `استخدام متوقع ${utilization}٪ ووسيط انتظار محاكى ${wait?.toFixed(1)} ساعة.`
                      : `Expected utilization ${utilization}% and simulated median wait ${wait?.toFixed(1)} hours.`}
              </p>
            </div>
          </div>
          <div className="scenario-metrics">
            <div>
              <span>{ar ? "الطاقة" : "Capacity"}</span>
              <strong>{capacity}</strong>
              <small>{ar ? "حالة/أسبوع" : "cases/week"}</small>
            </div>
            <div>
              <span>{ar ? "الاستخدام" : "Utilization"}</span>
              <strong>{utilization}%</strong>
              <small>
                {utilization > 95
                  ? ar
                    ? "هش"
                    : "fragile"
                  : ar
                    ? "ضمن الحد"
                    : "within limit"}
              </small>
            </div>
            <div>
              <span>{ar ? "الانتظار" : "Median wait"}</span>
              <strong>{wait == null ? "—" : `${wait.toFixed(1)}h`}</strong>
              <small>
                {ar ? "محاكاة · ٥٠ تشغيلًا" : "simulation · 50 runs"}
              </small>
            </div>
          </div>
        </section>
      </div>
    </div>
  );
}

function ScenarioInput({
  locale,
  id,
  label,
  value,
  min,
  max,
  step = 1,
  unit,
  set,
}: {
  locale: Locale;
  id: string;
  label: string;
  value: number;
  min: number;
  max: number;
  step?: number;
  unit: string;
  set: (v: number) => void;
}) {
  const ar = locale === "ar";
  return (
    <div className="scenario-input">
      <div>
        <label htmlFor={`${id}-range`}>{label}</label>
        <span>
          {min}–{max} {unit}
        </span>
      </div>
      <div>
        <input
          id={`${id}-range`}
          type="range"
          min={min}
          max={max}
          step={step}
          value={value}
          onChange={(e) => set(Number(e.target.value))}
        />
        <label className="number-field">
          <span className="sr-only">
            {label} {ar ? "قيمة دقيقة" : "exact value"}
          </span>
          <input
            type="number"
            min={min}
            max={max}
            step={step}
            value={value}
            onChange={(e) =>
              set(Math.min(max, Math.max(min, Number(e.target.value))))
            }
          />
          <bdi>{unit}</bdi>
        </label>
      </div>
    </div>
  );
}

export function ReportsScreen({
  locale,
  workspace,
}: {
  locale: Locale;
  workspace?: string;
}) {
  const ar = locale === "ar";
  const [section, setSection] = useState("summary");
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState(
    ar
      ? "نمت الإيرادات ١٢٫٤٪، بينما انخفض هامش الربح الإجمالي ٣٫١ نقطة مئوية. يحتاج ضغط الدعم وتبعية مورد مشروع أطلس إلى مراجعة."
      : "Revenue grew 12.4%, while gross margin narrowed 3.1 percentage points. Support pressure and the Atlas supplier dependency need review.",
  );
  const [savedText, setSavedText] = useState(text);
  const [version, setVersion] = useState(4);
  function save() {
    setSavedText(text);
    setVersion((v) => v + 1);
    setEditing(false);
  }
  return (
    <div className="report-workspace">
      <aside className="report-nav">
        <p className="eyebrow">{ar ? "أقسام التقرير" : "Report sections"}</p>
        <h2>{ar ? "مراجعة يونيو التنفيذية" : "June executive review"}</h2>
        {[
          ["summary", ar ? "الملخص التنفيذي" : "Executive summary"],
          ["performance", ar ? "الأداء التجاري" : "Commercial performance"],
          ["operations", ar ? "العمليات والمشاريع" : "Operations & projects"],
          ["actions", ar ? "الإجراءات" : "Actions"],
          ["appendix", ar ? "التعاريف والقيود" : "Definitions & limits"],
        ].map(([id, label], index) => (
          <button
            className={section === id ? "active" : ""}
            key={id}
            onClick={() => setSection(id)}
          >
            <span>{index + 1}</span>
            {label}
            <ChevronRight />
          </button>
        ))}
        <div className="report-version">
          <History />
          <div>
            <b>{ar ? `الإصدار ${version}` : `Version ${version}`}</b>
            <span>{ar ? "مسودة خاصة" : "Private draft"}</span>
          </div>
        </div>
      </aside>
      <main className="report-main">
        <header className="report-toolbar">
          <div>
            <span className="badge badge--demo">
              {workspace === "demo"
                ? ar
                  ? "تقرير بيانات خيالية"
                  : "Fictional-data report"
                : ar
                  ? "مسودة"
                  : "Draft"}
            </span>
            <span>{ar ? "آخر حفظ الآن" : "Saved just now"}</span>
          </div>
          <div>
            <button className="button button--secondary">
              <GitCompareArrows />
              {ar ? "قارن الإصدارات" : "Compare versions"}
            </button>
            <button className="button button--secondary">
              <Download />
              {ar ? "تصدير" : "Export"}
            </button>
            <button
              className="button button--primary"
              onClick={save}
              disabled={!editing}
            >
              <Save />
              {ar ? "حفظ إصدار" : "Save version"}
            </button>
          </div>
        </header>
        <article className="document-canvas">
          <header className="document-cover">
            <span className="brand-mark">ب</span>
            <p>{ar ? "تقرير تنفيذي" : "EXECUTIVE REPORT"}</p>
            <h1>
              {ar
                ? "مراجعة الأداء والنقاط التي تستحق قرارًا"
                : "Performance review and decision points"}
            </h1>
            <dl>
              <div>
                <dt>{ar ? "الشركة" : "Company"}</dt>
                <dd>
                  {ar
                    ? "شركة نماء للخدمات الصناعية"
                    : "Namaa Industrial Services"}
                </dd>
              </div>
              <div>
                <dt>{ar ? "الفترة" : "Period"}</dt>
                <dd>{ar ? "١ يناير–٣٠ يونيو ٢٠٢٦" : "1 Jan–30 Jun 2026"}</dd>
              </div>
              <div>
                <dt>{ar ? "نوع التقرير" : "Report type"}</dt>
                <dd>{ar ? "لقطة غير متغيرة" : "Immutable snapshot"}</dd>
              </div>
            </dl>
          </header>
          <section className="document-section">
            <div className="document-section__label">
              <span>01</span>
              <p>{ar ? "الملخص التنفيذي" : "Executive summary"}</p>
            </div>
            <div className="editable-block">
              <header>
                <span>
                  <MessageSquareText />
                  {ar ? "نص قابل للتحرير" : "Editable narrative"}
                </span>
                <button
                  className="button button--ghost button--small"
                  onClick={() => setEditing((v) => !v)}
                >
                  {editing
                    ? ar
                      ? "معاينة"
                      : "Preview"
                    : ar
                      ? "تحرير"
                      : "Edit"}
                </button>
              </header>
              {editing ? (
                <textarea
                  value={text}
                  onChange={(e) => setText(e.target.value)}
                  aria-label={
                    ar ? "نص الملخص التنفيذي" : "Executive summary text"
                  }
                  rows={6}
                />
              ) : (
                <p>{savedText}</p>
              )}
            </div>
            <div className="linked-metrics">
              <MetricBlock
                label={ar ? "صافي الإيرادات" : "Net revenue"}
                value="JOD 1.84m"
                result="result_demo_rev_17"
              />
              <MetricBlock
                label={ar ? "هامش الربح" : "Gross margin"}
                value="26.8%"
                result="result_demo_margin_17"
              />
              <MetricBlock
                label={ar ? "حالات الدعم" : "Open support cases"}
                value="284"
                result="result_demo_support_09"
              />
            </div>
            <div className="document-callout">
              <Sparkles />
              <div>
                <p className="eyebrow">
                  {ar ? "توصية للمراجعة" : "Recommendation for review"}
                </p>
                <h2>
                  {ar
                    ? "اختبر تغطية نهاية الأسبوع لأربع أسابيع"
                    : "Pilot weekend coverage for four weeks"}
                </h2>
                <p>
                  {ar
                    ? "راجع الأثر على زمن الاستجابة، العمل المتراكم، والتكلفة قبل اعتماد التغيير."
                    : "Review response time, backlog, and cost before adopting the change."}
                </p>
              </div>
              <button className="button button--secondary">
                {ar ? "تحويل لمسودة قرار" : "Create decision draft"}
              </button>
            </div>
          </section>
          <footer className="document-footer">
            <span>BASEERA · {ar ? "بيانات خيالية" : "Fictional data"}</span>
            <span>{ar ? "صفحة ١ من ٦" : "Page 1 of 6"}</span>
          </footer>
        </article>
      </main>
      <aside className="report-assistant">
        <div className="report-assistant__head">
          <Bot />
          <div>
            <p className="eyebrow">{ar ? "تحرير مساعد" : "Assisted editing"}</p>
            <h2>{ar ? "اقترح تغييرًا" : "Propose a change"}</h2>
          </div>
        </div>
        <p>
          {ar
            ? "التغييرات اللغوية لا تعدّل القيم. تغيير الفترة أو الفلاتر ينشئ نتائج جديدة قبل المعاينة."
            : "Wording changes never alter values. Period or filter changes create new results before preview."}
        </p>
        <div className="suggested-prompts">
          <button>
            {ar ? "اختصر الملخص إلى ٣ نقاط" : "Condense summary to 3 points"}
          </button>
          <button>
            {ar ? "حوّل التقرير إلى العربية" : "Translate report to Arabic"}
          </button>
          <button>
            {ar ? "غيّر الفترة إلى الربع الثاني" : "Change period to Q2"}
          </button>
        </div>
        <form onSubmit={(e) => e.preventDefault()}>
          <label htmlFor="report-instruction">
            {ar ? "تعليمات التغيير" : "Edit instruction"}
          </label>
          <textarea
            id="report-instruction"
            rows={4}
            placeholder={
              ar ? "صف التغيير المطلوب…" : "Describe the requested change…"
            }
          />
          <button className="button button--primary button--wide">
            {ar ? "إنشاء معاينة" : "Generate preview"}
            <ArrowRight />
          </button>
        </form>
        <div className="guardrail-note">
          <LockKeyhole />
          <p>
            {ar
              ? "تُطبق الرقعة على الإصدار المتوقع فقط؛ يظهر التعارض بدل الكتابة فوق عمل آخر."
              : "The patch applies only to its expected version; conflicts are shown instead of overwriting work."}
          </p>
        </div>
      </aside>
    </div>
  );
}

function MetricBlock({
  label,
  value,
  result,
}: {
  label: string;
  value: string;
  result: string;
}) {
  return (
    <article>
      <span>{label}</span>
      <strong>
        <bdi>{value}</bdi>
      </strong>
      <small>
        <ShieldCheck /> <bdi>{result}</bdi>
      </small>
    </article>
  );
}

export function DecisionsScreen({
  locale,
  kind = "decisions",
}: {
  locale: Locale;
  kind?: "decisions" | "approvals";
}) {
  const ar = locale === "ar";
  const [selected, setSelected] = useState(0);
  const [notice, setNotice] = useState("");
  if (kind === "approvals") return <ApprovalsScreen locale={locale} />;
  const decisions = [
    {
      title: ar ? "تجربة تغطية نهاية الأسبوع" : "Weekend coverage pilot",
      owner: ar ? "ليلى حداد" : "Layla Haddad",
      state: ar ? "للمراجعة" : "Review due",
      review: "2026-07-06",
      evidence: 4,
    },
    {
      title: ar ? "إعادة جدولة معلم أطلس" : "Reschedule Atlas milestone",
      owner: ar ? "عمر النجار" : "Omar Al-Najjar",
      state: ar ? "قيد التنفيذ" : "In progress",
      review: "2026-07-03",
      evidence: 3,
    },
    {
      title: ar ? "تعديل ضوابط الخصم" : "Adjust discount guardrails",
      owner: ar ? "رانيا شحادة" : "Rania Shehadeh",
      state: ar ? "مسودة" : "Draft",
      review: "2026-07-12",
      evidence: 5,
    },
  ];
  const item = decisions[selected];
  return (
    <div className="stack-page">
      <header className="page-header">
        <div>
          <p className="eyebrow">
            {ar ? "من الدليل إلى المتابعة" : "Evidence to follow-up"}
          </p>
          <h1>{ar ? "مركز القرارات" : "Decision center"}</h1>
          <p>
            {ar
              ? "سجّل المشكلة والخيارات والمالك والنتيجة المتوقعة، ثم قارنها بما حدث."
              : "Record the problem, options, owner, and expected result—then compare with what happened."}
          </p>
        </div>
        <button className="button button--primary">
          <Plus />
          {ar ? "قرار جديد" : "New decision"}
        </button>
      </header>
      {notice ? (
        <div className="success-message" role="status">
          <Check />
          {notice}
        </div>
      ) : null}
      <div className="decision-layout">
        <section className="decision-list">
          {decisions.map((decision, index) => (
            <button
              className={selected === index ? "selected" : ""}
              key={decision.title}
              onClick={() => setSelected(index)}
            >
              <span className="decision-icon">
                <Gauge />
              </span>
              <div>
                <b>{decision.title}</b>
                <span>
                  {decision.owner} · {decision.state}
                </span>
                <small>
                  <CalendarClock />
                  {decision.review} · {decision.evidence}{" "}
                  {ar ? "مراجع دليل" : "evidence refs"}
                </small>
              </div>
              <ChevronRight />
            </button>
          ))}
        </section>
        <article className="decision-detail">
          <header>
            <div>
              <p className="eyebrow">DEC-2026-00{selected + 7}</p>
              <h2>{item.title}</h2>
            </div>
            <span className="badge badge--warning">{item.state}</span>
          </header>
          <section>
            <h3>{ar ? "المشكلة" : "Problem"}</h3>
            <p>
              {ar
                ? "يتجاوز طلب الدعم في نهاية الأسبوع التغطية المتاحة، مع ارتفاع وقت الانتظار والعمل المتراكم."
                : "Weekend support demand exceeds staffed coverage, with rising wait time and backlog."}
            </p>
          </section>
          <section>
            <h3>{ar ? "الأدلة المرتبطة" : "Linked evidence"}</h3>
            <div className="evidence-chips">
              <button>
                <ShieldCheck />
                support_open · v9
              </button>
              <button>
                <ShieldCheck />
                forecast_run_004
              </button>
              <button>
                <ShieldCheck />
                scenario_calc_007
              </button>
            </div>
          </section>
          <section>
            <h3>{ar ? "الخيارات التي روجعت" : "Options reviewed"}</h3>
            <ol className="option-list">
              <li>
                <span>A</span>
                <div>
                  <b>
                    {ar ? "الإبقاء على الجدول الحالي" : "Keep current roster"}
                  </b>
                  <p>
                    {ar
                      ? "لا تكلفة إضافية؛ يتوقع استمرار العجز."
                      : "No added cost; the shortfall likely continues."}
                  </p>
                </div>
              </li>
              <li className="chosen">
                <span>B</span>
                <div>
                  <b>
                    {ar
                      ? "تجربة وردية مرنة لأربع أسابيع"
                      : "Four-week flexible-shift pilot"}
                  </b>
                  <p>
                    {ar
                      ? "ضمن حد الموازنة؛ قياس SLA والعمل المتراكم أسبوعيًا."
                      : "Within budget; measure SLA and backlog weekly."}
                  </p>
                </div>
                <Check />
              </li>
              <li>
                <span>C</span>
                <div>
                  <b>{ar ? "تعهيد جزء من الطلب" : "Outsource overflow"}</b>
                  <p>
                    {ar
                      ? "زمن بدء أطول وتكلفة حالة أعلى."
                      : "Longer lead time and higher cost per case."}
                  </p>
                </div>
              </li>
            </ol>
          </section>
          <footer>
            <dl>
              <div>
                <dt>{ar ? "المالك" : "Owner"}</dt>
                <dd>{item.owner}</dd>
              </div>
              <div>
                <dt>{ar ? "مراجعة النتيجة" : "Outcome review"}</dt>
                <dd>{item.review}</dd>
              </div>
              <div>
                <dt>{ar ? "مؤشر النجاح" : "Success metric"}</dt>
                <dd>
                  {ar
                    ? "SLA ≥ 90٪ والعمل المتراكم < 180"
                    : "SLA ≥ 90% and backlog < 180"}
                </dd>
              </div>
            </dl>
            <button
              className="button button--primary"
              onClick={() =>
                setNotice(
                  ar
                    ? "تم تسجيل مراجعة القرار محليًا؛ يحتاج API للحفظ الدائم."
                    : "Decision review recorded locally; API is required for persistence.",
                )
              }
            >
              <UserCheck />
              {ar ? "تسجيل مراجعة" : "Record review"}
            </button>
          </footer>
        </article>
      </div>
    </div>
  );
}

function ApprovalsScreen({ locale }: { locale: Locale }) {
  const ar = locale === "ar";
  const [status, setStatus] = useState<"pending" | "approved" | "rejected">(
    "pending",
  );
  return (
    <div className="stack-page">
      <header className="page-header">
        <div>
          <p className="eyebrow">
            {ar ? "مراجعة قبل الأثر" : "Review before consequence"}
          </p>
          <h1>{ar ? "صندوق الموافقات" : "Approval inbox"}</h1>
          <p>
            {ar
              ? "اطلع على الفرق والمجاميع والنطاق قبل السماح بتغيير جوهري."
              : "Inspect the diff, totals, and scope before allowing a material change."}
          </p>
        </div>
        <span className="badge badge--warning">
          1 {ar ? "بانتظارك" : "awaiting you"}
        </span>
      </header>
      {status !== "pending" ? (
        <div
          className={`resource-state resource-state--${status === "approved" ? "empty" : "error"}`}
          role="status"
        >
          <span className="resource-state__icon">
            {status === "approved" ? <CheckCircle2 /> : <XCircle />}
          </span>
          <div>
            <h2>
              {status === "approved"
                ? ar
                  ? "تمت الموافقة"
                  : "Approved"
                : ar
                  ? "تم الرفض"
                  : "Rejected"}
            </h2>
            <p>
              {ar
                ? "سُجل القرار مع الهوية والوقت والتعليل. التنفيذ النهائي يعالج عبر مهمة منفصلة."
                : "The identity, time, and rationale were recorded. Final execution is handled by a separate job."}
            </p>
            <button
              className="button button--secondary"
              onClick={() => setStatus("pending")}
            >
              {ar ? "عرض الطلب" : "Review request"}
            </button>
          </div>
        </div>
      ) : (
        <article className="approval-review">
          <header>
            <div className="approval-type">
              <FileCheck2 />
              <div>
                <p className="eyebrow">
                  {ar ? "تحويل بيانات جوهري" : "Material data transformation"}
                </p>
                <h2>
                  {ar
                    ? "نشر cleaned-v2 لمجموعة طلبات المبيعات"
                    : "Publish cleaned-v2 for sales orders"}
                </h2>
              </div>
            </div>
            <span className="badge badge--warning">raw-v1 → cleaned-v2</span>
          </header>
          <div className="approval-summary">
            <div>
              <span>{ar ? "الصفوف المتأثرة" : "Affected rows"}</span>
              <strong>646</strong>
            </div>
            <div>
              <span>{ar ? "المكررات المعزولة" : "Duplicates quarantined"}</span>
              <strong>428</strong>
            </div>
            <div>
              <span>{ar ? "تواريخ غير محلولة" : "Unresolved dates"}</span>
              <strong>37</strong>
            </div>
            <div>
              <span>
                {ar ? "فرق الإجمالي غير المفسر" : "Unexplained total delta"}
              </span>
              <strong className="positive">JOD 0.00</strong>
            </div>
          </div>
          <section className="approval-diff">
            <h3>{ar ? "ملخص العواقب" : "Consequence summary"}</h3>
            <ul>
              <li>
                <Check />
                {ar
                  ? "يصبح cleaned-v2 إصدار التحليل المنشور؛ يبقى raw-v1 دون تعديل."
                  : "cleaned-v2 becomes the published analysis version; raw-v1 remains immutable."}
              </li>
              <li>
                <Check />
                {ar
                  ? "يهبط صافي الإيراد ٤٦٬٦٢٤٫٥٠ د.أ لأن دفعة مكررة ستُعزل."
                  : "Net revenue falls JOD 46,624.50 because a duplicate batch is quarantined."}
              </li>
              <li>
                <AlertTriangle />
                {ar
                  ? "تبقى ٣٧ قيمة تاريخ ملتبسة خارج مقاييس الزمن حتى حلها."
                  : "37 ambiguous dates remain outside time metrics until resolved."}
              </li>
              <li>
                <Check />
                {ar
                  ? "تبقى ٦٢ قيمة مرتجع سالبة وتدخل صافي الإيراد."
                  : "62 legitimate negative returns remain included in net revenue."}
              </li>
            </ul>
          </section>
          <label className="field">
            <span>{ar ? "ملاحظة المراجع" : "Reviewer note"}</span>
            <textarea
              rows={3}
              placeholder={
                ar
                  ? "أضف سبب الموافقة أو الرفض…"
                  : "Add the reason for approval or rejection…"
              }
            />
          </label>
          <footer>
            <div>
              <span>
                {ar
                  ? "طلبته سارة منصور · محللة"
                  : "Requested by Sara Mansour · Analyst"}
              </span>
              <small>{ar ? "ينتهي خلال ٢٢ ساعة" : "Expires in 22 hours"}</small>
            </div>
            <button
              className="button button--danger"
              onClick={() => setStatus("rejected")}
            >
              <X />
              {ar ? "رفض" : "Reject"}
            </button>
            <button
              className="button button--primary"
              onClick={() => setStatus("approved")}
            >
              <Check />
              {ar ? "موافقة ونشر" : "Approve & publish"}
            </button>
          </footer>
        </article>
      )}
    </div>
  );
}

export function AdminScreen({
  locale,
  workspace,
}: {
  locale: Locale;
  workspace?: string;
}) {
  const ar = locale === "ar";
  const [tab, setTab] = useState("availability");
  const capabilities = [
    {
      name: "File ingestion · CSV/TSV/XLSX/JSONL/Parquet",
      state: "ready",
      detail: ar
        ? "منفذ؛ يلزم فحص API لكل مصدر."
        : "Implemented; source-specific API verification required.",
    },
    {
      name: "PostgreSQL read connector",
      state: "ready",
      detail: ar
        ? "اكتشاف، معاينة، مزامنة تزايدية."
        : "Discovery, preview, and incremental sync.",
    },
    {
      name: "Odoo adapter",
      state: "config",
      detail: ar
        ? "يحتاج بيانات اعتماد خيالية أو مخولة للاختبار الحي."
        : "Needs authorized credentials for live verification.",
    },
    {
      name: "Hosted LLM provider",
      state: "config",
      detail: ar
        ? "لم تُهيأ مفاتيح مزود في هذه المساحة."
        : "No hosted-provider key configured in this workspace.",
    },
    {
      name: "Google Sheets",
      state: "unsupported",
      detail: ar
        ? "استخدم تصدير CSV/XLSX حاليًا."
        : "Use CSV/XLSX export for now.",
    },
    {
      name: "Chronos / TabPFN",
      state: "optional",
      detail: ar
        ? "ملف تنفيذ اختياري؛ غير محمّل."
        : "Optional execution profile; weights are not loaded.",
    },
  ];
  return (
    <div className="admin-page">
      <header className="page-header">
        <div>
          <p className="eyebrow">
            {ar ? "الحوكمة والتشغيل" : "Governance & operations"}
          </p>
          <h1>{ar ? "الإدارة" : "Administration"}</h1>
          <p>
            {ar
              ? "أدر الإتاحة والصلاحيات والتعاريف والموارد دون إخفاء ما يحتاج إعدادًا."
              : "Manage availability, access, definitions, and resources without hiding configuration gaps."}
          </p>
        </div>
        <span className="badge badge--demo">
          {workspace === "demo"
            ? ar
              ? "إدارة مساحة خيالية"
              : "Fictional workspace admin"
            : ar
              ? "دور مسؤول"
              : "Administrator role"}
        </span>
      </header>
      <div className="admin-layout">
        <nav
          className="admin-tabs"
          aria-label={ar ? "أقسام الإدارة" : "Administration sections"}
        >
          {[
            ["availability", ar ? "إتاحة الإمكانات" : "Feature availability"],
            ["users", ar ? "المستخدمون والأدوار" : "Users & roles"],
            ["definitions", ar ? "تعريفات الأعمال" : "Business definitions"],
            ["providers", ar ? "مزودو النماذج" : "Model providers"],
            ["schedules", ar ? "الجداول" : "Schedules"],
            ["audit", ar ? "سجل التدقيق" : "Audit events"],
          ].map(([id, label]) => (
            <button
              className={tab === id ? "active" : ""}
              key={id}
              onClick={() => setTab(id)}
            >
              {label}
              <ChevronRight />
            </button>
          ))}
        </nav>
        <section className="admin-content">
          {tab === "availability" ? (
            <>
              <header className="panel-heading">
                <div>
                  <p className="eyebrow">
                    {ar ? "حالة صريحة" : "Honest status"}
                  </p>
                  <h2>{ar ? "إتاحة الإمكانات" : "Capability availability"}</h2>
                  <p>
                    {ar
                      ? "الجاهزية هنا ليست دليل اتصال حي؛ كل تكامل يحمل حالته الفعلية."
                      : "Readiness here is not proof of a live connection; every integration exposes its actual state."}
                  </p>
                </div>
              </header>
              <div className="capability-list">
                {capabilities.map((item) => (
                  <article key={item.name}>
                    <span
                      className={`capability-state capability-state--${item.state}`}
                    />{" "}
                    <div>
                      <h3>{item.name}</h3>
                      <p>{item.detail}</p>
                    </div>
                    <span
                      className={`badge badge--${item.state === "ready" ? "ready" : item.state === "config" ? "warning" : "neutral"}`}
                    >
                      {item.state === "ready"
                        ? ar
                          ? "منفذ"
                          : "Implemented"
                        : item.state === "config"
                          ? ar
                            ? "يحتاج إعدادًا"
                            : "Needs configuration"
                          : item.state === "optional"
                            ? ar
                              ? "اختياري غير متاح"
                              : "Optional unavailable"
                            : ar
                              ? "غير مدعوم"
                              : "Unsupported"}
                    </span>
                  </article>
                ))}
              </div>
            </>
          ) : tab === "users" ? (
            <AdminUsers locale={locale} />
          ) : tab === "schedules" ? (
            <Schedules locale={locale} />
          ) : (
            <ResourceState
              locale={locale}
              status="empty"
              compact
              reason={
                ar
                  ? "لا توجد سجلات تجريبية لهذا القسم. تتوفر الوظيفة عند اتصال API المخوّل."
                  : "No demo records for this section. The capability is available with an authorized API connection."
              }
            />
          )}
        </section>
      </div>
    </div>
  );
}

function AdminUsers({ locale }: { locale: Locale }) {
  const ar = locale === "ar";
  return (
    <>
      <header className="panel-heading">
        <div>
          <p className="eyebrow">
            {ar ? "نطاق أقل صلاحية" : "Least-privilege scopes"}
          </p>
          <h2>{ar ? "المستخدمون والأدوار" : "Users & roles"}</h2>
        </div>
        <button className="button button--primary">
          <Plus />
          {ar ? "دعوة مستخدم" : "Invite user"}
        </button>
      </header>
      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>{ar ? "المستخدم" : "User"}</th>
              <th>{ar ? "الدور" : "Role"}</th>
              <th>{ar ? "نطاق الإدارات" : "Department scope"}</th>
              <th>{ar ? "آخر جلسة" : "Last session"}</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <th>Maryam Al-Ali</th>
              <td>Executive</td>
              <td>All departments · no HR compensation</td>
              <td>Now</td>
            </tr>
            <tr>
              <th>Sara Mansour</th>
              <td>Analyst</td>
              <td>Finance, Sales, Operations</td>
              <td>12 min ago</td>
            </tr>
            <tr>
              <th>Rami Odeh</th>
              <td>Department manager</td>
              <td>Customer operations</td>
              <td>Yesterday</td>
            </tr>
          </tbody>
        </table>
      </div>
    </>
  );
}

function Schedules({ locale }: { locale: Locale }) {
  const ar = locale === "ar";
  const [paused, setPaused] = useState(false);
  return (
    <>
      <header className="panel-heading">
        <div>
          <p className="eyebrow">
            {ar ? "توقيت مع إعادة تحقق" : "Scheduled with re-authorization"}
          </p>
          <h2>{ar ? "الجداول النشطة" : "Active schedules"}</h2>
        </div>
      </header>
      <article className="schedule-row">
        <span className="schedule-icon">
          <Clock3 />
        </span>
        <div>
          <h3>{ar ? "مزامنة فواتير ERP" : "ERP invoice sync"}</h3>
          <p>
            {ar
              ? "كل ساعة · Asia/Amman · المالك: Finance data"
              : "Hourly · Asia/Amman · owner: Finance data"}
          </p>
          <small>
            {paused
              ? ar
                ? "متوقف مؤقتًا"
                : "Paused"
              : ar
                ? "التشغيل التالي ١٢:٠٠"
                : "Next run 12:00"}
          </small>
        </div>
        <button
          className="button button--secondary"
          onClick={() => setPaused((v) => !v)}
        >
          {paused ? <Play /> : <Pause />}
          {paused ? (ar ? "استئناف" : "Resume") : ar ? "إيقاف" : "Pause"}
        </button>
      </article>
    </>
  );
}
