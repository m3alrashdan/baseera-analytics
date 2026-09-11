import type { Locale, OverviewResponse, QualityIssue } from "./contracts";

export const DEMO_REPORTING_DATE = "2026-06-30";

export function demoOverview(locale: Locale): OverviewResponse {
  const ar = locale === "ar";
  return {
    status: "partial",
    company: {
      name: ar ? "شركة نماء للخدمات الصناعية" : "Namaa Industrial Services",
      demo: true,
      currency: "JOD",
      timezone: "Asia/Amman",
    },
    period: {
      label: ar ? "يناير–يونيو ٢٠٢٦" : "Jan–Jun 2026",
      comparison: ar ? "الفترة السابقة" : "previous period",
    },
    brief: ar
      ? "نمت الإيرادات، لكن الخصومات ومزيج المنتجات قلّصا الهامش. ضغط الدعم يستحق مراجعة التغطية الأسبوعية."
      : "Revenue grew, while discounts and product mix narrowed margin. Support pressure makes weekend coverage worth reviewing.",
    metrics: [
      {
        id: "revenue_net",
        name: ar ? "صافي الإيرادات" : "Net revenue",
        value: 1842500,
        unit: "JOD",
        change: 12.4,
        trend: "up",
        definition: ar
          ? "إيرادات الفواتير ناقص المبالغ المستردة المعتمدة."
          : "Invoiced revenue less approved refunds.",
        source: ar ? "فواتير ERP · الإصدار 17" : "ERP invoices · v17",
        freshness: ar
          ? "تاريخ العرض ٣٠ يونيو ٢٠٢٦"
          : "Reporting date 30 Jun 2026",
        result_id: "result_demo_rev_17",
        warning: ar
          ? "يونيو فترة غير مكتملة."
          : "June is an incomplete period.",
      },
      {
        id: "gross_margin",
        name: ar ? "هامش الربح الإجمالي" : "Gross margin",
        value: 26.8,
        unit: "%",
        change: -3.1,
        trend: "down",
        definition: ar
          ? "صافي الإيرادات ناقص التكلفة المتاحة، كنسبة من صافي الإيرادات."
          : "Net revenue less available cost, divided by net revenue.",
        source: ar
          ? "الفواتير والتكلفة · الإصدار 17"
          : "Invoices + available cost · v17",
        freshness: ar
          ? "تاريخ العرض ٣٠ يونيو ٢٠٢٦"
          : "Reporting date 30 Jun 2026",
        result_id: "result_demo_margin_17",
        warning: ar
          ? "التكلفة مفقودة في ٢٫٧٪ من البنود؛ استُبعدت من الهامش."
          : "Cost is missing for 2.7% of lines; those lines are excluded from margin.",
      },
      {
        id: "support_open",
        name: ar ? "حالات الدعم المفتوحة" : "Open support cases",
        value: 284,
        unit: ar ? "حالة" : "cases",
        change: 31,
        trend: "up",
        definition: ar
          ? "الحالات المستلمة التي لا تحمل وقت حل صالحًا حتى نهاية النطاق."
          : "Received cases without a valid resolution timestamp at scope end.",
        source: ar ? "نظام الدعم · الإصدار 9" : "Support system · v9",
        freshness: ar
          ? "تاريخ العرض ٣٠ يونيو ٢٠٢٦"
          : "Reporting date 30 Jun 2026",
        result_id: "result_demo_support_09",
      },
      {
        id: "projects_at_risk",
        name: ar ? "مشاريع معرّضة للتأخير" : "Projects at risk",
        value: 4,
        unit: ar ? "مشاريع" : "projects",
        change: 1,
        trend: "up",
        definition: ar
          ? "مشاريع مفتوحة لها معلم متأخر أو تبعية حرجة غير محلولة."
          : "Open projects with an overdue milestone or unresolved critical dependency.",
        source: ar ? "سجل المشاريع · الإصدار 12" : "Project register · v12",
        freshness: ar
          ? "تاريخ العرض ٣٠ يونيو ٢٠٢٦"
          : "Reporting date 30 Jun 2026",
        result_id: "result_demo_projects_12",
      },
    ],
    trend: [
      { period: ar ? "يناير" : "Jan", current: 278000, comparison: 249000 },
      { period: ar ? "فبراير" : "Feb", current: 291000, comparison: 260000 },
      { period: ar ? "مارس" : "Mar", current: 304000, comparison: 271000 },
      { period: ar ? "أبريل" : "Apr", current: 315000, comparison: 278000 },
      { period: ar ? "مايو" : "May", current: 343000, comparison: 291000 },
      { period: ar ? "يونيو" : "Jun", current: 311500, comparison: 290000 },
    ],
    attention: [
      {
        id: "att_1",
        severity: "critical",
        title: ar
          ? "ضغط الدعم تجاوز الطاقة"
          : "Support demand exceeds capacity",
        detail: ar
          ? "الطلب أعلى من التغطية المتاحة بـ٣١٪، خصوصًا في نهاية الأسبوع."
          : "Demand is 31% above staffed capacity, concentrated on weekends.",
      },
      {
        id: "att_2",
        severity: "warning",
        title: ar
          ? "الهامش تراجع رغم نمو الإيرادات"
          : "Margin narrowed despite growth",
        detail: ar
          ? "الخصومات ومزيج الخدمات يفسران معظم فرق الهامش حسابيًا، لا سببيًا."
          : "Discounts and service mix account for most of the arithmetic variance; this is not a causal claim.",
      },
      {
        id: "att_3",
        severity: "warning",
        title: ar
          ? "تبعية مورد تهدد مشروع أطلس"
          : "Supplier dependency threatens Atlas",
        detail: ar
          ? "تأخر التسليم ١١ يومًا والمعلم التالي خلال ٦ أيام."
          : "Delivery is 11 days late; the next milestone is due in 6 days.",
      },
    ],
    departments: [
      {
        name: ar ? "عمليات العملاء" : "Customer operations",
        value: 131,
        target: 100,
      },
      { name: ar ? "التنفيذ" : "Delivery", value: 114, target: 100 },
      { name: ar ? "المبيعات" : "Sales", value: 93, target: 100 },
      { name: ar ? "المالية" : "Finance", value: 76, target: 100 },
    ],
    actions: [
      {
        id: "dec_1",
        title: ar ? "مراجعة تغطية نهاية الأسبوع" : "Review weekend coverage",
        owner: ar ? "العمليات" : "Operations",
        due: "2026-07-06",
        status: ar ? "للمراجعة" : "review",
      },
      {
        id: "dec_2",
        title: ar
          ? "إعادة تفاوض موعد مورد أطلس"
          : "Renegotiate Atlas supplier date",
        owner: ar ? "المشتريات" : "Procurement",
        due: "2026-07-03",
        status: ar ? "مسودة" : "draft",
      },
    ],
  };
}

