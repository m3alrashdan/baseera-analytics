import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { LoginForm } from "@/components/login-form";

describe("LoginForm", () => {
  it("keeps field values and shows connected validation messages", async () => {
    const user = userEvent.setup();
    render(<LoginForm locale="en" onLogin={vi.fn()} onDemo={vi.fn()} />);

    await user.type(screen.getByLabelText(/work email/i), "not-an-email");
    await user.click(screen.getByRole("button", { name: /sign in/i }));

    expect(screen.getByLabelText(/work email/i)).toHaveValue("not-an-email");
    expect(screen.getByText(/valid email/i)).toHaveAttribute(
      "id",
      "work-email-error",
    );
    expect(screen.getByText(/password is required/i)).toBeVisible();
    expect(screen.getByLabelText(/work email/i)).toHaveAttribute(
      "aria-invalid",
      "true",
    );
  });

  it("offers an explicitly fictional demo workspace", async () => {
    const onDemo = vi.fn();
    const user = userEvent.setup();
    render(<LoginForm locale="en" onLogin={vi.fn()} onDemo={onDemo} />);
    await user.click(screen.getByRole("button", { name: /fictional demo/i }));
    expect(onDemo).toHaveBeenCalledOnce();
  });
});
