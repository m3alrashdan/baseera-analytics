/**
 * Chart tokens and ECharts theming.
 *
 * The categorical order is fixed and never cycled: a series keeps its hue when other
 * series are filtered out, so a reader who learned "North is teal" is not misled later.
 *
 * Both palettes were validated with the data-viz palette checker rather than chosen by
 * eye — light on #ffffff and dark on #121e26, all six slots passing the lightness band,
 * chroma floor, adjacent CVD separation and normal-vision floor. In light mode slots 4
 * and 5 fall below 3:1 against the surface, so every chart built on these tokens ships
 * a table view as the required relief.
 */
import type { Locale } from "./contracts";

export const SERIES_LIGHT = [
  "#0d8f9e", // teal — the product's own brand hue
  "#eb6834", // orange
  "#2a78d6", // blue
  "#eda100", // yellow
  "#e87ba4", // magenta
  "#4a3aa7", // violet
] as const;

export const SERIES_DARK = [
  "#22a3b0",
  "#d95926",
  "#3987e5",
  "#c98500",
  "#d55181",
  "#9085e9",
] as const;

export const MAX_SERIES = SERIES_LIGHT.length;

export interface StatusPalette {
  good: string;
  warning: string;
  serious: string;
  critical: string;
  neutral: string;
}

/** Status is reserved: it means a state, never "series 4". */
export const STATUS: { light: StatusPalette; dark: StatusPalette } = {
  light: {
    good: "#19704a",
    warning: "#99620a",
    serious: "#c0562c",
    critical: "#a4363d",
    neutral: "#52697e",
  },
  dark: {
    good: "#77d2a7",
    warning: "#f3c36d",
    serious: "#f0a06d",
    critical: "#f2a0a5",
    neutral: "#91a5a9",
  },
};

/** One hue, light to dark. Never a rainbow. */
export const SEQUENTIAL_LIGHT = [
  "#e8f4f5",
  "#c2e3e7",
  "#8ccdd4",
  "#4fb1bc",
  "#0d8f9e",
  "#0a6e79",
  "#074e56",
];
export const SEQUENTIAL_DARK = [
  "#0e2a2e",
  "#134047",
  "#1a5b64",
  "#227a86",
  "#2f9ba8",
  "#5cbcc6",
  "#93d6dd",
];

/** Two opposed hues with a neutral midpoint — never a hue in the middle. */
export const DIVERGING_LIGHT = [
  "#a4363d",
  "#d1736f",
  "#eab5ad",
  "#eceae5",
  "#9fc9d4",
  "#4b9fb2",
  "#0d6f7d",
];
export const DIVERGING_DARK = [
  "#f2a0a5",
  "#cf7a80",
  "#9a5b62",
  "#3a4d57",
  "#3f8593",
  "#2fa3b3",
  "#6fd0da",
];

export interface VizTheme {
  mode: "light" | "dark";
  series: readonly string[];
  sequential: string[];
  diverging: string[];
  status: StatusPalette;
  surface: string;
  surfaceSoft: string;
  ink: string;
  inkMuted: string;
  grid: string;
  axis: string;
  band: string;
}

export function vizTheme(mode: "light" | "dark"): VizTheme {
  return mode === "dark"
    ? {
        mode,
        series: SERIES_DARK,
        sequential: SEQUENTIAL_DARK,
        diverging: DIVERGING_DARK,
        status: STATUS.dark,
        surface: "#121e26",
        surfaceSoft: "#18262e",
        ink: "#e7eeee",
        inkMuted: "#91a5a9",
        grid: "#243642",
        axis: "#3a4d57",
        band: "rgba(34,163,176,0.16)",
      }
    : {
        mode,
        series: SERIES_LIGHT,
        sequential: SEQUENTIAL_LIGHT,
        diverging: DIVERGING_LIGHT,
        status: STATUS.light,
        surface: "#ffffff",
        surfaceSoft: "#f8f9f7",
        ink: "#142536",
        inkMuted: "#52697e",
        grid: "#e9edec",
        axis: "#c8d0d0",
        band: "rgba(13,143,158,0.14)",
      };
}