export const demoQualityIssues = (locale: Locale): QualityIssue[] => {
  const ar = locale === "ar";
  return [
    {
      id: "dup-batch",
      title: ar ? "دفعة استيراد مكررة" : "Duplicated import batch",
      field: "batch_id",
      count: 428,
      severity: "high",
      example: "batch_2026_05_14",
      treatment: ar
        ? "عزل النسخة الثانية حسب مفتاح الدفعة وموقع الصف"
        : "Quarantine the second copy using batch key and row provenance",
      rationale: ar
        ? "تطابق مفتاح العمل وبصمة الصف والمصدر."
        : "Business key, row fingerprint, and source location match.",
      accepted: true,
    },
    {
      id: "amb-date",
      title: ar ? "تواريخ محلية ملتبسة" : "Ambiguous locale dates",
      field: "order_date",
      count: 37,
      severity: "high",
      example: "03/04/2026",
      treatment: ar
        ? "احتفظ بها كاستثناء حتى اختيار نمط التاريخ"
        : "Retain as exceptions until a date convention is approved",
      rationale: ar
        ? "يمكن قراءتها ٣ أبريل أو ٤ مارس."
        : "Could mean 3 April or 4 March.",
      accepted: true,
    },
    {
      id: "missing-cost",
      title: ar ? "تكلفة غير متوفرة" : "Missing item cost",
      field: "unit_cost",
      count: 119,
      severity: "medium",
      example: "null",
      treatment: ar
        ? "علّمها غير معروفة واستبعدها من الهامش"
        : "Mark unknown and exclude from margin",
      rationale: ar
        ? "لا يوجد مصدر موثوق للتعويض؛ الصفر سيحرّف الهامش."
        : "No reliable imputation source; zero would distort margin.",
      accepted: true,
    },
    {
      id: "negative-return",
      title: ar ? "قيم سالبة مشروعة" : "Legitimate negative returns",
      field: "net_amount",
      count: 62,
      severity: "low",
      example: "-184.50",
      treatment: ar
        ? "احتفظ بها واربطها بالفاتورة الأصلية"
        : "Retain and link to the original invoice",
      rationale: ar
        ? "تحمل نوع حركة إرجاع معتمدًا."
        : "Rows carry an approved return transaction type.",
      accepted: true,
    },
  ];
};

