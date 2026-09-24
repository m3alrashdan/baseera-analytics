"""From findings to decisions: the strategist's recommendation playbook.

Each recommendation names the action, why (the evidence), the expected impact in the
business's own units where it can be sized, a priority from impact × confidence, a
rough effort, the KPI to watch, and the findings it rests on.
"""

from __future__ import annotations

from typing import Any

from .common import bi, fmt, pct


def _rec(
    key: str,
    title: tuple[str, str],
    rationale: tuple[str, str],
    actions: list[tuple[str, str]],
    impact: tuple[str, str],
    score: float,
    effort: str,
    kpis: list[str],
    based_on: list[str],
    horizon: str = "30_days",
) -> dict[str, Any]:
    priority = "P1" if score >= 0.6 else "P2" if score >= 0.4 else "P3"
    return {
        "id": key,
        "title": bi(*title),
        "rationale": bi(*rationale),
        "actions": [bi(*a) for a in actions],
        "expected_impact": bi(*impact),
        "priority": priority,
        "score": round(score, 3),
        "effort": effort,
        "horizon": horizon,
        "kpis_to_track": kpis,
        "based_on": based_on,
    }


def recommend(findings: list[dict[str, Any]], frame_info: dict[str, Any]) -> list[dict[str, Any]]:
    kpi = frame_info.get("primary_kpi") or frame_info.get("outcome") or "records"
    recs: list[dict[str, Any]] = []

    def weight(f: dict[str, Any]) -> float:
        return f["importance"] * (0.5 + 0.5 * f["confidence_score"])

    for f in findings:
        e = f.get("evidence", {})
        kind = f["kind"]
        if kind == "data_quality":
            recs.append(
                _rec(
                    "fix-data-quality",
                    (
                        "Fix the data issues before relying on the numbers",
                        "عالج مشكلات البيانات قبل الاعتماد على الأرقام",
                    ),
                    (f["summary"]["en"], f["summary"]["ar"]),
                    [
                        (
                            "Apply the proposed cleaning steps in Data preparation and re-run the analysis.",
                            "طبّق خطوات التنظيف المقترحة في مساحة تجهيز البيانات ثم أعد التحليل.",
                        ),
                        (
                            "Add validation at the point of data entry for the affected columns.",
                            "أضف تحققًا عند إدخال البيانات للأعمدة المتأثرة.",
                        ),
                    ],
                    (
                        "More reliable totals, trends and models.",
                        "مجاميع واتجاهات ونماذج أكثر موثوقية.",
                    ),
                    weight(f) + 0.1,
                    "low",
                    ["data_quality_score"],
                    [f["id"]],
                    "7_days",
                )
            )
        elif kind == "anomaly_records" and e.get("extreme"):
            recs.append(
                _rec(
                    "audit-extreme-records",
                    (
                        f"Audit the {e['extreme']} extreme records",
                        f"دقّق السجلات المتطرفة الـ{e['extreme']}",
                    ),
                    (f["summary"]["en"], f["summary"]["ar"]),
                    [
                        (
                            "Confirm each record with its source system; correct or exclude data-entry errors.",
                            "تحقّق من كل سجل مع نظامه المصدر؛ صحّح أخطاء الإدخال أو استبعدها.",
                        ),
                        (
                            "Re-run the analysis after correction to see the clean picture.",
                            "أعد التحليل بعد التصحيح لرؤية الصورة الصحيحة.",
                        ),
                    ],
                    (
                        f"Removes distortion worth {pct(e.get('value_share'))} of {kpi}."
                        if e.get("value_share")
                        else "Removes distortion from totals and models.",
                        f"يزيل تشويهًا يعادل {pct(e.get('value_share'))} من {kpi}."
                        if e.get("value_share")
                        else "يزيل التشويه من المجاميع والنماذج.",
                    ),
                    weight(f),
                    "low",
                    [kpi],
                    [f["id"]],
                    "7_days",
                )
            )
        elif kind == "change":
            relative = e.get("relative_change") or 0.0
            path = e.get("root_cause_path") or []
            counter = e.get("counter_movement")
            normal = e.get("within_normal_range") is True
            if relative < -0.03 and path and not normal:
                step = path[0]
                recs.append(
                    _rec(
                        f"recover-{step['dimension']}-{step['member']}",
                        (
                            f"Recovery plan for {step['dimension']} = {step['member']}",
                            f"خطة تعافٍ لـ{step['dimension']} = {step['member']}",
                        ),
                        (f["summary"]["en"], f["summary"]["ar"]),
                        [
                            (
                                f"Interview the owners of {step['member']} about what changed in {', '.join(s['member'] for s in path)}.",
                                f"استطلع مسؤولي {step['member']} عمّا تغيّر في {'، '.join(s['member'] for s in path)}.",
                            ),
                            (
                                "Compare pricing, availability and competitor activity for the period.",
                                "قارن التسعير والتوفر ونشاط المنافسين خلال الفترة.",
                            ),
                            (
                                "Set a weekly recovery target and review it.",
                                "حدد هدف تعافٍ أسبوعيًا وراجعه.",
                            ),
                        ],
                        (
                            f"Closing the gap recovers ≈{fmt(abs(step['delta']))} of {kpi} per period.",
                            f"سد الفجوة يستعيد ≈{fmt(abs(step['delta']))} من {kpi} لكل فترة.",
                        ),
                        weight(f) + 0.1,
                        "medium",
                        [kpi],
                        [f["id"]],
                    )
                )
            elif (
                counter
                and counter.get("delta", 0) < 0
                and (counter.get("member_change") or 0) <= -0.15
            ):
                recs.append(
                    _rec(
                        f"fix-drag-{counter['dimension']}-{counter['member']}",
                        (
                            f"Address the drag from {counter['dimension']} = {counter['member']}",
                            f"عالج التراجع في {counter['dimension']} = {counter['member']}",
                        ),
                        (
                            f"{counter['member']} declined {pct(counter.get('member_change'))} "
                            f"({fmt(counter['delta'])}) while the total moved {pct(relative, signed=True)}.",
                            f"تراجع {counter['member']} بنسبة {pct(counter.get('member_change'))} "
                            f"({fmt(counter['delta'])}) بينما تحرك الإجمالي {pct(relative, signed=True)}.",
                        ),
                        [
                            (
                                f"Diagnose {counter['member']} specifically: volumes, prices, customers lost.",
                                f"شخّص {counter['member']} تحديدًا: الكميات والأسعار والعملاء المفقودين.",
                            ),
                            (
                                "Replicate what worked in the growing members.",
                                "كرر ما نجح في العناصر النامية.",
                            ),
                        ],
                        (
                            f"Up to {fmt(abs(counter['delta']))} of {kpi} per period.",
                            f"حتى {fmt(abs(counter['delta']))} من {kpi} لكل فترة.",
                        ),
                        weight(f),
                        "medium",
                        [kpi],
                        [f["id"]],
                    )
                )
        elif kind == "trend" and e.get("direction") == "decreasing":
            recs.append(
                _rec(
                    "reverse-decline",
                    (f"Treat the decline in {kpi} as a priority", f"اعتبر تراجع {kpi} أولوية"),
                    (f["summary"]["en"], f["summary"]["ar"]),
                    [
                        (
                            "Use the change explanation to target the members driving the decline.",
                            "استخدم تفسير التغيّر لاستهداف العناصر المسببة للتراجع.",
                        ),
                        (
                            "Review the forecast weekly against actuals.",
                            "راجع التنبؤ أسبوعيًا مقارنة بالفعلي.",
                        ),
                    ],
                    (
                        "Stops further erosion of the main KPI.",
                        "يوقف مزيدًا من تآكل المؤشر الرئيسي.",
                    ),
                    weight(f) + 0.1,
                    "medium",
                    [kpi],
                    [f["id"]],
                )
            )
        elif kind == "forecast":
            change = e.get("expected_change")
            if change is None:
                continue
            if change > 0.05:
                title = (
                    f"Prepare capacity for {pct(change, signed=True)} {kpi}",
                    f"جهّز الطاقة لنمو {kpi} بنسبة {pct(change, signed=True)}",
                )
                actions = [
                    (
                        "Align inventory, staffing and cash plans with the forecast range, not just the point.",
                        "واءم المخزون والتوظيف والسيولة مع مدى التنبؤ لا القيمة المفردة فقط.",
                    ),
                    (
                        "Track actuals against the interval each period; re-forecast on a breach.",
                        "تابع الفعلي مقابل الفاصل كل فترة وأعد التنبؤ عند الخروج عنه.",
                    ),
                ]
            elif change < -0.05:
                title = (
                    f"Plan for a {pct(change, signed=True)} dip in {kpi}",
                    f"خطط لانخفاض {kpi} بنسبة {pct(change, signed=True)}",
                )
                actions = [
                    (
                        "Adjust purchasing and variable costs to the lower expected volume.",
                        "عدّل المشتريات والتكاليف المتغيرة وفق الحجم المتوقع الأقل.",
                    ),
                    (
                        "Launch demand actions early in the weakest periods.",
                        "أطلق مبادرات لتحفيز الطلب مبكرًا في أضعف الفترات.",
                    ),
                ]
            else:
                continue
            recs.append(
                _rec(
                    "plan-to-forecast",
                    title,
                    (f["summary"]["en"], f["summary"]["ar"]),
                    actions,
                    (
                        f["summary"]["en"].split(". Model")[0] + ".",
                        f["summary"]["ar"].split(". النموذج")[0] + ".",
                    ),
                    weight(f),
                    "medium",
                    [kpi],
                    [f["id"]],
                    "90_days",
                )
            )
        elif kind == "seasonality":
            recs.append(
                _rec(
                    "plan-for-season",
                    (
                        "Plan inventory, staff and campaigns around the seasonal peaks",
                        "خطط للمخزون والموظفين والحملات حول ذروة الموسم",
                    ),
                    (f["summary"]["en"], f["summary"]["ar"]),
                    [
                        (
                            "Build stock and staffing 4–6 weeks before peak months.",
                            "جهّز المخزون والموظفين قبل أشهر الذروة بـ4–6 أسابيع.",
                        ),
                        (
                            "Use the weak months for maintenance, training and retention campaigns.",
                            "استغل الأشهر الضعيفة للصيانة والتدريب وحملات الاحتفاظ.",
                        ),
                    ],
                    (
                        "Fewer stock-outs at peak, lower idle cost in troughs.",
                        "نفاد أقل في الذروة وتكلفة خمول أقل في الركود.",
                    ),
                    weight(f),
                    "medium",
                    [kpi],
                    [f["id"]],
                    "90_days",
                )
            )
        elif kind == "concentration":
            dimension = e.get("dimension")
            top_share = e.get("top_share") or 0
            recs.append(
                _rec(
                    f"manage-concentration-{dimension}",
                    (
                        f"Manage dependency on the top {dimension} values",
                        f"أدِر الاعتماد على أعلى قيم {dimension}",
                    ),
                    (f["summary"]["en"], f["summary"]["ar"]),
                    [
                        (
                            f"Set up a key-account plan for the largest {dimension} values.",
                            f"ضع خطة حسابات رئيسية لأكبر قيم {dimension}.",
                        ),
                        (
                            "Grow the long tail to reduce single-point risk.",
                            "نمِّ القاعدة الأوسع لتقليل مخاطر الاعتماد على عنصر واحد.",
                        ),
                    ],
                    (
                        f"Protects the {pct(top_share)} held by the largest member.",
                        f"يحمي نسبة {pct(top_share)} التي يستحوذ عليها العنصر الأكبر.",
                    ),
                    weight(f) - 0.05,
                    "medium",
                    [kpi],
                    [f["id"]],
                    "90_days",
                )
            )
        elif kind == "group_difference":
            dimension = e.get("dimension")
            recs.append(
                _rec(
                    f"close-gap-{dimension}",
                    (
                        f"Lean into {e.get('top_group')} and review {e.get('bottom_group')} ({dimension})",
                        f"ركّز على {e.get('top_group')} وراجع {e.get('bottom_group')} ({dimension})",
                    ),
                    (f["summary"]["en"], f["summary"]["ar"]),
                    [
                        (
                            "First establish whether the gap is structural (price point, customer type) or performance; the data shows it, not why.",
                            "حدد أولًا إن كانت الفجوة هيكلية (مستوى السعر أو نوع العميل) أم أداءً؛ البيانات تُظهرها ولا تفسّر سببها.",
                        ),
                        (
                            f"If structural: steer promotion and sales effort toward {e.get('top_group')}.",
                            f"إن كانت هيكلية: وجّه الترويج وجهود البيع نحو {e.get('top_group')}.",
                        ),
                        (
                            f"If performance: document what works in {e.get('top_group')} and pilot it in {e.get('bottom_group')}.",
                            f"إن كانت أداءً: وثّق ما ينجح في {e.get('top_group')} وجرّبه في {e.get('bottom_group')}.",
                        ),
                    ],
                    (
                        f"Gap of {fmt(e.get('gap'))} per record between best and worst.",
                        f"فجوة قدرها {fmt(e.get('gap'))} لكل سجل بين الأعلى والأدنى.",
                    ),
                    weight(f) - 0.05,
                    "medium",
                    [kpi],
                    [f["id"]],
                )
            )
        elif kind == "what_if":
            lever, target = e.get("lever"), e.get("target")
            step = e.get("step", 0)
            improves = True
            recs.append(
                _rec(
                    f"pull-lever-{lever}-{target}",
                    (
                        f"Test moving {lever} by {step:+.0f}% to improve {target}",
                        f"اختبر تغيير {lever} بنسبة {step:+.0f}% لتحسين {target}",
                    ),
                    (f["summary"]["en"], f["summary"]["ar"]),
                    [
                        (
                            f"Run a controlled pilot (A/B or one region) changing {lever} only.",
                            f"نفّذ تجربة مضبوطة (A/B أو منطقة واحدة) بتغيير {lever} فقط.",
                        ),
                        (
                            "Measure the target against a control group for 4–6 weeks before scaling.",
                            "قِس الهدف مقابل مجموعة ضابطة لمدة 4–6 أسابيع قبل التعميم.",
                        ),
                    ],
                    (f["summary"]["en"], f["summary"]["ar"]),
                    weight(f) if improves else 0.2,
                    "medium",
                    [target or kpi, lever or ""],
                    [f["id"]],
                    "90_days",
                )
            )
        elif kind == "customers" and (e.get("at_risk_share") or 0) > 0.02:
            recs.append(
                _rec(
                    "win-back-at-risk",
                    (
                        f"Win back the {e.get('at_risk_entities')} at-risk customers",
                        f"استعد {e.get('at_risk_entities')} من العملاء المعرضين للفقدان",
                    ),
                    (f["summary"]["en"], f["summary"]["ar"]),
                    [
                        (
                            "Contact at-risk high-value customers personally within two weeks.",
                            "تواصل شخصيًا مع العملاء ذوي القيمة العالية المعرضين للفقدان خلال أسبوعين.",
                        ),
                        (
                            "Offer a targeted incentive and track reactivation.",
                            "قدّم حافزًا موجّهًا وتابع عودة النشاط.",
                        ),
                        (
                            "Create a 'Champions' loyalty track to keep the best customers.",
                            "أنشئ برنامج ولاء لـ«الأبطال» للحفاظ على أفضل العملاء.",
                        ),
                    ],
                    (
                        f"Historic value of the at-risk tier: {fmt(e.get('at_risk_value'))}.",
                        f"القيمة التاريخية لشريحة المعرضين للفقدان: {fmt(e.get('at_risk_value'))}.",
                    ),
                    weight(f) + 0.05,
                    "low",
                    ["repeat_rate", kpi],
                    [f["id"]],
                )
            )
        elif kind == "retention" and (e.get("retention") or 1) < 0.25:
            recs.append(
                _rec(
                    "improve-early-retention",
                    ("Improve early repeat behaviour", "حسّن تكرار التعامل المبكر"),
                    (f["summary"]["en"], f["summary"]["ar"]),
                    [
                        (
                            "Design an onboarding / second-purchase journey for new customers.",
                            "صمّم رحلة ترحيب وشراء ثانٍ للعملاء الجدد.",
                        ),
                        (
                            "Track next-period retention by cohort monthly.",
                            "تابع الاحتفاظ في الفترة التالية لكل دفعة شهريًا.",
                        ),
                    ],
                    (
                        f"Next-period retention is only {pct(e.get('retention'))}; each point gained compounds.",
                        f"الاحتفاظ في الفترة التالية {pct(e.get('retention'))} فقط؛ وكل نقطة تحسن تتراكم.",
                    ),
                    weight(f),
                    "medium",
                    ["retention_rate"],
                    [f["id"]],
                    "90_days",
                )
            )
    # Deduplicate by id, keep the strongest, order by score.
    unique: dict[str, dict[str, Any]] = {}
    for rec in recs:
        if rec["id"] not in unique or rec["score"] > unique[rec["id"]]["score"]:
            unique[rec["id"]] = rec
    ordered = sorted(unique.values(), key=lambda r: -r["score"])
    for index, rec in enumerate(ordered, 1):
        rec["rank"] = index
    return ordered[:10]


