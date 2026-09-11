"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import {
  ArrowRight,
  BarChart3,
  Building2,
  CheckCircle2,
  Database,
  Languages,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { useRouter } from "next/navigation";
import type { Locale, OverviewResponse } from "@/lib/contracts";
import {
  ApiError,
  getOverview,
  postJson,
  resourceStatusFromError,
} from "@/lib/api";
import { demoOverview } from "@/lib/demo-data";
import { AnalysisWorkspace } from "./analysis-assistant";
import { AssistantScreen } from "./local-assistant";
import { AppShell } from "./app-shell";
import { CompanyModuleScreen, type ModuleId } from "./company-screens";
import {
  AdminScreen,
  DecisionsScreen,
  ForecastScreen,
  ReportsScreen,
  ScenarioScreen,
} from "./decision-screens";
import {
  CatalogScreen,
  OnboardingScreen,
  QualityScreen,
  SourcesScreen,
} from "./data-workspaces";
import { AnalystWorkspace } from "./analyst";
import { DataPrepWorkspace } from "./data-prep";
import { ForecastWorkspace } from "./forecast-workspace";
import { ExecutiveOverview } from "./executive-overview";
import { LocaleDocument } from "./locale-document";
import { LoginForm } from "./login-form";
import { ResourceState } from "./resource-state";
import {
  LiveAdmin,
  LiveAnalysis,
  LiveCatalog,
  LiveCompany,
  LiveDecisions,
  LiveForecast,
  LiveQuality,
  LiveReports,
  LiveScenario,
  LiveSources,
} from "./live-workspaces";

interface ProductRouteProps {
  locale: Locale;
  route: string;
  workspace?: string;
}

export function ProductRoute({ locale, route, workspace }: ProductRouteProps) {
  const router = useRouter();
  const ar = locale === "ar";
  if (route === "login")
    return (
      <>
        <LocaleDocument locale={locale} />
        <LoginScreen locale={locale} onNavigate={(path) => router.push(path)} />
      </>
    );
  if (route === "onboarding")
    return (
      <>
        <LocaleDocument locale={locale} />
        <OnboardingScreen locale={locale} />
      </>
    );
  return (
    <>
      <LocaleDocument locale={locale} />
      <AppShell locale={locale} route={route} workspace={workspace}>
        {renderRoute(locale, route, workspace)}
      </AppShell>
    </>
  );
}

function renderRoute(locale: Locale, route: string, workspace?: string) {
  if (route === "overview")
    return <OverviewRoute locale={locale} workspace={workspace} />;
  if (route === "assistant") return <AssistantScreen locale={locale} />;
  if (route.startsWith("company/"))
    return <LiveCompany locale={locale} module={route.split("/")[1]} />;
  const screens: Record<string, React.ComponentType<{ locale: Locale }>> = {
    "data/prepare": DataPrepWorkspace,
    insights: AnalystWorkspace,
    "data/quality": LiveQuality,
    "data/sources": LiveSources,
    "data/catalog": LiveCatalog,
    reports: LiveReports,
    forecasts: ForecastWorkspace,
    scenarios: LiveScenario,
    explore: LiveAnalysis,
    decisions: LiveDecisions,
    admin: LiveAdmin,
  };
  if (route === "approvals") return <LiveDecisions locale={locale} approvals />;
  const Screen = screens[route];
  return Screen ? (
    <Screen locale={locale} />
  ) : (
    <ResourceState
      locale={locale}
      status="unavailable"
      reason={
        locale === "ar"
          ? "هذا المسار غير مدعوم. استخدم التنقل الرئيسي."
          : "This route is unsupported. Use the primary navigation."
      }
    />
  );
}

function OverviewRoute({
  locale,
  workspace,
}: {
  locale: Locale;
  workspace?: string;
}) {
  const ar = locale === "ar";
  const [data, setData] = useState<OverviewResponse | null>(null);
  const [status, setStatus] = useState<
    "loading" | "error" | "denied" | "unavailable"
  >("loading");
  const [reason, setReason] = useState("");
  const [correlationId, setCorrelationId] = useState<string>();
  const [offline, setOffline] = useState(false);
  const load = useCallback(() => {
    const controller = new AbortController();
    setStatus("loading");
    setReason("");
    setOffline(false);
    getOverview(controller.signal, locale)
      .then((response) => {
        if (controller.signal.aborted) return;
        setData(response);
        setStatus("loading");
      })
      .catch((error) => {
        if (controller.signal.aborted) return;
        setData(null);
        setStatus(resourceStatusFromError(error));
        setReason(
          error instanceof Error
            ? error.message
            : ar
              ? "لم تستجب الخدمة."
              : "The service did not respond.",
        );
        if (error instanceof ApiError)
          setCorrelationId(error.problem.correlationId);
      });
    return () => controller.abort();
  }, [ar, locale]);
  useEffect(() => load(), [load]);
  if (data)
    return <ExecutiveOverview locale={locale} data={data} offline={offline} />;
  return (
    <ResourceState
      locale={locale}
      status={status}
      reason={
        reason ||
        (ar ? "جارٍ طلب النتائج المسموح بها…" : "Requesting permitted results…")
      }
      correlationId={correlationId}
      onRetry={status !== "loading" ? load : undefined}
    />
  );
}

