import type { Locale } from "./contracts";

const messages = {
  en: {
    "brand.name": "BASEERA",
    "brand.arabic": "بصيرة",
    "nav.overview": "Overview",
    "nav.explore": "Explore",
    "nav.prepare": "Prepare data",
    "nav.insights": "Analyst findings",
    "nav.assistant": "AI consultant",
    "nav.sources": "Data sources",
    "nav.catalog": "Data catalog",
    "nav.quality": "Data quality",
    "nav.customers": "Customers & sales",
    "nav.people": "People & teams",
    "nav.projects": "Projects",
    "nav.operations": "Operations",
    "nav.finance": "Costs & budgets",
    "nav.support": "Support & suppliers",
    "nav.objectives": "Objectives",
    "nav.forecasts": "Forecasts",
    "nav.scenarios": "Scenario lab",
    "nav.reports": "Reports",
    "nav.decisions": "Decisions",
    "nav.approvals": "Approvals",
    "nav.admin": "Administration",
    "group.understand": "Understand",
    "group.company": "Company",
    "group.decide": "Decide",
    "group.manage": "Manage",
    "action.retry": "Retry",
    "action.close": "Close",
    "action.inspect": "Inspect evidence",
    "action.table": "View data table",
    "action.chart": "View chart",
    "state.denied.title": "Access restricted",
    "state.error.title": "We couldn’t load this view",
    "state.unavailable.title": "Capability unavailable",
    "state.empty.title": "No data in this scope",
    "state.loading.title": "Loading verified results",
    "state.stale.title": "Source data is stale",
    "evidence.title": "Metric evidence",
    "overview.title": "Executive overview",
    "overview.brief": "Executive brief",
    "overview.attention": "Needs attention",
    "overview.actions": "Reviewed actions",
    "overview.departments": "Pressure by department",
    "overview.trend": "Revenue and prior-year comparison",
    "demo.label": "Fictional demo",
    "demo.offline":
      "Offline demo snapshot — illustrative data, not a live company result.",
  },
  ar: {
    "brand.name": "BASEERA",
    "brand.arabic": "بصيرة",
    "nav.overview": "نظرة عامة",
    "nav.explore": "التحليل",
    "nav.prepare": "إعداد البيانات",
    "nav.insights": "نتائج المحلل",
    "nav.assistant": "المستشار الذكي",
    "nav.sources": "مصادر البيانات",
    "nav.catalog": "دليل البيانات",
    "nav.quality": "جودة البيانات",
    "nav.customers": "العملاء والمبيعات",
    "nav.people": "الأفراد والفرق",
    "nav.projects": "المشاريع",
    "nav.operations": "العمليات",
    "nav.finance": "التكاليف والموازنات",
    "nav.support": "الدعم والموردون",
    "nav.objectives": "الأهداف",
    "nav.forecasts": "التنبؤات",
    "nav.scenarios": "مختبر السيناريو",
    "nav.reports": "التقارير",
    "nav.decisions": "القرارات",
    "nav.approvals": "الموافقات",
    "nav.admin": "الإدارة",
    "group.understand": "افهم",
    "group.company": "الشركة",
    "group.decide": "اتخذ قرارًا",
    "group.manage": "أدر",
    "action.retry": "إعادة المحاولة",
    "action.close": "إغلاق",
    "action.inspect": "فحص الدليل",
    "action.table": "عرض جدول البيانات",
    "action.chart": "عرض الرسم",
    "state.denied.title": "الوصول مقيّد",
    "state.error.title": "تعذّر تحميل هذا العرض",
    "state.unavailable.title": "الإمكانات غير متاحة",
    "state.empty.title": "لا توجد بيانات ضمن هذا النطاق",
    "state.loading.title": "جارٍ تحميل النتائج المتحققة",
    "state.stale.title": "بيانات المصدر قديمة",
    "evidence.title": "دليل المؤشر",
    "overview.title": "نظرة تنفيذية",
    "overview.brief": "الملخص التنفيذي",
    "overview.attention": "يتطلب الانتباه",
    "overview.actions": "إجراءات تمت مراجعتها",
    "overview.departments": "الضغط حسب الإدارة",
    "overview.trend": "الإيرادات ومقارنة العام السابق",
    "demo.label": "بيانات تجريبية خيالية",
    "demo.offline":
      "لقطة تجريبية دون اتصال — بيانات توضيحية وليست نتيجة حية للشركة.",
  },
} satisfies Record<Locale, Record<string, string>>;

export function isLocale(value: string): value is Locale {
  return value === "ar" || value === "en";
}

export function directionFor(locale: Locale): "rtl" | "ltr" {
  return locale === "ar" ? "rtl" : "ltr";
}

export function t(locale: Locale, key: string): string {
  const localized: Record<string, string> = messages[locale];
  const fallback: Record<string, string> = messages.en;
  return localized[key] ?? fallback[key] ?? key;
}

export function formatCompactNumber(value: number, locale: Locale): string {
  return new Intl.NumberFormat(locale === "ar" ? "ar-JO" : "en-US", {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(value);
}

export function formatNumber(
  value: number,
  locale: Locale,
  maximumFractionDigits = 1,
): string {
  return new Intl.NumberFormat(locale === "ar" ? "ar-JO" : "en-US", {
    maximumFractionDigits,
  }).format(value);
}

export function formatCurrency(
  value: number,
  currency: string,
  locale: Locale,
): string {
  return new Intl.NumberFormat(locale === "ar" ? "ar-JO" : "en-US", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(value);
}

export function formatDate(value: string, locale: Locale): string {
  const date = new Date(`${value}T12:00:00Z`);
  return new Intl.DateTimeFormat(locale === "ar" ? "ar-JO" : "en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    timeZone: "UTC",
  }).format(date);
}
