import {
  AlertTriangle,
  Ban,
  DatabaseZap,
  LoaderCircle,
  RefreshCw,
} from "lucide-react";
import type { Locale, ResourceStatus } from "@/lib/contracts";
import { t } from "@/lib/i18n";

interface ResourceStateProps {
  locale: Locale;
  status: Exclude<ResourceStatus, "ready" | "partial">;
  reason?: string;
  correlationId?: string;
  onRetry?: () => void;
  compact?: boolean;
}

const titleKeys: Partial<Record<ResourceStateProps["status"], string>> = {
  denied: "state.denied.title",
  error: "state.error.title",
  unavailable: "state.unavailable.title",
  empty: "state.empty.title",
  loading: "state.loading.title",
  stale: "state.stale.title",
};

export function ResourceState({
  locale,
  status,
  reason,
  correlationId,
  onRetry,
  compact,
}: ResourceStateProps) {
  const Icon =
    status === "loading"
      ? LoaderCircle
      : status === "denied"
        ? Ban
        : status === "empty"
          ? DatabaseZap
          : AlertTriangle;
  const title = t(locale, titleKeys[status] ?? "state.error.title");
  const fallback =
    locale === "ar"
      ? "لا تتوفر تفاصيل إضافية."
      : "No additional details are available.";
  return (
    <section
      className={`resource-state resource-state--${status}${compact ? " resource-state--compact" : ""}`}
      role={status === "loading" ? "status" : "alert"}
      aria-live={status === "loading" ? "polite" : "assertive"}
    >
      <span className="resource-state__icon" aria-hidden="true">
        <Icon size={20} />
      </span>
      <div>
        <h2>{title}</h2>
        <p>{reason || fallback}</p>
        {correlationId ? (
          <p className="meta">
            <span>{locale === "ar" ? "مرجع الدعم" : "Support reference"}</span>{" "}
            <bdi>{correlationId}</bdi>
          </p>
        ) : null}
        {onRetry && status !== "loading" ? (
          <button
            className="button button--secondary button--small"
            type="button"
            onClick={onRetry}
          >
            <RefreshCw size={15} aria-hidden="true" />{" "}
            {t(locale, "action.retry")}
          </button>
        ) : null}
      </div>
    </section>
  );
}
