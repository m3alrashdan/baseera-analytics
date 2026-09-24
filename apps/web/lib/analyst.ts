/**
 * Types, API calls and formatting for the AI analyst team workspace.
 *
 * The server owns every number. The browser only formats what the team produced and
 * never recomputes a figure, so what a reader sees here is what the dossier and the
 * exports contain.
 */
import type { Locale } from "./contracts";
import { apiRequest, postJson } from "./api";

export type Bi = { en: string; ar: string };
export type PartialBi = Partial<Bi>;

export interface AgentEvent {
  t: number;
  agent: string;
  type: string;
  title: Bi;
  detail: Record<string, unknown>;
}

export interface ChartSpec {
  type: string;
  title?: Bi;
  x?: Array<string | number>;
  x_ar?: string[];
  y?: string[];
  series?: Array<{ name: string; data: unknown[]; style?: string }>;
  markers?: Array<{ x: string; label: string }>;
  history?: number[];
  forecast?: number[];
  lower?: number[];
  upper?: number[];
  values?: Array<Array<number | null>>;
  reference?: number;
  start?: number;
  end?: number;
  deltas?: number[];
  other?: number;
  x_label?: string;
  y_label?: string;
}

export interface Metric {
  label: Bi;
  value: number | string | null;
  format: "number" | "percent" | "money" | "ratio" | "score" | "text";
  delta: number | null;
}

export interface Finding {
  id: string;
  agent: string;
  kind: string;
  title: Bi;
  summary: Bi;
  details: Bi[];
  importance: number;
  confidence: "high" | "medium" | "low";
  confidence_score: number;
  metrics: Metric[];
  chart: ChartSpec | null;
  evidence_id: string | null;
  evidence: Record<string, unknown>;
  caveats: Bi[];
  tags: string[];
  so_what?: PartialBi;
}

export interface Recommendation {
  id: string;
  title: Bi;
  rationale: Bi;
  actions: Bi[];
  actions_model?: Partial<Record<Locale, string[]>>;
  expected_impact: Bi;
  priority: "P1" | "P2" | "P3";
  score: number;
  effort: "low" | "medium" | "high";
  horizon: string;
  kpis_to_track: string[];
  based_on: string[];
  rank: number;
}

export interface EvidenceItem {
  id: string;
  tool: string;
  agent: string;
  title: Bi;
  arguments: Record<string, unknown>;
  result: Record<string, unknown>;
  elapsed_seconds: number;
}

export interface Verification {
  mode: string;
  passed: boolean;
  numbers_checked: number;
  unverified: string[];
  verified_share?: number;
  causal_language?: string[];
  fallback?: string;
}

export interface EngineInfo {
  provider: string;
  model: string | null;
  status?: string;
  execution?: string;
  error?: { code: string; message: string };
  usage?: Record<string, unknown>;
  description?: Bi;
}

export interface Dossier {
  dataset: { id?: string; name?: string; version_id?: string; rows?: number };
  locale: Locale;
  generated_in_seconds: number;
  engine: EngineInfo;
  schema: Record<string, unknown>;
  health: Record<string, unknown>;
  executive_summary: PartialBi & { source?: string };
  headline: PartialBi | null;
  key_insights: string[];
  sections: Array<{ id: string; title: Bi; findings: string[] }>;
  findings: Finding[];
  recommendations: Recommendation[];
  next_questions: PartialBi[];
  risks: PartialBi[];
  evidence: Record<string, EvidenceItem>;
  verification: Verification;
  stats: { tool_calls: number; findings: number; evidence_items: number };
}

export interface QuestionResult {
  question: string;
  locale: Locale;
  answer: string;
  engine: EngineInfo;
  evidence: EvidenceItem[];
  verification: Verification;
  generated_in_seconds: number;
}

export type RunStatus =
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "cancelled";

export interface AgentRun {
  id: string;
  dataset_version_id: string;
  thread_id: string | null;
  mode: "autopilot" | "question";
  locale: Locale;
  question: string | null;
  status: RunStatus;
  engine: EngineInfo;
  events: AgentEvent[];
  events_total: number;
  error: { code: string; message: string } | null;
  created_at: string | null;
  started_at: string | null;
  finished_at: string | null;
  elapsed_seconds: number | null;
  result?: Dossier | QuestionResult | null;
  answer_preview?: string;
  summary?: { findings: number; recommendations: number };
}

export interface TeamMember {
  id: string;
  name: Bi;
  role: Bi;
  icon: string;
}

export interface TeamInfo {
  team: TeamMember[];
  engine: EngineInfo;
  tools: Array<{ name: string; agent: string; title: Bi }>;
  principles: Bi[];
}

export interface WorkspaceDataset {
  id: string;
  name: string;
  filename: string;
  created_at: string | null;
  versions: Array<{
    id: string;
    version_number: number;
    kind: string;
    row_count: number;
    columns: number;
  }>;
  latest_version_id: string;
  last_analysis: AgentRun | null;
}

