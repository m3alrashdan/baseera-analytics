import { expect, test } from "@playwright/test";

test.beforeEach(async ({ page }) => {
  await page.route("**/api/v1/auth/context", (route) =>
    route.fulfill({
      json: {
        user: {
          id: "u-test",
          display_name: "Test Executive",
          email: "test@example.com",
        },
        membership: {
          role: "executive",
          permissions: ["analytics:read"],
          department_ids: [],
        },
        tenant: {
          id: "t-test",
          name_en: "Fixture company",
          name_ar: "شركة الاختبار",
          currency: "JOD",
          timezone: "Asia/Amman",
          reporting_date: "2026-06-30",
          is_demo: true,
        },
      },
    }),
  );
});

test("English login exposes demo and empty workspace paths", async ({
  page,
}) => {
  await page.goto("/en/login");
  await expect(
    page.getByRole("heading", { name: /decisions deserve evidence/i }),
  ).toBeVisible();
  await expect(
    page.getByRole("button", { name: /fictional demo/i }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: /start an empty workspace/i }),
  ).toBeVisible();
});

test("Arabic shell uses RTL and keeps metric IDs isolated", async ({
  page,
}) => {
  await page.route("**/api/v1/overview", (route) =>
    route.fulfill({
      json: {
        status: "ready",
        company: {
          name: "شركة نماء للخدمات الصناعية",
          demo: true,
          currency: "JOD",
          timezone: "Asia/Amman",
        },
        period: { label: "يناير–يونيو ٢٠٢٦", comparison: "الفترة السابقة" },
        brief: "ارتفعت الإيرادات بينما تقلص الهامش.",
        metrics: [],
        trend: [],
        attention: [],
        departments: [],
        actions: [],
      },
    }),
  );
  await page.goto("/ar/overview");
  await expect(page.locator("html")).toHaveAttribute("dir", "rtl");
  await expect(
    page.getByRole("heading", { name: /نظرة تنفيذية/i }),
  ).toBeVisible();
});

test("API failure is honest and retryable", async ({ page }) => {
  await page.route("**/api/v1/overview", (route) =>
    route.fulfill({ status: 503, json: { message: "Source unavailable" } }),
  );
  await page.goto("/en/overview");
  await expect(page.locator(".resource-state[role=alert]")).toContainText(
    /couldn.t load|تعذر/i,
  );
  await expect(page.getByRole("button", { name: /retry/i })).toBeVisible();
});
