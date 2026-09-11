from __future__ import annotations

import argparse
import random
from datetime import date, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from .auth import hash_password
from .config import load_settings
from .database import Base, build_engine, build_session_factory
from .models import (
    Customer,
    Department,
    Employee,
    Expense,
    Membership,
    Objective,
    Organization,
    ProcessEvent,
    Project,
    SalesOrder,
    Supplier,
    SupportCase,
    User,
)

DEMO_TENANT_ID = "tenant-demo"
EMPTY_TENANT_ID = "tenant-empty"
DEMO_REPORTING_DATE = date(2026, 6, 30)

DEPARTMENTS = [
    ("dept-sales", "Sales", "المبيعات"),
    ("dept-support", "Customer Support", "دعم العملاء"),
    ("dept-operations", "Operations", "العمليات"),
    ("dept-technology", "Technology", "التقنية"),
    ("dept-finance", "Finance", "المالية"),
    ("dept-people", "People", "الموارد البشرية"),
    ("dept-strategy", "Strategy", "الاستراتيجية"),
]


def _month_start(offset: int) -> date:
    year = 2024 + (6 + offset) // 12
    month = (6 + offset) % 12 + 1
    return date(year, month, 1)


def seed_demo(db: Session) -> None:
    if db.get(Organization, DEMO_TENANT_ID) is not None:
        return
    rng = random.Random(20260630)
    demo = Organization(
        id=DEMO_TENANT_ID,
        name_en="Namaa Industrial Services (Fictional Demo)",
        name_ar="شركة نماء للخدمات الصناعية",
        timezone="Asia/Amman",
        currency="JOD",
        is_demo=True,
        reporting_date=DEMO_REPORTING_DATE,
    )
    empty = Organization(
        id=EMPTY_TENANT_ID,
        name_en="Empty workspace",
        name_ar="مساحة عمل فارغة",
        timezone="Asia/Amman",
        currency="JOD",
        is_demo=False,
        reporting_date=DEMO_REPORTING_DATE,
    )
    db.add_all([demo, empty])
    db.flush()

    users = [
        User(
            id="user-executive",
            email="executive@demo.baseera.local",
            display_name="Rana Al-Hadidi",
            password_hash=hash_password("BaseeraDemo!2026"),
        ),
        User(
            id="user-manager",
            email="manager@demo.baseera.local",
            display_name="Sami Nassar",
            password_hash=hash_password("BaseeraManager!2026"),
        ),
        User(
            id="user-hr",
            email="hr@demo.baseera.local",
            display_name="Lina Haddad",
            password_hash=hash_password("BaseeraHR!2026"),
        ),
        User(
            id="user-empty",
            email="viewer@empty.baseera.local",
            display_name="Empty Workspace Viewer",
            password_hash=hash_password("BaseeraEmpty!2026"),
        ),
    ]
    db.add_all(users)
    db.flush()
    db.add_all(
        [
            Membership(
                id="membership-executive",
                organization_id=DEMO_TENANT_ID,
                user_id="user-executive",
                role="executive",
                department_ids=[],
                permissions=["analytics:read", "artifacts:write", "people:aggregate"],
            ),
            Membership(
                id="membership-manager",
                organization_id=DEMO_TENANT_ID,
                user_id="user-manager",
                role="department_manager",
                department_ids=["dept-support"],
                permissions=["analytics:read", "artifacts:write", "people:department"],
            ),
            Membership(
                id="membership-hr",
                organization_id=DEMO_TENANT_ID,
                user_id="user-hr",
                role="hr_specialist",
                department_ids=[],
                permissions=["analytics:read", "people:approved", "artifacts:write"],
            ),
            Membership(
                id="membership-empty",
                organization_id=EMPTY_TENANT_ID,
                user_id="user-empty",
                role="viewer",
                department_ids=[],
                permissions=["analytics:read"],
            ),
        ]
    )
    db.flush()

    departments = [
        Department(id=item[0], organization_id=DEMO_TENANT_ID, name_en=item[1], name_ar=item[2])
        for item in DEPARTMENTS
    ]
    db.add_all(departments)
    db.flush()

    skill_sets = [
        ["analytics", "arabic"],
        ["customer_service", "arabic"],
        ["project_delivery", "technical"],
        ["finance", "planning"],
        ["operations", "quality"],
    ]
    people: list[Employee] = []
    for index in range(100):
        dept = DEPARTMENTS[index % len(DEPARTMENTS)][0]
        capacity = 40.0
        workload = round(rng.uniform(24, 39), 1)
        if dept == "dept-support" and index > 70:
            workload = round(rng.uniform(39, 48), 1)
        people.append(
            Employee(
                id=f"employee-{index + 1:03d}",
                organization_id=DEMO_TENANT_ID,
                department_id=dept,
                name=f"Fictional Colleague {index + 1:03d}",
                role_title=("Team lead" if index % 13 == 0 else "Specialist"),
                skills=skill_sets[index % len(skill_sets)],
                capacity_hours=capacity,
                workload_hours=workload,
            )
        )
    db.add_all(people)

    customers = [
        Customer(
            id=f"customer-{index + 1:04d}",
            organization_id=DEMO_TENANT_ID,
            name=f"Fictional Customer {index + 1:04d}",
            segment=["Enterprise", "Mid-market", "Small business"][index % 3],
            region=["Jordan", "Saudi Arabia", "UAE", "Iraq"][index % 4],
        )
        for index in range(240)
    ]
    db.add_all(customers)

    suppliers = [
        Supplier(
            id=f"supplier-{index + 1:02d}",
            organization_id=DEMO_TENANT_ID,
            name=f"Fictional Supplier {index + 1:02d}",
            category=["Cloud", "Logistics", "Equipment"][index % 3],
            on_time_rate=round(0.96 - index * 0.025, 3),
            risk_level=("high" if index == 4 else "medium" if index >= 3 else "low"),
        )
        for index in range(6)
    ]
    db.add_all(suppliers)
    db.flush()

    projects: list[Project] = []
    for index in range(20):
        delayed = index in {3, 8, 14, 18}
        projects.append(
            Project(
                id=f"project-{index + 1:03d}",
                organization_id=DEMO_TENANT_ID,
                department_id=DEPARTMENTS[index % len(DEPARTMENTS)][0],
                supplier_id=f"supplier-{index % 6 + 1:02d}" if index % 3 == 0 else None,
                name=f"Fictional Transformation Initiative {index + 1:02d}",
                status="delayed" if delayed else "active",
                progress=round(0.25 + (index % 8) * 0.09, 2),
                budget=float(35_000 + index * 2_500),
                actual_cost=float(22_000 + index * 2_200 + (8_000 if delayed else 0)),
                due_date=DEMO_REPORTING_DATE + timedelta(days=(index - 6) * 12),
                delay_days=(14 + index if delayed else 0),
            )
        )
    db.add_all(projects)
    db.flush()

    orders: list[SalesOrder] = []
    cases: list[SupportCase] = []
    expenses: list[Expense] = []
    events: list[ProcessEvent] = []
    order_number = 0
    case_number = 0
    event_number = 0
    for month_index in range(24):
        month = _month_start(month_index)
        recent = month_index >= 18
        order_volume = 34 + month_index // 4
        for within_month in range(order_volume):
            order_number += 1
            base = 650 + (within_month % 11) * 85 + month_index * 12
            discounted = recent and within_month % 3 == 0
            revenue = base * (0.83 if discounted else 1.0)
            cost_ratio = 0.72 if discounted else (0.61 + month_index * 0.002)
            if within_month == order_volume - 1 and month_index % 5 == 0:
                revenue = -round(base * 0.28, 2)
                cost = -round(base * 0.18, 2)
                status = "return"
            else:
                cost = round(revenue * cost_ratio, 2)
                status = "invoiced"
            order_date = month + timedelta(days=(within_month * 7) % 27)
            order_id = f"order-{order_number:06d}"
            orders.append(
                SalesOrder(
                    id=order_id,
                    organization_id=DEMO_TENANT_ID,
                    source_id=f"SO-{order_number:06d}",
                    customer_id=f"customer-{within_month % 240 + 1:04d}",
                    department_id="dept-sales",
                    order_date=order_date,
                    revenue=round(revenue, 2),
                    cost=cost,
                    status=status,
                    discounted=discounted,
                )
            )
            if order_number <= 90:
                for sequence, activity in enumerate(["created", "approved", "fulfilled"]):
                    event_number += 1
                    wait_hours = 4 + (order_number % 6) + (16 if order_number % 17 == 0 else 0)
                    events.append(
                        ProcessEvent(
                            id=f"event-{event_number:07d}",
                            organization_id=DEMO_TENANT_ID,
                            case_id=order_id,
                            activity=activity,
                            occurred_at=datetime.combine(order_date, datetime.min.time())
                            + timedelta(hours=sequence * wait_hours),
                            lifecycle="complete",
                            resource_ref=f"resource-{order_number % 12 + 1:02d}",
                        )
                    )
                if order_number % 19 == 0:
                    event_number += 1
                    events.append(
                        ProcessEvent(
                            id=f"event-{event_number:07d}",
                            organization_id=DEMO_TENANT_ID,
                            case_id=order_id,
                            activity="approved",
                            occurred_at=datetime.combine(order_date, datetime.min.time())
                            + timedelta(hours=30),
                            lifecycle="complete",
                            resource_ref=f"resource-{order_number % 12 + 1:02d}",
                        )
                    )

        case_volume = 24 + month_index // 5 + (22 if month_index >= 21 else 0)
        for within_month in range(case_volume):
            case_number += 1
            opened = datetime.combine(
                month + timedelta(days=(within_month * 5) % 27), datetime.min.time()
            ) + timedelta(hours=9)
            resolution_hours = 10 + (within_month % 9) * 3 + (12 if recent else 0)
            cases.append(
                SupportCase(
                    id=f"case-{case_number:06d}",
                    organization_id=DEMO_TENANT_ID,
                    customer_id=f"customer-{within_month % 240 + 1:04d}",
                    department_id="dept-support",
                    opened_at=opened,
                    resolved_at=opened + timedelta(hours=resolution_hours),
                    priority=["low", "medium", "high"][within_month % 3],
                    status="resolved",
                    reopened=within_month % 13 == 0,
                )
            )

        for dept_index, department in enumerate(DEPARTMENTS):
            budget = 18_000 + dept_index * 2_000
            overrun = 1.13 if department[0] == "dept-support" and recent else 0.96
            expenses.append(
                Expense(
                    id=f"expense-{month_index + 1:02d}-{dept_index + 1:02d}",
                    organization_id=DEMO_TENANT_ID,
                    department_id=department[0],
                    expense_date=month,
                    category="Operating expense",
                    actual=round(budget * overrun, 2),
                    budget=float(budget),
                )
            )
    db.add_all(orders)
    db.add_all(cases)
    db.add_all(expenses)
    db.add_all(events)

    db.add_all(
        [
            Objective(
                id=f"objective-{index + 1:02d}",
                organization_id=DEMO_TENANT_ID,
                department_id=dept[0],
                title=f"Improve {dept[1]} operating outcome",
                metric_id=["net_revenue", "avg_resolution_hours", "budget_variance"][index % 3],
                target=float(90 + index * 4),
                progress=float(62 + index * 4),
                owner=f"Fictional Owner {index + 1}",
                review_date=date(2026, 7, 15) + timedelta(days=index * 7),
            )
            for index, dept in enumerate(DEPARTMENTS)
        ]
    )
    db.commit()


def reset_and_seed(db: Session) -> None:
    for table in reversed(Base.metadata.sorted_tables):
        db.execute(delete(table))
    db.commit()
    seed_demo(db)


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed deterministic BASEERA demo data")
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()
    settings = load_settings()
    engine = build_engine(settings.database_url)
    Base.metadata.create_all(engine)
    with build_session_factory(engine)() as session:
        if args.reset:
            reset_and_seed(session)
        else:
            seed_demo(session)
    count = 0
    with build_session_factory(engine)() as session:
        count = len(session.scalars(select(SalesOrder)).all())
    print(f"Seeded deterministic demo through {DEMO_REPORTING_DATE.isoformat()} ({count} orders)")


if __name__ == "__main__":
    main()
