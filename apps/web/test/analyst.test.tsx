import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "jest-axe";
import { describe, expect, it } from "vitest";
import {
  formatDelta,
  formatMetric,
  loc,
  mergeRun,
  type AgentRun,
  type Dossier,
  type TeamMember,
} from "@/lib/analyst";
import { chartOption, chartTable, supportsChart } from "@/lib/agent-charts";
import { vizTheme } from "@/lib/viz";
import { LiveRun } from "@/components/analyst/live-run";
import { DossierView } from "@/components/analyst/dossier";

const bi = (en: string, ar = en) => ({ en, ar });

const team: TeamMember[] = [
  {
    id: "chief",
    name: bi("Chief Analyst", "كبير المحللين"),
    role: bi("Leads"),
    icon: "brain",
  },
  {
    id: "data_engineer",
    name: bi("Data Engineer", "مهندس البيانات"),
    role: bi("Schema"),
    icon: "database",
  },
  {
    id: "forecaster",
    name: bi("Forecaster", "خبير التنبؤ"),
    role: bi("Time"),
    icon: "trending",
  },
];

function run(overrides: Partial<AgentRun> = {}): AgentRun {
  return {
    id: "run-1",
    dataset_version_id: "v1",
    thread_id: null,
    mode: "autopilot",
    locale: "en",
    question: null,
    status: "running",
    engine: { provider: "deterministic", model: null },
    events: [
      {
        t: 0.1,
        agent: "chief",
        type: "plan",
        title: bi("Analysis plan"),
        detail: {
          steps: [
            {
              agent: "data_engineer",
              task: bi("Audit quality"),
              applicable: true,
            },
            { agent: "forecaster", task: bi("Forecast"), applicable: false },
          ],
        },
      },
      {
        t: 1.2,
        agent: "data_engineer",
        type: "tool_result",
        title: bi("Data health: done"),
        detail: { summary: bi("12 rows audited") },
      },
    ],
    events_total: 2,
    error: null,
    created_at: null,
    started_at: null,
    finished_at: null,
    elapsed_seconds: 1.2,
    ...overrides,
  };
}

const dossier: Dossier = {
  dataset: { name: "Retail", rows: 1200, version_id: "v1" },
  locale: "en",
  generated_in_seconds: 9.5,
  engine: { provider: "deterministic", model: null },
  schema: {
    columns_detail: [],
    time_column: "order_date",
    primary_kpi: "revenue",
  },
  health: { score: 98 },
  executive_summary: {
    en: "Revenue grew.\n\nNorth fell.",
    ar: "نمت الإيرادات.",
  },
  headline: null,
  key_insights: ["f-2"],
  sections: [
    { id: "why", title: bi("What changed and why"), findings: ["f-2"] },
  ],
  findings: [
    {
      id: "f-1",
      agent: "chief",
      kind: "kpi",
      title: bi("Headline numbers"),
      summary: bi("Revenue totals 2.5M."),
      details: [],
      importance: 0.6,
      confidence: "high",
      confidence_score: 0.9,
      metrics: [
        {
          label: bi("revenue"),
          value: 2_500_000,
          format: "number",
          delta: -0.047,
        },
      ],
      chart: null,
      evidence_id: null,
      evidence: {},
      caveats: [],
      tags: [],
    },
    {
      id: "f-2",
      agent: "chief",
      kind: "change",
      title: bi("Why revenue fell"),
      summary: bi("North declined 34% while the total grew 5.5%."),
      details: [bi("North: -11.4K")],
      importance: 0.8,
      confidence: "medium",
      confidence_score: 0.6,
      metrics: [],
      chart: null,
      evidence_id: "ev-1",
      evidence: {},
      caveats: [bi("Association is not causation.")],
      tags: [],
    },
  ],
  recommendations: [
    {
      id: "fix-north",
      title: bi("Recovery plan for North"),
      rationale: bi("North declined."),
      actions: [bi("Interview the owners of North.")],
      expected_impact: bi("Up to 11.4K per quarter."),
      priority: "P1",
      score: 0.8,
      effort: "medium",
      horizon: "30_days",
      kpis_to_track: ["revenue"],
      based_on: ["f-2"],
      rank: 1,
    },
  ],
  next_questions: [bi("What happened to North week by week?")],
  risks: [],
  evidence: {
    "ev-1": {
      id: "ev-1",
      tool: "explain_change",
      agent: "detective",
      title: bi("Change explanation"),
      arguments: { measure: "revenue" },
      result: { method: "additive_contribution_analysis" },
      elapsed_seconds: 0.2,
    },
  },
  verification: {
    mode: "deterministic",
    passed: true,
    numbers_checked: 0,
    unverified: [],
  },
  stats: { tool_calls: 12, findings: 2, evidence_items: 1 },
};

