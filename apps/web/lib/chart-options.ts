/**
 * Chart option builders.
 *
 * Each returns a function of the resolved theme so light and dark are separately
 * chosen from the same ramps rather than flipped at render time.
 */
import type { Locale } from "./contracts";
import {
  baseOption,
  categoryAxis,
  compact,
  num,
  valueAxis,
  type VizTheme,
} from "./viz";

type Option = Record<string, unknown>;

const dash = (locale: Locale) => (locale === "ar" ? "—" : "—");

function tooltipRows(
  locale: Locale,
  theme: VizTheme,
  header: string,
  rows: Array<{ colour: string; label: string; value: string }>,
): string {
  const swatch = (colour: string) =>
    `<i style="display:inline-block;width:9px;height:9px;border-radius:3px;background:${colour};margin-inline-end:7px"></i>`;
  const body = rows
    .map(
      (row) =>
        `<div style="display:flex;gap:14px;justify-content:space-between;align-items:center;margin-top:3px">` +
        `<span style="color:${theme.inkMuted}">${swatch(row.colour)}${row.label}</span>` +
        `<b style="font-variant-numeric:tabular-nums">${row.value}</b></div>`,
    )
    .join("");
  return `<div style="font-weight:700;margin-bottom:2px">${header}</div>${body}`;
}

/**
 * History and forecast on one continuous line, with the interval drawn as a band.
 *
 * The band is the point of the chart: a forecast shown as a bare line invites the
 * reader to treat an estimate as a measurement. The lower bound is a transparent
 * stack base and the visible band is the width above it, so the fill tracks an
 * interval that need not be symmetric about zero.
 */
