"use client";

import { Fragment, useCallback, useEffect, useRef, useState } from "react";
import {
  BadgeCheck,
  MessageSquare,
  Plus,
  Send,
  TriangleAlert,
} from "lucide-react";
import type { Locale } from "@/lib/contracts";
import {
  ACTIVE,
  analystApi,
  loc,
  mergeRun,
  type AgentRun,
  type EvidenceItem,
  type QuestionResult,
  type TeamMember,
} from "@/lib/analyst";
import { AgentChart } from "./agent-chart";
import { LiveRun } from "./live-run";
import { AgentAvatar } from "./team";

const SUGGESTIONS = {
  en: [
    "Summarize this dataset in five points",
    "What drives the main KPI, and by how much?",
    "Forecast the next 6 months",
    "Why did it change compared with the same quarter last year?",
    "Which records look like errors?",
    "Show the top 10 by the main KPI",
  ],
  ar: [
    "لخّص هذه البيانات في خمس نقاط",
    "ما العوامل التي تحرّك المؤشر الرئيسي وبأي مقدار؟",
    "توقع الأشهر الستة القادمة",
    "لماذا تغيّر مقارنة بالربع نفسه من العام الماضي؟",
    "ما السجلات التي تبدو أخطاء؟",
    "اعرض أعلى 10 حسب المؤشر الرئيسي",
  ],
};

interface Thread {
  id: string;
  title: string;
  turns: number;
  updated_at: string | null;
}

