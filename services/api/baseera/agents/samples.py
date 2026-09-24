"""Deterministic, realistic sample datasets for trying the analyst team immediately.

The samples are fictional but carry the structure real business data has, so every
agent has something true to find:

* ``retail_sales`` – three years of orders with trend, year-end seasonality, a
  channel shift to online, a regional drop in 2026 (a change to explain), a discount
  lever that lifts volume but erodes margin, slow deliveries that drive returns and
  low satisfaction, repeat customers (RFM, cohorts) and a handful of anomalous orders.
* ``customer_churn`` – a subscription customer base whose churn is driven by support
  load, low usage, late payments, plan and tenure (a classification problem).

Both are generated with a fixed seed, in English or Arabic column names/values.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import numpy as np

SAMPLES = {
    "retail_sales": {
        "title": {"en": "Retail sales (3 years of orders)", "ar": "مبيعات التجزئة (طلبات 3 سنوات)"},
        "description": {
            "en": "Orders with regions, channels, categories, discounts, returns and satisfaction.",
            "ar": "طلبات بالمناطق والقنوات والفئات والخصومات والمرتجعات والرضا.",
        },
    },
    "customer_churn": {
        "title": {"en": "Subscription churn", "ar": "تسرب المشتركين"},
        "description": {
            "en": "Subscribers with plan, usage, support load, payments and whether they churned.",
            "ar": "مشتركون مع الباقة والاستخدام وطلبات الدعم والمدفوعات وحالة التسرب.",
        },
    },
}

RETAIL_AR = {
    "order_id": "رقم_الطلب",
    "order_date": "تاريخ_الطلب",
    "region": "المنطقة",
    "channel": "القناة",
    "category": "الفئة",
    "customer_id": "رقم_العميل",
    "customer_segment": "شريحة_العميل",
    "units": "الكمية",
    "unit_price": "سعر_الوحدة",
    "discount_pct": "نسبة_الخصم",
    "revenue": "الإيرادات",
    "cost": "التكلفة",
    "profit": "الربح",
    "delivery_days": "أيام_التوصيل",
    "returned": "مرتجع",
    "satisfaction": "الرضا",
}
VALUES_AR = {
    "North": "الشمال",
    "South": "الجنوب",
    "East": "الشرق",
    "West": "الغرب",
    "Central": "الوسط",
    "Online": "إلكتروني",
    "Retail store": "متجر",
    "Wholesale": "جملة",
    "Electronics": "إلكترونيات",
    "Home": "منزل",
    "Fashion": "أزياء",
    "Beauty": "تجميل",
    "Grocery": "بقالة",
    "Consumer": "أفراد",
    "SMB": "شركات صغيرة",
    "Corporate": "شركات كبرى",
    "Yes": "نعم",
    "No": "لا",
    "Basic": "أساسية",
    "Pro": "احترافية",
    "Enterprise": "مؤسسات",
}
CHURN_AR = {
    "customer_id": "رقم_المشترك",
    "signup_date": "تاريخ_الاشتراك",
    "plan": "الباقة",
    "region": "المنطقة",
    "monthly_fee": "الرسوم_الشهرية",
    "tenure_months": "مدة_الاشتراك_بالأشهر",
    "usage_hours": "ساعات_الاستخدام",
    "support_tickets": "طلبات_الدعم",
    "late_payments": "الدفعات_المتأخرة",
    "nps": "مؤشر_الولاء",
    "discount_pct": "نسبة_الخصم",
    "churned": "تسرب",
}


def generate(name: str, locale: str = "en") -> tuple[list[str], list[dict[str, Any]]]:
    if name == "retail_sales":
        columns, rows = _retail()
        mapping = RETAIL_AR
    elif name == "customer_churn":
        columns, rows = _churn()
        mapping = CHURN_AR
    else:
        raise KeyError(name)
    if locale == "ar":
        columns = [mapping[c] for c in columns]
        rows = [
            {mapping[k]: VALUES_AR.get(v, v) if isinstance(v, str) else v for k, v in row.items()}
            for row in rows
        ]
    return columns, rows


def _retail() -> tuple[list[str], list[dict[str, Any]]]:
    rng = np.random.default_rng(20260630)
    start, end = date(2023, 7, 1), date(2026, 6, 30)
    regions = ["North", "South", "East", "West", "Central"]
    region_weight = np.array([0.24, 0.2, 0.19, 0.17, 0.2])
    channels = ["Online", "Retail store", "Wholesale"]
    categories = {
        "Electronics": (180.0, 0.72),
        "Home": (65.0, 0.6),
        "Fashion": (48.0, 0.52),
        "Beauty": (28.0, 0.45),
        "Grocery": (12.0, 0.8),
    }
    segments = ["Consumer", "SMB", "Corporate"]
    customers = [f"C-{i:04d}" for i in range(1, 1601)]
    customer_segment = {c: segments[int(rng.choice(3, p=[0.7, 0.22, 0.08]))] for c in customers}
    customer_region = {c: regions[int(rng.choice(5, p=region_weight))] for c in customers}
    loyalty = rng.pareto(1.6, len(customers)) + 0.2
    loyalty = loyalty / loyalty.sum()
    rows: list[dict[str, Any]] = []
    day = start
    order_number = 1
    total_days = (end - start).days
    while day <= end:
        t = (day - start).days / total_days
        month = day.month
        seasonal = {11: 1.45, 12: 1.7, 1: 0.85, 2: 0.82, 6: 0.9, 7: 0.88, 8: 0.9, 9: 1.0}.get(
            month, 1.0
        )
        weekday = 1.18 if day.weekday() in (3, 4) else 0.92 if day.weekday() == 6 else 1.0
        expected = 9.0 * (1 + 0.5 * t) * seasonal * weekday
        if day == date(2025, 11, 28) or day == date(2024, 11, 29):
            expected *= 4.2  # Black Friday
        count = int(rng.poisson(expected))
        for _ in range(count):
            customer = customers[int(rng.choice(len(customers), p=loyalty))]
            region = (
                customer_region[customer] if rng.random() < 0.85 else regions[int(rng.choice(5))]
            )
            if region == "North" and day >= date(2026, 3, 1) and rng.random() < 0.45:
                continue  # a competitor opened in the North in March 2026
            online_share = 0.3 + 0.28 * t
            channel_p = np.array([online_share, 0.82 - online_share, 0.18])
            channel = channels[int(rng.choice(3, p=channel_p / channel_p.sum()))]
            category = list(categories)[int(rng.choice(5, p=[0.2, 0.22, 0.24, 0.16, 0.18]))]
            base_price, cost_ratio = categories[category]
            segment = customer_segment[customer]
            discount = float(
                np.clip(rng.gamma(2.0, 3.2) + (4 if channel == "Online" else 0), 0, 35)
            )
            if month in (11, 12):
                discount = float(np.clip(discount + 5, 0, 40))
            size = {"Consumer": 1.0, "SMB": 1.7, "Corporate": 2.6}[segment]
            size *= 2.0 if channel == "Wholesale" else 1.0
            units = max(1, int(rng.poisson(1.6 * size * (1 + discount / 45))))
            unit_price = round(base_price * float(rng.lognormal(0, 0.25)), 2)
            revenue = round(units * unit_price * (1 - discount / 100), 2)
            cost = round(units * unit_price * cost_ratio * float(rng.normal(1, 0.04)), 2)
            delivery = int(np.clip(rng.gamma(2.2, 1.4) + (2.5 if region == "West" else 0), 0, 21))
            if channel == "Retail store":
                delivery = 0
            return_p = 0.03 + 0.018 * delivery + (0.05 if category == "Fashion" else 0.0)
            returned = "Yes" if rng.random() < min(return_p, 0.6) else "No"
            satisfaction = int(
                np.clip(
                    round(
                        4.6
                        - 0.22 * delivery
                        - (1.2 if returned == "Yes" else 0)
                        + rng.normal(0, 0.6)
                    ),
                    1,
                    5,
                )
            )
            rows.append(
                {
                    "order_id": f"ORD-{order_number:06d}",
                    "order_date": day.isoformat(),
                    "region": region,
                    "channel": channel,
                    "category": category,
                    "customer_id": customer,
                    "customer_segment": segment,
                    "units": units,
                    "unit_price": unit_price,
                    "discount_pct": round(discount, 1),
                    "revenue": revenue,
                    "cost": cost,
                    "profit": round(revenue - cost, 2),
                    "delivery_days": delivery,
                    "returned": returned,
                    "satisfaction": satisfaction,
                }
            )
            order_number += 1
        day += timedelta(days=1)
    # A few data-entry errors an analyst should catch.
    for index in rng.choice(len(rows), 6, replace=False):
        row = rows[int(index)]
        row["units"] = int(row["units"]) * 10
        row["revenue"] = round(
            row["units"] * row["unit_price"] * (1 - row["discount_pct"] / 100), 2
        )
        row["cost"] = round(row["units"] * row["unit_price"] * 0.6, 2)
        row["profit"] = round(row["revenue"] - row["cost"], 2)
    columns = list(rows[0].keys())
    return columns, rows


def _churn() -> tuple[list[str], list[dict[str, Any]]]:
    rng = np.random.default_rng(20260701)
    plans = {"Basic": 19.0, "Pro": 49.0, "Enterprise": 199.0}
    regions = ["North", "South", "East", "West", "Central"]
    rows: list[dict[str, Any]] = []
    for number in range(1, 3001):
        plan = list(plans)[int(rng.choice(3, p=[0.55, 0.35, 0.10]))]
        signup = date(2023, 1, 1) + timedelta(days=int(rng.integers(0, 1260)))
        tenure = max(1, int((date(2026, 6, 30) - signup).days / 30.4))
        usage = float(np.clip(rng.gamma(3, 6) * (1.6 if plan != "Basic" else 1.0), 0, 200))
        tickets = int(rng.poisson(1.2 + (1.8 if usage < 8 else 0)))
        late = int(rng.poisson(0.35 + (0.5 if plan == "Basic" else 0)))
        discount = float(np.clip(rng.choice([0, 0, 0, 10, 15, 20]) + rng.normal(0, 1), 0, 25))
        nps = int(np.clip(round(8 - 0.9 * tickets + 0.03 * usage + rng.normal(0, 1.5)), 0, 10))
        logit = (
            -1.2
            + 0.45 * tickets
            - 0.05 * usage
            + 0.7 * late
            + (0.6 if plan == "Basic" else -0.4 if plan == "Enterprise" else 0.0)
            - 0.035 * tenure
            - 0.12 * (nps - 7)
            - 0.02 * discount
        )
        churned = "Yes" if rng.random() < 1 / (1 + np.exp(-logit)) else "No"
        fee = plans[plan] * (1 - discount / 100)
        rows.append(
            {
                "customer_id": f"S-{number:05d}",
                "signup_date": signup.isoformat(),
                "plan": plan,
                "region": regions[int(rng.integers(0, 5))],
                "monthly_fee": round(fee, 2),
                "tenure_months": tenure,
                "usage_hours": round(usage, 1),
                "support_tickets": tickets,
                "late_payments": late,
                "nps": nps,
                "discount_pct": round(discount, 1),
                "churned": churned,
            }
        )
    return list(rows[0].keys()), rows
