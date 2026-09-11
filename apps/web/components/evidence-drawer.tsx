"use client";

import { useEffect, useId, useRef } from "react";
import {
  AlertTriangle,
  BookOpen,
  Clock3,
  Database,
  Fingerprint,
  Layers3,
  X,
} from "lucide-react";
import type { Locale } from "@/lib/contracts";
import { t } from "@/lib/i18n";

export interface EvidenceRecord {
  metricId: string;
  resultId: string;
  definition: string;
  scope: string;
  source: string;
  freshness: string;
  warning?: string;
}

interface EvidenceDrawerProps {
  locale: Locale;
  evidence: EvidenceRecord | null;
  open: boolean;
  onClose: () => void;
}

export function EvidenceDrawer({
  locale,
  evidence,
  open,
  onClose,
}: EvidenceDrawerProps) {
  const titleId = useId();
  const dialogRef = useRef<HTMLDivElement>(null);
  const previousFocus = useRef<HTMLElement | null>(null);
  const ar = locale === "ar";

  useEffect(() => {
    if (!open) return;
    previousFocus.current = document.activeElement as HTMLElement;
    dialogRef.current?.focus();
    const close = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
      if (event.key !== "Tab") return;
      const focusable = dialogRef.current?.querySelectorAll<HTMLElement>(
        "button:not([disabled]), a[href], input:not([disabled]), [tabindex='0']",
      );
      if (!focusable?.length) {
        event.preventDefault();
        dialogRef.current?.focus();
        return;
      }
      const first = focusable[0],
        last = focusable[focusable.length - 1];
      if (
        event.shiftKey &&
        (document.activeElement === first ||
          document.activeElement === dialogRef.current)
      ) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", close);
    const priorOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", close);
      document.body.style.overflow = priorOverflow;
      previousFocus.current?.focus();
    };
  }, [open, onClose]);

  if (!open || !evidence) return null;
  const items = [
    {
      icon: BookOpen,
      label: ar ? "التعريف المعتمد" : "Approved definition",
      value: evidence.definition,
    },
    {
      icon: Layers3,
      label: ar ? "النطاق والفلاتر" : "Scope and filters",
      value: evidence.scope,
    },
    {
      icon: Database,
      label: ar ? "المصدر والإصدار" : "Source and version",
      value: evidence.source,
    },
    {
      icon: Clock3,
      label: ar ? "حداثة البيانات" : "Data freshness",
      value: evidence.freshness,
    },
    {
      icon: Fingerprint,
      label: ar ? "معرّف النتيجة" : "Result ID",
      value: evidence.resultId,
      isolate: true,
    },
  ];
  return (
    <div className="drawer-layer">
      <button
        className="drawer-scrim"
        type="button"
        aria-label={t(locale, "action.close")}
        onClick={onClose}
      />
      <div
        ref={dialogRef}
        className="evidence-drawer"
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
      >
        <header className="drawer-header">
          <div>
            <p className="eyebrow">
              {ar ? "سجل قابل لإعادة الإنتاج" : "Reproducible record"}
            </p>
            <h2 id={titleId}>{t(locale, "evidence.title")}</h2>
          </div>
          <button
            className="icon-button"
            type="button"
            onClick={onClose}
            aria-label={t(locale, "action.close")}
          >
            <X aria-hidden="true" />
          </button>
        </header>
        <p className="metric-code">
          <bdi>{evidence.metricId}</bdi>
        </p>
        {evidence.warning ? (
          <div className="evidence-warning">
            <AlertTriangle size={18} aria-hidden="true" />
            <p>{evidence.warning}</p>
          </div>
        ) : null}
        <dl className="evidence-list">
          {items.map(({ icon: Icon, label, value, isolate }) => (
            <div key={label}>
              <dt>
                <Icon size={16} aria-hidden="true" />
                {label}
              </dt>
              <dd>{isolate ? <bdi>{value}</bdi> : value}</dd>
            </div>
          ))}
        </dl>
        <div className="drawer-footer">
          {evidence.resultId ? (
            <a
              className="button button--secondary"
              href={`/api/v1/metric-results/${encodeURIComponent(evidence.resultId)}`}
              target="_blank"
              rel="noreferrer"
            >
              {ar ? "افتح سجل النتيجة الكامل" : "Open full result record"}
            </a>
          ) : null}
          <p>
            {ar
              ? "تعتمد اللوحة والتقرير والمستشار على معرّف النتيجة نفسه."
              : "Dashboard, report, and assistant bind to this same result ID."}
          </p>
        </div>
      </div>
    </div>
  );
}
