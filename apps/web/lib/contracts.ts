export type Locale = "ar" | "en";

export interface SessionContext {
  user: { id: string; email: string; display_name: string };
  membership: { role: string; department_ids: string[]; permissions: string[] };
  tenant: {
    id: string;
    name_ar: string;
    name_en: string;
    currency: string;
    timezone: string;
    is_demo: boolean;
    reporting_date: string | null;
  };
}

export type ResourceStatus =
  | "ready"
  | "loading"
  | "partial"
  | "empty"
  | "error"
  | "denied"
  | "unavailable"
  | "stale";

export interface CompanyContext {
  name: string;
  demo: boolean;
  currency: string;
  timezone: string;
}

export interface PeriodContext {
  label: string;
  comparison: string;
}

export interface MetricResult {
  id: string;
  name: string;
  value: number | null;
  unit: string;
  change: number | null;
  trend: "up" | "down" | "flat" | "unavailable";
  definition: string;
  source: string;
  freshness: string;
  result_id: string;
  warning?: string;
}

export interface OverviewResponse {
  status: ResourceStatus;
  company: CompanyContext;
  period: PeriodContext;
  brief: string;
  metrics: MetricResult[];
  trend: Array<{
    period: string;
    current: number | null;
    comparison: number | null;
  }>;
  attention: Array<{
    id: string;
    severity: "info" | "warning" | "critical";
    title: string;
    detail: string;
  }>;
  departments: Array<{ name: string; value: number; target: number }>;
  actions: Array<{
    id: string;
    title: string;
    owner: string;
    due: string;
    status: string;
  }>;
  correlation_id?: string;
}

export interface ApiProblem {
  code: string;
  message: string;
  status: number;
  correlationId?: string;
  fields?: Record<string, string>;
}

export interface UploadAccepted {
  dataset_id: string;
  status: "accepted";
  version_id?: string;
  version_number?: number;
  job_id?: string;
}

export interface QualityIssue {
  id: string;
  title: string;
  field: string;
  count: number;
  severity: "low" | "medium" | "high";
  example: string;
  treatment: string;
  rationale: string;
  accepted: boolean;
}

export interface ModuleSnapshot {
  status: ResourceStatus;
  generatedAt: string;
  resultId: string;
  rows: Array<Record<string, string | number | null>>;
}
