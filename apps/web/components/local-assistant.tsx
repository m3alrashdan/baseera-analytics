"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import {
  Bot,
  FilePlus2,
  MessageSquareText,
  Send,
  Square,
  UserRound,
  Save,
} from "lucide-react";
import type { Locale, SessionContext } from "@/lib/contracts";
import { apiRequest, postJson, resourceStatusFromError } from "@/lib/api";
import { ResourceState } from "./resource-state";

type Result = {
  result_id: string;
  metric_id: string;
  status: string;
  value?: number | null;
  unit?: string;
  warnings?: string[];
  evidence: {
    source?: string;
    input_hash: string;
    scope?: Record<string, unknown>;
  };
};
type Provider = {
  mode: string;
  model?: string;
  status?: string;
  elapsed_seconds?: number;
  live_verified?: boolean;
};
type Reply = {
  conversation_id: string;
  answer: string;
  status: string;
  results: Result[];
  provider: Provider;
  plan: Record<string, unknown>;
};
type Message = {
  role: "user" | "assistant";
  text: string;
  results?: Result[];
  rerun?: boolean;
};
type Conversation = { id: string; title: string; created_at: string };

export function AssistantScreen({
  locale,
}: {
  locale: Locale;
  workspace?: string;
}) {
  const ar = locale === "ar";
  const [context, setContext] = useState<SessionContext | null>(null);
  const [provider, setProvider] = useState<Provider | null>(null);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [conversationId, setConversationId] = useState<string>();
  const [messages, setMessages] = useState<Message[]>([]);
  const [question, setQuestion] = useState("");
  const [plan, setPlan] = useState<Record<string, unknown> | null>(null);
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<unknown>(null);
  const [notice, setNotice] = useState("");
  const [savedReport, setSavedReport] = useState<string>();
  const active = useRef<AbortController | null>(null);
  const latestMessage = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      apiRequest<SessionContext>("/api/v1/auth/context", {
        signal: controller.signal,
      }),
      apiRequest<Provider>("/api/v1/assistant/status", {
        signal: controller.signal,
      }),
      apiRequest<{ items: Conversation[] }>("/api/v1/conversations", {
        signal: controller.signal,
      }),
    ])
      .then(([session, status, history]) => {
        if (!controller.signal.aborted) {
          setContext(session);
          setProvider(status);
          setConversations(history.items);
        }
      })
      .catch((error) => {
        if (!controller.signal.aborted) setProblem(error);
      });
    return () => {
      controller.abort();
      active.current?.abort();
    };
  }, []);
  useEffect(() => {
    latestMessage.current?.scrollIntoView?.({ block: "nearest" });
  }, [messages, busy]);

  function freshConversation() {
    if (busy) return;
    setConversationId(undefined);
    setMessages([]);
    setQuestion("");
    setPlan(null);
    setProblem(null);
    setNotice("");
    setSavedReport(undefined);
  }
  async function openConversation(id: string) {
    if (busy) return;
    setBusy(true);
    setProblem(null);
    setMessages([]);
    setPlan(null);
    setSavedReport(undefined);
    const controller = new AbortController();
    active.current = controller;
    try {
      const history = await apiRequest<{
        items: {
          role: Message["role"];
          content: string;
          rerun_required: boolean;
        }[];
      }>(`/api/v1/conversations/${encodeURIComponent(id)}`, {
        signal: controller.signal,
      });
      if (controller.signal.aborted) return;
      setConversationId(id);
      setMessages(
        history.items.map((row) => ({
          role: row.role,
          text:
            row.rerun_required && ar
              ? "تحليل محفوظ. أعد السؤال للتحقق من صلاحياتك والبيانات الحالية."
              : row.content,
          rerun: row.rerun_required,
        })),
      );
    } catch (error) {
      if (!controller.signal.aborted) setProblem(error);
    } finally {
      if (active.current === controller) {
        setBusy(false);
        active.current = null;
      }
    }
  }
  async function send() {
    const text = question.trim();
    if (!text || busy) return;
    setMessages((all) => [...all, { role: "user", text }]);
    setQuestion("");
    setProblem(null);
    setNotice("");
    setSavedReport(undefined);
    setBusy(true);
    const controller = new AbortController();
    active.current = controller;
    try {
      const response = await apiRequest<Reply>("/api/v1/assistant/query", {
        method: "POST",
        body: JSON.stringify({
          question: text,
          locale,
          ...(conversationId ? { conversation_id: conversationId } : {}),
        }),
        signal: controller.signal,
      });
      if (controller.signal.aborted) return;
      setProvider(response.provider);
      setConversationId(response.conversation_id);
      setPlan(response.plan);
      setMessages((all) => [
        ...all,
        { role: "assistant", text: response.answer, results: response.results },
      ]);
      setConversations((all) =>
        all.some((item) => item.id === response.conversation_id)
          ? all
          : [
              {
                id: response.conversation_id,
                title: text.slice(0, 160),
                created_at: new Date().toISOString(),
              },
              ...all,
            ],
      );
    } catch (error) {
      if (!controller.signal.aborted) {
        setProblem(error);
        setQuestion(text);
      }
    } finally {
      if (active.current === controller) {
        active.current = null;
        setBusy(false);
      }
    }
  }
  function cancelWaiting() {
    active.current?.abort();
    setNotice(
      ar
        ? "أُلغي انتظار الرد. قد يكون الخادم ما زال يكمل الطلب؛ راجع سجل المحادثات قبل إعادة الإرسال."
        : "Stopped waiting. The server may still finish this request; check conversation history before retrying.",
    );
  }
  async function preserve(result: Result) {
    setProblem(null);
    setSavedReport(undefined);
    try {
      const report = await postJson<{ id: string }>("/api/v1/reports", {
        title: `${result.metric_id} · ${ar ? "دليل التحليل" : "Analysis evidence"}`,
        language: locale,
        sections: [{ type: "metric", result_id: result.result_id }],
      });
      setSavedReport(report.id);
    } catch (error) {
      setProblem(error);
    }
  }
  const suggestions = ar
    ? [
        "ما هي الإيرادات هذا الشهر؟",
        "اعرض عدد حالات الدعم ومتوسط وقت الحل",
        "توقع حجم حالات الدعم للأشهر الستة القادمة",
      ]
    : [
        "What is net revenue this month?",
        "Show support case count and average resolution time",
        "Forecast support volume for the next six months",
      ];

  return (
    <div className="assistant-page">
      <aside className="conversation-rail">
        <header>
          <div>
            <p className="eyebrow">{ar ? "المحادثات" : "Conversations"}</p>
            <h2>{ar ? "سجل التحليل" : "Analysis history"}</h2>
          </div>
          <button
            className="icon-button"
            disabled={busy}
            onClick={freshConversation}
            aria-label={ar ? "محادثة جديدة" : "New conversation"}
          >
            <FilePlus2 />
          </button>
        </header>
        {!conversations.length ? (
          <p className="muted">
            {ar
              ? "ستظهر محادثاتك المحفوظة هنا."
              : "Your saved conversations will appear here."}
          </p>
        ) : (
          conversations.map((item) => (
            <button
              key={item.id}
              disabled={busy}
              className={`conversation-item${item.id === conversationId ? " active" : ""}`}
              onClick={() => openConversation(item.id)}
            >
              <span>
                <MessageSquareText />
              </span>
              <div>
                <b>{item.title}</b>
                <small>
                  {new Date(item.created_at).toLocaleDateString(
                    ar ? "ar-JO" : "en",
                  )}
                </small>
              </div>
            </button>
          ))
        )}
      </aside>
      <section className="conversation-main">
        <header className="assistant-header">
          <div>
            <span className="assistant-avatar">
              <Bot />
            </span>
            <div>
              <p className="eyebrow">BASEERA · LOCAL AI</p>
              <h1>{ar ? "المستشار التحليلي" : "Analytics consultant"}</h1>
            </div>
          </div>
        </header>
        <div className="truth-banner">
          {ar
            ? "يفهم النموذج السؤال محليًا؛ تحسب أدوات معتمدة الأرقام ضمن صلاحياتك. راجع النطاق والدليل مع كل نتيجة."
            : "The local model interprets your question; approved tools calculate results within your access. Review each result’s scope and evidence."}
        </div>
        <div className="messages" aria-live="polite">
          {!messages.length ? (
            <article className="message message--assistant">
              <span className="message-avatar">
                <Bot />
              </span>
              <div>
                <p>
                  {ar
                    ? "ابدأ بسؤال محدد عن المؤشر والفترة. لا تُرسل سجلات شركتك الخام إلى النموذج."
                    : "Start with a metric and period. Raw company records are not sent to the model."}
                </p>
              </div>
            </article>
          ) : null}
          {messages.map((message, index) => (
            <article key={index} className={`message message--${message.role}`}>
              <span className="message-avatar">
                {message.role === "assistant" ? <Bot /> : <UserRound />}
              </span>
              <div>
                <p style={{ whiteSpace: "pre-wrap" }}>{message.text}</p>
                {message.rerun ? (
                  <button
                    className="button button--secondary button--small"
                    onClick={() => setQuestion(messages[index - 1]?.text ?? "")}
                  >
                    {ar ? "أعد استخدام السؤال" : "Reuse question"}
                  </button>
                ) : null}
                {message.results?.map((result) => (
                  <details className="assistant-result" key={result.result_id}>
                    <summary>
                      {result.metric_id} ·{" "}
                      {result.status === "completed"
                        ? ar
                          ? "محسوب"
                          : "Calculated"
                        : ar
                          ? "راجع القيود"
                          : "Review limitations"}
                    </summary>
                    <dl className="compact-dl">
                      <div>
                        <dt>{ar ? "المصدر" : "Source"}</dt>
                        <dd>{result.evidence.source}</dd>
                      </div>
                      <div>
                        <dt>{ar ? "معرّف النتيجة" : "Result ID"}</dt>
                        <dd>
                          <bdi>{result.result_id}</bdi>
                        </dd>
                      </div>
                    </dl>
                    <pre className="evidence-json" dir="ltr">
                      {JSON.stringify(result.evidence, null, 2)}
                    </pre>
                    {result.warnings?.map((warning) => (
                      <p key={warning}>{warning}</p>
                    ))}
                    <button
                      className="button button--secondary button--small"
                      onClick={() => preserve(result)}
                    >
                      <Save size={14} />
                      {ar ? "احفظ كتقرير" : "Save as report"}
                    </button>
                  </details>
                ))}
              </div>
            </article>
          ))}
          {busy ? (
            <div className="execution-status" role="status">
              <span className="pulse-dot" />
              <div>
                <b>{ar ? "جارٍ تنفيذ الطلب…" : "Processing request…"}</b>
                <small>
                  {ar
                    ? "قد يستغرق النموذج المحلي عدة دقائق حسب ضغط الجهاز."
                    : "The local model may take a few minutes depending on device load."}
                </small>
              </div>
            </div>
          ) : null}
          {problem ? (
            <ResourceState
              locale={locale}
              status={resourceStatusFromError(problem)}
              compact
              reason={
                problem instanceof Error ? problem.message : String(problem)
              }
            />
          ) : null}
          {notice ? <p role="status">{notice}</p> : null}
          {savedReport ? (
            <p role="status">
              {ar ? "حُفظ التقرير بالدليل." : "Report saved with evidence."}{" "}
              <Link href={`/${locale}/reports`}>
                {ar ? "افتح التقارير" : "Open reports"}
              </Link>
            </p>
          ) : null}
          <div ref={latestMessage} />
        </div>
        <div className="prompt-suggestions">
          {suggestions.map((prompt) => (
            <button
              disabled={busy}
              key={prompt}
              onClick={() => setQuestion(prompt)}
            >
              {prompt}
            </button>
          ))}
        </div>
        <form
          className="composer"
          onSubmit={(event) => {
            event.preventDefault();
            void send();
          }}
        >
          <label htmlFor="assistant-question" className="sr-only">
            {ar ? "اكتب سؤالك" : "Type your question"}
          </label>
          <textarea
            id="assistant-question"
            rows={3}
            maxLength={8000}
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder={
              ar ? "اسأل عن مؤشرات الشركة…" : "Ask about company metrics…"
            }
          />
          <div className="composer-foot">
            <Link href={`/${locale}/explore`}>
              {ar ? "تحليل مباشر دون نموذج" : "Direct analysis without AI"}
            </Link>
            {busy ? (
              <button
                type="button"
                className="button button--danger"
                onClick={cancelWaiting}
              >
                <Square size={14} />
                {ar ? "إلغاء الانتظار" : "Stop waiting"}
              </button>
            ) : (
              <button
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
        <p className="eyebrow">{ar ? "السياق الفعلي" : "Live context"}</p>
        <h2>{ar ? "نطاق التنفيذ" : "Execution scope"}</h2>
        <dl className="compact-dl">
          <div>
            <dt>{ar ? "النموذج" : "Model"}</dt>
            <dd>
              <bdi>{provider?.model ?? "—"}</bdi>
            </dd>
          </div>
          <div>
            <dt>{ar ? "الحالة" : "Status"}</dt>
            <dd>{provider?.status ?? "—"}</dd>
          </div>
          <div>
            <dt>{ar ? "مدة التخطيط الأخير" : "Last planning duration"}</dt>
            <dd>
              {provider?.elapsed_seconds != null
                ? `${provider.elapsed_seconds.toFixed(1)} s`
                : "—"}
            </dd>
          </div>
          <div>
            <dt>{ar ? "الصلاحية" : "Access"}</dt>
            <dd>{context?.membership.role ?? "—"}</dd>
          </div>
          <div>
            <dt>{ar ? "الإدارات" : "Departments"}</dt>
            <dd>
              {context?.membership.role === "department_manager"
                ? context.membership.department_ids.join(" · ") ||
                  (ar ? "لا توجد إدارات مصرح بها" : "No authorized departments")
                : context
                  ? ar
                    ? "ضمن صلاحيات المؤسسة"
                    : "Authorized organization scope"
                  : "—"}
            </dd>
          </div>
          <div>
            <dt>{ar ? "مرجع الفترات النسبية" : "Relative-date reference"}</dt>
            <dd>
              <bdi>{context?.tenant.reporting_date ?? "—"}</bdi>
            </dd>
          </div>
        </dl>
        {plan ? (
          <details>
            <summary>{ar ? "خطة الطلب الأخير" : "Last request plan"}</summary>
            <pre className="evidence-json" dir="ltr">
              {JSON.stringify(plan, null, 2)}
            </pre>
          </details>
        ) : null}
      </aside>
    </div>
  );
}