export function forecastOption(
  locale: Locale,
  history: Array<{ period: string; value: number; used_for_fitting?: boolean }>,
  forecast: Array<{
    period: string;
    value: number;
    lower: number;
    upper: number;
  }>,
  options: { unit?: string; intervalLevel?: number } = {},
) {
  return (theme: VizTheme): Option => {
    const ar = locale === "ar";
    const periods = [
      ...history.map((row) => row.period),
      ...forecast.map((row) => row.period.slice(0, 7)),
    ];
    // History excluded from the fit is drawn on its own muted line. Annotating "18
    // periods excluded" without showing which ones leaves the reader unable to check.
    const anyExcluded = history.some((row) => row.used_for_fitting === false);
    const actual = [
      ...history.map((row) =>
        row.used_for_fitting === false ? null : row.value,
      ),
      ...forecast.map(() => null as number | null),
    ];
    const excludedLine = anyExcluded
      ? [
          ...history.map((row, index) =>
            row.used_for_fitting === false ||
            // Join to the first fitted point so the two lines meet.
            history[index - 1]?.used_for_fitting === false
              ? row.value
              : (null as number | null),
          ),
          ...forecast.map(() => null as number | null),
        ]
      : [];
    // Repeat the last observed point so the two lines meet with no visible gap.
    const projected = [
      ...history.slice(0, -1).map(() => null as number | null),
      ...(history.length ? [history[history.length - 1].value] : []),
      ...forecast.map((row) => row.value),
    ];
    const base = [
      ...history.map(() => null as number | null),
      ...forecast.map((row) => row.lower),
    ];
    const span = [
      ...history.map(() => null as number | null),
      ...forecast.map((row) => row.upper - row.lower),
    ];
    const excluded = history.filter(
      (row) => row.used_for_fitting === false,
    ).length;
    const excludedLabel = ar ? "خارج نطاق الملاءمة" : "Excluded from the fit";
    const level = options.intervalLevel
      ? `${Math.round(options.intervalLevel * 100)}%`
      : "";

    return {
      ...baseOption(theme, locale),
      grid: { left: 8, right: 8, top: 34, bottom: 8, containLabel: true },
      legend: {
        ...baseOption(theme, locale).legend,
        data: [
          ar ? "المرصود" : "Observed",
          ...(anyExcluded ? [excludedLabel] : []),
          ar ? "المتوقع" : "Projected",
          ar ? `فاصل ${level}` : `${level} interval`,
        ],
        top: 0,
      },
      tooltip: {
        ...baseOption(theme, locale).tooltip,
        trigger: "axis",
        axisPointer: {
          type: "line",
          lineStyle: { color: theme.axis, type: "dashed" },
        },
        formatter: (
          params: Array<{ dataIndex: number; axisValue: string }>,
        ) => {
          const index = params[0]?.dataIndex ?? 0;
          const offset = index - history.length;
          if (offset >= 0) {
            const row = forecast[offset];
            return tooltipRows(locale, theme, row.period.slice(0, 7), [
              {
                colour: theme.series[0],
                label: ar ? "المتوقع" : "Projected",
                value: num(row.value, locale),
              },
              {
                colour: theme.band,
                label: ar ? `فاصل ${level}` : `${level} interval`,
                value: `${num(row.lower, locale)} – ${num(row.upper, locale)}`,
              },
            ]);
          }
          const row = history[index];
          return tooltipRows(locale, theme, row.period, [
            {
              colour: theme.ink,
              label: ar ? "المرصود" : "Observed",
              value: num(row.value, locale),
            },
            ...(row.used_for_fitting === false
              ? [
                  {
                    colour: theme.status.warning,
                    label: ar ? "خارج نطاق الملاءمة" : "Excluded from fit",
                    value: ar ? "نعم" : "Yes",
                  },
                ]
              : []),
          ]);
        },
      },
      xAxis: {
        ...categoryAxis(theme, locale),
        data: periods,
        boundaryGap: false,
      },
      yAxis: valueAxis(theme, locale, options.unit),
      series: [
        ...(anyExcluded
          ? [
              {
                name: excludedLabel,
                type: "line" as const,
                data: excludedLine,
                symbol: "circle" as const,
                symbolSize: 6,
                lineStyle: {
                  width: 1.5,
                  color: theme.axis,
                  type: "dotted" as const,
                },
                itemStyle: { color: theme.axis },
                z: 2,
              },
            ]
          : []),
        {
          name: ar ? "المرصود" : "Observed",
          type: "line",
          data: actual,
          symbol: "circle",
          symbolSize: 8,
          showSymbol: history.length <= 24,
          lineStyle: { width: 2, color: theme.ink },
          itemStyle: {
            color: theme.ink,
            borderColor: theme.surface,
            borderWidth: 2,
          },
          z: 4,
        },
        {
          name: ar ? "المتوقع" : "Projected",
          type: "line",
          data: projected,
          symbol: "circle",
          symbolSize: 8,
          lineStyle: { width: 2, color: theme.series[0], type: "dashed" },
          itemStyle: {
            color: theme.series[0],
            borderColor: theme.surface,
            borderWidth: 2,
          },
          z: 3,
        },
        {
          name: ar ? `فاصل ${level}` : `${level} interval`,
          type: "line",
          stack: "interval",
          data: base,
          symbol: "none",
          lineStyle: { opacity: 0 },
          areaStyle: { opacity: 0 },
          silent: true,
          z: 1,
        },
        {
          name: ar ? `فاصل ${level}` : `${level} interval`,
          type: "line",
          stack: "interval",
          data: span,
          symbol: "none",
          lineStyle: { opacity: 0 },
          areaStyle: { color: theme.band },
          silent: true,
          z: 1,
        },
      ],
    };
  };
}