/** Read the theme the shell has stamped on <html>, falling back to the OS setting. */
export function currentMode(): "light" | "dark" {
  if (typeof document === "undefined") return "light";
  const stamped = document.documentElement.dataset.theme;
  if (stamped === "dark" || stamped === "light") return stamped;
  return typeof window !== "undefined" &&
    window.matchMedia?.("(prefers-color-scheme: dark)").matches
    ? "dark"
    : "light";
}

const AR_NUMBERS = new Intl.NumberFormat("ar-JO", { maximumFractionDigits: 2 });
const EN_NUMBERS = new Intl.NumberFormat("en-JO", { maximumFractionDigits: 2 });

export function num(value: number | null | undefined, locale: Locale): string {
  if (value == null || !Number.isFinite(value)) return "—";
  return (locale === "ar" ? AR_NUMBERS : EN_NUMBERS).format(value);
}

/** Compact axis labels: an axis reading 1,250,000 wastes the space a chart needs. */
export function compact(value: number, locale: Locale): string {
  const abs = Math.abs(value);
  const unit =
    abs >= 1e9
      ? [1e9, locale === "ar" ? "مليار" : "B"]
      : abs >= 1e6
        ? [1e6, locale === "ar" ? "م" : "M"]
        : abs >= 1e3
          ? [1e3, locale === "ar" ? "ألف" : "K"]
          : [1, ""];
  const scaled = value / (unit[0] as number);
  const text =
    Math.abs(scaled) >= 100
      ? scaled.toFixed(0)
      : scaled.toFixed(1).replace(/\.0$/, "");
  return `${text}${unit[1]}`;
}

/**
 * Base ECharts options every chart in the product starts from.
 *
 * Grid and axis lines are recessive, the tooltip is on by default, and animation is
 * short enough to feel responsive rather than decorative.
 */
export function baseOption(theme: VizTheme, locale: Locale) {
  const rtl = locale === "ar";
  return {
    backgroundColor: "transparent",
    animationDuration: 320,
    animationEasing: "cubicOut" as const,
    textStyle: {
      fontFamily: rtl
        ? '"Noto Sans Arabic Variable", "Manrope Variable", system-ui, sans-serif'
        : '"Manrope Variable", system-ui, sans-serif',
      color: theme.ink,
      fontSize: 12,
    },
    grid: {
      left: 8,
      right: 8,
      top: 24,
      bottom: 8,
      containLabel: true,
    },
    tooltip: {
      backgroundColor: theme.mode === "dark" ? "#1b2b34" : "#ffffff",
      borderColor: theme.axis,
      borderWidth: 1,
      padding: [10, 12],
      textStyle: { color: theme.ink, fontSize: 12 },
      extraCssText:
        "border-radius:10px;box-shadow:0 12px 32px rgb(9 24 35 / 18%);" +
        (rtl ? "direction:rtl;text-align:right;" : ""),
    },
    legend: {
      type: "scroll" as const,
      icon: "roundRect",
      itemWidth: 10,
      itemHeight: 10,
      itemGap: 16,
      textStyle: { color: theme.inkMuted, fontSize: 12 },
      inactiveColor: theme.axis,
    },
  };
}

export function categoryAxis(theme: VizTheme, locale: Locale) {
  return {
    type: "category" as const,
    inverse: locale === "ar",
    axisLine: { lineStyle: { color: theme.axis } },
    axisTick: { show: false },
    axisLabel: { color: theme.inkMuted, fontSize: 11, hideOverlap: true },
    splitLine: { show: false },
  };
}

export function valueAxis(theme: VizTheme, locale: Locale, unit?: string) {
  return {
    type: "value" as const,
    position: locale === "ar" ? ("right" as const) : ("left" as const),
    axisLine: { show: false },
    axisTick: { show: false },
    axisLabel: {
      color: theme.inkMuted,
      fontSize: 11,
      formatter: (value: number) =>
        compact(value, locale) + (unit === "%" ? "%" : ""),
    },
    splitLine: { lineStyle: { color: theme.grid, type: "solid" as const } },
  };
}
