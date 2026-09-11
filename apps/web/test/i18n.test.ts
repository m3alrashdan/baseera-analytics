import { describe, expect, it } from "vitest";
import { directionFor, formatCompactNumber, isLocale, t } from "@/lib/i18n";

describe("internationalization", () => {
  it("uses real Arabic direction and translated navigation", () => {
    expect(isLocale("ar")).toBe(true);
    expect(directionFor("ar")).toBe("rtl");
    expect(directionFor("en")).toBe("ltr");
    expect(t("ar", "nav.overview")).toBe("نظرة عامة");
  });

  it("formats values without changing the stored number", () => {
    expect(formatCompactNumber(1842500, "en")).toMatch(/1\.8/);
    expect(formatCompactNumber(1842500, "ar")).not.toBe("1842500");
  });
});