/** A single measure over time, one hue, optional comparison period. */
export function trendOption(
  locale: Locale,
  rows: Array<{
    label: string;
    value: number | null;
    comparison?: number | null;
  }>,
  options: {
    unit?: string;
    currentLabel?: string;
    comparisonLabel?: string;
  } = {},
) {
  return (theme: VizTheme): Option => {
    const ar = locale === "ar";
    const hasComparison = rows.some((row) => row.comparison != null);
    const current =
      options.currentLabel ?? (ar ? "الفترة الحالية" : "Current period");
    const previous =
      options.comparisonLabel ?? (ar ? "فترة المقارنة" : "Comparison");
    return {
      ...baseOption(theme, locale),
      legend: hasComparison
        ? {
            ...baseOption(theme, locale).legend,
            data: [current, previous],
            top: 0,
          }
        : { show: false },
      grid: {
        left: 8,
        right: 8,
        top: hasComparison ? 32 : 12,
        bottom: 8,
        containLabel: true,
      },
      tooltip: {
        ...baseOption(theme, locale).tooltip,
        trigger: "axis",
        axisPointer: {
          type: "line",
          lineStyle: { color: theme.axis, type: "dashed" },
        },
        formatter: (
          params: Array<{ dataIndex: number; axisValue: string }>,
        ) => {
          const row = rows[params[0]?.dataIndex ?? 0];
          return tooltipRows(locale, theme, row.label, [
            {
              colour: theme.series[0],
              label: current,
              value: row.value == null ? dash(locale) : num(row.value, locale),
            },
            ...(hasComparison
              ? [
                  {
                    colour: theme.inkMuted,
                    label: previous,
                    value:
                      row.comparison == null
                        ? dash(locale)
                        : num(row.comparison, locale),
                  },
                ]
              : []),
          ]);
        },
      },
      xAxis: {
        ...categoryAxis(theme, locale),
        data: rows.map((row) => row.label),
        boundaryGap: false,
      },
      yAxis: valueAxis(theme, locale, options.unit),
      series: [
        {
          name: current,
          type: "line",
          data: rows.map((row) => row.value),
          smooth: 0.25,
          symbol: "circle",
          symbolSize: 8,
          showSymbol: rows.length <= 24,
          lineStyle: { width: 2, color: theme.series[0] },
          itemStyle: {
            color: theme.series[0],
            borderColor: theme.surface,
            borderWidth: 2,
          },
          areaStyle: {
            color: {
              type: "linear",
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: theme.band },
                { offset: 1, color: "rgba(0,0,0,0)" },
              ],
            },
          },
        },
        ...(hasComparison
          ? [
              {
                name: previous,
                type: "line",
                data: rows.map((row) => row.comparison ?? null),
                smooth: 0.25,
                symbol: "none",
                lineStyle: { width: 2, color: theme.inkMuted, type: "dashed" },
              },
            ]
          : []),
      ],
    };
  };
}

/**
 * Ranked categories. One series, one hue — a value ramp here would double-encode
 * bar length as colour and spend the only free channel on nothing.
 */
export function rankedBarOption(
  locale: Locale,
  rows: Array<{ label: string; value: number; highlight?: boolean }>,
  options: { unit?: string; horizontal?: boolean } = {},
) {
  return (theme: VizTheme): Option => {
    const horizontal = options.horizontal ?? true;
    const ordered = [...rows].sort((a, b) => b.value - a.value);
    const display = horizontal ? [...ordered].reverse() : ordered;
    const bar = {
      type: "bar" as const,
      data: display.map((row) => ({
        value: row.value,
        itemStyle: {
          color: row.highlight ? theme.series[1] : theme.series[0],
          borderRadius: horizontal ? [0, 4, 4, 0] : [4, 4, 0, 0],
        },
      })),
      barMaxWidth: 26,
      label: {
        show: display.length <= 12,
        position: horizontal ? ("right" as const) : ("top" as const),
        color: theme.inkMuted,
        fontSize: 11,
        formatter: ({ value }: { value: number }) => compact(value, locale),
      },
    };
    const labels = display.map((row) => row.label);
    return {
      ...baseOption(theme, locale),
      legend: { show: false },
      grid: { left: 8, right: 24, top: 12, bottom: 8, containLabel: true },
      tooltip: {
        ...baseOption(theme, locale).tooltip,
        trigger: "item",
        formatter: (params: { dataIndex: number }) => {
          const row = display[params.dataIndex];
          return tooltipRows(locale, theme, row.label, [
            {
              colour: row.highlight ? theme.series[1] : theme.series[0],
              label: options.unit ?? (locale === "ar" ? "القيمة" : "Value"),
              value: num(row.value, locale),
            },
          ]);
        },
      },
      xAxis: horizontal
        ? valueAxis(theme, locale, options.unit)
        : { ...categoryAxis(theme, locale), data: labels },
      yAxis: horizontal
        ? { ...categoryAxis(theme, locale), data: labels, inverse: false }
        : valueAxis(theme, locale, options.unit),
      series: [bar],
    };
  };
}

