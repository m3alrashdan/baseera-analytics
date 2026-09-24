"use client";

import { useMemo, useState } from "react";
import {
  AlertTriangle,
  ArrowDownRight,
  ArrowUpRight,
  BadgeCheck,
  ChevronDown,
  Download,
  FileSpreadsheet,
  FileText,
  Lightbulb,
  ListChecks,
  MessageSquare,
  Presentation,
  RefreshCw,
  ShieldCheck,
} from "lucide-react";
import type { Locale } from "@/lib/contracts";
import {
  downloadExport,
  formatDelta,
  formatMetric,
  loc,
  type Dossier,
  type EvidenceItem,
  type Finding,
  type Recommendation,
  type TeamMember,
} from "@/lib/analyst";
import { AgentChart } from "./agent-chart";
import { AgentAvatar } from "./team";

type Tab = "summary" | "actions" | "findings" | "method";

const CONFIDENCE = {
  high: { en: "High confidence", ar: "ثقة عالية" },
  medium: { en: "Medium confidence", ar: "ثقة متوسطة" },
  low: { en: "Low confidence", ar: "ثقة منخفضة" },
};
const EFFORT = {
  low: { en: "Low effort", ar: "جهد منخفض" },
  medium: { en: "Medium effort", ar: "جهد متوسط" },
  high: { en: "High effort", ar: "جهد مرتفع" },
};
const HORIZON: Record<string, { en: string; ar: string }> = {
  "7_days": { en: "This week", ar: "هذا الأسبوع" },
  "30_days": { en: "30 days", ar: "30 يومًا" },
  "90_days": { en: "90 days", ar: "90 يومًا" },
};
const EXPORTS = [
  { format: "pdf", label: "PDF", icon: FileText },
  { format: "docx", label: "Word", icon: FileText },
  { format: "pptx", label: "PowerPoint", icon: Presentation },
  { format: "html", label: "HTML", icon: FileText },
  { format: "md", label: "Markdown", icon: FileText },
  { format: "json", label: "JSON", icon: FileSpreadsheet },
];

