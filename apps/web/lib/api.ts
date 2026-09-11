import type {
  ApiProblem,
  Locale,
  OverviewResponse,
  UploadAccepted,
} from "./contracts";

export class ApiError extends Error {
  constructor(readonly problem: ApiProblem) {
    super(problem.message);
    this.name = "ApiError";
  }
}

let csrfToken: string | undefined;
let csrfRequest: Promise<string> | undefined;
export function clearApiSession() {
  csrfToken = undefined;
  csrfRequest = undefined;
}

async function parseProblem(response: Response): Promise<ApiProblem> {
  let body: Record<string, unknown> = {};
  try {
    body = await response.json();
  } catch {
    /* Preserve status for non-JSON errors. */
  }
  const nested = (body.error ?? body.detail ?? body) as Record<string, unknown>;
  return {
    status: response.status,
    code: String(nested.code ?? `HTTP_${response.status}`),
    message: String(
      nested.message ??
        body.message ??
        "The service did not return a readable response.",
    ),
    correlationId:
      String(
        nested.correlation_id ?? response.headers.get("x-correlation-id") ?? "",
      ) || undefined,
  };
}

async function sessionCsrf(): Promise<string> {
  if (csrfToken) return csrfToken;
  csrfRequest ??= fetch("/api/v1/auth/csrf", {
    credentials: "include",
    headers: { Accept: "application/json" },
  })
    .then(async (response) => {
      if (!response.ok) throw new ApiError(await parseProblem(response));
      const body: unknown = await response.json();
      if (
        !body ||
        typeof body !== "object" ||
        typeof (body as { csrf_token?: unknown }).csrf_token !== "string"
      ) {
        throw new ApiError({
          status: 502,
          code: "csrf_response_invalid",
          message: "The service returned an invalid session token response.",
        });
      }
      csrfToken = (body as { csrf_token: string }).csrf_token;
      return csrfToken;
    })
    .finally(() => {
      csrfRequest = undefined;
    });
  return csrfRequest;
}

export async function apiRequest<T>(
  path: string,
  init: RequestInit = {},
  csrfRetried = false,
): Promise<T> {
  const headers = new Headers(init.headers);
  headers.set("Accept", "application/json");
  if (init.body && !(init.body instanceof FormData))
    headers.set("Content-Type", "application/json");
  const mutation = !["GET", "HEAD", "OPTIONS"].includes(
    (init.method ?? "GET").toUpperCase(),
  );
  if (mutation && path !== "/api/v1/auth/login")
    headers.set("X-CSRF-Token", await sessionCsrf());
  const response = await fetch(path, {
    ...init,
    headers,
    credentials: "include",
  });
  if (!response.ok) {
    if (response.status === 401) clearApiSession();
    const problem = await parseProblem(response);
    // csrf_failed is raised before the handler executes: retry this one rejected
    // mutation after a different tab rotated the token, never retry other failures.
    if (
      mutation &&
      problem.code === "csrf_failed" &&
      !csrfRetried &&
      !init.signal?.aborted
    ) {
      clearApiSession();
      return apiRequest<T>(path, init, true);
    }
    throw new ApiError(problem);
  }
  if (response.status === 204) return undefined as T;
  const body = await response.json();
  if (path === "/api/v1/auth/login" && typeof body.csrf_token === "string")
    csrfToken = body.csrf_token;
  if (path === "/api/v1/auth/logout") clearApiSession();
  return body as T;
}