export function AskTheTeam({
  versionId,
  locale,
  team,
  seed,
  onSeedConsumed,
}: {
  versionId: string;
  locale: Locale;
  team: TeamMember[];
  seed?: string | null;
  onSeedConsumed?: () => void;
}) {
  const ar = locale === "ar";
  const [threads, setThreads] = useState<Thread[]>([]);
  const [threadId, setThreadId] = useState<string | null>(null);
  const [turns, setTurns] = useState<AgentRun[]>([]);
  const [draft, setDraft] = useState("");
  const [error, setError] = useState("");
  const members = Object.fromEntries(team.map((m) => [m.id, m]));
  const chief = members.chief;
  const bottom = useRef<HTMLDivElement>(null);

  const refreshThreads = useCallback(async () => {
    try {
      setThreads((await analystApi.threads(versionId)).items);
    } catch {
      /* The thread list is a convenience; the conversation still works without it. */
    }
  }, [versionId]);

  useEffect(() => {
    setThreadId(null);
    setTurns([]);
    void refreshThreads();
  }, [versionId, refreshThreads]);

  async function openThread(id: string) {
    setThreadId(id);
    setError("");
    try {
      const list = await analystApi.runs({
        thread_id: id,
        dataset_version_id: versionId,
        limit: "30",
      });
      const ordered = [...list.items].reverse();
      setTurns(
        await Promise.all(ordered.map((item) => analystApi.run(item.id))),
      );
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : String(cause));
    }
  }

  const pending = turns.find((turn) => ACTIVE.includes(turn.status));

  useEffect(() => {
    if (!pending) return;
    let stopped = false;
    const timer = window.setInterval(async () => {
      try {
        const since = pending.events.length;
        const next = await analystApi.run(pending.id, since);
        if (stopped) return;
        setTurns((current) =>
          current.map((turn) =>
            turn.id === next.id ? mergeRun(turn, next, since) : turn,
          ),
        );
        if (!ACTIVE.includes(next.status)) void refreshThreads();
      } catch {
        /* Keep polling; a transient failure should not end the conversation. */
      }
    }, 1100);
    return () => {
      stopped = true;
      window.clearInterval(timer);
    };
  }, [pending, refreshThreads]);

  useEffect(() => {
    bottom.current?.scrollIntoView?.({ behavior: "smooth", block: "end" });
  }, [turns.length, pending?.events.length]);

  const ask = useCallback(
    async (question: string) => {
      const text = question.trim();
      if (!text || pending) return;
      setDraft("");
      setError("");
      try {
        const run = await analystApi.startRun({
          dataset_version_id: versionId,
          mode: "question",
          locale,
          question: text,
          thread_id: threadId,
        });
        if (!threadId && run.thread_id) setThreadId(run.thread_id);
        setTurns((current) => [...current, run]);
        if (!ACTIVE.includes(run.status)) void refreshThreads();
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : String(cause));
      }
    },
    [pending, versionId, locale, threadId, refreshThreads],
  );

  useEffect(() => {
    if (seed) {
      void ask(seed);
      onSeedConsumed?.();
    }
  }, [seed, ask, onSeedConsumed]);

  return (
    <div className="ask-layout">
      <aside
        className="thread-list"
        aria-label={ar ? "المحادثات" : "Conversations"}
      >
        <button
          type="button"
          className="button button--secondary"
          onClick={() => {
            setThreadId(null);
            setTurns([]);
          }}
        >
          <Plus size={15} aria-hidden="true" />
          {ar ? "محادثة جديدة" : "New conversation"}
        </button>
        <ul>
          {threads.map((thread) => (
            <li key={thread.id}>
              <button
                type="button"
                className={thread.id === threadId ? "active" : undefined}
                onClick={() => void openThread(thread.id)}
              >
                <MessageSquare size={14} aria-hidden="true" />
                <span>{thread.title}</span>
                <small>{thread.turns}</small>
              </button>
            </li>
          ))}
        </ul>
      </aside>
      <section
        className="conversation"
        aria-label={ar ? "اسأل فريق المحللين" : "Ask the analyst team"}
      >
        {!turns.length ? (
          <div className="conversation__empty">
            <AgentAvatar member={chief} size={48} />
            <h3>
              {ar
                ? "اسأل فريقك أي سؤال عن هذه البيانات"
                : "Ask your team anything about this data"}
            </h3>
            <p className="muted">
              {ar
                ? "يخطط كبير المحللين، ويكلّف المختصين بالحساب، ثم يجيب مع الدليل. كل رقم محسوب ومتحقق منه."
                : "The chief analyst plans, delegates the calculations to specialists, then answers with evidence. Every figure is computed and checked."}
            </p>
            <div className="suggestions">
              {SUGGESTIONS[locale].map((text) => (
                <button
                  key={text}
                  type="button"
                  className="question-chip"
                  onClick={() => void ask(text)}
                >
                  {text}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <div className="turns">
            {turns.map((turn) => (
              <Turn
                key={turn.id}
                turn={turn}
                locale={locale}
                team={team}
                chief={chief}
              />
            ))}
            <div ref={bottom} />
          </div>
        )}
        {error ? (
          <p className="truth-banner" role="alert">
            {error}
          </p>
        ) : null}
        <form
          className="composer"
          onSubmit={(event) => {
            event.preventDefault();
            void ask(draft);
          }}
        >
          <label htmlFor="ask-input" className="sr-only">
            {ar ? "سؤالك" : "Your question"}
          </label>
          <textarea
            id="ask-input"
            value={draft}
            rows={2}
            maxLength={4000}
            placeholder={
              ar
                ? "مثال: لماذا انخفضت الإيرادات في الربع الأخير؟ ماذا لو خفّضنا الخصم 10%؟"
                : "e.g. Why did revenue drop last quarter? What if we cut the discount by 10%?"
            }
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey) {
                event.preventDefault();
                void ask(draft);
              }
            }}
          />
          <button
            type="submit"
            className="button button--primary"
            disabled={!draft.trim() || Boolean(pending)}
          >
            <Send size={16} aria-hidden="true" />
            {ar ? "اسأل" : "Ask"}
          </button>
        </form>
      </section>
    </div>
  );
}

function Turn({
  turn,
  locale,
  team,
  chief,
}: {
  turn: AgentRun;
  locale: Locale;
  team: TeamMember[];
  chief: TeamMember | undefined;
}) {
  const ar = locale === "ar";
  const result = turn.result as QuestionResult | null | undefined;
  const [selected, setSelected] = useState<string | null>(null);
  const evidence = result?.evidence ?? [];
  const byId = Object.fromEntries(evidence.map((item) => [item.id, item]));
  const active = ACTIVE.includes(turn.status);
  const charted = evidence.filter((item) => item.result?.chart);
  const shown = selected ? byId[selected] : charted[0];
  return (
    <div className="turn">
      <div className="bubble bubble--user">
        <p>{turn.question}</p>
      </div>
      <div className="bubble bubble--team">
        <div className="bubble__who">
          <AgentAvatar member={chief} size={28} />
          <strong>{chief ? loc(chief.name, locale) : "Chief"}</strong>
          {result ? (
            <VerificationBadge result={result} locale={locale} />
          ) : null}
        </div>
        {active ? (
          <LiveRun run={turn} team={team} locale={locale} compact />
        ) : turn.status === "completed" && result ? (
          <>
            <RichAnswer
              text={result.answer}
              onCite={setSelected}
              available={new Set(Object.keys(byId))}
            />
            {shown?.result?.chart ? (
              <div className="turn__evidence">
                <AgentChart
                  spec={shown.result.chart as never}
                  locale={locale}
                  source={`${shown.id} · ${loc(shown.title, locale)}`}
                />
              </div>
            ) : null}
            {evidence.length ? (
              <div
                className="citations"
                aria-label={ar ? "الأدلة" : "Evidence"}
              >
                {evidence.map((item: EvidenceItem) => (
                  <button
                    type="button"
                    key={item.id}
                    className={`chip${shown?.id === item.id ? " chip--active" : ""}`}
                    onClick={() => setSelected(item.id)}
                  >
                    {item.id} · {loc(item.title, locale)}
                  </button>
                ))}
              </div>
            ) : null}
            <p className="muted small">
              {result.engine.provider === "deterministic"
                ? ar
                  ? "أجاب المحرك الخبير المدمج"
                  : "Answered by the built-in expert engine"
                : `${result.engine.provider} · ${result.engine.model ?? ""}`}{" "}
              · {result.generated_in_seconds}
              {ar ? " ث" : "s"}
            </p>
          </>
        ) : (
          <p className="truth-banner">
            {turn.error?.message ??
              (ar ? "تعذّرت الإجابة." : "No answer was produced.")}
          </p>
        )}
      </div>
    </div>
  );
}