/** Contribution and its running share — the standard concentration read. */
export function paretoOption(
  locale: Locale,
  rows: Array<{ label: string; value: number }>,
  options: { unit?: string } = {},
) {
  return (theme: VizTheme): Option => {
    const ar = locale === "ar";
    const ordered = [...rows].sort((a, b) => b.value - a.value).slice(0, 14);
    const total = ordered.reduce((sum, row) => sum + row.value, 0) || 1;
    let running = 0;
    const cumulative = ordered.map((row) => {
      running += row.value;
      return Math.round((running / total) * 1000) / 10;
    });
    const contribution = ar ? "المساهمة" : "Contribution";
    const share = ar ? "الحصة التراكمية" : "Cumulative share";
    return {
      ...baseOption(theme, locale),
      legend: {
        ...baseOption(theme, locale).legend,
        data: [contribution, share],
        top: 0,
      },
      grid: { left: 8, right: 8, top: 34, bottom: 8, containLabel: true },
      tooltip: {
        ...baseOption(theme, locale).tooltip,
        trigger: "axis",
        axisPointer: { type: "shadow" },
        formatter: (params: Array<{ dataIndex: number }>) => {
          const index = params[0]?.dataIndex ?? 0;
          return tooltipRows(locale, theme, ordered[index].label, [
            {
              colour: theme.series[0],
              label: contribution,
              value: num(ordered[index].value, locale),
            },
            {
              colour: theme.series[1],
              label: share,
              value: `${cumulative[index]}%`,
            },
          ]);
        },
      },
      xAxis: {
        ...categoryAxis(theme, locale),
        data: ordered.map((row) => row.label),
      },
      // Cumulative share is a percentage of the same measure, not a second quantity;
      // it is drawn on a 0-100 axis that is labelled as such rather than a free scale.
      yAxis: [
        valueAxis(theme, locale, options.unit),
        {
          ...valueAxis(theme, locale, "%"),
          position: ar ? "left" : "right",
          max: 100,
          min: 0,
          splitLine: { show: false },
        },
      ],
      series: [
        {
          name: contribution,
          type: "bar",
          data: ordered.map((row) => row.value),
          barMaxWidth: 30,
          itemStyle: { color: theme.series[0], borderRadius: [4, 4, 0, 0] },
        },
        {
          name: share,
          type: "line",
          yAxisIndex: 1,
          data: cumulative,
          symbol: "circle",
          symbolSize: 7,
          lineStyle: { width: 2, color: theme.series[1] },
          itemStyle: {
            color: theme.series[1],
            borderColor: theme.surface,
            borderWidth: 2,
          },
          markLine: {
            silent: true,
            symbol: "none",
            data: [{ yAxis: 80 }],
            lineStyle: { color: theme.axis, type: "dashed", width: 1 },
            label: {
              formatter: "80%",
              color: theme.inkMuted,
              fontSize: 10,
              position: ar ? "insideStartTop" : "insideEndTop",
            },
          },
        },
      ],
    };
  };
}

