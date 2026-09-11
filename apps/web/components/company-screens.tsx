"use client";

import { useMemo, useState } from "react";
import {
  Activity,
  ArrowRight,
  Boxes,
  BriefcaseBusiness,
  Building2,
  CalendarDays,
  Check,
  ChevronRight,
  CircleAlert,
  CircleDollarSign,
  Clock3,
  Eye,
  GitBranch,
  Goal,
  Headphones,
  Network,
  PackageCheck,
  RotateCcw,
  ShieldCheck,
  Table2,
  UsersRound,
} from "lucide-react";
import type { Locale } from "@/lib/contracts";
import { moduleRows } from "@/lib/demo-data";
import { formatCompactNumber } from "@/lib/i18n";
import { ChartPanel } from "./chart-panel";
import { EvidenceDrawer, type EvidenceRecord } from "./evidence-drawer";
import { ResourceState } from "./resource-state";

type ModuleId =
  | "customers"
  | "people"
  | "projects"
  | "operations"
  | "finance"
  | "support"
  | "objectives";

const configs: Record<
  ModuleId,
  {
    icon: typeof Building2;
    title: [string, string];
    kicker: [string, string];
    description: [string, string];
    kpis: Array<{
      label: [string, string];
      value: string;
      delta: string;
      tone?: string;
    }>;
    primary: [string, string];
    insight: [string, string];
  }