export interface SampleInfo {
  id: string;
  title: Bi;
  description: Bi;
}

export const ACTIVE: RunStatus[] = ["queued", "running"];

export function loc(
  value: PartialBi | Bi | string | null | undefined,
  locale: Locale,
): string {
  if (value == null) return "";
  if (typeof value === "string") return value;
  return value[locale] ?? value.en ?? value.ar ?? "";
}

const numberFormat = (locale: Locale, digits = 1) =>
  new Intl.NumberFormat(locale === "ar" ? "ar-JO" : "en-US", {
    maximumFractionDigits: digits,
  });

export function compactNumber(value: number, locale: Locale): string {
  return new Intl.NumberFormat(locale === "ar" ? "ar-JO" : "en-US", {
    notation: Math.abs(value) >= 10000 ? "compact" : "standard",
    maximumFractionDigits: Math.abs(value) >= 100 ? 1 : 2,
  }).format(value);
}

export function formatMetric(metric: Metric, locale: Locale): string {
  const { value, format } = metric;
  if (value == null || value === "") return "—";
  if (typeof value === "string") return value;
  if (!Number.isFinite(value)) return "—";
  if (format === "percent")
    return `${numberFormat(locale).format(value * 100)}%`;
  if (format === "ratio") return numberFormat(locale, 2).format(value);
  if (format === "score") return `${numberFormat(locale, 0).format(value)}/100`;
  return compactNumber(value, locale);
}

export function formatDelta(
  delta: number | null | undefined,
  locale: Locale,
): string {
  if (delta == null || !Number.isFinite(delta)) return "";
  const sign = delta > 0 ? "+" : "";
  return `${sign}${numberFormat(locale).format(delta * 100)}%`;
}

// ------------------------------------------------------------------------------ API
export const analystApi = {
  team: (signal?: AbortSignal) =>
    apiRequest<TeamInfo>("/api/v1/analyst/team", { signal }),
  workspace: (signal?: AbortSignal) =>
    apiRequest<{ items: WorkspaceDataset[]; engine: EngineInfo }>(
      "/api/v1/analyst/workspace",
      { signal },
    ),
  samples: () => apiRequest<{ items: SampleInfo[] }>("/api/v1/analyst/samples"),
  loadSample: (id: string, locale: Locale) =>
    postJson<{
      dataset: { id: string; name: string };
      version: { id: string };
    }>(`/api/v1/analyst/samples/${encodeURIComponent(id)}`, { locale }),
  upload: (file: File) => {
    const form = new FormData();
    form.set("file", file);
    return apiRequest<{ dataset: { id: string }; version: { id: string } }>(
      "/api/v1/datasets/upload",
      {
        method: "POST",
        body: form,
        headers: { "Idempotency-Key": crypto.randomUUID() },
      },
    );
  },
  startRun: (body: {
    dataset_version_id: string;
    mode: "autopilot" | "question";
    locale: Locale;
    question?: string;
    thread_id?: string | null;
  }) => postJson<AgentRun>("/api/v1/analyst/runs", body),
  run: (id: string, since = 0, signal?: AbortSignal) =>
    apiRequest<AgentRun>(
      `/api/v1/analyst/runs/${encodeURIComponent(id)}?since=${since}`,
      { signal },
    ),
  runs: (params: Record<string, string>) =>
    apiRequest<{ items: AgentRun[] }>(
      `/api/v1/analyst/runs?${new URLSearchParams(params).toString()}`,
    ),
  cancel: (id: string) =>
    postJson<AgentRun>(
      `/api/v1/analyst/runs/${encodeURIComponent(id)}/cancel`,
      {},
    ),
  threads: (versionId: string) =>
    apiRequest<{
      items: Array<{
        id: string;
        title: string;
        turns: number;
        updated_at: string | null;
      }>;
    }>(
      `/api/v1/analyst/threads?dataset_version_id=${encodeURIComponent(versionId)}`,
    ),
};

export async function downloadExport(
  runId: string,
  format: string,
  locale: Locale,
): Promise<void> {
  const response = await fetch(
    `/api/v1/analyst/runs/${encodeURIComponent(runId)}/export?format=${format}&locale=${locale}`,
    { credentials: "include" },
  );
  if (!response.ok) throw new Error(`Export failed (${response.status})`);
  const blob = await response.blob();
  const disposition = response.headers.get("content-disposition") ?? "";
  const match = /filename="([^"]+)"/.exec(disposition);
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = match?.[1] ?? `baseera-analysis.${format}`;
  link.click();
  URL.revokeObjectURL(url);
}

/** Merge a polled page of events into what the client already holds. */
export function mergeRun(
  previous: AgentRun | null,
  next: AgentRun,
  since: number,
): AgentRun {
  if (!previous || previous.id !== next.id) return next;
  const events = [...previous.events.slice(0, since), ...next.events];
  return { ...next, events };
}
