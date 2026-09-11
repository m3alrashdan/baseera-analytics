"use client";

import { useRef, useState } from "react";
import {
  BarChart3,
  Bot,
  Check,
  ChevronDown,
  CircleAlert,
  FilePlus2,
  Filter,
  MessageSquareText,
  Pin,
  Play,
  RotateCcw,
  Send,
  SlidersHorizontal,
  Sparkles,
  Square,
  Table2,
  UserRound,
  X,
} from "lucide-react";
import type { Locale } from "@/lib/contracts";
import { apiRequest } from "@/lib/api";
import { ChartPanel } from "./chart-panel";
import { EvidenceDrawer, type EvidenceRecord } from "./evidence-drawer";
import { ResourceState } from "./resource-state";

const analysisData = [
  { label: "Jan", value: 278000, comparison: 249000 },
  { label: "Feb", value: 291000, comparison: 260000 },
  { label: "Mar", value: 304000, comparison: 271000 },
  { label: "Apr", value: 315000, comparison: 278000 },
  { label: "May", value: 343000, comparison: 291000 },
  { label: "Jun", value: 311500, comparison: 290000 },
];

export function AnalysisWorkspace({
  locale,
  workspace,
}: {
  locale: Locale;
  workspace?: string;
}) {
  const ar = locale === "ar";
  const [metric, setMetric] = useState("revenue_net");
  const [dimension, setDimension] = useState("month");
  const [chart, setChart] = useState<"line" | "bar">("line");
  const [filter, setFilter] = useState("All departments");
  const [evidence, setEvidence] = useState<EvidenceRecord | null>(null);
  const [notice, setNotice] = useState("");
  const evidenceRecord: EvidenceRecord = {
    metricId: metric,
    resultId: "result_demo_rev_17",
    definition: ar
      ? "إيرادات الفواتير ناقص المبالغ المستردة المعتمدة."
      : "Invoiced revenue less approved refunds.",
    scope: `${filter} · Jan–Jun 2026 · ${dimension}`,
    source: "ERP invoices · v17",
    freshness: ar ? "تاريخ العرض ٣٠ يونيو ٢٠٢٦" : "Reporting date 30 Jun 2026",
    warning: ar ? "يونيو فترة غير مكتملة." : "June is an incomplete period.",
  };
  return (
    <div className="analysis-workspace">
      <header className="page-header">
        <div>
          <p className="eyebrow">
            {ar ? "مساحة تحقيق" : "Investigation workspace"}
          </p>
          <h1>
            {ar
              ? "حلّل سؤالًا، ثم ثبّت النتيجة"
              : "Analyze a question, then pin the finding"}
          </h1>
          <p>
            {ar
              ? "كل تغيير يعيد طلب نتيجة مرتبطة بالتعريف والنطاق والإصدار."
              : "Every change requests a result bound to definition, scope, and version."}
          </p>
        </div>
        <div className="action-row">
          <button
            className="button button--secondary"
            onClick={() => {
              setMetric("revenue_net");
              setDimension("month");
              setChart("line");
              setFilter("All departments");
            }}
          >
            <RotateCcw size={16} />
            {ar ? "إعادة الضبط" : "Reset"}
          </button>
          <button
            className="button button--primary"
            onClick={() =>
              setNotice(
                ar
                  ? "تم إنشاء مسودة عنصر لوحة؛ يلزم حفظها في API."
                  : "Dashboard widget draft created; API persistence is required.",
              )
            }
          >
            <Pin size={16} />
            {ar ? "ثبّت في لوحة" : "Pin to dashboard"}
          </button>
        </div>
      </header>
      {workspace === "demo" ? (
        <div className="truth-banner">
          <CircleAlert size={17} />
          {ar
            ? "تحليل مجموعة نماء الخيالية · لقطة ٣٠ يونيو ٢٠٢٦."
            : "Analysis of fictional Namaa data · snapshot dated 30 Jun 2026."}
        </div>
      ) : null}
      {notice ? (
        <div role="status" className="success-message">
          <Check size={17} />
          {notice}
          <button
            className="icon-button"
            aria-label={ar ? "إغلاق" : "Dismiss"}
            onClick={() => setNotice("")}
          >
            <X />
          </button>
        </div>
      ) : null}
      <section
        className="analysis-controls"
        aria-label={ar ? "عناصر تكوين التحليل" : "Analysis controls"}
      >
        <label>
          <span>{ar ? "المؤشر" : "Metric"}</span>
          <select value={metric} onChange={(e) => setMetric(e.target.value)}>
            <option value="revenue_net">
              {ar ? "صافي الإيرادات" : "Net revenue"}
            </option>
            <option value="gross_margin">
              {ar ? "هامش الربح الإجمالي" : "Gross margin"}
            </option>
            <option value="support_open">
              {ar ? "حالات الدعم المفتوحة" : "Open support cases"}
            </option>
          </select>
        </label>
        <label>
          <span>{ar ? "التقسيم" : "Dimension"}</span>
          <select
            value={dimension}
            onChange={(e) => setDimension(e.target.value)}
          >
            <option value="month">{ar ? "الشهر" : "Month"}</option>
            <option value="department">{ar ? "الإدارة" : "Department"}</option>
            <option value="service">{ar ? "خط الخدمة" : "Service line"}</option>
          </select>
        </label>
        <label>
          <span>{ar ? "النطاق" : "Scope"}</span>
          <select value={filter} onChange={(e) => setFilter(e.target.value)}>
            <option>All departments</option>
            <option>Customer operations</option>
            <option>Delivery</option>
          </select>
        </label>
        <div className="control-toggle">
          <span>{ar ? "العرض" : "View"}</span>
          <div>
            <button
              aria-pressed={chart === "line"}
              onClick={() => setChart("line")}
              aria-label={ar ? "رسم خطي" : "Line chart"}
            >
              <BarChart3 />
            </button>
            <button
              aria-pressed={chart === "bar"}
              onClick={() => setChart("bar")}
              aria-label={ar ? "رسم أعمدة" : "Bar chart"}
            >
              <Table2 />
            </button>
          </div>
        </div>
      </section>
      <div className="investigation-grid">
        <div className="analysis-canvas">
          <ChartPanel
            locale={locale}
            kind={chart}
            title={
              metric === "revenue_net"
                ? ar
                  ? "اتجاه صافي الإيرادات"
                  : "Net revenue trend"
                : metric === "gross_margin"
                  ? ar
                    ? "اتجاه الهامش"
                    : "Gross margin trend"
                  : ar
                    ? "ضغط الدعم"
                    : "Support pressure"
            }
            description={
              ar
                ? "الفترة الحالية مقابل الفترة السابقة؛ انقر نقطة لفحص نطاقها."
                : "Current versus previous period; select a point to inspect its scope."
            }
            data={analysisData}
            unit={
              metric === "gross_margin"
                ? "%"
                : metric === "support_open"
                  ? "cases"
                  : "JOD"
            }
            source="result_demo_rev_17 · ERP invoices v17"
            onPointSelect={(point) =>
              setEvidence({
                ...evidenceRecord,
                scope: `${point.label} · ${filter}`,
              })
            }
          />
          <div className="finding-strip">
            <span>
              <Sparkles />
            </span>
            <div>
              <p className="eyebrow">
                {ar ? "نتيجة حسابية" : "Calculated finding"}
              </p>
              <h2>
                {ar
                  ? "مايو قدّم أكبر مساهمة في نمو الفترة"
                  : "May contributed the largest share of period growth"}
              </h2>
              <p>
                {ar
                  ? "يمثل فرق مايو ٥٢ ألف د.أ من إجمالي فرق ١٤٣٫٥ ألف د.أ. هذا تفكيك مساهمة وليس تفسيرًا سببيًا."
                  : "May accounts for JOD 52k of the JOD 143.5k total difference. This is a contribution breakdown, not a causal explanation."}
              </p>
            </div>
            <button
              className="button button--ghost"
              onClick={() => setEvidence(evidenceRecord)}
            >
              {ar ? "الدليل" : "Evidence"}
            </button>
          </div>
        </div>
        <ContextAssistant locale={locale} />
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

function ContextAssistant({ locale }: { locale: Locale }) {
  const ar = locale === "ar";
  const [question, setQuestion] = useState("");
  const [reply, setReply] = useState("");
  return (
    <aside
      className="context-assistant"
      aria-labelledby="context-assistant-title"
    >
      <header>
        <span>
          <Bot />
        </span>
        <div>
          <p className="eyebrow">
            {ar ? "في سياق هذا التحليل" : "In this analysis context"}
          </p>
          <h2 id="context-assistant-title">
            {ar ? "اسأل عن النتيجة" : "Ask about the result"}
          </h2>
        </div>
      </header>
      <div className="suggested-prompts">
        <button
          onClick={() =>
            setQuestion(
              ar
                ? "ما الإدارات التي صنعت الفرق؟"
                : "Which departments drove the difference?",
            )
          }
        >
          {ar ? "قسّم حسب الإدارة" : "Break down by department"}
        </button>
        <button
          onClick={() =>
            setQuestion(
              ar
                ? "هل التغير خارج النمط الموسمي؟"
                : "Is the change outside the seasonal pattern?",
            )
          }
        >
          {ar ? "تحقق من الموسمية" : "Check seasonality"}
        </button>
      </div>
      {reply ? (
        <div className="mini-answer" role="status">
          <b>{ar ? "طلب جاهز للتنفيذ" : "Request ready to run"}</b>
          <p>{reply}</p>
          <small>
            {ar ? "لم يُنفذ حساب جديد بعد." : "No new calculation has run yet."}
          </small>
        </div>
      ) : (
        <div className="assistant-empty">
          <MessageSquareText />
          <p>
            {ar
              ? "يحمل السؤال تلقائيًا المؤشر والنطاق والفلاتر الحالية."
              : "Questions inherit the current metric, scope, and filters."}
          </p>
        </div>
      )}
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (question.trim()) {
            setReply(question);
            setQuestion("");
          }
        }}
      >
        <label className="sr-only" htmlFor="context-question">
          {ar ? "سؤال المتابعة" : "Follow-up question"}
        </label>
        <textarea
          id="context-question"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder={ar ? "اسأل سؤال متابعة…" : "Ask a follow-up…"}
          rows={3}
        />
        <button
          type="submit"
          className="icon-button"
          aria-label={ar ? "إرسال" : "Send"}
        >
          <Send />
        </button>
      </form>
    </aside>
  );
}