> = {
  customers: {
    icon: Building2,
    title: ["Customers & sales", "العملاء والمبيعات"],
    kicker: ["Demand to margin", "من الطلب إلى الهامش"],
    description: [
      "Follow revenue, returns, opportunities, and margin only where cost coverage permits it.",
      "تابع الإيراد والمرتجعات والفرص والهامش فقط حين تسمح تغطية التكلفة.",
    ],
    kpis: [
      {
        label: ["Net revenue", "صافي الإيرادات"],
        value: "JOD 1.84m",
        delta: "+12.4%",
      },
      {
        label: ["Approved returns", "المرتجعات المعتمدة"],
        value: "JOD 84.2k",
        delta: "+4.6%",
        tone: "warn",
      },
      {
        label: ["Pipeline", "قيمة الفرص"],
        value: "JOD 612k",
        delta: "1.8× cover",
      },
      {
        label: ["Cost coverage", "تغطية التكلفة"],
        value: "97.3%",
        delta: "119 missing",
      },
    ],
    primary: ["Revenue & margin movement", "حركة الإيراد والهامش"],
    insight: [
      "Growth is concentrated in enterprise services; discounts and mix account for most of the arithmetic margin gap.",
      "يتركز النمو في خدمات المؤسسات؛ الخصومات ومزيج الخدمات يمثلان معظم فجوة الهامش حسابيًا.",
    ],
  },
  people: {
    icon: UsersRound,
    title: ["People & teams", "الأفراد والفرق"],
    kicker: ["Capacity in context", "الطاقة ضمن سياقها"],
    description: [
      "Compare approved capacity and assignments without ranking people or inferring private traits.",
      "قارن الطاقة والتكليفات المعتمدة دون ترتيب الأفراد أو استنتاج صفات خاصة.",
    ],
    kpis: [
      { label: ["Headcount", "عدد الموظفين"], value: "104", delta: "+3 net" },
      {
        label: ["Available capacity", "الطاقة المتاحة"],
        value: "8,420 h",
        delta: "H2 plan",
      },
      {
        label: ["Over-allocated teams", "فرق فوق الطاقة"],
        value: "2",
        delta: "review",
        tone: "warn",
      },
      {
        label: ["Leave coverage", "تغطية الإجازات"],
        value: "92%",
        delta: "3 gaps",
      },
    ],
    primary: [
      "Assigned work vs available capacity",
      "العمل المكلّف مقابل الطاقة المتاحة",
    ],
    insight: [
      "Customer operations is assigned at 131% of approved capacity. Complexity, support load, and leave coverage are included; this is not an employee productivity score.",
      "تكليف عمليات العملاء يبلغ ١٣١٪ من الطاقة المعتمدة. يشمل السياق التعقيد والدعم والإجازات؛ وليس تقييمًا لإنتاجية الأفراد.",
    ],
  },
  projects: {
    icon: BriefcaseBusiness,
    title: ["Project portfolio", "محفظة المشاريع"],
    kicker: ["Delivery & dependencies", "التنفيذ والتبعيات"],
    description: [
      "See milestones, effort, budget, and evidence-backed dependency exposure together.",
      "شاهد المعالم والجهد والموازنة وانكشاف التبعيات المدعوم بالدليل معًا.",
    ],
    kpis: [
      {
        label: ["Active projects", "مشاريع نشطة"],
        value: "18",
        delta: "4 at risk",
      },
      {
        label: ["Milestones on time", "معالم في موعدها"],
        value: "82%",
        delta: "−4.1 pp",
        tone: "warn",
      },
      {
        label: ["Planned effort", "الجهد المخطط"],
        value: "14,260 h",
        delta: "H2",
      },
      {
        label: ["Budget consumed", "الموازنة المستهلكة"],
        value: "64.8%",
        delta: "+2.2 pp",
      },
    ],
    primary: ["Milestone delivery trend", "اتجاه تسليم المعالم"],
    insight: [
      "Atlas has an unresolved supplier dependency: delivery is 11 days late and the next milestone is due in 6 days.",
      "لدى أطلس تبعية مورد غير محلولة: التسليم متأخر ١١ يومًا والمعلم التالي بعد ٦ أيام.",
    ],
  },
  operations: {
    icon: GitBranch,
    title: ["Process intelligence", "ذكاء العمليات"],
    kicker: ["Waiting, rework & flow", "الانتظار وإعادة العمل والتدفق"],
    description: [
      "Analyze event-derived process paths and inspect the permitted event trace behind each variant.",
      "حلل مسارات العملية المستخرجة من الأحداث وافحص أثر الأحداث المسموح لكل مسار.",
    ],
    kpis: [
      {
        label: ["Cases completed", "حالات مكتملة"],
        value: "5,884",
        delta: "+8.2%",
      },
      {
        label: ["Median throughput", "وسيط زمن الإنجاز"],
        value: "23.6 h",
        delta: "+3.7 h",
        tone: "warn",
      },
      {
        label: ["Waiting share", "حصة الانتظار"],
        value: "78%",
        delta: "18.4 h",
      },
      {
        label: ["Rework rate", "نسبة إعادة العمل"],
        value: "11.2%",
        delta: "+1.8 pp",
        tone: "warn",
      },
    ],
    primary: ["Case flow variants", "مسارات تدفق الحالات"],
    insight: [
      "Approval waiting—not hands-on processing—accounts for most elapsed time. 614 cases repeat validation after a return step.",
      "انتظار الموافقة، لا المعالجة الفعلية، يمثل معظم الزمن. ٦١٤ حالة أعادت التحقق بعد الإرجاع.",
    ],
  },
  finance: {
    icon: CircleDollarSign,
    title: ["Costs & budgets", "التكاليف والموازنات"],
    kicker: ["Variance with meaning", "فروق ذات معنى"],
    description: [
      "Keep recognized expense, commitments, invoices, and cash movements distinct.",
      "افصل المصروف المعترف به والالتزامات والفواتير والحركة النقدية.",
    ],
    kpis: [
      {
        label: ["Actual expense", "المصروف الفعلي"],
        value: "JOD 768k",
        delta: "+2.8%",
      },
      {
        label: ["Approved budget", "الموازنة المعتمدة"],
        value: "JOD 804k",
        delta: "95.5% used",
      },
      {
        label: ["Open commitments", "التزامات مفتوحة"],
        value: "JOD 116k",
        delta: "not actual",
      },
      {
        label: ["Unexplained variance", "فرق غير مفسر"],
        value: "JOD 7.4k",
        delta: "review",
        tone: "warn",
      },
    ],
    primary: [
      "Actual, budget, and commitments",
      "الفعلي والموازنة والالتزامات",
    ],
    insight: [
      "Contractor expense is JOD 34k above budget. Open commitments would raise exposure, but are not counted as recognized expense.",
      "مصروف المتعاقدين أعلى من الموازنة بـ٣٤ ألف د.أ. الالتزامات المفتوحة ترفع الانكشاف لكنها ليست مصروفًا معترفًا به.",
    ],
  },
  support: {
    icon: Headphones,
    title: ["Support & suppliers", "الدعم والموردون"],
    kicker: ["Demand & downstream exposure", "الطلب والانكشاف اللاحق"],
    description: [
      "Connect service demand, SLA policy, supplier deliveries, and affected projects.",
      "اربط طلب الخدمة وسياسة SLA وتسليمات الموردين والمشاريع المتأثرة.",
    ],
    kpis: [
      {
        label: ["Open cases", "حالات مفتوحة"],
        value: "284",
        delta: "+31%",
        tone: "warn",
      },
      {
        label: ["SLA achieved", "تحقق SLA"],
        value: "84.6%",
        delta: "−5.4 pp",
        tone: "warn",
      },
      {
        label: ["Supplier on-time", "المورد في الموعد"],
        value: "88.1%",
        delta: "−2.0 pp",
      },
      {
        label: ["Exposed projects", "مشاريع منكشفة"],
        value: "3",
        delta: "1 critical",
      },
    ],
    primary: ["Demand vs staffed capacity", "الطلب مقابل طاقة التغطية"],
    insight: [
      "Weekend arrivals exceed staffed capacity by 31%. Northstar’s late delivery is linked to Atlas; the link is operational evidence, not causation.",
      "الوارد في نهاية الأسبوع أعلى من طاقة التغطية بـ٣١٪. تأخر نورث ستار مرتبط بأطلس؛ الرابط دليل تشغيلي وليس سببية.",
    ],
  },
  objectives: {
    icon: Goal,
    title: ["Objectives", "الأهداف"],
    kicker: ["Strategy to evidence", "من الاستراتيجية إلى الدليل"],
    description: [
      "Connect approved goals to KPI versions, owners, targets, and review dates.",
      "اربط الأهداف المعتمدة بإصدارات المؤشرات والمالكين والمستهدفات ومواعيد المراجعة.",
    ],
    kpis: [
      {
        label: ["Active objectives", "أهداف نشطة"],
        value: "12",
        delta: "7 on track",
      },
      {
        label: ["At risk", "معرّضة للخطر"],
        value: "3",
        delta: "review",
        tone: "warn",
      },
      {
        label: ["Missing evidence", "دليل مفقود"],
        value: "2",
        delta: "not zero",
      },
      {
        label: ["Reviews due", "مراجعات مستحقة"],
        value: "4",
        delta: "next 14d",
      },
    ],
    primary: [
      "Objective progress by evidence status",
      "تقدم الأهداف حسب حالة الدليل",
    ],
    insight: [
      "Weekend SLA has a target but no approved current-period result. It remains “missing evidence,” not 0% progress.",
      "لـSLA نهاية الأسبوع مستهدف لكن لا توجد نتيجة معتمدة للفترة. يبقى «الدليل مفقودًا» وليس تقدمًا ٠٪.",
    ],
  },
};

