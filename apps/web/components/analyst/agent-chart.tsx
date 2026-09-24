"use client";

import { useMemo } from "react";
import type { Locale } from "@/lib/contracts";
import type { ChartSpec } from "@/lib/analyst";
import { loc } from "@/lib/analyst";
import { chartOption, chartTable, supportsChart } from "@/lib/agent-charts";
import { Chart } from "../chart";

export function AgentChart({
  spec,
  locale,
  height = 280,
  source,
}: {
  spec: ChartSpec | null | undefined;
  locale: Locale;
  height?: number;
  source?: string;
}) {
  const option = useMemo(
    () => (spec ? chartOption(spec, locale) : null),
    [spec, locale],
  );
  const table = useMemo(
    () => (spec ? chartTable(spec, locale) : null),
    [spec, locale],
  );
  if (!spec || !option || !table || !supportsChart(spec)) return null;
  const rows = Math.max(spec.y?.length ?? 0, spec.x?.length ?? 0);
  const computedHeight =
    spec.type === "bar_horizontal"
      ? Math.max(180, (spec.x?.length ?? 4) * 34)
      : spec.type === "heatmap"
        ? Math.max(260, Math.min(520, rows * 28 + 80))
        : height;
  return (
    <Chart
      locale={locale}
      title={loc(spec.title, locale)}
      option={option}
      table={table}
      height={computedHeight}
      source={source}
    />
  );
}
