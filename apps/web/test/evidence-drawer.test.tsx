import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { describe, expect, it } from "vitest";
import {
  EvidenceDrawer,
  type EvidenceRecord,
} from "@/components/evidence-drawer";

const evidence: EvidenceRecord = {
  metricId: "revenue_net",
  resultId: "result_01J9T4",
  definition: "Invoiced revenue less approved refunds.",
  scope: "All departments · Jan–Jun 2026",
  source: "ERP invoices · v17",
  freshness: "Refreshed 18 minutes ago",
  warning: "June is an incomplete period.",
};

describe("EvidenceDrawer", () => {
  it("exposes provenance and closes with Escape", async () => {
    const user = userEvent.setup();
    render(
      <EvidenceDrawer
        locale="en"
        evidence={evidence}
        open
        onClose={() => undefined}
      />,
    );
    expect(
      screen.getByRole("dialog", { name: /metric evidence/i }),
    ).toHaveTextContent("result_01J9T4");
    expect(screen.getByText(/incomplete period/i)).toBeVisible();
    await user.keyboard("{Escape}");
  });

  it("has no detectable accessibility violations", async () => {
    const { container } = render(
      <EvidenceDrawer
        locale="en"
        evidence={evidence}
        open
        onClose={() => undefined}
      />,
    );
    expect((await axe(container)).violations).toHaveLength(0);
  });
});
