"use client";

import { useEffect, useId, useRef, useState } from "react";
import { Table2, BarChart3, Download } from "lucide-react";
import type { EChartsType } from "echarts/core";
import type { Locale } from "@/lib/contracts";
import { currentMode, num, vizTheme, type VizTheme } from "@/lib/viz";

export interface ChartTableColumn {
  key: string;
  label: string;
  numeric?: boolean;
}

interface ChartProps {
  locale: Locale;
  title?: string;
  description?: string;
  /** Built from the resolved theme so light and dark are separately chosen, not flipped. */
  option: (theme: VizTheme) => Record<string, unknown>;
  height?: number;
  /**
   * The table is not optional. Two light-mode series colors sit below 3:1 against the
   * surface, and the palette's relief rule requires a non-colour route to the values.
   */
  table: { columns: ChartTableColumn[]; rows: Array<Record<string, unknown>> };
  source?: string;
  footnote?: string;
  /** Loads the 3D extension. Only pass this for a chart that genuinely needs depth. */
  threeDimensional?: boolean;
  onSelect?: (params: {
    name: string;
    seriesName: string;
    value: unknown;
  }) => void;
}

export function Chart({
  locale,
  title,
  description,
  option,
  height = 320,
  table,
  source,
  footnote,
  threeDimensional = false,
  onSelect,
}: ChartProps) {
  const holder = useRef<HTMLDivElement>(null);
  const instance = useRef<EChartsType | null>(null);
  const [showTable, setShowTable] = useState(false);
  const [failed, setFailed] = useState(false);
  const titleId = useId();
  const ar = locale === "ar";

  useEffect(() => {
    if (showTable) return;
    let disposed = false;
    let observer: ResizeObserver | undefined;
    let watcher: MutationObserver | undefined;

    async function draw() {
      const node = holder.current;
      if (!node) return;
      try {
        const echarts = await import("echarts");
        if (threeDimensional) await import("echarts-gl");
        if (disposed || !holder.current) return;
        instance.current?.dispose();
        const chart = echarts.init(holder.current, undefined, {
          renderer: "canvas",
          useDirtyRect: true,
        });
        instance.current = chart;
        const paint = () =>
          chart.setOption(option(vizTheme(currentMode())), { notMerge: true });
        paint();
        if (onSelect) {
          chart.on("click", (params) =>
            onSelect({
              name: String(params.name),
              seriesName: String(params.seriesName ?? ""),
              value: params.value,
            }),
          );
        }
        observer = new ResizeObserver(() => chart.resize());
        observer.observe(holder.current);
        // The shell stamps data-theme on <html>; repaint from the same ramps rather
        // than inverting the rendered canvas.
        watcher = new MutationObserver(paint);
        watcher.observe(document.documentElement, {
          attributes: true,
          attributeFilter: ["data-theme"],
        });
      } catch {
        // A chart that cannot render must not take the numbers with it.
        if (!disposed) setFailed(true);
      }
    }
    void draw();
    return () => {
      disposed = true;
      observer?.disconnect();
      watcher?.disconnect();
      instance.current?.dispose();
      instance.current = null;
    };
  }, [option, onSelect, showTable, threeDimensional]);

  const asTable = showTable || failed;

  function downloadCsv() {
    const header = table.columns.map((column) => column.label).join(",");
    const body = table.rows
      .map((row) =>
        table.columns
          .map((column) => {
            const value = row[column.key];
            const text = value == null ? "" : String(value);
            return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
          })
          .join(","),
      )
      .join("\n");
    const blob = new Blob([`﻿${header}\n${body}`], {
      type: "text/csv;charset=utf-8",
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${(title ?? "chart").replace(/[^\w؀-ۿ-]+/g, "-")}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  }

  return (
    <figure className="viz" aria-labelledby={title ? titleId : undefined}>
      {(title || description) && (
        <figcaption className="viz__head">
          <div>
            {title && <h3 id={titleId}>{title}</h3>}
            {description && <p>{description}</p>}
          </div>
          <div className="viz__tools">
            <button
              type="button"
              className="chip-button"
              onClick={() => setShowTable((value) => !value)}
              aria-pressed={showTable}
              disabled={failed}
            >
              {showTable ? <BarChart3 size={14} /> : <Table2 size={14} />}
              {showTable ? (ar ? "الرسم" : "Chart") : ar ? "الجدول" : "Table"}
            </button>
            <button type="button" className="chip-button" onClick={downloadCsv}>
              <Download size={14} />
              CSV
            </button>
          </div>
        </figcaption>
      )}
      {failed && (
        <p className="viz__fallback" role="status">
          {ar
            ? "تعذّر رسم الشكل البياني. القيم معروضة كاملة في الجدول أدناه."
            : "The chart could not be drawn. The full values are shown in the table below."}
        </p>
      )}
      {asTable ? (
        <div className="table-scroll" tabIndex={0}>
          <table className="viz__table">
            <thead>
              <tr>
                {table.columns.map((column) => (
                  <th key={column.key} scope="col">
                    {column.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {table.rows.map((row, index) => (
                <tr key={index}>
                  {table.columns.map((column, position) => {
                    const value = row[column.key];
                    const content =
                      typeof value === "number"
                        ? num(value, locale)
                        : (value ?? "—");
                    return position === 0 ? (
                      <th key={column.key} scope="row">
                        {String(content)}
                      </th>
                    ) : (
                      <td
                        key={column.key}
                        className={column.numeric ? "numeric" : undefined}
                      >
                        {String(content)}
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div
          ref={holder}
          className="viz__canvas"
          style={{ height }}
          role="img"
          aria-label={`${title ?? ""}. ${description ?? ""}`}
        />
      )}
      {(source || footnote) && (
        <footer className="viz__foot">
          {footnote && <span>{footnote}</span>}
          {source && (
            <span className="viz__source">
              {ar ? "المصدر:" : "Source:"} {source}
            </span>
          )}
        </footer>
      )}
    </figure>
  );
}
