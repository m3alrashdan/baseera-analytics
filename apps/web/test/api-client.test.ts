import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  clearApiSession,
  getOverview,
  normalizeOverviewPayload,
  postJson,
  uploadDataset,
} from "@/lib/api";

const backendOverview = {
  as_of: "2026-06-30",
  is_demo: true,
  currency: "JOD",
  timezone: "Asia/Amman",
  metrics: {
    net_revenue: { value: 1842500, unit: "JOD" },
    gross_margin: { value: 493690, unit: "JOD" },
    support_case_count: { value: 284, unit: "cases" },
    avg_resolution_hours: { value: 19.4, unit: "hours" },
    budget_variance: { value: -36000, unit: "JOD" },
    project_delay_rate: { value: 0.2, unit: "ratio" },
  },
  attention: [
    {
      kind: "project_risk",
      count: 4,
      message: "Projects have recorded delay.",
    },
  ],
  scope: { tenant_id: "tenant-demo" },
};

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("API boundary", () => {
  it("refreshes a rotated CSRF token once after a pre-execution rejection", async () => {
    const mock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ csrf_token: "old-token" }))
      .mockResolvedValueOnce(
        jsonResponse(
          { error: { code: "csrf_failed", message: "Token expired" } },
          403,
        ),
      )
      .mockResolvedValueOnce(jsonResponse({ csrf_token: "renewed-token" }))
      .mockResolvedValueOnce(jsonResponse({ id: "saved-once" }));
    vi.stubGlobal("fetch", mock);
    await postJson("/api/v1/auth/login", {
      email: "test@example.com",
      password: "test",
    });
    expect(await postJson("/api/v1/reports", { title: "Reviewed" })).toEqual({
      id: "saved-once",
    });
    expect(mock).toHaveBeenCalledTimes(4);
    expect(new Headers(mock.mock.calls[3][1].headers).get("X-CSRF-Token")).toBe(
      "renewed-token",
    );
  });
  beforeEach(() => {
    sessionStorage.clear();
    clearApiSession();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("normalizes the real backend overview without inventing missing series", () => {
    const overview = normalizeOverviewPayload(backendOverview, "en");

    expect(overview.status).toBe("partial");
    expect(overview.company).toMatchObject({ demo: true, currency: "JOD" });
    expect(overview.period.label).toContain("Jun");
    expect(overview.metrics).toHaveLength(6);
    expect(
      overview.metrics.find((item) => item.id === "gross_margin"),
    ).toMatchObject({
      value: 493690,
      unit: "JOD",
      change: null,
      trend: "unavailable",
    });
    expect(overview.trend).toEqual([]);
    expect(overview.departments).toEqual([]);
    expect(overview.actions).toEqual([]);
    expect(overview.metrics[0].warning).toMatch(
      /does not include a persisted result ID/i,
    );
  });

  it("normalizes the backend payload returned by getOverview", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse(backendOverview)),
    );

    const overview = await getOverview(undefined, "ar");

    expect(overview.company.name).toBe("شركة نماء للخدمات الصناعية");
    expect(overview.attention[0]).toMatchObject({
      id: "project_risk",
      severity: "warning",
    });
  });

  it("keeps the HttpOnly session in the cookie and sends the returned CSRF token on mutations", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(
        jsonResponse({ csrf_token: "csrf-test", user: { id: "u1" } }),
      )
      .mockResolvedValueOnce(jsonResponse({ status: "created" }));
    vi.stubGlobal("fetch", fetchMock);

    await postJson("/api/v1/auth/login", {
      email: "owner@example.com",
      password: "correct horse battery staple",
    });
    await postJson("/api/v1/decisions", { title: "Review capacity" });

    const loginInit = fetchMock.mock.calls[0][1] as RequestInit;
    const mutationInit = fetchMock.mock.calls[1][1] as RequestInit;
    expect(loginInit.credentials).toBe("include");
    expect(new Headers(loginInit.headers).has("X-CSRF-Token")).toBe(false);
    expect(new Headers(mutationInit.headers).get("X-CSRF-Token")).toBe(
      "csrf-test",
    );
    expect(localStorage.getItem("baseera-csrf")).toBeNull();
    expect(sessionStorage.getItem("baseera-csrf")).toBeNull();
  });

  it("adapts an accepted backend upload to the UI contract", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(jsonResponse({ csrf_token: "csrf-test" }))
        .mockResolvedValueOnce(
          jsonResponse(
            {
              dataset: { id: "dataset-1", name: "orders" },
              version: { id: "dataset-version-1", version_number: 1 },
              coverage: { rows_discovered: 2, rows_accepted: 2 },
              deduplicated: false,
            },
            201,
          ),
        ),
    );

    const accepted = await uploadDataset(
      new File(["id,total\n1,12"], "orders.csv"),
    );

    expect(accepted).toMatchObject({
      status: "accepted",
      dataset_id: "dataset-1",
      version_id: "dataset-version-1",
    });
  });

  it("reads the backend problem envelope", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse(
          {
            error: {
              code: "version_conflict",
              message: "Refresh before applying.",
              details: { fields: { expected_version: "stale" } },
            },
          },
          409,
        ),
      ),
    );

    await expect(postJson("/api/v1/reports/r1", {})).rejects.toMatchObject({
      problem: {
        code: "version_conflict",
        message: "Refresh before applying.",
        status: 409,
      },
    });
  });
});
