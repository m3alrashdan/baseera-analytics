import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ResourceState } from "@/components/resource-state";

describe("ResourceState", () => {
  it("explains unavailable and denied results without treating them as empty", () => {
    render(
      <ResourceState
        locale="en"
        status="denied"
        reason="Your department scope excludes payroll."
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent(/access restricted/i);
    expect(screen.getByText(/excludes payroll/i)).toBeVisible();
  });

  it("offers a working retry for failed requests", async () => {
    const retry = vi.fn();
    const user = userEvent.setup();
    render(
      <ResourceState
        locale="en"
        status="error"
        reason="The API did not respond."
        onRetry={retry}
      />,
    );
    await user.click(screen.getByRole("button", { name: /retry/i }));
    expect(retry).toHaveBeenCalledOnce();
  });
});