/** Five quality dimensions on one shape. */
export function radarOption(
  locale: Locale,
  dimensions: Record<string, number>,
  labels: Record<string, string>,
) {
  return (theme: VizTheme): Option => ({
    ...baseOption(theme, locale),
    legend: { show: false },
    tooltip: {
      ...baseOption(theme, locale).tooltip,
      trigger: "item",
      formatter: () =>
        tooltipRows(
          locale,
          theme,
          locale === "ar" ? "أبعاد الجودة" : "Quality dimensions",
          Object.entries(dimensions).map(([key, value]) => ({
            colour: theme.series[0],
            label: labels[key] ?? key,
            value: `${Math.round(value * 100)}%`,
          })),
        ),
    },
    radar: {
      indicator: Object.keys(dimensions).map((key) => ({
        name: labels[key] ?? key,
        max: 100,
      })),
      shape: "polygon",
      splitNumber: 4,
      axisName: { color: theme.inkMuted, fontSize: 11 },
      splitLine: { lineStyle: { color: theme.grid } },
      splitArea: { areaStyle: { color: [theme.surface, theme.surfaceSoft] } },
      axisLine: { lineStyle: { color: theme.grid } },
    },
    series: [
      {
        type: "radar",
        data: [
          {
            value: Object.values(dimensions).map(
              (value) => Math.round(value * 1000) / 10,
            ),
            name: locale === "ar" ? "الجودة" : "Quality",
            lineStyle: { width: 2, color: theme.series[0] },
            itemStyle: { color: theme.series[0] },
            areaStyle: { color: theme.band },
          },
        ],
      },
    ],
  });
}

/** Magnitude across two categorical axes — one hue, light to dark. */
export function heatmapOption(
  locale: Locale,
  rows: Array<{ x: string; y: string; value: number }>,
  options: { unit?: string; xLabel?: string; yLabel?: string } = {},
) {
  return (theme: VizTheme): Option => {
    const xs = [...new Set(rows.map((row) => row.x))];
    const ys = [...new Set(rows.map((row) => row.y))];
    const values = rows.map((row) => row.value);
    return {
      ...baseOption(theme, locale),
      legend: { show: false },
      grid: { left: 8, right: 8, top: 12, bottom: 56, containLabel: true },
      tooltip: {
        ...baseOption(theme, locale).tooltip,
        trigger: "item",
        formatter: (params: { data: [number, number, number] }) =>
          tooltipRows(
            locale,
            theme,
            `${ys[params.data[1]]} · ${xs[params.data[0]]}`,
            [
              {
                colour: theme.series[0],
                label: options.unit ?? (locale === "ar" ? "القيمة" : "Value"),
                value: num(params.data[2], locale),
              },
            ],
          ),
      },
      xAxis: {
        ...categoryAxis(theme, locale),
        data: xs,
        splitArea: { show: true },
      },
      yAxis: { ...categoryAxis(theme, locale), data: ys, inverse: false },
      visualMap: {
        min: Math.min(...values, 0),
        max: Math.max(...values, 1),
        calculable: true,
        orient: "horizontal",
        left: "center",
        bottom: 4,
        itemWidth: 12,
        itemHeight: 90,
        textStyle: { color: theme.inkMuted, fontSize: 11 },
        inRange: { color: theme.sequential },
      },
      series: [
        {
          type: "heatmap",
          data: rows.map((row) => [
            xs.indexOf(row.x),
            ys.indexOf(row.y),
            row.value,
          ]),
          itemStyle: {
            borderColor: theme.surface,
            borderWidth: 2,
            borderRadius: 3,
          },
          emphasis: { itemStyle: { borderColor: theme.ink, borderWidth: 2 } },
        },
      ],
    };
  };
}

/**
 * Two measures across a categorical grid, with height as the third.
 *
 * Depth costs readability, so this is reserved for the case where a flat heatmap
 * genuinely loses the shape — a surface with a ridge or a saddle. Everything the
 * bars encode is also in the table view.
 */
