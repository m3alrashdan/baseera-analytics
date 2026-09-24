"use client";

import {
  AlertTriangle,
  BadgeCheck,
  Bot,
  Brain,
  CheckCircle2,
  CircleAlert,
  CircleDot,
  Database,
  FileText,
  Lightbulb,
  ListChecks,
  Network,
  Play,
  ScanSearch,
  ShieldCheck,
  Sigma,
  Target,
  TrendingUp,
  type LucideIcon,
} from "lucide-react";
import type { AgentEvent, TeamMember } from "@/lib/analyst";

export const AGENT_ICONS: Record<string, LucideIcon> = {
  brain: Brain,
  database: Database,
  sigma: Sigma,
  trending: TrendingUp,
  search: ScanSearch,
  network: Network,
  target: Target,
  shield: ShieldCheck,
  file: FileText,
};

export const EVENT_ICONS: Record<string, LucideIcon> = {
  status: CircleDot,
  plan: ListChecks,
  tool_call: Play,
  tool_result: CheckCircle2,
  tool_error: CircleAlert,
  finding: Lightbulb,
  warning: AlertTriangle,
  delegate: Bot,
  done: BadgeCheck,
};

export function AgentAvatar({
  member,
  size = 34,
  state,
}: {
  member: TeamMember | undefined;
  size?: number;
  state?: "idle" | "working" | "done";
}) {
  const Icon = AGENT_ICONS[member?.icon ?? "brain"] ?? Brain;
  return (
    <span
      className={`agent-avatar agent-avatar--${member?.id ?? "chief"}${state ? ` is-${state}` : ""}`}
      style={{ width: size, height: size }}
      aria-hidden="true"
    >
      <Icon size={Math.round(size * 0.5)} />
    </span>
  );
}

export type AgentState = "idle" | "working" | "done";

export function agentStates(
  team: TeamMember[],
  events: AgentEvent[],
  active: boolean,
): Record<string, AgentState> {
  const states: Record<string, AgentState> = Object.fromEntries(
    team.map((member) => [member.id, "idle" as AgentState]),
  );
  for (const event of events)
    if (event.agent in states) states[event.agent] = "done";
  const last = events[events.length - 1];
  if (active && last && last.agent in states) states[last.agent] = "working";
  return states;
}