export function CompanyModuleScreen({
  locale,
  module,
  workspace,
}: {
  locale: Locale;
  module: ModuleId;
  workspace?: string;
}) {
  const ar = locale === "ar";
  const config = configs[module];
  const Icon = config.icon;
  const [evidence, setEvidence] = useState<EvidenceRecord | null>(null);
  const [selectedRow, setSelectedRow] = useState(0);
  if (workspace === "denied")
    return (
      <ResourceState
        locale={locale}
        status="denied"
        reason={
          ar
            ? "نطاق إدارتك لا يسمح بعرض حقول الأفراد المقيّدة."
            : "Your department scope does not permit restricted people fields."
        }
        correlationId="req_scope_demo_403"
      />
    );
  const rows = moduleRows[module];
  const evidenceRecord: EvidenceRecord = {
    metricId: `${module}_primary`,
    resultId: `result_demo_${module}_01`,
    definition: config.primary[ar ? 1 : 0],
    scope: ar
      ? "كل الإدارات · يناير–يونيو ٢٠٢٦"
      : "All departments · Jan–Jun 2026",
    source: `${module}_snapshot · demo-v1`,
    freshness: ar ? "تاريخ العرض ٣٠ يونيو ٢٠٢٦" : "Reporting date 30 Jun 2026",
  };
  const trend = [
    { label: "Jan", value: 68, comparison: 64 },
    { label: "Feb", value: 72, comparison: 67 },
    { label: "Mar", value: 74, comparison: 70 },
    { label: "Apr", value: 81, comparison: 71 },
    { label: "May", value: 92, comparison: 75 },
    { label: "Jun", value: 88, comparison: 77 },
  ];
  return (
    <div className="module-page">
      <header className="module-hero">
        <div className="module-title">
          <span>
            <Icon />
          </span>
          <div>
            <p className="eyebrow">{config.kicker[ar ? 1 : 0]}</p>
            <h1>{config.title[ar ? 1 : 0]}</h1>
            <p>{config.description[ar ? 1 : 0]}</p>
          </div>
        </div>
        <div className="module-actions">
          <button className="button button--secondary">
            {ar ? "تصفية" : "Filter"}
          </button>
          <button className="button button--primary">
            {ar ? "اسأل عن الوحدة" : "Ask about module"}
            <ArrowRight />
          </button>
        </div>
      </header>
      {workspace === "demo" ? (
        <div className="truth-banner">
          <CircleAlert size={17} />
          {ar
            ? "بيانات شركة خيالية · لقطة ثابتة بتاريخ ٣٠ يونيو ٢٠٢٦."
            : "Fictional company data · fixed snapshot dated 30 Jun 2026."}
        </div>
      ) : null}
      <section
        className="module-kpis"
        aria-label={ar ? "مؤشرات الوحدة" : "Module indicators"}
      >
        {config.kpis.map((kpi, index) => (
          <button
            key={kpi.label[0]}
            className="module-kpi"
            onClick={() =>
              setEvidence({
                ...evidenceRecord,
                metricId: `${module}_kpi_${index}`,
                definition: kpi.label[ar ? 1 : 0],
              })
            }
          >
            <span>{kpi.label[ar ? 1 : 0]}</span>
            <strong>
              <bdi>{kpi.value}</bdi>
            </strong>
            <small className={kpi.tone === "warn" ? "warning-text" : ""}>
              <bdi>{kpi.delta}</bdi>
            </small>
            <Eye size={15} aria-hidden="true" />
          </button>
        ))}
      </section>
      {module === "operations" ? (
        <ProcessMap locale={locale} />
      ) : (
        <div className="module-primary">
          <ChartPanel
            locale={locale}
            title={config.primary[ar ? 1 : 0]}
            description={
              ar
                ? "ستة أشهر؛ المقارنة بالفترة السابقة."
                : "Six months; compared with the previous period."
            }
            data={trend}
            unit={
              module === "finance" || module === "customers" ? "k JOD" : "%"
            }
            source={`result_demo_${module}_01`}
            onPointSelect={() => setEvidence(evidenceRecord)}
          />
          <aside className="module-insight">
            <p className="eyebrow">
              {ar ? "ما يستحق المراجعة" : "Worth reviewing"}
            </p>
            <h2>{ar ? "خلاصة مرتبطة بالدليل" : "Evidence-linked brief"}</h2>
            <p>{config.insight[ar ? 1 : 0]}</p>
            <button
              className="button button--ghost"
              onClick={() => setEvidence(evidenceRecord)}
            >
              {ar ? "افحص النتيجة" : "Inspect result"}
              <ChevronRight />
            </button>
          </aside>
        </div>
      )}
      <section className="records-panel">
        <header className="panel-heading">
          <div>
            <p className="eyebrow">{ar ? "تفصيل مسموح" : "Permitted detail"}</p>
            <h2>{ar ? "السجلات ذات الصلة" : "Related records"}</h2>
          </div>
          <span className="badge">
            {rows.length} {ar ? "من ٢٥" : "of 25"}
          </span>
        </header>
        <div className="table-scroll" tabIndex={0}>
          <table>
            <thead>
              <tr>
                {Object.keys(rows[0]).map((key) => (
                  <th key={key}>{key}</th>
                ))}
                <th>
                  <span className="sr-only">{ar ? "فتح" : "Open"}</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row, index) => (
                <tr
                  key={index}
                  className={selectedRow === index ? "selected" : ""}
                >
                  {Object.values(row).map((value, cell) => (
                    <td key={cell}>
                      <bdi>{value}</bdi>
                    </td>
                  ))}
                  <td>
                    <button
                      className="icon-button"
                      aria-label={
                        ar
                          ? `افتح السجل ${index + 1}`
                          : `Open record ${index + 1}`
                      }
                      onClick={() => setSelectedRow(index)}
                    >
                      <ChevronRight />
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      {module === "projects" ? <ThreeVariableExplorer locale={locale} /> : null}
      <EvidenceDrawer
        locale={locale}
        evidence={evidence}
        open={Boolean(evidence)}
        onClose={() => setEvidence(null)}
      />
    </div>
  );
}