export function surface3dOption(
  locale: Locale,
  rows: Array<{ x: string; y: string; value: number }>,
  options: { unit?: string } = {},
) {
  return (theme: VizTheme): Option => {
    const xs = [...new Set(rows.map((row) => row.x))];
    const ys = [...new Set(rows.map((row) => row.y))];
    const values = rows.map((row) => row.value);
    const axis = {
      axisLine: { lineStyle: { color: theme.axis } },
      axisLabel: { color: theme.inkMuted, fontSize: 10 },
      splitLine: { lineStyle: { color: theme.grid } },
      nameTextStyle: { color: theme.inkMuted },
    };
    return {
      ...baseOption(theme, locale),
      legend: { show: false },
      tooltip: {
        ...baseOption(theme, locale).tooltip,
        formatter: (params: { data: [number, number, number] }) =>
          tooltipRows(
            locale,
            theme,
            `${ys[params.data[1]]} · ${xs[params.data[0]]}`,
            [
              {
                colour: theme.series[0],
                label: options.unit ?? (locale === "ar" ? "القيمة" : "Value"),
                value: num(params.data[2], locale),
              },
            ],
          ),
      },
      visualMap: {
        min: Math.min(...values, 0),
        max: Math.max(...values, 1),
        calculable: true,
        orient: "horizontal",
        left: "center",
        bottom: 0,
        itemWidth: 12,
        textStyle: { color: theme.inkMuted, fontSize: 11 },
        inRange: { color: theme.sequential },
      },
      xAxis3D: { type: "category", data: xs, ...axis },
      yAxis3D: { type: "category", data: ys, ...axis },
      zAxis3D: { type: "value", ...axis },
      grid3D: {
        boxWidth: 110,
        boxDepth: 78,
        boxHeight: 58,
        viewControl: {
          alpha: 24,
          beta: 32,
          distance: 190,
          rotateSensitivity: 1,
        },
        light: {
          main: { intensity: 1.1, shadow: true, alpha: 40, beta: 30 },
          ambient: { intensity: 0.35 },
        },
        environment: theme.surface,
        axisPointer: { lineStyle: { color: theme.axis } },
      },
      series: [
        {
          type: "bar3D",
          shading: "lambert",
          data: rows.map((row) => [
            xs.indexOf(row.x),
            ys.indexOf(row.y),
            row.value,
          ]),
          barSize: 6,
          bevelSize: 0.25,
          itemStyle: { opacity: 0.95 },
          emphasis: { itemStyle: { color: theme.series[1] } },
        },
      ],
    };
  };
}

/** Two numeric columns against each other, with the fitted line drawn. */
export function scatterOption(
  locale: Locale,
  points: Array<[number, number]>,
  options: {
    xLabel: string;
    yLabel: string;
    fit?: { slope: number; intercept: number };
  },
) {
  return (theme: VizTheme): Option => {
    const xs = points.map((point) => point[0]);
    const min = Math.min(...xs);
    const max = Math.max(...xs);
    return {
      ...baseOption(theme, locale),
      legend: { show: false },
      grid: { left: 8, right: 16, top: 16, bottom: 8, containLabel: true },
      tooltip: {
        ...baseOption(theme, locale).tooltip,
        trigger: "item",
        formatter: (params: { data: [number, number] }) =>
          tooltipRows(locale, theme, "", [
            {
              colour: theme.series[0],
              label: options.xLabel,
              value: num(params.data[0], locale),
            },
            {
              colour: theme.series[2],
              label: options.yLabel,
              value: num(params.data[1], locale),
            },
          ]),
      },
      xAxis: {
        ...valueAxis(theme, locale),
        name: options.xLabel,
        nameLocation: "middle",
        nameGap: 28,
        nameTextStyle: { color: theme.inkMuted, fontSize: 11 },
        scale: true,
      },
      yAxis: {
        ...valueAxis(theme, locale),
        name: options.yLabel,
        nameTextStyle: { color: theme.inkMuted, fontSize: 11 },
        scale: true,
      },
      series: [
        {
          type: "scatter",
          data: points,
          symbolSize: 9,
          itemStyle: {
            color: theme.series[0],
            opacity: 0.7,
            borderColor: theme.surface,
            borderWidth: 1,
          },
        },
        ...(options.fit
          ? [
              {
                type: "line",
                data: [
                  [min, options.fit.intercept + options.fit.slope * min],
                  [max, options.fit.intercept + options.fit.slope * max],
                ],
                symbol: "none",
                silent: true,
                lineStyle: { color: theme.series[1], width: 2, type: "dashed" },
              },
            ]
          : []),
      ],
    };
  };
}
