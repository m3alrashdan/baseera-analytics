/**
 * Turn the analyst team's chart specifications into themed ECharts options plus the
 * table every chart must carry. One adapter for every chart the agents produce.
 */
import type { ChartTableColumn } from "@/components/chart";
import type { Locale } from "./contracts";
import type { ChartSpec } from "./analyst";
import {
  baseOption,
  categoryAxis,
  compact,
  valueAxis,
  type VizTheme,
} from "./viz";

type Option = Record<string, unknown>;

const SERIES_LABELS: Record<string, [string, string]> = {
  trend: ["Trend", "الاتجاه"],
  history: ["Actual", "الفعلي"],
  forecast: ["Forecast", "المتوقع"],
  cumulative_share: ["Cumulative share", "الحصة التراكمية"],
  share_of_explained: ["Share of explained", "الحصة من التفسير"],
  share_of_value: ["Share of value", "الحصة من القيمة"],
  share_of_entities: ["Share of customers", "الحصة من العملاء"],
  index: ["Seasonal index", "المؤشر الموسمي"],
  count: ["Count", "العدد"],
};

export function seriesLabel(name: string, locale: Locale): string {
  const entry = SERIES_LABELS[name];
  return entry ? entry[locale === "ar" ? 1 : 0] : name;
}

const isNumber = (value: unknown): value is number =>
  typeof value === "number" && Number.isFinite(value);

function isShareSeries(values: unknown[]): boolean {
  const numbers = values.filter(isNumber);
  return numbers.length > 0 && numbers.every((v) => v >= -1 && v <= 1);
}

export function supportsChart(spec: ChartSpec | null | undefined): boolean {
  return Boolean(
    spec &&
      [
        "line",
        "forecast",
        "bar",
        "bar_horizontal",
        "pareto",
        "waterfall",
        "heatmap",
        "scatter",
      ].includes(spec.type),
  );
}

