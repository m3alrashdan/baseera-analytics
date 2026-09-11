import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { ExecutiveOverview } from "@/components/executive-overview";
import type { OverviewResponse } from "@/lib/contracts";

const overview: OverviewResponse = {
  status: "ready",
  company: {
    name: "Namaa Industrial Services",
    demo: true,
    currency: "JOD",
    timezone: "Asia/Amman",
  },
  period: { label: "Jan–Jun 2026", comparison: "previous period" },
  brief: "Revenue grew while margin narrowed. Support pressure needs review.",
  metrics: [
    {
      id: "revenue_net",
      name: "Net revenue",
      value: 1842500,
      unit: "JOD",
      change: 12.4,
      trend: "up",
      definition: "Invoiced revenue less approved refunds.",
      source: "ERP invoices · v17",
      freshness: "18 minutes ago",
      result_id: "result_01J9T4",
    },
  ],
  trend: [{ period: "Jan", current: 280000, comparison: 250000 }],
  attention: [
    {
      id: "a1",
      severity: "warning",
      title: "Support queue rising",
      detail: "31% above staffed capacity",
    },
  ],
  departments: [{ name: "Customer operations", value: 131, target: 100 }],
  actions: [
    {
      id: "d1",
      title: "Review weekend coverage",
      owner: "Operations",
      due: "2026-06-18",
      status: "review",
    },
  ],
};

describe("ExecutiveOverview", () => {
  it("opens evidence for a selected KPI without losing the overview", async () => {
    const user = userEvent.setup();
    render(<ExecutiveOverview locale="en" data={overview} />);
    expect(
      screen.getByRole("heading", { name: /executive overview/i }),
    ).toBeVisible();
    await user.click(
      screen.getByRole("button", { name: /inspect evidence for net revenue/i }),
    );
    expect(
      screen.getByRole("dialog", { name: /metric evidence/i }),
    ).toHaveTextContent("result_01J9T4");
    expect(
      screen.getByText(/revenue grew while margin narrowed/i),
    ).toBeVisible();
  });
});