def next_questions(
    frame_info: dict[str, Any], findings: list[dict[str, Any]]
) -> list[dict[str, str]]:
    kpi = frame_info.get("primary_kpi") or frame_info.get("outcome") or "the KPI"
    questions = []
    kinds = {f["kind"] for f in findings}
    change = next((f for f in findings if f["kind"] == "change"), None)
    if change and change["evidence"].get("root_cause_path"):
        step = change["evidence"]["root_cause_path"][0]
        questions.append(
            bi(
                f"What happened to {step['member']} ({step['dimension']}) in the last period, week by week?",
                f"ماذا حدث لـ{step['member']} ({step['dimension']}) في الفترة الأخيرة أسبوعًا بأسبوع؟",
            )
        )
    if "drivers" in kinds:
        questions.append(
            bi(
                f"Which lever would lift {kpi} most for the least effort, and what would a 10% change do?",
                f"أي رافعة ترفع {kpi} بأكبر قدر وبأقل جهد، وماذا يفعل تغيير بنسبة 10%؟",
            )
        )
    if "forecast" in kinds:
        questions.append(
            bi(
                f"What is the forecast for {kpi} in each region or channel separately?",
                f"ما التنبؤ لـ{kpi} في كل منطقة أو قناة على حدة؟",
            )
        )
    if "customers" in kinds:
        questions.append(
            bi(
                "Who exactly are the at-risk high-value customers?",
                "من هم بالتحديد العملاء ذوو القيمة العالية المعرضون للفقدان؟",
            )
        )
    questions.append(
        bi(
            f"Which combinations of dimensions have the lowest {kpi} per record?",
            f"ما تركيبات الأبعاد التي لديها أدنى {kpi} لكل سجل؟",
        )
    )
    return questions[:5]