export function DossierView({
  dossier,
  runId,
  locale,
  team,
  onAsk,
  onRerun,
}: {
  dossier: Dossier;
  runId: string;
  locale: Locale;
  team: TeamMember[];
  onAsk: (question: string) => void;
  onRerun: () => void;
}) {
  const ar = locale === "ar";
  const [tab, setTab] = useState<Tab>("summary");
  const [focus, setFocus] = useState<string | null>(null);
  const [exporting, setExporting] = useState<string | null>(null);
  const [exportError, setExportError] = useState("");
  const [exportLocale, setExportLocale] = useState<Locale>(locale);
  const byId = useMemo(
    () => Object.fromEntries(dossier.findings.map((f) => [f.id, f])),
    [dossier],
  );
  const members = useMemo(
    () => Object.fromEntries(team.map((m) => [m.id, m])),
    [team],
  );
  const kpi = dossier.findings.find((f) => f.kind === "kpi");
  const summary = loc(dossier.executive_summary, locale);
  const headline = dossier.headline ? loc(dossier.headline, locale) : "";
  const p1 = dossier.recommendations.filter((r) => r.priority === "P1").length;

  async function exportAs(format: string) {
    setExporting(format);
    setExportError("");
    try {
      await downloadExport(runId, format, exportLocale);
    } catch (error) {
      setExportError(error instanceof Error ? error.message : String(error));
    } finally {
      setExporting(null);
    }
  }

  function openFinding(id: string) {
    setFocus(id);
    setTab("findings");
    requestAnimationFrame(() =>
      document
        .getElementById(`finding-${id}`)
        ?.scrollIntoView?.({ behavior: "smooth", block: "start" }),
    );
  }

  const tabs: Array<{ id: Tab; label: string; count?: number }> = [
    { id: "summary", label: ar ? "الملخص التنفيذي" : "Executive summary" },
    {
      id: "actions",
      label: ar ? "التوصيات" : "Recommendations",
      count: dossier.recommendations.length,
    },
    {
      id: "findings",
      label: ar ? "النتائج والأدلة" : "Findings & evidence",
      count: dossier.findings.length,
    },
    { id: "method", label: ar ? "المنهجية والتحقق" : "Method & verification" },
  ];

  return (
    <article
      className="dossier"
      aria-label={ar ? "تقرير التحليل" : "Analysis dossier"}
    >
      <header className="dossier__hero">
        <div className="dossier__hero-text">
          <p className="eyebrow">
            {dossier.dataset.name} ·{" "}
            {(dossier.dataset.rows ?? 0).toLocaleString(ar ? "ar-JO" : "en-US")}{" "}
            {ar ? "سجل" : "records"} · {ar ? "أُنجز خلال" : "completed in"}{" "}
            {dossier.generated_in_seconds}
            {ar ? " ث" : "s"}
          </p>
          <h2>
            {headline ||
              (ar ? "ما وجده فريق المحللين" : "What the analyst team found")}
          </h2>
          <div className="dossier__badges">
            <span className="pill pill--teal">
              <Lightbulb size={14} aria-hidden="true" />
              {dossier.stats.findings} {ar ? "نتيجة" : "findings"}
            </span>
            <span className="pill pill--amber">
              <ListChecks size={14} aria-hidden="true" />
              {p1} {ar ? "أولوية قصوى" : "top-priority actions"}
            </span>
            <VerificationPill dossier={dossier} locale={locale} />
            <EnginePill dossier={dossier} locale={locale} />
          </div>
        </div>
        <div className="dossier__actions">
          <div className="export-menu">
            <details>
              <summary className="button button--primary">
                <Download size={16} aria-hidden="true" />
                {exporting
                  ? ar
                    ? "جارٍ التصدير…"
                    : "Exporting…"
                  : ar
                    ? "تصدير التقرير"
                    : "Export report"}
                <ChevronDown size={14} aria-hidden="true" />
              </summary>
              <div className="export-menu__panel" role="menu">
                <div
                  className="ai-seg"
                  role="group"
                  aria-label={ar ? "لغة التقرير" : "Report language"}
                >
                  {(["ar", "en"] as Locale[]).map((value) => (
                    <button
                      key={value}
                      type="button"
                      aria-pressed={exportLocale === value}
                      onClick={() => setExportLocale(value)}
                    >
                      {value === "ar" ? "العربية" : "English"}
                    </button>
                  ))}
                </div>
                {EXPORTS.map(({ format, label, icon: Icon }) => (
                  <button
                    key={format}
                    type="button"
                    role="menuitem"
                    disabled={Boolean(exporting)}
                    onClick={() => void exportAs(format)}
                  >
                    <Icon size={15} aria-hidden="true" />
                    {label}
                  </button>
                ))}
              </div>
            </details>
          </div>
          <button
            type="button"
            className="button button--secondary"
            onClick={onRerun}
          >
            <RefreshCw size={15} aria-hidden="true" />
            {ar ? "أعد التحليل" : "Re-run"}
          </button>
        </div>
      </header>
      {exportError ? (
        <p className="truth-banner" role="alert">
          {exportError}
        </p>
      ) : null}
      <div
        className="tabs"
        role="tablist"
        aria-label={ar ? "أقسام التقرير" : "Dossier sections"}
      >
        {tabs.map((item) => (
          <button
            key={item.id}
            type="button"
            role="tab"
            aria-selected={tab === item.id}
            className={tab === item.id ? "active" : undefined}
            onClick={() => setTab(item.id)}
          >
            {item.label}
            {item.count != null ? (
              <span className="tabs__count">{item.count}</span>
            ) : null}
          </button>
        ))}
      </div>

      {tab === "summary" ? (
        <div className="dossier__panel" role="tabpanel">
          {kpi ? (
            <div className="kpi-strip">
              {kpi.metrics.slice(0, 6).map((metric, index) => (
                <div className="kpi-tile" key={index}>
                  <span>{loc(metric.label, locale)}</span>
                  <strong>{formatMetric(metric, locale)}</strong>
                  {metric.delta != null ? (
                    <small className={metric.delta >= 0 ? "up" : "down"}>
                      {metric.delta >= 0 ? (
                        <ArrowUpRight size={13} />
                      ) : (
                        <ArrowDownRight size={13} />
                      )}
                      {formatDelta(metric.delta, locale)}
                    </small>
                  ) : null}
                </div>
              ))}
            </div>
          ) : null}
          <section className="exec-summary">
            <h3>{ar ? "الملخص التنفيذي" : "Executive summary"}</h3>
            {summary.split("\n\n").map((block, index) => (
              <p key={index}>{block}</p>
            ))}
            {dossier.executive_summary.source === "model" ? (
              <p className="muted small">
                {ar
                  ? "صاغه كبير المحللين وتحقق المراجع الناقد من أرقامه مقابل الأدلة."
                  : "Written by the chief analyst; every figure checked against evidence by the reviewer."}
              </p>
            ) : null}
          </section>
          <section>
            <h3>{ar ? "أهم ما يجب معرفته" : "What matters most"}</h3>
            <div className="insight-grid">
              {dossier.key_insights.map((id) => {
                const finding = byId[id];
                if (!finding) return null;
                return (
                  <button
                    type="button"
                    key={id}
                    className="insight-card"
                    onClick={() => openFinding(id)}
                  >
                    <span className="insight-card__head">
                      <AgentAvatar member={members[finding.agent]} size={26} />
                      <span className={`conf conf--${finding.confidence}`}>
                        {CONFIDENCE[finding.confidence][locale]}
                      </span>
                    </span>
                    <strong>{loc(finding.title, locale)}</strong>
                    <span className="insight-card__text">
                      {loc(finding.so_what, locale) ||
                        firstSentence(loc(finding.summary, locale))}
                    </span>
                  </button>
                );
              })}
            </div>
          </section>
          <section className="two-col">
            <div>
              <h3>{ar ? "أولويات العمل" : "Priorities"}</h3>
              <ol className="priority-list">
                {dossier.recommendations.slice(0, 4).map((rec) => (
                  <li key={rec.id}>
                    <span
                      className={`badge badge--${rec.priority.toLowerCase()}`}
                    >
                      {rec.priority}
                    </span>
                    <button
                      type="button"
                      className="link-button"
                      onClick={() => setTab("actions")}
                    >
                      {loc(rec.title, locale)}
                    </button>
                  </li>
                ))}
              </ol>
            </div>
            <div>
              <h3>
                {ar ? "أسئلة تستحق المتابعة" : "Questions worth asking next"}
              </h3>
              <ul className="question-list">
                {dossier.next_questions.map((question, index) => (
                  <li key={index}>
                    <button
                      type="button"
                      className="question-chip"
                      onClick={() => onAsk(loc(question, locale))}
                    >
                      <MessageSquare size={14} aria-hidden="true" />
                      {loc(question, locale)}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          </section>
          {dossier.risks.length ? (
            <section className="risk-box">
              <h3>
                <AlertTriangle size={16} aria-hidden="true" />{" "}
                {ar ? "المخاطر والتحفظات" : "Risks and caveats"}
              </h3>
              <ul>
                {dossier.risks.map((risk, index) => (
                  <li key={index}>{loc(risk, locale)}</li>
                ))}
              </ul>
            </section>
          ) : null}
        </div>
      ) : null}

      {tab === "actions" ? (
        <div className="dossier__panel" role="tabpanel">
          <p className="muted">
            {ar
              ? "مرتبة حسب الأثر × الثقة. كل توصية مرتبطة بالنتائج التي بُنيت عليها."
              : "Ranked by impact × confidence. Every recommendation links to the findings it rests on."}
          </p>
          <div className="rec-list">
            {dossier.recommendations.map((rec) => (
              <RecommendationCard
                key={rec.id}
                rec={rec}
                locale={locale}
                findings={byId}
                onOpen={openFinding}
              />
            ))}
          </div>
        </div>
      ) : null}

      {tab === "findings" ? (
        <div className="dossier__panel" role="tabpanel">
          <nav
            className="section-chips"
            aria-label={ar ? "الأقسام" : "Sections"}
          >
            {dossier.sections.map((section) => (
              <a
                key={section.id}
                href={`#section-${section.id}`}
                className="chip"
              >
                {loc(section.title, locale)}{" "}
                <span>{section.findings.length}</span>
              </a>
            ))}
          </nav>
          {dossier.sections.map((section) => (
            <section
              key={section.id}
              id={`section-${section.id}`}
              className="finding-section"
            >
              <h3>{loc(section.title, locale)}</h3>
              {section.findings.map((id) =>
                byId[id] ? (
                  <FindingCard
                    key={id}
                    finding={byId[id]}
                    locale={locale}
                    member={members[byId[id].agent]}
                    evidence={
                      byId[id].evidence_id
                        ? dossier.evidence[byId[id].evidence_id as string]
                        : undefined
                    }
                    highlighted={focus === id}
                  />
                ) : null,
              )}
            </section>
          ))}
        </div>
      ) : null}

      {tab === "method" ? (
        <MethodPanel dossier={dossier} locale={locale} members={members} />
      ) : null}
    </article>
  );
}

function firstSentence(text: string): string {
  const match = /^(.{40,260}?[.!؟?])\s/.exec(text + " ");
  return match ? match[1] : text.slice(0, 220);
}

function VerificationPill({
  dossier,
  locale,
}: {
  dossier: Dossier;
  locale: Locale;
}) {
  const ar = locale === "ar";
  const verification = dossier.verification;
  if (verification.mode === "deterministic")
    return (
      <span className="pill pill--green">
        <ShieldCheck size={14} aria-hidden="true" />
        {ar
          ? "أرقام محسوبة وقابلة لإعادة الإنتاج"
          : "Computed, reproducible figures"}
      </span>
    );
  return verification.unverified.length ? (
    <span className="pill pill--red">
      <AlertTriangle size={14} aria-hidden="true" />
      {ar ? "أرقام تحتاج مراجعة" : "Figures to review"}:{" "}
      {verification.unverified.length}
    </span>
  ) : (
    <span className="pill pill--green">
      <BadgeCheck size={14} aria-hidden="true" />
      {ar ? "كل الأرقام متحقق منها" : "Every figure verified"} (
      {verification.numbers_checked})
    </span>
  );
}

function EnginePill({ dossier, locale }: { dossier: Dossier; locale: Locale }) {
  const ar = locale === "ar";
  const engine = dossier.engine;
  const name =
    engine.provider === "anthropic"
      ? `Claude · ${engine.model ?? ""}`
      : engine.provider === "ollama"
        ? `${ar ? "نموذج محلي" : "Local model"} · ${engine.model ?? ""}`
        : ar
          ? "المحرك الخبير المدمج"
          : "Built-in expert engine";
  return (
    <span
      className={`pill${engine.error ? " pill--amber" : ""}`}
      title={engine.error?.message}
    >
      {name}
      {engine.error
        ? ` · ${ar ? "تراجع للمحرك الخبير" : "fell back to expert engine"}`
        : ""}
    </span>
  );
}

function RecommendationCard({
  rec,
  locale,
  findings,
  onOpen,
}: {
  rec: Recommendation;
  locale: Locale;
  findings: Record<string, Finding>;
  onOpen: (id: string) => void;
}) {
  const ar = locale === "ar";
  const actions =
    rec.actions_model?.[locale] ??
    rec.actions.map((action) => loc(action, locale));
  return (
    <article className={`rec-card rec-card--${rec.priority.toLowerCase()}`}>
      <header>
        <span className={`badge badge--${rec.priority.toLowerCase()}`}>
          {rec.priority}
        </span>
        <h4>{loc(rec.title, locale)}</h4>
      </header>
      <p>{loc(rec.rationale, locale)}</p>
      <p className="rec-card__impact">
        <strong>{ar ? "الأثر المتوقع:" : "Expected impact:"}</strong>{" "}
        {loc(rec.expected_impact, locale)}
      </p>
      <ul className="rec-card__actions">
        {actions.map((action, index) => (
          <li key={index}>{action}</li>
        ))}
      </ul>
      <footer>
        <span className="chip">
          {EFFORT[rec.effort]?.[locale] ?? rec.effort}
        </span>
        <span className="chip">
          {HORIZON[rec.horizon]?.[locale] ?? rec.horizon}
        </span>
        {rec.kpis_to_track.filter(Boolean).map((kpi) => (
          <span className="chip chip--muted" key={kpi}>
            {ar ? "مؤشر المتابعة:" : "Track:"} {kpi}
          </span>
        ))}
        {rec.based_on.map((id) =>
          findings[id] ? (
            <button
              key={id}
              type="button"
              className="link-button small"
              onClick={() => onOpen(id)}
            >
              {ar ? "الدليل" : "Evidence"}: {loc(findings[id].title, locale)}
            </button>
          ) : null,
        )}
      </footer>
    </article>
  );
}

function FindingCard({
  finding,
  locale,
  member,
  evidence,
  highlighted,
}: {
  finding: Finding;
  locale: Locale;
  member: TeamMember | undefined;
  evidence: EvidenceItem | undefined;
  highlighted: boolean;
}) {
  const ar = locale === "ar";
  const [open, setOpen] = useState(false);
  const soWhat = loc(finding.so_what, locale);
  return (
    <article
      id={`finding-${finding.id}`}
      className={`finding-card${highlighted ? " is-highlighted" : ""}`}
    >
      <header>
        <AgentAvatar member={member} size={30} />
        <div>
          <small>{member ? loc(member.name, locale) : finding.agent}</small>
          <h4>{loc(finding.title, locale)}</h4>
        </div>
        <span className={`conf conf--${finding.confidence}`}>
          {CONFIDENCE[finding.confidence][locale]}
        </span>
      </header>
      {loc(finding.summary, locale)
        .split("\n")
        .filter(Boolean)
        .map((line, index) => (
          <p key={index} className="finding-card__text">
            {line}
          </p>
        ))}
      {soWhat ? (
        <p className="so-what">
          <strong>{ar ? "ماذا يعني ذلك؟" : "So what?"}</strong> {soWhat}
        </p>
      ) : null}
      {finding.metrics.length ? (
        <div className="metric-row">
          {finding.metrics.slice(0, 5).map((metric, index) => (
            <div key={index} className="metric-chip">
              <span>{loc(metric.label, locale)}</span>
              <strong>{formatMetric(metric, locale)}</strong>
              {metric.delta != null ? (
                <small>{formatDelta(metric.delta, locale)}</small>
              ) : null}
            </div>
          ))}
        </div>
      ) : null}
      {finding.details.length ? (
        <ul className="finding-card__details">
          {finding.details.slice(0, 8).map((detail, index) => (
            <li key={index}>{loc(detail, locale)}</li>
          ))}
        </ul>
      ) : null}
      {finding.chart ? (
        <AgentChart
          spec={finding.chart}
          locale={locale}
          source={evidence ? loc(evidence.title, locale) : undefined}
        />
      ) : null}
      {finding.caveats.length ? (
        <details className="caveats">
          <summary>
            <AlertTriangle size={14} aria-hidden="true" />
            {ar ? "تحفظات المراجع" : "Reviewer caveats"} (
            {finding.caveats.length})
          </summary>
          <ul>
            {finding.caveats.map((caveat, index) => (
              <li key={index}>{loc(caveat, locale)}</li>
            ))}
          </ul>
        </details>
      ) : null}
      {evidence ? (
        <div className="evidence-line">
          <button
            type="button"
            className="link-button small"
            onClick={() => setOpen((value) => !value)}
            aria-expanded={open}
          >
            {ar ? "كيف حُسبت؟" : "How was this computed?"} · {evidence.id}
          </button>
          {open ? <EvidenceDetail evidence={evidence} locale={locale} /> : null}
        </div>
      ) : null}
    </article>
  );
}

function EvidenceDetail({
  evidence,
  locale,
}: {
  evidence: EvidenceItem;
  locale: Locale;
}) {
  const ar = locale === "ar";
  const method = String(evidence.result?.method ?? "");
  return (
    <dl className="evidence-detail">
      <div>
        <dt>{ar ? "الأداة" : "Tool"}</dt>
        <dd>
          {loc(evidence.title, locale)} (<code>{evidence.tool}</code>)
        </dd>
      </div>
      {method ? (
        <div>
          <dt>{ar ? "الطريقة" : "Method"}</dt>
          <dd>
            <code>{method}</code>
          </dd>
        </div>
      ) : null}
      <div>
        <dt>{ar ? "المدخلات" : "Arguments"}</dt>
        <dd>
          <code>{JSON.stringify(evidence.arguments)}</code>
        </dd>
      </div>
      <div>
        <dt>{ar ? "زمن الحساب" : "Compute time"}</dt>
        <dd>{evidence.elapsed_seconds}s</dd>
      </div>
    </dl>
  );
}

function MethodPanel({
  dossier,
  locale,
  members,
}: {
  dossier: Dossier;
  locale: Locale;
  members: Record<string, TeamMember>;
}) {
  const ar = locale === "ar";
  const schema = dossier.schema as {
    columns_detail?: Array<{
      name: string;
      role: string;
      semantic_type: string;
      missing_rate: number;
      distinct_count: number;
    }>;
    time_column?: string | null;
    primary_kpi?: string | null;
    outcome?: string | null;
  };
  const health = dossier.health as {
    score?: number;
    issues?: Array<{ title: { en: string; ar: string }; severity: string }>;
    readiness?: { checks?: Record<string, boolean> };
  };
  const verification = dossier.verification;
  const roleLabel: Record<string, [string, string]> = {
    time: ["Time", "زمن"],
    measure: ["Measure", "مقياس"],
    dimension: ["Dimension", "بُعد"],
    entity: ["Entity", "كيان"],
    identifier: ["Identifier", "معرّف"],
    flag: ["Outcome flag", "مؤشر نتيجة"],
    text: ["Free text", "نص حر"],
    constant: ["Constant", "ثابت"],
    empty: ["Empty", "فارغ"],
  };
  return (
    <div className="dossier__panel method-panel" role="tabpanel">
      <section className="principles">
        <div>
          <ShieldCheck aria-hidden="true" />
          <p>
            <strong>{ar ? "أرقام حتمية" : "Deterministic figures"}</strong>
            {ar
              ? "كل رقم في هذا التقرير حسبته أداة إحصائية قابلة لإعادة الإنتاج، لا نموذج لغوي."
              : "Every figure here was computed by a reproducible statistical tool, not a language model."}
          </p>
        </div>
        <div>
          <BadgeCheck aria-hidden="true" />
          <p>
            <strong>{ar ? "تحقق من النص" : "Narrative verification"}</strong>
            {verification.mode === "deterministic"
              ? ar
                ? "السرد مولَّد من النتائج مباشرة."
                : "The narrative is generated directly from the results."
              : ar
                ? `تحقق المراجع من ${verification.numbers_checked} رقمًا؛ غير المتحقق منها: ${verification.unverified.join("، ") || "لا شيء"}.`
                : `The reviewer checked ${verification.numbers_checked} figures; unverified: ${verification.unverified.join(", ") || "none"}.`}
          </p>
        </div>
        <div>
          <Lightbulb aria-hidden="true" />
          <p>
            <strong>
              {ar ? "الارتباط ليس سببية" : "Association is not causation"}
            </strong>
            {ar
              ? "العوامل المؤثرة وسيناريوهات «ماذا لو» تُختبر بتجربة مضبوطة قبل القرارات الكبيرة."
              : "Drivers and what-if scenarios should be confirmed with a controlled test before large decisions."}
          </p>
        </div>
      </section>
      <section>
        <h3>{ar ? "كيف فهم الفريق بياناتك" : "How the team read your data"}</h3>
        <p className="muted">
          {ar ? "عمود الزمن" : "Time column"}:{" "}
          <b>{schema.time_column ?? "—"}</b> ·{" "}
          {ar ? "المؤشر الرئيسي" : "Primary KPI"}:{" "}
          <b>{schema.primary_kpi ?? "—"}</b> ·{" "}
          {ar ? "النتيجة المستهدفة" : "Outcome"}: <b>{schema.outcome ?? "—"}</b>{" "}
          · {ar ? "درجة الجودة" : "Quality score"}: <b>{health.score ?? "—"}</b>
        </p>
        <div className="table-scroll" tabIndex={0}>
          <table className="data-table">
            <thead>
              <tr>
                <th scope="col">{ar ? "العمود" : "Column"}</th>
                <th scope="col">{ar ? "الدور" : "Role"}</th>
                <th scope="col">{ar ? "النوع" : "Type"}</th>
                <th scope="col">{ar ? "القيم المختلفة" : "Distinct"}</th>
                <th scope="col">{ar ? "المفقود" : "Missing"}</th>
              </tr>
            </thead>
            <tbody>
              {(schema.columns_detail ?? []).map((column) => (
                <tr key={column.name}>
                  <th scope="row">{column.name}</th>
                  <td>{roleLabel[column.role]?.[ar ? 1 : 0] ?? column.role}</td>
                  <td>{column.semantic_type}</td>
                  <td className="numeric">
                    {column.distinct_count.toLocaleString(
                      ar ? "ar-JO" : "en-US",
                    )}
                  </td>
                  <td className="numeric">
                    {(column.missing_rate * 100).toFixed(1)}%
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      {health.issues?.length ? (
        <section>
          <h3>{ar ? "ملاحظات الجودة" : "Quality notes"}</h3>
          <ul>
            {health.issues.map((issue, index) => (
              <li key={index}>{loc(issue.title, locale)}</li>
            ))}
          </ul>
        </section>
      ) : null}
      <section>
        <h3>{ar ? "سجل الأدلة" : "Evidence register"}</h3>
        <div className="table-scroll" tabIndex={0}>
          <table className="data-table">
            <thead>
              <tr>
                <th scope="col">ID</th>
                <th scope="col">{ar ? "المختص" : "Specialist"}</th>
                <th scope="col">{ar ? "التحليل" : "Analysis"}</th>
                <th scope="col">{ar ? "الطريقة" : "Method"}</th>
              </tr>
            </thead>
            <tbody>
              {Object.values(dossier.evidence).map((item) => (
                <tr key={item.id}>
                  <th scope="row">{item.id}</th>
                  <td>
                    {members[item.agent]
                      ? loc(members[item.agent].name, locale)
                      : item.agent}
                  </td>
                  <td>{loc(item.title, locale)}</td>
                  <td>
                    <code>{String(item.result?.method ?? item.tool)}</code>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