function VerificationBadge({
  result,
  locale,
}: {
  result: QuestionResult;
  locale: Locale;
}) {
  const ar = locale === "ar";
  if (result.verification.mode === "deterministic") return null;
  return result.verification.unverified.length ? (
    <span
      className="pill pill--red"
      title={result.verification.unverified.join(", ")}
    >
      <TriangleAlert size={13} aria-hidden="true" />
      {ar ? "أرقام غير متحقق منها" : "Unverified figures"}:{" "}
      {result.verification.unverified.join(", ")}
    </span>
  ) : (
    <span className="pill pill--green">
      <BadgeCheck size={13} aria-hidden="true" />
      {ar ? "الأرقام متحقق منها" : "Figures verified"}
    </span>
  );
}

/** Minimal, safe rendering: paragraphs, bullets, **bold** and [ev-N] citations. */
function RichAnswer({
  text,
  onCite,
  available,
}: {
  text: string;
  onCite: (id: string) => void;
  available: Set<string>;
}) {
  const blocks = text.split(/\n{2,}/);
  return (
    <div className="rich-answer">
      {blocks.map((block, index) => {
        const lines = block.split("\n").filter((line) => line.trim());
        const bulleted =
          lines.length > 1 &&
          lines.slice(1).every((line) => /^\s*([-•*]|\d+[.)])\s+/.test(line));
        if (
          lines.length &&
          lines.every((line) => /^\s*([-•*]|\d+[.)])\s+/.test(line))
        )
          return (
            <ul key={index}>
              {lines.map((line, i) => (
                <li key={i}>
                  {inline(
                    line.replace(/^\s*([-•*]|\d+[.)])\s+/, ""),
                    onCite,
                    available,
                  )}
                </li>
              ))}
            </ul>
          );
        if (bulleted)
          return (
            <Fragment key={index}>
              <p>{inline(lines[0], onCite, available)}</p>
              <ul>
                {lines.slice(1).map((line, i) => (
                  <li key={i}>
                    {inline(
                      line.replace(/^\s*([-•*]|\d+[.)])\s+/, ""),
                      onCite,
                      available,
                    )}
                  </li>
                ))}
              </ul>
            </Fragment>
          );
        return (
          <p key={index}>
            {lines.map((line, i) => (
              <Fragment key={i}>
                {i ? <br /> : null}
                {inline(line.replace(/^#+\s*/, ""), onCite, available)}
              </Fragment>
            ))}
          </p>
        );
      })}
    </div>
  );
}

function inline(
  text: string,
  onCite: (id: string) => void,
  available: Set<string>,
) {
  const parts = text.split(/(\*\*[^*]+\*\*|\[ev-\d+\])/g);
  return parts.map((part, index) => {
    const cite = /^\[(ev-\d+)\]$/.exec(part);
    if (cite)
      return available.has(cite[1]) ? (
        <button
          key={index}
          type="button"
          className="cite"
          onClick={() => onCite(cite[1])}
        >
          {cite[1]}
        </button>
      ) : (
        <span key={index} className="cite cite--missing">
          {cite[1]}
        </span>
      );
    if (part.startsWith("**") && part.endsWith("**"))
      return <strong key={index}>{part.slice(2, -2)}</strong>;
    return <Fragment key={index}>{part}</Fragment>;
  });
}