describe("analyst formatting", () => {
  it("formats metrics and deltas in both languages", () => {
    expect(
      formatMetric(
        { label: bi("x"), value: 0.123, format: "percent", delta: null },
        "en",
      ),
    ).toBe("12.3%");
    expect(
      formatMetric(
        { label: bi("x"), value: 98, format: "score", delta: null },
        "en",
      ),
    ).toBe("98/100");
    expect(
      formatMetric(
        { label: bi("x"), value: null, format: "number", delta: null },
        "en",
      ),
    ).toBe("—");
    expect(formatDelta(0.05, "en")).toBe("+5%");
    expect(formatDelta(null, "en")).toBe("");
    expect(loc({ en: "A", ar: "ب" }, "ar")).toBe("ب");
  });

  it("appends only new events when merging a poll", () => {
    const previous = run();
    const next = run({
      status: "completed",
      events: [
        { t: 2, agent: "chief", type: "done", title: bi("Done"), detail: {} },
      ],
      events_total: 3,
    });
    const merged = mergeRun(previous, next, 2);
    expect(merged.events).toHaveLength(3);
    expect(merged.status).toBe("completed");
  });
});

describe("agent charts", () => {
  const theme = vizTheme("light");
  it("builds an option and a table for every chart the team emits", () => {
    const specs = [
      {
        type: "line",
        x: ["a", "b"],
        series: [{ name: "trend", data: [1, 2] }],
      },
      {
        type: "forecast",
        x: ["a", "b", "c"],
        history: [1, 2],
        forecast: [3],
        lower: [2],
        upper: [4],
      },
      {
        type: "bar",
        x: ["a", "b"],
        series: [{ name: "v", data: [1, 2] }],
        reference: 1.5,
      },
      {
        type: "bar_horizontal",
        x: ["a", "b"],
        series: [{ name: "share_of_explained", data: [0.6, 0.4] }],
      },
      {
        type: "pareto",
        x: ["a", "b"],
        series: [
          { name: "v", data: [3, 1] },
          { name: "cumulative_share", data: [0.75, 1] },
        ],
      },
      {
        type: "waterfall",
        x: ["Q1", "North", "Q2"],
        start: 10,
        deltas: [-2],
        end: 8,
      },
      {
        type: "heatmap",
        x: ["a", "b"],
        y: ["a", "b"],
        values: [
          [1, -0.2],
          [-0.2, 1],
        ],
      },
      {
        type: "scatter",
        x_label: "x",
        y_label: "y",
        series: [{ name: "s", data: [[1, 2]] }],
      },
    ];
    for (const spec of specs) {
      expect(supportsChart(spec)).toBe(true);
      const option = chartOption(spec, "ar")(theme) as { series: unknown[] };
      expect(Array.isArray(option.series)).toBe(true);
      expect(chartTable(spec, "en").rows.length).toBeGreaterThan(0);
    }
    const forecast = chartTable(specs[1], "en");
    expect(forecast.rows[2]).toMatchObject({
      x: "c",
      forecast: 3,
      lower: 2,
      upper: 4,
    });
  });
});

describe("LiveRun", () => {
  it("shows who is working and the activity log", async () => {
    const { container } = render(
      <LiveRun
        run={run()}
        team={team}
        locale="en"
        onCancel={() => undefined}
      />,
    );
    expect(screen.getByRole("progressbar")).toBeInTheDocument();
    const members = screen.getByRole("list", { name: /team members/i });
    expect(within(members).getByText("Working")).toBeInTheDocument();
    expect(screen.getByText("12 rows audited")).toBeVisible();
    expect(screen.getByRole("button", { name: /stop/i })).toBeEnabled();
    expect((await axe(container)).violations).toHaveLength(0);
  });

  it("reports a failed run", () => {
    render(
      <LiveRun
        run={run({
          status: "failed",
          error: { code: "x", message: "The analysis failed unexpectedly." },
        })}
        team={team}
        locale="ar"
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("failed unexpectedly");
  });
});

describe("DossierView", () => {
  it("leads with the summary and links recommendations to evidence", async () => {
    const user = userEvent.setup();
    const asked: string[] = [];
    render(
      <DossierView
        dossier={dossier}
        runId="run-1"
        locale="en"
        team={team}
        onAsk={(q) => asked.push(q)}
        onRerun={() => undefined}
      />,
    );
    expect(screen.getByText("Revenue grew.")).toBeVisible();
    expect(screen.getByText("2.5M")).toBeVisible();
    await user.click(
      screen.getByRole("button", { name: /what happened to north/i }),
    );
    expect(asked).toEqual(["What happened to North week by week?"]);
    await user.click(screen.getByRole("tab", { name: /recommendations/i }));
    expect(screen.getByText("Recovery plan for North")).toBeVisible();
    await user.click(
      screen.getByRole("button", { name: /evidence: why revenue fell/i }),
    );
    expect(screen.getByRole("tab", { name: /findings/i })).toHaveAttribute(
      "aria-selected",
      "true",
    );
    await user.click(
      screen.getByRole("button", { name: /how was this computed/i }),
    );
    expect(screen.getByText("additive_contribution_analysis")).toBeVisible();
    await user.click(screen.getByRole("tab", { name: /method/i }));
    expect(screen.getByText(/evidence register/i)).toBeVisible();
  });
});
