import { expect, test } from "@playwright/test";

test("live upload → reviewed cleaning → metric → dashboard → versioned export", async ({
  page,
}, info) => {
  test.skip(
    !process.env.BASEERA_LIVE_E2E,
    "Requires an explicitly selected local seeded API; no API mocks.",
  );
  test.setTimeout(120_000);
  const ar = info.project.name.includes("ar");
  const locale = ar ? "ar" : "en";
  const label = (en: string, arabic: string) => (ar ? arabic : en);
  const consoleErrors: string[] = [];
  page.on("pageerror", (error) => consoleErrors.push(error.message));
  await page.goto(`/${locale}/login`);
  await page
    .getByRole("button", {
      name: ar ? /مساحة تجريبية خيالية/ : /fictional demo/i,
    })
    .click();
  await expect(page).toHaveURL(/analyst/);
  await expect(page.locator(".ai-hero")).toBeVisible();
  await page.goto(`/${locale}/overview`);
  await expect(page.locator(".kpi-card")).toHaveCount(7);
  await page
    .getByRole("button", {
      name: ar ? "تفعيل المظهر الداكن" : "Use dark theme",
    })
    .click();
  await expect(page.locator("html")).toHaveAttribute("data-theme", "dark");
  await page.screenshot({
    path: info.outputPath("overview-dark.png"),
    fullPage: true,
  });

  await page.goto(`/${locale}/data/sources`);
  await page.locator('input[type="file"]').setInputFiles({
    name: `journey-${locale}.csv`,
    mimeType: "text/csv",
    buffer: Buffer.from(
      "id,revenue,cost\n001,100,60\n001,100,60\n002,-10,-4\n",
    ),
  });
  await page
    .getByRole("button", { name: label("Upload and inspect", "ارفع وافحص") })
    .click();
  await expect(page.locator(".upload-studio [role=status]")).toContainText(
    label("Upload accepted", "تم قبول الملف"),
  );

  await page.goto(`/${locale}/data/quality`);
  await page
    .getByRole("button", { name: label("Inspect version", "افحص الإصدار") })
    .click();
  await page
    .getByRole("combobox", {
      name: label("Cleaning step", "خطوة التنظيف"),
      exact: true,
    })
    .selectOption("deduplicate");
  await page
    .getByRole("combobox", { name: label("Column", "العمود"), exact: true })
    .selectOption("id");
  await page
    .getByRole("button", { name: label("Preview changes", "عاين التغييرات") })
    .click();
  await expect(page.locator(".live-review")).toBeVisible();
  await expect(
    page.getByRole("button", {
      name: label("Apply reviewed recipe", "طبّق الخطوات المراجعة"),
    }),
  ).toBeDisabled();
  await page.locator(".live-review input[type=checkbox]").check();
  await page
    .getByRole("button", {
      name: label("Apply reviewed recipe", "طبّق الخطوات المراجعة"),
    })
    .click();
  await expect(page.locator(".success-message")).toContainText(
    label("Version 2 saved", "حُفظ الإصدار 2"),
  );

  await page.goto(`/${locale}/explore`);
  const resultResponse = page.waitForResponse(
    (response) =>
      response.url().endsWith("/metrics/query") &&
      response.request().method() === "POST",
  );
  await page
    .getByRole("button", { name: label("Run analysis", "شغّل التحليل") })
    .click();
  const result = await (await resultResponse).json();
  expect(result.value).toBe(90);
  expect(result.evidence.dataset_version_id).toBeTruthy();
  await page
    .getByRole("button", { name: label("Save to dashboard", "احفظ في لوحة") })
    .click();
  await expect(page.locator(".success-message")).toContainText(
    label("Dashboard saved", "حُفظت اللوحة"),
  );
  await page.reload();
  await expect(
    page.getByRole("heading", {
      name: label("Saved dashboards", "اللوحات المحفوظة"),
    }),
  ).toBeVisible();
  await page
    .getByRole("button", { name: /net_revenue.*v1/ })
    .first()
    .click();
  await expect(page.locator(".live-summary")).toContainText("completed");

  await page.goto(`/${locale}/reports`);
  await page
    .getByLabel(label("Report title", "عنوان التقرير"), { exact: true })
    .fill(`Reviewed revenue ${locale}`);
  await page
    .getByLabel(label("Commentary", "التعليق"), { exact: true })
    .fill(
      label(
        "Duplicate removed after reconciliation.",
        "أزيل التكرار بعد المطابقة.",
      ),
    );
  await page
    .getByLabel(label("Result ID (optional)", "معرّف نتيجة (اختياري)"), {
      exact: true,
    })
    .fill(result.result_id);
  await page
    .getByRole("button", { name: label("Save version", "احفظ الإصدار") })
    .click();
  await expect(page.locator(".live-export [role=status]")).toContainText("1");
  const href = await page
    .getByRole("link", { name: "JSON", exact: true })
    .getAttribute("href");
  expect(href).toBeTruthy();
  const exported = await page.request.get(href!);
  expect(exported.status()).toBe(200);
  expect(exported.headers()["x-content-sha256"]).toMatch(/^[a-f0-9]{64}$/);
  const snapshot = await exported.json();
  expect(
    snapshot.sections.find(
      (section: { result_id?: string }) =>
        section.result_id === result.result_id,
    ).result.value,
  ).toBe(90);
  await page.screenshot({
    path: info.outputPath("report-evidence.png"),
    fullPage: true,
  });
  expect(consoleErrors).toEqual([]);
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth > window.innerWidth + 1,
  );
  expect(overflow).toBe(false);
});

test("live AI analyst team: sample → full analysis → dossier → question", async ({
  page,
}, info) => {
  test.skip(
    !process.env.BASEERA_LIVE_E2E,
    "Requires an explicitly selected local seeded API; no API mocks.",
  );
  test.setTimeout(240_000);
  const ar = info.project.name.includes("ar");
  const locale = ar ? "ar" : "en";
  const consoleErrors: string[] = [];
  page.on("pageerror", (error) => consoleErrors.push(error.message));
  await page.goto(`/${locale}/login`);
  await page
    .getByRole("button", {
      name: ar ? /مساحة تجريبية خيالية/ : /fictional demo/i,
    })
    .click();
  await expect(page).toHaveURL(/analyst/);
  await page.locator(".sample-card").nth(1).click();
  // Wait for the sample to become the selected dataset before commissioning it.
  await expect(page.locator(".ai-main__head h2")).toHaveText(
    ar ? "تسرب المشتركين" : "Subscription churn",
  );
  await expect(page.locator(".launch-card button")).toBeEnabled();
  await page.locator(".launch-card button").click();
  await expect(page.locator(".live-run")).toBeVisible();
  await expect(page.locator(".dossier")).toBeVisible({ timeout: 180_000 });
  await expect(
    page.locator(".rec-card, .priority-list li").first(),
  ).toBeVisible();
  await page.locator(".ai-main > .tabs button").nth(1).click();
  await page
    .locator(".composer textarea")
    .fill(ar ? "ما العوامل التي تؤثر على التسرب؟" : "What drives churned?");
  await page.locator(".composer button[type=submit]").click();
  await expect(page.locator(".rich-answer").first()).toBeVisible({
    timeout: 120_000,
  });
  await page.screenshot({
    path: info.outputPath("ai-analyst.png"),
    fullPage: true,
  });
  expect(consoleErrors).toEqual([]);
});