const metricLabels: Record<string, [string, string]> = {
  net_revenue: ["Net revenue", "صافي الإيرادات"],
  gross_margin: ["Gross profit", "الربح الإجمالي"],
  gross_margin_rate: ["Gross margin rate", "نسبة هامش الربح"],
  support_case_count: ["Support cases", "حالات الدعم"],
  avg_resolution_hours: ["Average resolution", "متوسط زمن الحل"],
  budget_variance: ["Budget variance", "فرق الموازنة"],
  project_delay_rate: ["Project delay rate", "نسبة تأخر المشاريع"],
};
type WireRecord = Record<string, any>;
export function normalizeOverviewPayload(
  payload: unknown,
  locale: Locale = "en",
): OverviewResponse {
  const data = payload as WireRecord;
  if (Array.isArray(data.metrics) && data.company)
    return data as OverviewResponse;
  const ar = locale === "ar";
  const asOf = data.as_of
    ? new Intl.DateTimeFormat(ar ? "ar-JO" : "en", {
        dateStyle: "medium",
        timeZone: "UTC",
      }).format(new Date(`${data.as_of}T12:00:00Z`))
    : ar
      ? "الفترة المتاحة"
      : "Available period";
  return {
    status: "partial",
    company: {
      name:
        data.company?.name ??
        (ar ? data.tenant?.name_ar : data.tenant?.name_en) ??
        (data.is_demo
          ? ar
            ? "شركة نماء للخدمات الصناعية"
            : "Namaa Industrial Services"
          : ar
            ? "مساحة الشركة"
            : "Company workspace"),
      demo: Boolean(data.is_demo),
      currency: data.currency ?? data.tenant?.currency ?? "—",
      timezone: data.timezone ?? data.tenant?.timezone ?? "—",
    },
    period: {
      label: `${ar ? "كل التاريخ المتاح حتى" : "All available history through"} ${asOf}`,
      comparison: data.trend?.length
        ? ar
          ? "الرسم: أشهر مقابل العام السابق"
          : "Chart: months vs prior year"
        : ar
          ? "المقارنة غير متاحة"
          : "Comparison unavailable",
    },
    brief: ar
      ? "مؤشرات محسوبة ضمن صلاحياتك. افحص التعريف والتغطية قبل اتخاذ القرار."
      : "Calculated metrics within your permitted scope. Review definitions and coverage before deciding.",
    metrics: Object.entries(data.metrics ?? {}).map(([id, raw]) => {
      const metric = raw as WireRecord;
      return {
        id,
        name: metricLabels[id]?.[ar ? 1 : 0] ?? id,
        value: typeof metric.value === "number" ? metric.value : null,
        unit: metric.unit ?? "",
        change: null,
        trend: "unavailable" as const,
        definition:
          metric.definition ??
          (ar
            ? "مؤشر محسوب من سجلات الشركة ضمن النطاق المسموح."
            : "Calculated from company records in the permitted scope."),
        source: metric.source ?? "Company records",
        freshness: asOf,
        result_id: metric.result_id ?? "",
        warning: metric.result_id
          ? undefined
          : ar
            ? "لا يتضمن هذا الملخص معرّف نتيجة محفوظة. المقارنة التاريخية غير متاحة."
            : "This summary does not include a persisted result ID. Historical comparison is unavailable.",
      };
    }),
    trend: data.trend ?? [],
    attention: (data.attention ?? []).map((item: WireRecord) => ({
      id: item.kind,
      severity: "warning",
      title:
        item.kind === "project_risk"
          ? ar
            ? "تأخر مشاريع"
            : "Project delays"
          : ar
            ? "استثناء في الطاقة"
            : "Capacity exception",
      detail: `${item.count ?? ""} · ${item.message ?? ""}`,
    })),
    departments: [],
    actions: [],
  };
}

export async function getOverview(
  signal?: AbortSignal,
  locale: Locale = "en",
): Promise<OverviewResponse> {
  return normalizeOverviewPayload(
    await apiRequest("/api/v1/overview", { signal }),
    locale,
  );
}
export async function uploadDataset(file: File): Promise<UploadAccepted> {
  const form = new FormData();
  form.set("file", file);
  const body = await apiRequest<{
    dataset: { id: string };
    version: { id: string; version_number: number };
  }>("/api/v1/datasets/upload", {
    method: "POST",
    body: form,
    headers: { "Idempotency-Key": crypto.randomUUID() },
  });
  const accepted: UploadAccepted = {
    status: "accepted",
    dataset_id: body.dataset.id,
    version_id: body.version.id,
    version_number: body.version.version_number,
  };
  sessionStorage.setItem("baseera-last-upload", JSON.stringify(accepted));
  return accepted;
}
export function postJson<T>(
  path: string,
  body: unknown,
  version?: string,
): Promise<T> {
  return apiRequest<T>(path, {
    method: "POST",
    body: JSON.stringify(body),
    headers: {
      "Idempotency-Key": crypto.randomUUID(),
      ...(version ? { "If-Match": version } : {}),
    },
  });
}
export function resourceStatusFromError(
  error: unknown,
): "denied" | "unavailable" | "error" {
  if (error instanceof ApiError && [401, 403].includes(error.problem.status))
    return "denied";
  if (error instanceof ApiError && [404, 501].includes(error.problem.status))
    return "unavailable";
  return "error";
}
