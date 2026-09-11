import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, expect, it, vi } from "vitest";
import { AssistantScreen } from "@/components/local-assistant";
import { apiRequest } from "@/lib/api";

vi.mock("@/lib/api", () => ({
  apiRequest: vi.fn(),
  postJson: vi.fn(),
  resourceStatusFromError: () => "error",
}));
const context = {
  user: { display_name: "Analyst" },
  membership: { role: "executive", department_ids: [] },
  tenant: { reporting_date: "2026-06-30" },
};

beforeEach(() => {
  vi.clearAllMocks();
  vi.mocked(apiRequest).mockImplementation(async (path) => {
    if (path.endsWith("auth/context")) return context;
    if (path.endsWith("assistant/status"))
      return { mode: "ollama", model: "local-test-model", status: "available" };
    if (path.endsWith("conversations")) return { items: [] };
    return {
      conversation_id: "conversation-one",
      status: "completed",
      answer: "Revenue: 90 JOD",
      results: [],
      plan: { action: "metric_query" },
      provider: {
        mode: "ollama",
        model: "local-test-model",
        status: "completed",
      },
    };
  });
});

it("uses live model context and resets the server conversation ID for a new conversation", async () => {
  render(<AssistantScreen locale="en" />);
  await screen.findByText("local-test-model");
  fireEvent.change(screen.getByLabelText("Type your question"), {
    target: { value: "Revenue?" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Analyze" }));
  await screen.findByText("Revenue: 90 JOD");
  fireEvent.click(screen.getByRole("button", { name: "New conversation" }));
  expect(screen.queryByText("Revenue: 90 JOD")).not.toBeInTheDocument();
  fireEvent.change(screen.getByLabelText("Type your question"), {
    target: { value: "Support count?" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Analyze" }));
  await screen.findByText("Revenue: 90 JOD");
  const queries = vi
    .mocked(apiRequest)
    .mock.calls.filter(([path]) => path.endsWith("assistant/query"));
  expect(queries).toHaveLength(2);
  expect(JSON.parse(String(queries[1][1]?.body))).not.toHaveProperty(
    "conversation_id",
  );
});

it("preserves a failed question for retry without inventing a reply", async () => {
  const baseline = vi.mocked(apiRequest).getMockImplementation()!;
  vi.mocked(apiRequest).mockImplementation(async (path, init) => {
    if (path.endsWith("assistant/query"))
      throw new Error("Ollama is unreachable");
    return baseline(path, init);
  });
  render(<AssistantScreen locale="en" />);
  await screen.findByText("local-test-model");
  fireEvent.change(screen.getByLabelText("Type your question"), {
    target: { value: "Revenue?" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Analyze" }));
  await screen.findByText(/Ollama is unreachable/);
  await waitFor(() =>
    expect(screen.getByLabelText("Type your question")).toHaveValue("Revenue?"),
  );
  expect(screen.queryByText("Revenue: 90 JOD")).not.toBeInTheDocument();
});
