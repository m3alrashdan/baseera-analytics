"use client";

import { useId, useMemo, useState } from "react";
import { BarChart3, Table2 } from "lucide-react";
import type { Locale } from "@/lib/contracts";
import { formatNumber, t } from "@/lib/i18n";

export interface ChartDatum {
  label: string;
  value: number | null;
  comparison?: number | null;
  forecastLow?: number | null;
  forecastHigh?: number | null;
}

interface ChartPanelProps {
  locale: Locale;
  title: string;
  description?: string;
  data: ChartDatum[];
  unit?: string;
  source?: string;
  kind?: "line" | "bar" | "forecast";
  onPointSelect?: (point: ChartDatum) => void;
}

function points(
  values: Array<number | null>,
  width: number,
  height: number,
  max: number,
  min: number,
) {
  const span = max - min || 1;
  const gap = values.length > 1 ? width / (values.length - 1) : width;
  return values
    .map((value, index) =>
      value == null
        ? null
        : `${index === 0 || values[index - 1] == null ? "M" : "L"}${values.length === 1 ? width / 2 : index * gap},${height - ((value - min) / span) * height}`,
    )
    .filter(Boolean)
    .join(" ");
}

export function ChartPanel({
  locale,
  title,
  description,
  data,
  unit,
  source,
  kind = "line",
  onPointSelect,
}: ChartPanelProps) {
  const [table, setTable] = useState(false);
  const titleId = useId();
  const values = data
    .flatMap((row) => [
      row.value,
      row.comparison,
      row.forecastLow,
      row.forecastHigh,
    ])
    .filter((value): value is number => typeof value === "number");
  const { max, min } = useMemo(
    () => ({ max: Math.max(...values, 1), min: Math.min(...values, 0) }),
    [values],
  );
  const width = 640;
  const height = 220;
  const format = (value: number | null | undefined) =>
    value == null
      ? "—"
      : `${formatNumber(value, locale)}${unit ? ` ${unit}` : ""}`;

  return (
    <section className="chart-panel" aria-labelledby={titleId}>
      <header className="panel-heading">
        <div>
          <h2 id={titleId}>{title}</h2>
          {description ? <p>{description}</p> : null}
        </div>
        <button
          className="button button--ghost button--small"
          type="button"
          onClick={() => setTable((value) => !value)}
          aria-pressed={table}
        >
          {table ? (
            <BarChart3 size={16} aria-hidden="true" />
          ) : (
            <Table2 size={16} aria-hidden="true" />
          )}
          {table ? t(locale, "action.chart") : t(locale, "action.table")}
        </button>
      </header>
      {!values.length ? (
        <p className="muted">
          {locale === "ar"
            ? "لا توجد قيم متاحة لهذا الرسم ضمن النطاق الحالي."
            : "No chart values are available in the current scope."}
        </p>
      ) : table ? (
        <div
          className="table-scroll"
          tabIndex={0}
          aria-label={
            locale === "ar" ? "جدول بيانات الرسم" : "Chart data table"
          }
        >
          <table>
            <thead>
              <tr>
                <th>{locale === "ar" ? "الفترة" : "Period"}</th>
                <th>{locale === "ar" ? "الحالي" : "Current"}</th>
                {data.some((d) => d.comparison != null) ? (
                  <th>{locale === "ar" ? "المقارنة" : "Comparison"}</th>
                ) : null}
              </tr>
            </thead>
            <tbody>
              {data.map((row) => (
                <tr key={row.label}>
                  <th scope="row">{row.label}</th>
                  <td>{format(row.value)}</td>
                  {data.some((d) => d.comparison != null) ? (
                    <td>{format(row.comparison)}</td>
                  ) : null}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : kind === "bar" ? (
        <div
          className="bar-chart"
          role="img"
          aria-label={`${title}. ${description ?? ""}`}
        >
          {data.map((row) => (
            <button
              type="button"
              className="bar-chart__row"
              key={row.label}
              onClick={() => onPointSelect?.(row)}
              disabled={!onPointSelect}
            >
              <span>{row.label}</span>
              <i
                style={{
                  inlineSize: `${Math.max(3, ((row.value ?? 0) / max) * 100)}%`,
                }}
              />
              <b>{format(row.value)}</b>
            </button>
          ))}
        </div>
      ) : (
        <div className="line-chart">
          <svg
            viewBox={`-18 -20 ${width + 36} ${height + 60}`}
            role="img"
            aria-labelledby={`${titleId}-svg-title ${titleId}-svg-desc`}
          >
            <title id={`${titleId}-svg-title`}>{title}</title>
            <desc id={`${titleId}-svg-desc`}>
              {description ??
                (locale === "ar"
                  ? "اتجاه زمني مع قيم مقارنة"
                  : "Time trend with comparison values")}
            </desc>
            {[0, 0.25, 0.5, 0.75, 1].map((ratio) => (
              <line
                key={ratio}
                x1="0"
                x2={width}
                y1={height * ratio}
                y2={height * ratio}
                className="chart-grid"
              />
            ))}
            {data.some((row) => row.comparison != null) ? (
              <path
                className="chart-line chart-line--comparison"
                d={points(
                  data.map((d) => d.comparison ?? null),
                  width,
                  height,
                  max,
                  min,
                )}
              />
            ) : null}
            <path
              className={`chart-line ${kind === "forecast" ? "chart-line--forecast" : ""}`}
              d={points(
                data.map((d) => d.value),
                width,
                height,
                max,
                min,
              )}
            />
            {data.map((row, index) => {
              if (row.value == null) return null;
              const x =
                data.length > 1
                  ? index * (width / (data.length - 1))
                  : width / 2;
              const y =
                height - ((row.value - min) / (max - min || 1)) * height;
              return (
                <g key={row.label}>
                  <circle
                    className="chart-dot"
                    cx={x}
                    cy={y}
                    r="5"
                    tabIndex={onPointSelect ? 0 : undefined}
                    role={onPointSelect ? "button" : undefined}
                    aria-label={`${row.label}: ${format(row.value)}`}
                    onClick={() => onPointSelect?.(row)}
                    onKeyDown={(event) =>
                      (event.key === "Enter" || event.key === " ") &&
                      onPointSelect?.(row)
                    }
                  >
                    <title>
                      {row.label}: {format(row.value)}
                    </title>
                  </circle>
                  <text
                    className="chart-label"
                    x={x}
                    y={height + 28}
                    textAnchor="middle"
                  >
                    {row.label}
                  </text>
                </g>
              );
            })}
          </svg>
          <div className="chart-legend">
            <span>
              <i className="legend-swatch legend-swatch--current" />
              {locale === "ar" ? "الحالي" : "Current"}
            </span>
            {data.some((row) => row.comparison != null) ? (
              <span>
                <i className="legend-swatch legend-swatch--comparison" />
                {locale === "ar" ? "فترة المقارنة" : "Comparison period"}
              </span>
            ) : null}
          </div>
        </div>
      )}
      {source ? (
        <footer className="panel-source">
          {locale === "ar" ? "المصدر:" : "Source:"} {source}
        </footer>
      ) : null}
    </section>
  );
}