function ProcessMap({ locale }: { locale: Locale }) {
  const ar = locale === "ar";
  const [selected, setSelected] = useState("approve");
  const [table, setTable] = useState(false);
  const nodes = [
    {
      id: "receive",
      label: ar ? "استلام" : "Receive",
      count: 5884,
      wait: "0.2 h",
    },
    {
      id: "validate",
      label: ar ? "تحقق" : "Validate",
      count: 5731,
      wait: "4.8 h",
    },
    {
      id: "approve",
      label: ar ? "موافقة" : "Approve",
      count: 5214,
      wait: "14.6 h",
    },
    {
      id: "complete",
      label: ar ? "إكمال" : "Complete",
      count: 4907,
      wait: "0.4 h",
    },
  ];
  const item = nodes.find((node) => node.id === selected)!;
  return (
    <section className="process-panel">
      <header className="panel-heading">
        <div>
          <p className="eyebrow">
            {ar
              ? "٥٬٨٨٤ حالة · ٩٤٪ تغطية أحداث"
              : "5,884 cases · 94% event coverage"}
          </p>
          <h2>{ar ? "مسار الطلب إلى الموافقة" : "Request-to-approval flow"}</h2>
        </div>
        <button
          className="button button--ghost button--small"
          onClick={() => setTable((value) => !value)}
        >
          {table ? <Network /> : <Table2 />}
          {table
            ? ar
              ? "الخريطة"
              : "Map"
            : ar
              ? "الجدول البديل"
              : "Table alternative"}
        </button>
      </header>
      {table ? (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>{ar ? "النشاط" : "Activity"}</th>
                <th>{ar ? "الحالات" : "Cases"}</th>
                <th>{ar ? "الانتظار الوسيط" : "Median wait"}</th>
              </tr>
            </thead>
            <tbody>
              {nodes.map((node) => (
                <tr key={node.id}>
                  <th>{node.label}</th>
                  <td>{node.count}</td>
                  <td>{node.wait}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div
          className="process-map"
          role="img"
          aria-label={
            ar
              ? "مسار من الاستلام إلى التحقق ثم الموافقة والإكمال"
              : "Flow from receive to validate to approve to complete"
          }
        >
          {nodes.map((node, index) => (
            <div key={node.id} className="process-step">
              <button
                className={selected === node.id ? "selected" : ""}
                onClick={() => setSelected(node.id)}
                aria-pressed={selected === node.id}
              >
                <span>{index + 1}</span>
                <b>{node.label}</b>
                <small>{node.count.toLocaleString()}</small>
              </button>
              {index < nodes.length - 1 ? (
                <span className="process-edge">
                  <i />
                  {index === 1 ? (
                    <em>{ar ? "٦١٤ إعادة" : "614 rework"}</em>
                  ) : null}
                </span>
              ) : null}
            </div>
          ))}
        </div>
      )}
      <aside className="process-detail">
        <span className="process-detail__icon">
          <Clock3 />
        </span>
        <div>
          <p className="eyebrow">
            {ar ? "الخطوة المحددة" : "Selected activity"}
          </p>
          <h3>{item.label}</h3>
          <p>
            {ar
              ? `وسيط الانتظار ${item.wait}. السجل يعتمد على أحداث لها وقت ومصدر ومعرّف حالة.`
              : `Median wait ${item.wait}. The result uses timestamped events with source and case IDs.`}
          </p>
        </div>
        <button className="button button--secondary">
          {ar ? "افتح أثر حدث" : "Inspect event trace"}
        </button>
      </aside>
    </section>
  );
}

function ThreeVariableExplorer({ locale }: { locale: Locale }) {
  const ar = locale === "ar";
  const [angle, setAngle] = useState(22);
  const [table, setTable] = useState(false);
  const [selected, setSelected] = useState("Atlas rollout");
  const points = [
    { name: "Atlas rollout", x: 78, y: 92, z: 88 },
    { name: "Service hub", x: 64, y: 71, z: 54 },
    { name: "Ledger renewal", x: 42, y: 49, z: 28 },
    { name: "North region setup", x: 86, y: 82, z: 74 },
  ];
  const projected = (point: (typeof points)[number]) => {
    const radians = (angle * Math.PI) / 180;
    return {
      left: 8 + point.x * 0.72 + Math.cos(radians) * point.z * 0.18,
      top: 84 - point.y * 0.65 - Math.sin(radians) * point.z * 0.2,
    };
  };
  return (
    <section className="explorer-3d">
      <header className="panel-heading">
        <div>
          <p className="eyebrow">
            {ar ? "استكشاف ثلاثي المتغيرات" : "Three-variable exploration"}
          </p>
          <h2>
            {ar
              ? "مخاطر المشروع: التقدم، استهلاك الموازنة، والتبعية"
              : "Project exposure: progress, budget, and dependency"}
          </h2>
          <p>
            {ar
              ? "منظور استكشافي؛ لا يُستخدم للمقارنة الدقيقة دون الجدول البديل."
              : "Exploratory perspective; use the table alternative for exact comparison."}
          </p>
        </div>
        <button
          className="button button--ghost"
          onClick={() => setTable((value) => !value)}
        >
          {table ? <Boxes /> : <Table2 />}
          {table
            ? ar
              ? "عرض ثلاثي"
              : "3D view"
            : ar
              ? "جدول دقيق"
              : "Exact table"}
        </button>
      </header>
      {table ? (
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>{ar ? "المشروع" : "Project"}</th>
                <th>{ar ? "التقدم %" : "Progress %"}</th>
                <th>{ar ? "الموازنة %" : "Budget %"}</th>
                <th>{ar ? "مخاطر التبعية" : "Dependency risk"}</th>
              </tr>
            </thead>
            <tbody>
              {points.map((point) => (
                <tr key={point.name}>
                  <th>{point.name}</th>
                  <td>{point.x}</td>
                  <td>{point.y}</td>
                  <td>{point.z}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="three-d-stage">
          <div className="axis axis--x">{ar ? "التقدم" : "Progress"}</div>
          <div className="axis axis--y">{ar ? "الموازنة" : "Budget"}</div>
          <div className="axis axis--z">{ar ? "التبعية" : "Dependency"}</div>
          {points.map((point) => {
            const pos = projected(point);
            return (
              <button
                key={point.name}
                className={
                  selected === point.name ? "point-3d selected" : "point-3d"
                }
                style={{
                  insetInlineStart: `${pos.left}%`,
                  insetBlockStart: `${pos.top}%`,
                  inlineSize: `${18 + point.z * 0.18}px`,
                  blockSize: `${18 + point.z * 0.18}px`,
                }}
                onClick={() => setSelected(point.name)}
                aria-label={`${point.name}: progress ${point.x}%, budget ${point.y}%, dependency risk ${point.z}`}
              >
                <span>{point.name}</span>
              </button>
            );
          })}
        </div>
      )}
      <div className="explorer-controls">
        <label htmlFor="view-angle">
          {ar ? "زاوية العرض" : "View angle"}
          <input
            id="view-angle"
            type="range"
            min="0"
            max="60"
            value={angle}
            onChange={(e) => setAngle(Number(e.target.value))}
          />
          <output>{angle}°</output>
        </label>
        <button
          className="button button--secondary button--small"
          onClick={() => setAngle(22)}
        >
          <RotateCcw />
          {ar ? "إعادة العرض" : "Reset view"}
        </button>
        <p>
          <b>{selected}</b> ·{" "}
          {ar
            ? "التحديد يغيّر التفاصيل دون تغيير النتيجة الأصلية."
            : "Selection changes detail, not the source result."}
        </p>
      </div>
    </section>
  );
}

export type { ModuleId };