export const moduleRows: Record<
  string,
  Array<Record<string, string | number>>
> = {
  customers: [
    {
      Customer: "Sahab Logistics",
      Segment: "Enterprise",
      Revenue: 246800,
      Returns: -12400,
      Margin: "24.1%",
    },
    {
      Customer: "Afaq Retail Group",
      Segment: "Growth",
      Revenue: 189300,
      Returns: -4200,
      Margin: "31.8%",
    },
    {
      Customer: "Madar Clinics",
      Segment: "Enterprise",
      Revenue: 172600,
      Returns: -2100,
      Margin: "— missing cost",
    },
  ],
  people: [
    {
      Team: "Customer operations",
      Available: 960,
      Assigned: 1258,
      Coverage: "76%",
      Status: "Review",
    },
    {
      Team: "Delivery",
      Available: 1440,
      Assigned: 1642,
      Coverage: "88%",
      Status: "Review",
    },
    {
      Team: "Finance",
      Available: 720,
      Assigned: 548,
      Coverage: "100%",
      Status: "Balanced",
    },
  ],
  projects: [
    {
      Project: "Atlas rollout",
      Progress: "68%",
      Variance: "+11 days",
      Budget: "72% used",
      Dependency: "Northstar Components",
    },
    {
      Project: "Service hub",
      Progress: "82%",
      Variance: "+2 days",
      Budget: "79% used",
      Dependency: "Approval",
    },
    {
      Project: "Ledger renewal",
      Progress: "54%",
      Variance: "On plan",
      Budget: "49% used",
      Dependency: "None",
    },
  ],
  operations: [
    {
      Path: "Receive → validate → approve",
      Cases: 4821,
      Processing: "3.4 h",
      Waiting: "19.6 h",
      Rework: "8.2%",
    },
    {
      Path: "Receive → return → validate → approve",
      Cases: 614,
      Processing: "5.8 h",
      Waiting: "41.2 h",
      Rework: "31.4%",
    },
  ],
  finance: [
    {
      Category: "Contractors",
      Actual: 284000,
      Budget: 250000,
      Variance: "+13.6%",
      Commitment: 42000,
    },
    {
      Category: "Cloud & software",
      Actual: 118500,
      Budget: 126000,
      Variance: "−6.0%",
      Commitment: 17600,
    },
    {
      Category: "Travel",
      Actual: 47200,
      Budget: 65000,
      Variance: "−27.4%",
      Commitment: 8400,
    },
  ],
  support: [
    {
      Queue: "Platform",
      Open: 116,
      MedianResponse: "42 min",
      Resolution: "19.4 h",
      Reopened: "7.8%",
    },
    {
      Queue: "Field service",
      Open: 98,
      MedianResponse: "1 h 12 min",
      Resolution: "31.1 h",
      Reopened: "4.2%",
    },
    {
      Queue: "Billing",
      Open: 70,
      MedianResponse: "28 min",
      Resolution: "11.8 h",
      Reopened: "9.1%",
    },
  ],
  objectives: [
    {
      Objective: "Reduce approval waiting time",
      Owner: "Operations",
      Target: "−20%",
      Progress: "On track",
      Review: "15 Jul 2026",
    },
    {
      Objective: "Restore service margin",
      Owner: "Commercial",
      Target: "30%",
      Progress: "At risk",
      Review: "8 Jul 2026",
    },
    {
      Objective: "Improve weekend SLA",
      Owner: "Support",
      Target: "90%",
      Progress: "Missing evidence",
      Review: "12 Jul 2026",
    },
  ],
};