export function chartOption(spec: ChartSpec, locale: Locale) {
  const ar = locale === "ar";
  return (theme: VizTheme): Option => {
    const base = baseOption(theme, locale);
    const labels = (ar && spec.x_ar?.length ? spec.x_ar : (spec.x ?? [])).map(
      String,
    );
    switch (spec.type) {
      case "forecast": {
        const history = spec.history ?? [];
        const future = spec.forecast ?? [];
        const lower = spec.lower ?? [];
        const upper = spec.upper ?? [];
        const pad = (n: number) =>
          Array.from({ length: n }, () => null as number | null);
        return {
          ...base,
          legend: {
            ...base.legend,
            top: 0,
            data: [
              seriesLabel("history", locale),
              seriesLabel("forecast", locale),
              ar ? "فاصل الثقة" : "Interval",
            ],
          },
          grid: { ...base.grid, top: 36 },
          tooltip: { ...base.tooltip, trigger: "axis" },
          xAxis: {
            ...categoryAxis(theme, locale),
            data: labels,
            boundaryGap: false,
          },
          yAxis: valueAxis(theme, locale),
          series: [
            {
              name: "lower",
              type: "line",
              data: [...pad(history.length), ...lower],
              stack: "band",
              lineStyle: { opacity: 0 },
              symbol: "none",
              tooltip: { show: false },
            },
            {
              name: ar ? "فاصل الثقة" : "Interval",
              type: "line",
              data: [
                ...pad(history.length),
                ...upper.map((u, i) => u - (lower[i] ?? 0)),
              ],
              stack: "band",
              lineStyle: { opacity: 0 },
              areaStyle: { color: theme.band },
              symbol: "none",
            },
            {
              name: seriesLabel("history", locale),
              type: "line",
              data: [...history, ...pad(future.length)],
              symbol: "none",
              lineStyle: { width: 2, color: theme.series[0] },
              itemStyle: { color: theme.series[0] },
            },
            {
              name: seriesLabel("forecast", locale),
              type: "line",
              data: [
                ...pad(Math.max(0, history.length - 1)),
                history[history.length - 1] ?? null,
                ...future,
              ],
              symbol: "circle",
              symbolSize: 5,
              lineStyle: { width: 2, type: "dashed", color: theme.series[1] },
              itemStyle: { color: theme.series[1] },
            },
          ],
        };
      }
      case "line": {
        const series = (spec.series ?? []).slice(0, 6);
        const share = series.every((s) => isShareSeries(s.data));
        const markers = new Set((spec.markers ?? []).map((m) => m.x));
        return {
          ...base,
          legend: { ...base.legend, top: 0, show: series.length > 1 },
          grid: { ...base.grid, top: series.length > 1 ? 36 : 16 },
          tooltip: { ...base.tooltip, trigger: "axis" },
          xAxis: {
            ...categoryAxis(theme, locale),
            data: labels,
            boundaryGap: false,
          },
          yAxis: {
            ...valueAxis(theme, locale),
            ...(share
              ? {
                  axisLabel: {
                    color: theme.inkMuted,
                    formatter: (v: number) => `${Math.round(v * 100)}%`,
                  },
                }
              : {}),
          },
          series: series.map((s, index) => ({
            name: seriesLabel(s.name, locale),
            type: "line",
            data: s.data.map((v, i) =>
              markers.has(labels[i])
                ? {
                    value: v,
                    symbol: "circle",
                    symbolSize: 9,
                    itemStyle: { color: theme.status.serious },
                  }
                : v,
            ),
            symbol: "none",
            smooth: false,
            lineStyle: {
              width: s.style === "dashed" ? 1.5 : 2,
              type: s.style === "dashed" ? "dashed" : "solid",
              color:
                s.style === "dashed"
                  ? theme.inkMuted
                  : theme.series[index % theme.series.length],
            },
            itemStyle: {
              color:
                s.style === "dashed"
                  ? theme.inkMuted
                  : theme.series[index % theme.series.length],
            },
          })),
        };
      }
      case "bar":
      case "pareto": {
        const [first, second] = spec.series ?? [];
        const data = (first?.data ?? []).map((v) => (isNumber(v) ? v : 0));
        const share =
          isShareSeries(data) &&
          spec.type === "bar" &&
          first?.name?.startsWith("share");
        return {
          ...base,
          legend: { ...base.legend, top: 0, show: Boolean(second) },
          grid: { ...base.grid, top: second ? 36 : 16 },
          tooltip: { ...base.tooltip, trigger: "axis" },
          xAxis: {
            ...categoryAxis(theme, locale),
            data: labels,
            axisLabel: {
              color: theme.inkMuted,
              interval: 0,
              rotate: labels.length > 6 ? 30 : 0,
              hideOverlap: true,
            },
          },
          yAxis: [
            share
              ? {
                  ...valueAxis(theme, locale),
                  axisLabel: {
                    color: theme.inkMuted,
                    formatter: (v: number) => `${Math.round(v * 100)}%`,
                  },
                }
              : valueAxis(theme, locale),
            ...(second
              ? [
                  {
                    type: "value",
                    max: 1,
                    position: ar ? "left" : "right",
                    axisLabel: {
                      color: theme.inkMuted,
                      formatter: (v: number) => `${Math.round(v * 100)}%`,
                    },
                    splitLine: { show: false },
                  },
                ]
              : []),
          ],
          series: [
            {
              name: seriesLabel(first?.name ?? "", locale),
              type: "bar",
              data,
              barMaxWidth: 36,
              itemStyle: { color: theme.series[0], borderRadius: [4, 4, 0, 0] },
              ...(isNumber(spec.reference)
                ? {
                    markLine: {
                      symbol: "none",
                      label: { show: false },
                      lineStyle: {
                        color: theme.status.warning,
                        type: "dashed",
                      },
                      data: [{ yAxis: spec.reference }],
                    },
                  }
                : {}),
            },
            ...(second
              ? [
                  {
                    name: seriesLabel(second.name, locale),
                    type: "line",
                    yAxisIndex: 1,
                    data: second.data,
                    symbol: "circle",
                    symbolSize: 5,
                    lineStyle: { color: theme.series[1] },
                    itemStyle: { color: theme.series[1] },
                  },
                ]
              : []),
          ],
        };
      }
      case "bar_horizontal": {
        const first = (spec.series ?? [])[0];
        const data = (first?.data ?? []).map((v) => (isNumber(v) ? v : 0));
        return {
          ...base,
          legend: { show: false },
          grid: { ...base.grid, top: 8, right: 28, left: 12 },
          tooltip: {
            ...base.tooltip,
            trigger: "axis",
            valueFormatter: (v: number) => `${(v * 100).toFixed(1)}%`,
          },
          xAxis: {
            type: "value",
            inverse: ar,
            axisLabel: {
              color: theme.inkMuted,
              formatter: (v: number) => `${Math.round(v * 100)}%`,
            },
            splitLine: { lineStyle: { color: theme.grid } },
          },
          yAxis: {
            type: "category",
            data: [...labels].reverse(),
            position: ar ? "right" : "left",
            axisLabel: {
              color: theme.ink,
              fontSize: 11,
              width: 150,
              overflow: "truncate",
            },
            axisTick: { show: false },
            axisLine: { lineStyle: { color: theme.axis } },
          },
          series: [
            {
              name: seriesLabel(first?.name ?? "", locale),
              type: "bar",
              data: [...data].reverse(),
              barMaxWidth: 22,
              itemStyle: {
                color: theme.series[0],
                borderRadius: ar ? [4, 0, 0, 4] : [0, 4, 4, 0],
              },
            },
          ],
        };
      }
      case "waterfall": {
        const deltas = spec.deltas ?? [];
        const start = spec.start ?? 0;
        const end = spec.end ?? 0;
        const bases: number[] = [0];
        const visible: Array<{ value: number; itemStyle: { color: string } }> =
          [{ value: start, itemStyle: { color: theme.inkMuted } }];
        let running = start;
        for (const delta of deltas) {
          const low = delta >= 0 ? running : running + delta;
          bases.push(low);
          visible.push({
            value: Math.abs(delta),
            itemStyle: {
              color: delta >= 0 ? theme.status.good : theme.status.critical,
            },
          });
          running += delta;
        }
        bases.push(0);
        visible.push({ value: end, itemStyle: { color: theme.inkMuted } });
        const minimum = Math.min(0, ...bases);
        return {
          ...base,
          grid: { ...base.grid, top: 16 },
          tooltip: {
            ...base.tooltip,
            trigger: "axis",
            formatter: (params: Array<{ dataIndex: number }>) => {
              const index = params[0]?.dataIndex ?? 0;
              const label = labels[index] ?? "";
              if (index === 0) return `${label}: ${compact(start, locale)}`;
              if (index === labels.length - 1)
                return `${label}: ${compact(end, locale)}`;
              const delta = deltas[index - 1] ?? 0;
              return `${label}: ${delta >= 0 ? "+" : ""}${compact(delta, locale)}`;
            },
          },
          xAxis: {
            ...categoryAxis(theme, locale),
            data: labels,
            axisLabel: {
              color: theme.inkMuted,
              interval: 0,
              rotate: labels.length > 6 ? 30 : 0,
            },
          },
          yAxis: {
            ...valueAxis(theme, locale),
            min:
              minimum < 0
                ? undefined
                : Math.floor(
                    Math.min(...bases.filter((b) => b > 0), start, end) * 0.8,
                  ),
          },
          series: [
            {
              type: "bar",
              stack: "w",
              data: bases,
              itemStyle: { color: "transparent" },
              tooltip: { show: false },
            },
            { type: "bar", stack: "w", data: visible, barMaxWidth: 36 },
          ],
        };
      }
      case "heatmap": {
        const xs = (spec.x ?? []).map(String);
        const ys = (spec.y ?? []).map(String);
        const cells: Array<[number, number, number | null]> = [];
        (spec.values ?? []).forEach((row, yi) =>
          row.forEach((value, xi) =>
            cells.push([
              xi,
              yi,
              isNumber(value) ? Number(value.toFixed(3)) : null,
            ]),
          ),
        );
        const numbers = cells.map((c) => c[2]).filter(isNumber);
        const diverging = numbers.some((v) => v < 0);
        return {
          ...base,
          grid: { ...base.grid, top: 8, bottom: 40 },
          tooltip: { ...base.tooltip, position: "top" },
          xAxis: {
            type: "category",
            data: xs,
            inverse: ar,
            axisLabel: {
              color: theme.inkMuted,
              rotate: xs.length > 5 ? 30 : 0,
            },
            splitArea: { show: false },
          },
          yAxis: {
            type: "category",
            data: ys,
            position: ar ? "right" : "left",
            axisLabel: { color: theme.inkMuted },
          },
          visualMap: {
            min: diverging ? -1 : Math.min(0, ...numbers),
            max: diverging ? 1 : Math.max(1, ...numbers),
            calculable: false,
            orient: "horizontal",
            left: "center",
            bottom: 0,
            itemHeight: 120,
            textStyle: { color: theme.inkMuted },
            inRange: { color: diverging ? theme.diverging : theme.sequential },
          },
          series: [
            {
              type: "heatmap",
              data: cells,
              label: {
                show: xs.length <= 8 && ys.length <= 12,
                color: theme.ink,
                fontSize: 10,
                formatter: (p: { value: [number, number, number] }) =>
                  isNumber(p.value[2])
                    ? diverging
                      ? p.value[2].toFixed(2)
                      : Math.abs(p.value[2]) <= 1
                        ? `${Math.round(p.value[2] * 100)}%`
                        : compact(p.value[2], locale)
                    : "",
              },
            },
          ],
        };
      }
      case "scatter": {
        return {
          ...base,
          legend: { ...base.legend, top: 0 },
          grid: { ...base.grid, top: 36 },
          tooltip: { ...base.tooltip, trigger: "item" },
          xAxis: {
            type: "value",
            name: spec.x_label,
            nameLocation: "middle",
            nameGap: 26,
            inverse: ar,
            axisLabel: {
              color: theme.inkMuted,
              formatter: (v: number) => compact(v, locale),
            },
            splitLine: { lineStyle: { color: theme.grid } },
          },
          yAxis: {
            type: "value",
            name: spec.y_label,
            position: ar ? "right" : "left",
            axisLabel: {
              color: theme.inkMuted,
              formatter: (v: number) => compact(v, locale),
            },
            splitLine: { lineStyle: { color: theme.grid } },
          },
          series: (spec.series ?? []).slice(0, 6).map((s, index) => ({
            name: s.name,
            type: "scatter",
            data: s.data,
            symbolSize: 5,
            itemStyle: {
              color: theme.series[index % theme.series.length],
              opacity: 0.65,
            },
          })),
        };
      }
      default:
        return base;
    }
  };
}