interface AssistantResponse {
  answer: string;
  result_id?: string;
  status?: string;
  evidence?: Array<{ title: string; detail: string }>;
  provider?: { mode: string; model?: string };
  results?: Array<{ id?: string; result_id?: string }>;
  conversation_id?: string;
}

export function AssistantScreen({
  locale,
  workspace,
}: {
  locale: Locale;
  workspace?: string;
}) {
  const ar = locale === "ar";
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<
    Array<{ role: "user" | "assistant"; text: string; resultId?: string }>
  >([
    {
      role: "assistant",
      text: ar
        ? "أنا جاهزة لتحليل النتائج المسموح بها. سأوضح ما هو ملاحظ أو محسوب أو متنبأ به، وأطلب توضيحًا عندما يغيّر الغموض الإجابة."
        : "I’m ready to analyze permitted results. I’ll label observations, calculations, and forecasts—and clarify ambiguity when it changes the answer.",
    },
  ]);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState("");
  const [scope, setScope] = useState(ar ? "كل الإدارات" : "All departments");
  const [provider, setProvider] = useState("");
  const [conversationId, setConversationId] = useState<string>();
  const abortRef = useRef<AbortController | null>(null);

  async function send() {
    const text = question.trim();
    if (!text || busy) return;
    setMessages((all) => [...all, { role: "user", text }]);
    setQuestion("");
    setProblem("");
    setBusy(true);
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      const response = await apiRequest<AssistantResponse>(
        "/api/v1/assistant/query",
        {
          method: "POST",
          body: JSON.stringify({
            question: text,
            locale,
            ...(conversationId ? { conversation_id: conversationId } : {}),
          }),
          headers: {
            "Content-Type": "application/json",
            "Idempotency-Key": crypto.randomUUID(),
          },
          signal: controller.signal,
        },
      );
      setProvider(
        response.provider
          ? `${response.provider.mode} · ${response.provider.model ?? ""}`
          : "",
      );
      setConversationId(response.conversation_id);
      setMessages((all) => [
        ...all,
        {
          role: "assistant",
          text: response.answer,
          resultId:
            response.result_id ??
            response.results?.[0]?.id ??
            response.results?.[0]?.result_id,
        },
      ]);
    } catch (error) {
      if ((error as Error).name !== "AbortError")
        setProblem(
          error instanceof Error
            ? error.message
            : ar
              ? "تعذر تنفيذ التحليل."
              : "The analysis could not run.",
        );
    } finally {
      setBusy(false);
      abortRef.current = null;
    }
  }

  return (
    <div className="assistant-page">
      {provider ? (
        <div className="assistant-provider" role="status">
          <Bot size={15} />
          <bdi>{provider}</bdi>
        </div>
      ) : null}
      <aside className="conversation-rail">
        <header>
          <div>
            <p className="eyebrow">{ar ? "المحادثات" : "Conversations"}</p>
            <h2>{ar ? "سجل التحليل" : "Analysis history"}</h2>
          </div>
          <button
            className="icon-button"
            aria-label={ar ? "محادثة جديدة" : "New conversation"}
            onClick={() => setMessages([])}
          >
            <FilePlus2 />
          </button>
        </header>
        <button className="conversation-item active">
          <span>
            <MessageSquareText />
          </span>
          <div>
            <b>
              {ar ? "ضغط الدعم وتأخير المشاريع" : "Support pressure & delays"}
            </b>
            <small>{ar ? "الآن · نطاق الشركة" : "Now · company scope"}</small>
          </div>
        </button>
        <button className="conversation-item">
          <span>
            <MessageSquareText />
          </span>
          <div>
            <b>{ar ? "تغير الهامش في الربع الثاني" : "Q2 margin movement"}</b>
            <small>{ar ? "أمس" : "Yesterday"}</small>
          </div>
        </button>
      </aside>
      <section className="conversation-main">
        <header className="assistant-header">
          <div>
            <span className="assistant-avatar">
              <Bot />
            </span>
            <div>
              <p className="eyebrow">BASEERA AI</p>
              <h1>{ar ? "المستشار التحليلي" : "Analytics consultant"}</h1>
            </div>
          </div>
          <label className="scope-select">
            <span>{ar ? "النطاق" : "Scope"}</span>
            <select value={scope} onChange={(e) => setScope(e.target.value)}>
              <option>{ar ? "كل الإدارات" : "All departments"}</option>
              <option>{ar ? "عمليات العملاء" : "Customer operations"}</option>
              <option>{ar ? "التنفيذ" : "Delivery"}</option>
            </select>
          </label>
        </header>
        {workspace === "demo" ? (
          <div className="truth-banner">
            <CircleAlert size={17} />
            {ar
              ? "مساحة خيالية. لا تُعرض إجابة مولدة إلا إذا نفذها مزود أو مسار أدوات متاح."
              : "Fictional workspace. No generated answer is shown unless an available provider or tool path executes it."}
          </div>
        ) : null}
        <div className="messages" aria-live="polite">
          {messages.map((message, index) => (
            <article key={index} className={`message message--${message.role}`}>
              <span className="message-avatar">
                {message.role === "assistant" ? <Bot /> : <UserRound />}
              </span>
              <div>
                <p>{message.text}</p>
                {message.resultId ? (
                  <footer>
                    <span className="badge badge--ready">
                      <Check size={13} />
                      {ar ? "نتيجة متحققة" : "Verified result"}
                    </span>
                    <bdi>{message.resultId}</bdi>
                  </footer>
                ) : null}
              </div>
            </article>
          ))}
          {busy ? (
            <article className="message message--assistant">
              <span className="message-avatar">
                <Bot />
              </span>
              <div className="execution-status" role="status">
                <span className="pulse-dot" />
                <div>
                  <b>
                    {ar
                      ? "ينفذ أدوات التحليل المسموح بها"
                      : "Running permitted analysis tools"}
                  </b>
                  <small>
                    {ar
                      ? "يمكنك الإلغاء؛ لا توجد نسبة تقدم مختلقة."
                      : "You can cancel; no fabricated progress percentage is shown."}
                  </small>
                </div>
              </div>
            </article>
          ) : null}
          {problem ? (
            <ResourceState
              locale={locale}
              status="unavailable"
              compact
              reason={`${problem} ${ar ? "تبقى اللوحات والحسابات الحتمية متاحة." : "Deterministic dashboards and calculations remain available."}`}
            />
          ) : null}
        </div>
        <div className="prompt-suggestions">
          {[
            ar
              ? "اعرض تأخير المشاريع وضغط الدعم هذا الشهر"
              : "Show project delays and support pressure this month",
            ar
              ? "قارن الإنفاق الفعلي بالموازنة"
              : "Compare actual spend against budget",
            ar
              ? "ما البيانات الناقصة لحساب الربح؟"
              : "What data is missing to calculate profit?",
          ].map((prompt) => (
            <button key={prompt} onClick={() => setQuestion(prompt)}>
              {prompt}
            </button>
          ))}
        </div>
        <form
          className="composer"
          onSubmit={(e) => {
            e.preventDefault();
            send();
          }}
        >
          <label className="sr-only" htmlFor="assistant-question">
            {ar ? "اكتب سؤالك" : "Type your question"}
          </label>
          <textarea
            id="assistant-question"
            rows={2}
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder={
              ar
                ? "اسأل عن الشركة أو البيانات أو القرار…"
                : "Ask about the company, data, or a decision…"
            }
          />
          <div className="composer-foot">
            <span>
              <SlidersHorizontal size={14} />
              {ar
                ? "يناير–يونيو ٢٠٢٦ · آسيا/عمّان"
                : "Jan–Jun 2026 · Asia/Amman"}
            </span>
            {busy ? (
              <button
                type="button"
                className="button button--danger button--small"
                onClick={() => abortRef.current?.abort()}
              >
                <Square size={13} />
                {ar ? "إيقاف" : "Stop"}
              </button>
            ) : (
              <button
                type="submit"
                className="button button--primary"
                disabled={!question.trim()}
              >
                <Send size={16} />
                {ar ? "تحليل" : "Analyze"}
              </button>
            )}
          </div>
        </form>
      </section>
      <aside className="assistant-evidence">
        <p className="eyebrow">{ar ? "السياق المرفق" : "Attached context"}</p>
        <h2>{ar ? "نطاق التنفيذ" : "Execution scope"}</h2>
        <dl className="compact-dl">
          <div>
            <dt>{ar ? "الفترة" : "Period"}</dt>
            <dd>{ar ? "يناير–يونيو ٢٠٢٦" : "Jan–Jun 2026"}</dd>
          </div>
          <div>
            <dt>{ar ? "النسخ" : "Versions"}</dt>
            <dd>
              <bdi>invoices v17 · support v9</bdi>
            </dd>
          </div>
          <div>
            <dt>{ar ? "الصلاحية" : "Access"}</dt>
            <dd>
              {ar ? "تنفيذي · كل الإدارات" : "Executive · all departments"}
            </dd>
          </div>
        </dl>
        <div className="guardrail-note">
          <ShieldIcon />
          <p>
            {ar
              ? "لن يرسل المستشار بيانات إلى مزود غير مهيأ أو يتجاوز نطاقك."
              : "The consultant will not send data to an unconfigured provider or exceed your scope."}
          </p>
        </div>
      </aside>
    </div>
  );
}

function ShieldIcon() {
  return (
    <span aria-hidden="true">
      <Bot size={18} />
    </span>
  );
}
