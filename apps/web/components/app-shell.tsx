"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import {
  Bell,
  BookOpenCheck,
  Bot,
  BriefcaseBusiness,
  Building2,
  ChartNoAxesCombined,
  ChevronLeft,
  ChevronRight,
  CircleDollarSign,
  Database,
  FileCheck2,
  FileText,
  FlaskConical,
  FolderKanban,
  Gauge,
  Goal,
  Lightbulb,
  Menu,
  Moon,
  PanelLeftClose,
  PanelLeftOpen,
  MessageSquareText,
  Search,
  Settings2,
  Sparkles,
  ShieldCheck,
  Sun,
  UsersRound,
  Wand2,
  X,
  LogOut,
} from "lucide-react";
import type { Locale, SessionContext } from "@/lib/contracts";
import { apiRequest, postJson } from "@/lib/api";
import { t } from "@/lib/i18n";

interface AppShellProps {
  locale: Locale;
  route: string;
  workspace?: string;
  children: React.ReactNode;
}

const navGroups = [
  {
    label: "group.ai",
    items: [
      { path: "analyst", label: "nav.analyst", icon: Sparkles },
      { path: "analyst/ask", label: "nav.ask", icon: MessageSquareText },
    ],
  },
  {
    label: "group.understand",
    items: [
      { path: "overview", label: "nav.overview", icon: Gauge },
      { path: "data/prepare", label: "nav.prepare", icon: Wand2 },
      { path: "insights", label: "nav.insights", icon: Lightbulb },
      { path: "explore", label: "nav.explore", icon: ChartNoAxesCombined },
      { path: "assistant", label: "nav.assistant", icon: Bot },
      { path: "data/sources", label: "nav.sources", icon: Database },
      { path: "data/catalog", label: "nav.catalog", icon: Search },
      { path: "data/quality", label: "nav.quality", icon: ShieldCheck },
    ],
  },
  {
    label: "group.company",
    items: [
      { path: "company/customers", label: "nav.customers", icon: Building2 },
      { path: "company/people", label: "nav.people", icon: UsersRound },
      { path: "company/projects", label: "nav.projects", icon: FolderKanban },
      {
        path: "company/operations",
        label: "nav.operations",
        icon: BriefcaseBusiness,
      },
      { path: "company/finance", label: "nav.finance", icon: CircleDollarSign },
      { path: "company/support", label: "nav.support", icon: Bell },
      { path: "company/objectives", label: "nav.objectives", icon: Goal },
    ],
  },
  {
    label: "group.decide",
    items: [
      { path: "forecasts", label: "nav.forecasts", icon: ChartNoAxesCombined },
      { path: "scenarios", label: "nav.scenarios", icon: FlaskConical },
      { path: "reports", label: "nav.reports", icon: FileText },
      { path: "decisions", label: "nav.decisions", icon: BookOpenCheck },
      { path: "approvals", label: "nav.approvals", icon: FileCheck2 },
    ],
  },
  {
    label: "group.manage",
    items: [{ path: "admin", label: "nav.admin", icon: Settings2 }],
  },
];