export function chartTable(
  spec: ChartSpec,
  locale: Locale,
): { columns: ChartTableColumn[]; rows: Array<Record<string, unknown>> } {
  const ar = locale === "ar";
  const labels = (ar && spec.x_ar?.length ? spec.x_ar : (spec.x ?? [])).map(
    String,
  );
  const label = ar ? "الفئة" : "Label";
  if (spec.type === "forecast") {
    const history = spec.history ?? [];
    return {
      columns: [
        { key: "x", label: ar ? "الفترة" : "Period" },
        { key: "actual", label: seriesLabel("history", locale), numeric: true },
        {
          key: "forecast",
          label: seriesLabel("forecast", locale),
          numeric: true,
        },
        { key: "lower", label: ar ? "الحد الأدنى" : "Lower", numeric: true },
        { key: "upper", label: ar ? "الحد الأعلى" : "Upper", numeric: true },
      ],
      rows: labels.map((x, i) => ({
        x,
        actual: i < history.length ? history[i] : null,
        forecast:
          i >= history.length ? spec.forecast?.[i - history.length] : null,
        lower: i >= history.length ? spec.lower?.[i - history.length] : null,
        upper: i >= history.length ? spec.upper?.[i - history.length] : null,
      })),
    };
  }
  if (spec.type === "waterfall") {
    const deltas = spec.deltas ?? [];
    return {
      columns: [
        { key: "x", label },
        { key: "value", label: ar ? "القيمة" : "Value", numeric: true },
      ],
      rows: labels.map((x, i) => ({
        x,
        value:
          i === 0
            ? spec.start
            : i === labels.length - 1
              ? spec.end
              : deltas[i - 1],
      })),
    };
  }
  if (spec.type === "heatmap") {
    const xs = (spec.x ?? []).map(String);
    return {
      columns: [
        { key: "y", label },
        ...xs.map((x, i) => ({ key: `c${i}`, label: x, numeric: true })),
      ],
      rows: (spec.y ?? []).map((y, yi) => ({
        y,
        ...Object.fromEntries(
          xs.map((_, xi) => [`c${xi}`, spec.values?.[yi]?.[xi] ?? null]),
        ),
      })),
    };
  }
  if (spec.type === "scatter") {
    const rows: Array<Record<string, unknown>> = [];
    for (const s of spec.series ?? [])
      for (const point of (s.data as Array<[number, number]>).slice(0, 50))
        rows.push({ group: s.name, x: point[0], y: point[1] });
    return {
      columns: [
        { key: "group", label: ar ? "الشريحة" : "Segment" },
        { key: "x", label: spec.x_label ?? "x", numeric: true },
        { key: "y", label: spec.y_label ?? "y", numeric: true },
      ],
      rows,
    };
  }
  const series = spec.series ?? [];
  return {
    columns: [
      { key: "x", label },
      ...series.map((s, i) => ({
        key: `s${i}`,
        label: seriesLabel(s.name, locale),
        numeric: true,
      })),
    ],
    rows: labels.map((x, i) => ({
      x,
      ...Object.fromEntries(
        series.map((s, si) => [`s${si}`, s.data[i] ?? null]),
      ),
    })),
  };
}
