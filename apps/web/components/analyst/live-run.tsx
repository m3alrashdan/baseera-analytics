"use client";

import { useEffect, useMemo, useRef } from "react";
import { LoaderCircle, Square } from "lucide-react";
import type { Locale } from "@/lib/contracts";
import {
  ACTIVE,
  loc,
  type AgentEvent,
  type AgentRun,
  type TeamMember,
} from "@/lib/analyst";
import { AgentAvatar, EVENT_ICONS, agentStates } from "./team";

const STATE_LABEL = {
  idle: { en: "Waiting", ar: "بالانتظار" },
  working: { en: "Working", ar: "يعمل الآن" },
  done: { en: "Done", ar: "أنجز" },
};

export function LiveRun({
  run,
  team,
  locale,
  onCancel,
  compact = false,
}: {
  run: AgentRun;
  team: TeamMember[];
  locale: Locale;
  onCancel?: () => void;
  compact?: boolean;
}) {
  const ar = locale === "ar";
  const active = ACTIVE.includes(run.status);
  const states = useMemo(
    () => agentStates(team, run.events, active),
    [team, run.events, active],
  );
  const byId = useMemo(
    () => Object.fromEntries(team.map((m) => [m.id, m])),
    [team],
  );
  const plan = run.events.find((event) => event.type === "plan");
  const planned = (
    (plan?.detail?.steps as Array<{ agent: string; applicable: boolean }>) ?? []
  )
    .filter((step) => step.applicable)
    .map((step) => step.agent);
  const started = new Set(run.events.map((event) => event.agent));
  const progress =
    run.status === "completed"
      ? 1
      : planned.length
        ? Math.min(
            0.95,
            planned.filter((agent) => started.has(agent)).length /
              (planned.length + 1),
          )
        : Math.min(0.9, run.events.length / 60);
  const log = useRef<HTMLOListElement>(null);
  useEffect(() => {
    const node = log.current;
    if (node) node.scrollTop = node.scrollHeight;
  }, [run.events.length]);
  const latest = run.events[run.events.length - 1];
  const findings = run.events.filter(
    (event) => event.type === "finding",
  ).length;

  return (
    <section
      className={`live-run${compact ? " live-run--compact" : ""}`}
      aria-labelledby={`live-${run.id}`}
    >
      <header className="live-run__head">
        <div>
          <p className="eyebrow">
            {ar ? "غرفة عمليات الفريق" : "Team war room"}
          </p>
          <h2 id={`live-${run.id}`}>
            {active ? (
              <>
                <LoaderCircle className="spin" size={18} aria-hidden="true" />{" "}
                {ar
                  ? "الفريق يعمل على بياناتك"
                  : "The team is working on your data"}
              </>
            ) : run.status === "completed" ? (
              ar ? (
                "اكتمل العمل"
              ) : (
                "Work complete"
              )
            ) : run.status === "cancelled" ? (
              ar ? (
                "أُوقف التحليل"
              ) : (
                "Analysis stopped"
              )
            ) : ar ? (
              "تعذّر إكمال التحليل"
            ) : (
              "The analysis could not finish"
            )}
          </h2>
          <p className="live-run__meta">
            <span>
              {ar ? "المدة" : "Elapsed"}: {run.elapsed_seconds ?? 0}
              {ar ? " ث" : "s"}
            </span>
            <span>
              {ar ? "النتائج" : "Findings"}: {findings}
            </span>
            <span>
              {ar ? "الخطوات" : "Steps"}: {run.events_total}
            </span>
          </p>
        </div>
        {active && onCancel ? (
          <button
            type="button"
            className="button button--secondary"
            onClick={onCancel}
          >
            <Square size={15} aria-hidden="true" />
            {ar ? "إيقاف" : "Stop"}
          </button>
        ) : null}
      </header>
      <div
        className="live-run__progress"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(progress * 100)}
        aria-label={ar ? "تقدم الفريق" : "Team progress"}
      >
        <span style={{ width: `${Math.round(progress * 100)}%` }} />
      </div>
      {!compact ? (
        <ul
          className="team-grid"
          aria-label={ar ? "أعضاء الفريق" : "Team members"}
        >
          {team.map((member) => (
            <li key={member.id} className={`team-card is-${states[member.id]}`}>
              <AgentAvatar member={member} state={states[member.id]} />
              <div>
                <strong>{loc(member.name, locale)}</strong>
                <small>
                  {STATE_LABEL[states[member.id] ?? "idle"][locale]}
                </small>
              </div>
            </li>
          ))}
        </ul>
      ) : null}
      <ol
        className="event-log"
        ref={log}
        aria-label={ar ? "سجل عمل الفريق" : "Team activity log"}
      >
        {run.events.map((event, index) => (
          <EventRow
            key={index}
            event={event}
            member={byId[event.agent]}
            locale={locale}
          />
        ))}
      </ol>
      <p className="sr-only" aria-live="polite">
        {latest ? loc(latest.title, locale) : ""}
      </p>
      {run.error ? (
        <p className="truth-banner" role="alert">
          {run.error.message}
        </p>
      ) : null}
    </section>
  );
}

function EventRow({
  event,
  member,
  locale,
}: {
  event: AgentEvent;
  member: TeamMember | undefined;
  locale: Locale;
}) {
  const Icon = EVENT_ICONS[event.type] ?? EVENT_ICONS.status;
  const summary = event.detail?.summary as
    | { en?: string; ar?: string }
    | undefined;
  const steps =
    event.type === "plan"
      ? (event.detail?.steps as Array<{
          agent: string;
          task: { en: string; ar: string };
          applicable: boolean;
        }>)
      : null;
  return (
    <li className={`event event--${event.type}`}>
      <AgentAvatar member={member} size={26} />
      <div className="event__body">
        <p>
          <strong>{member ? loc(member.name, locale) : event.agent}</strong>
          <Icon size={13} aria-hidden="true" className="event__icon" />
          <span>{loc(event.title, locale)}</span>
          <time>{event.t.toFixed(1)}s</time>
        </p>
        {summary && (summary[locale] || summary.en) ? (
          <p className="event__summary">{summary[locale] ?? summary.en}</p>
        ) : null}
        {steps ? (
          <ul className="event__plan">
            {steps.map((step) => (
              <li
                key={step.agent}
                className={step.applicable ? undefined : "is-skipped"}
              >
                {loc(step.task, locale)}
              </li>
            ))}
          </ul>
        ) : null}
      </div>
    </li>
  );
}