export function AppShell({
  locale,
  route,
  workspace,
  children,
}: AppShellProps) {
  const ar = locale === "ar";
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const [session, setSession] = useState<SessionContext | null>(null);
  const [sessionError, setSessionError] = useState("");
  useEffect(() => {
    const controller = new AbortController();
    apiRequest<SessionContext>("/api/v1/auth/context", {
      signal: controller.signal,
    })
      .then((value) => {
        if (!controller.signal.aborted) setSession(value);
      })
      .catch((error) => {
        if (!controller.signal.aborted) {
          setSession(null);
          setSessionError(error.message);
        }
      });
    return () => controller.abort();
  }, []);
  async function logout() {
    try {
      await postJson("/api/v1/auth/logout", {});
      sessionStorage.removeItem("baseera-last-upload");
      window.location.assign(`/${locale}/login`);
    } catch (error) {
      setSessionError(error instanceof Error ? error.message : String(error));
    }
  }
  const menuRef = useRef<HTMLElement>(null);
  const query = workspace ? `?workspace=${encodeURIComponent(workspace)}` : "";
  useEffect(() => {
    const saved =
      localStorage.getItem("baseera-theme") === "dark" ? "dark" : "light";
    setTheme(saved);
    document.documentElement.dataset.theme = saved;
  }, []);
  useEffect(() => {
    setMobileOpen(false);
  }, [route]);
  useEffect(() => {
    if (!mobileOpen) return;
    menuRef.current?.focus();
    const close = (event: KeyboardEvent) =>
      event.key === "Escape" && setMobileOpen(false);
    document.addEventListener("keydown", close);
    return () => document.removeEventListener("keydown", close);
  }, [mobileOpen]);
  function toggleTheme() {
    const next = theme === "light" ? "dark" : "light";
    setTheme(next);
    localStorage.setItem("baseera-theme", next);
    document.documentElement.dataset.theme = next;
  }
  const navigation = (
    <>
      {navGroups.map((group) => (
        <div className="nav-group" key={group.label}>
          <p>{t(locale, group.label)}</p>
          {group.items.map(({ path, label, icon: Icon }) => (
            <Link
              key={path}
              href={`/${locale}/${path}${query}`}
              className={route === path ? "active" : undefined}
              aria-current={route === path ? "page" : undefined}
              title={collapsed ? t(locale, label) : undefined}
            >
              <Icon size={18} aria-hidden="true" />
              <span>{t(locale, label)}</span>
            </Link>
          ))}
        </div>
      ))}
    </>
  );
  return (
    <div className={`app-frame${collapsed ? " app-frame--collapsed" : ""}`}>
      <a className="skip-link" href="#main-content">
        {ar ? "انتقل إلى المحتوى" : "Skip to content"}
      </a>
      <aside
        className="sidebar"
        aria-label={ar ? "التنقل الرئيسي" : "Primary navigation"}
      >
        <div className="brand">
          <span className="brand-mark">ب</span>
          <div>
            <strong>{t(locale, "brand.arabic")}</strong>
            <small>{t(locale, "brand.name")}</small>
          </div>
          <button
            className="icon-button collapse-button"
            type="button"
            onClick={() => setCollapsed((value) => !value)}
            aria-label={
              collapsed
                ? ar
                  ? "توسيع الشريط"
                  : "Expand sidebar"
                : ar
                  ? "طي الشريط"
                  : "Collapse sidebar"
            }
          >
            {collapsed ? (
              <PanelLeftOpen aria-hidden="true" />
            ) : (
              <PanelLeftClose aria-hidden="true" />
            )}
          </button>
        </div>
        <nav>{navigation}</nav>
        <div className="sidebar-footer">
          <span className="avatar">
            {session?.user.display_name.slice(0, 2) ?? "ب"}
          </span>
          <div>
            <strong>
              {session?.user.display_name ??
                (ar ? "غير مسجل" : "Not signed in")}
            </strong>
            <small>{session?.membership.role ?? "—"}</small>
          </div>
          {session ? (
            <button
              className="icon-button"
              onClick={logout}
              aria-label={ar ? "تسجيل الخروج" : "Sign out"}
            >
              <LogOut size={17} />
            </button>
          ) : (
            <Link href={`/${locale}/login`}>{ar ? "دخول" : "Sign in"}</Link>
          )}
        </div>
      </aside>
      {mobileOpen ? (
        <div className="mobile-nav-layer">
          <button
            className="drawer-scrim"
            aria-label={ar ? "إغلاق القائمة" : "Close menu"}
            onClick={() => setMobileOpen(false)}
          />
          <aside
            ref={menuRef}
            className="mobile-nav"
            tabIndex={-1}
            aria-label={ar ? "قائمة الهاتف" : "Mobile menu"}
          >
            <div className="mobile-nav__head">
              <span className="brand-mark">ب</span>
              <strong>
                بصيرة <small>BASEERA</small>
              </strong>
              <button
                className="icon-button"
                onClick={() => setMobileOpen(false)}
                aria-label={ar ? "إغلاق القائمة" : "Close menu"}
              >
                <X />
              </button>
            </div>
            <nav>{navigation}</nav>
          </aside>
        </div>
      ) : null}
      <div className="app-body">
        <header className="context-bar">
          <div className="context-bar__start">
            <button
              className="icon-button mobile-menu-button"
              type="button"
              onClick={() => setMobileOpen(true)}
              aria-expanded={mobileOpen}
              aria-label={ar ? "فتح القائمة" : "Open menu"}
            >
              <Menu />
            </button>
            <div className="company-context">
              <span className="company-symbol">ن</span>
              <div>
                <strong>
                  {session
                    ? ar
                      ? session.tenant.name_ar
                      : session.tenant.name_en
                    : "BASEERA · بصيرة"}
                </strong>
                <small>
                  {session?.tenant.is_demo
                    ? t(locale, "demo.label")
                    : ar
                      ? "مساحة العمل"
                      : "Workspace"}
                </small>
              </div>
            </div>
          </div>
          <div className="context-controls">
            <div className="context-pill">
              <span>
                {ar ? "تاريخ التقرير" : "Reporting cutoff"}:{" "}
                <bdi>{session?.tenant.reporting_date ?? "—"}</bdi>
              </span>
              <small>
                <bdi>
                  {session?.tenant.timezone ?? "—"} ·{" "}
                  {session?.tenant.currency ?? "—"}
                </bdi>
              </small>
            </div>
            <Link
              className="icon-button"
              href={`/${locale === "ar" ? "en" : "ar"}/${route}${query}`}
              hrefLang={locale === "ar" ? "en" : "ar"}
              aria-label={ar ? "Switch to English" : "التبديل إلى العربية"}
            >
              <span className="locale-label">{ar ? "EN" : "ع"}</span>
            </Link>
            <button
              className="icon-button"
              type="button"
              onClick={toggleTheme}
              aria-label={
                theme === "light"
                  ? ar
                    ? "تفعيل المظهر الداكن"
                    : "Use dark theme"
                  : ar
                    ? "تفعيل المظهر الفاتح"
                    : "Use light theme"
              }
            >
              {theme === "light" ? (
                <Moon aria-hidden="true" />
              ) : (
                <Sun aria-hidden="true" />
              )}
            </button>
          </div>
        </header>
        <main id="main-content" tabIndex={-1}>
          {sessionError ? (
            <p role="alert" className="truth-banner">
              {sessionError}
            </p>
          ) : null}
          {children}
        </main>
        <Link className="floating-ask" href={`/${locale}/analyst/ask${query}`}>
          <Bot size={18} aria-hidden="true" />
          {ar ? "اسأل فريق المحللين" : "Ask the analyst team"}
          {ar ? <ChevronLeft size={16} /> : <ChevronRight size={16} />}
        </Link>
      </div>
    </div>
  );
}