function LoginScreen({
  locale,
  onNavigate,
}: {
  locale: Locale;
  onNavigate: (path: string) => void;
}) {
  const ar = locale === "ar";
  async function login(credentials: { email: string; password: string }) {
    await postJson("/api/v1/auth/login", credentials);
    localStorage.removeItem("baseera-workspace");
    onNavigate(`/${locale}/overview`);
  }
  async function demo() {
    await postJson("/api/v1/auth/login", {
      email: "executive@demo.baseera.local",
      password: "BaseeraDemo!2026",
    });
    onNavigate(`/${locale}/overview?workspace=demo`);
  }
  return (
    <main className="login-page">
      <section className="login-story">
        <header className="login-brand">
          <span className="brand-mark brand-mark--large">ب</span>
          <div>
            <strong>بصيرة</strong>
            <small>BASEERA</small>
          </div>
        </header>
        <div className="login-story__body">
          <p className="eyebrow">
            {ar
              ? "من البيانات إلى قرار قابل للدفاع"
              : "From data to a defensible decision"}
          </p>
          <h1>
            {ar
              ? "القرارات تستحق دليلًا، لا مجرد لوحة."
              : "Decisions deserve evidence, not just a dashboard."}
          </h1>
          <p>
            {ar
              ? "اربط المعنى بالمقياس، والنتيجة بمصدرها، والإجراء بصاحبه ومراجعة أثره."
              : "Tie each metric to meaning, each result to its source, and each action to an owner and outcome review."}
          </p>
          <div className="login-principles">
            <div>
              <ShieldCheck />
              <span>
                <b>{ar ? "دليل يمكن تتبعه" : "Traceable evidence"}</b>
                <small>
                  {ar
                    ? "التعريف والنطاق والمصدر وإصدار النتيجة"
                    : "Definition, scope, source, and result version"}
                </small>
              </span>
            </div>
            <div>
              <BarChart3 />
              <span>
                <b>
                  {ar
                    ? "حسابات قابلة لإعادة الإنتاج"
                    : "Reproducible calculations"}
                </b>
                <small>
                  {ar
                    ? "القيمة نفسها في المحادثة واللوحة والتقرير"
                    : "The same value in chat, dashboard, and report"}
                </small>
              </span>
            </div>
            <div>
              <Building2 />
              <span>
                <b>{ar ? "صورة مترابطة للشركة" : "Connected company view"}</b>
                <small>
                  {ar
                    ? "المبيعات والأفراد والمشاريع والعمليات والموازنات"
                    : "Sales, people, projects, operations, and budgets"}
                </small>
              </span>
            </div>
          </div>
        </div>
        <footer>
          <span>
            {ar ? "منتج عربي وإنجليزي أصيل" : "Native Arabic and English"}
          </span>
          <span>·</span>
          <span>WCAG 2.2 AA</span>
          <span>·</span>
          <span>{ar ? "أقل صلاحية" : "Least privilege"}</span>
        </footer>
      </section>
      <section className="login-panel">
        <div className="login-panel__top">
          <Link
            href={`/${locale === "ar" ? "en" : "ar"}/login`}
            className="language-switch"
          >
            <Languages />
            {ar ? "English" : "العربية"}
          </Link>
        </div>
        <div className="login-box">
          <p className="eyebrow">
            {ar ? "مساحة العمل الآمنة" : "Secure workspace"}
          </p>
          <h2>{ar ? "مرحبًا بعودتك" : "Welcome back"}</h2>
          <p>
            {ar
              ? "استخدم جلسة التطوير المحلية أو افتح بيانات العرض الخيالية المنفصلة."
              : "Use the local development session or open the isolated fictional demo."}
          </p>
          <LoginForm locale={locale} onLogin={login} onDemo={demo} />
          <Link
            className="empty-workspace-link"
            href={`/${locale}/onboarding?mode=empty`}
            onClick={() => localStorage.removeItem("baseera-workspace")}
          >
            <Database />
            {ar ? "ابدأ مساحة عمل فارغة" : "Start an empty workspace"}
            <ArrowRight />
          </Link>
        </div>
        <p className="login-security">
          <CheckCircle2 />
          {ar
            ? "لا تُرسل بيانات الاعتماد إلى نموذج الذكاء الاصطناعي."
            : "Credentials are never sent to an AI model."}
        </p>
      </section>
    </main>
  );
}
