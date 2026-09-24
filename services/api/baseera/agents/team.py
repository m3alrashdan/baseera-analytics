"""The analyst team: who does what.

Each specialist owns a slice of the craft and a set of tools. The chief analyst plans,
delegates, synthesises and answers; the critic checks every claim before it ships.
"""

from __future__ import annotations

from typing import Any

from .common import bi

TEAM: list[dict[str, Any]] = [
    {
        "id": "chief",
        "name": bi("Chief Analyst", "كبير المحللين"),
        "role": bi(
            "Frames the business question, plans the analysis, delegates to specialists and "
            "writes the answer and the executive summary.",
            "يصوغ سؤال العمل ويخطط للتحليل ويوزّع المهام على المختصين ويكتب الإجابة والملخص التنفيذي.",
        ),
        "icon": "brain",
    },
    {
        "id": "data_engineer",
        "name": bi("Data Engineer", "مهندس البيانات"),
        "role": bi(
            "Understands the schema (time, measures, dimensions, entities), audits quality and "
            "states what the data can and cannot support.",
            "يفهم بنية البيانات (الزمن والمقاييس والأبعاد والكيانات) ويدقق الجودة ويحدد ما تدعمه البيانات.",
        ),
        "icon": "database",
    },
    {
        "id": "statistician",
        "name": bi("Statistician", "الإحصائي"),
        "role": bi(
            "Headline numbers, distributions, correlations, concentration and hypothesis tests "
            "with effect sizes and multiple-testing control.",
            "الأرقام الرئيسية والتوزيعات والارتباطات والتركّز واختبارات الفرضيات مع حجم الأثر وضبط المقارنات المتعددة.",
        ),
        "icon": "sigma",
    },
    {
        "id": "forecaster",
        "name": bi("Forecaster", "خبير التنبؤ"),
        "role": bi(
            "Trends, seasonality, structural breaks and backtested forecasts with calibrated "
            "intervals.",
            "الاتجاهات والموسمية والتحولات الهيكلية وتنبؤات مختبرة تاريخيًا بفواصل ثقة معايرة.",
        ),
        "icon": "trending",
    },
    {
        "id": "detective",
        "name": bi("Root-cause Detective", "محقق الأسباب"),
        "role": bi(
            "Explains why numbers moved (contribution and mix/rate analysis) and hunts anomalies "
            "in time and in records.",
            "يفسّر سبب تحرك الأرقام (تحليل المساهمة والمزيج والمعدل) ويرصد الشذوذ في الزمن والسجلات.",
        ),
        "icon": "search",
    },
    {
        "id": "data_scientist",
        "name": bi("Data Scientist", "عالم البيانات"),
        "role": bi(
            "Key-driver models, segmentation, customer value tiers and cohort retention.",
            "نماذج العوامل المؤثرة والتقسيم إلى شرائح وشرائح قيمة العملاء والاحتفاظ حسب الدفعة.",
        ),
        "icon": "network",
    },
    {
        "id": "strategist",
        "name": bi("Business Strategist", "المستشار الاستراتيجي"),
        "role": bi(
            "Turns findings into prioritised, quantified recommendations and what-if scenarios.",
            "يحوّل النتائج إلى توصيات مرتبة الأولوية ومحددة الأثر وسيناريوهات «ماذا لو».",
        ),
        "icon": "target",
    },
    {
        "id": "critic",
        "name": bi("Quality Reviewer", "المراجع الناقد"),
        "role": bi(
            "Challenges every claim: sample size, significance, causality language, forecast "
            "skill, data quality, and verifies every number in the narrative.",
            "يراجع كل ادعاء: حجم العينة والدلالة ولغة السببية ومهارة التنبؤ وجودة البيانات، ويتحقق من كل رقم في النص.",
        ),
        "icon": "shield",
    },
    {
        "id": "writer",
        "name": bi("Report Writer", "كاتب التقارير"),
        "role": bi(
            "Assembles the dossier: executive summary, evidence-linked sections, charts and exports.",
            "يجمع التقرير: الملخص التنفيذي والأقسام المرتبطة بالأدلة والرسوم والتصدير.",
        ),
        "icon": "file",
    },
]

TEAM_BY_ID = {member["id"]: member for member in TEAM}
