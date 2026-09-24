from __future__ import annotations

import heapq
import itertools
import math
import random
from collections import Counter, defaultdict
from datetime import date
from typing import Any

import numpy as np
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .errors import AppError
from .forecasting import forecast_series, monthly_series, monthly_step
from .models import Expense, ProcessEvent, Project, SalesOrder, SupportCase
from .profiling import coerce_number, detect_date_format, parse_date_value

METRIC_DEFINITIONS: dict[str, dict[str, Any]] = {
    "net_revenue": {"version": 1, "unit": "JOD", "label": "Net revenue"},
    "gross_margin": {"version": 1, "unit": "JOD", "label": "Gross margin"},
    "gross_margin_rate": {"version": 1, "unit": "%", "label": "Gross margin rate"},
    "support_case_count": {"version": 1, "unit": "cases", "label": "Support cases"},
    "avg_resolution_hours": {"version": 1, "unit": "hours", "label": "Resolution time"},
    "budget_variance": {"version": 1, "unit": "JOD", "label": "Budget variance"},
    "project_delay_rate": {"version": 1, "unit": "ratio", "label": "Project delay rate"},
}


def dataset_metric(metric_id: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    if metric_id not in METRIC_DEFINITIONS:
        return {
            "status": "unsupported",
            "value": None,
            "unit": None,
            "warnings": [f"Metric definition {metric_id!r} is not available."],
        }
    if metric_id == "net_revenue":
        values = [_number(row.get("revenue")) for row in rows]
        missing = sum(value is None for value in values)
        if not values or missing:
            return {
                "status": "insufficient_data",
                "value": None,
                "unit": "JOD",
                "warnings": [f"Revenue is missing for {missing or 'all'} in-scope rows."],
            }
        return {
            "status": "completed",
            "value": round(sum(value for value in values if value is not None), 10),
            "unit": "JOD",
            "warnings": [],
        }
    if metric_id in {"gross_margin", "gross_margin_rate"}:
        unit = METRIC_DEFINITIONS[metric_id]["unit"]
        revenue = [_number(row.get("revenue")) for row in rows]
        costs = [_number(row.get("cost")) for row in rows]
        missing_costs = sum(value is None for value in costs)
        if not rows or any(value is None for value in revenue) or missing_costs:
            return {
                "status": "insufficient_data",
                "value": None,
                "unit": unit,
                "warnings": [
                    f"Gross margin is unavailable because cost is missing for {missing_costs} rows."
                ],
            }
        total_revenue = sum(float(item) for item in revenue if item is not None)
        margin = total_revenue - sum(float(item) for item in costs if item is not None)
        if metric_id == "gross_margin_rate" and total_revenue == 0:
            return {
                "status": "insufficient_data",
                "value": None,
                "unit": unit,
                "warnings": ["Gross margin rate is undefined when total revenue is zero."],
            }
        return {
            "status": "completed",
            "value": round(
                margin / total_revenue * 100 if metric_id == "gross_margin_rate" else margin, 10
            ),
            "unit": unit,
            "warnings": [],
        }
    return {
        "status": "insufficient_data",
        "value": None,
        "unit": METRIC_DEFINITIONS[metric_id]["unit"],
        "warnings": ["This metric requires a mapped canonical company dataset."],
    }


def company_metrics(
    db: Session,
    tenant_id: str,
    department_ids: set[str] | None = None,
    start_date: date | None = None,
    end_date: date | None = None,
) -> dict[str, dict[str, Any]]:
    def scope(model: Any, *, resolved: bool = False) -> list[Any]:
        conditions = [model.organization_id == tenant_id]
        if department_ids is not None:
            conditions.append(model.department_id.in_(department_ids or {"__none__"}))
        date_column = {
            SalesOrder: SalesOrder.order_date,
            SupportCase: SupportCase.resolved_at if resolved else SupportCase.opened_at,
            Expense: Expense.expense_date,
            Project: Project.due_date,
        }[model]
        if start_date is not None:
            conditions.append(func.date(date_column) >= start_date.isoformat())
        if end_date is not None:
            conditions.append(func.date(date_column) < end_date.isoformat())
        return conditions

    revenue, cost = db.execute(
        select(func.sum(SalesOrder.revenue), func.sum(SalesOrder.cost)).where(*scope(SalesOrder))
    ).one()
    case_count = db.scalar(select(func.count(SupportCase.id)).where(*scope(SupportCase)))
    resolved = db.execute(
        select(SupportCase.opened_at, SupportCase.resolved_at).where(
            *scope(SupportCase, resolved=True), SupportCase.resolved_at.is_not(None)
        )
    ).all()
    durations = [(closed - opened).total_seconds() / 3600 for opened, closed in resolved]
    avg_resolution = sum(durations) / len(durations) if durations else None
    actual, budget = db.execute(
        select(func.sum(Expense.actual), func.sum(Expense.budget)).where(*scope(Expense))
    ).one()
    projects, delayed = db.execute(
        select(
            func.count(Project.id),
            func.sum(func.cast(Project.delay_days > 0, type_=Project.delay_days.type)),
        ).where(*scope(Project))
    ).one()

    def item(value: float | int | None, unit: str) -> dict[str, Any]:
        return {"value": round(float(value), 2) if value is not None else None, "unit": unit}

    return {
        "net_revenue": item(revenue, "JOD"),
        "gross_margin": item(
            float(revenue) - float(cost) if revenue is not None and cost is not None else None,
            "JOD",
        ),
        "gross_margin_rate": item(
            (float(revenue) - float(cost)) / float(revenue) * 100
            if revenue and cost is not None
            else None,
            "%",
        ),
        "support_case_count": item(case_count, "cases"),
        "avg_resolution_hours": item(avg_resolution, "hours"),
        "budget_variance": item(
            float(actual) - float(budget) if actual is not None and budget is not None else None,
            "JOD",
        ),
        "project_delay_rate": item(
            float(delayed) / float(projects) if delayed is not None and projects else None,
            "ratio",
        ),
    }


FORECASTABLE_METRICS: dict[str, dict[str, Any]] = {
    "support_case_count": {
        "unit": "cases",
        "label": {"en": "Support cases", "ar": "حالات الدعم"},
        "aggregation": "count",
        "non_negative": True,
    },
    "net_revenue": {
        "unit": "JOD",
        "label": {"en": "Net revenue", "ar": "صافي الإيرادات"},
        "aggregation": "sum",
        "non_negative": True,
    },
    "gross_margin": {
        "unit": "JOD",
        "label": {"en": "Gross margin", "ar": "هامش الربح الإجمالي"},
        "aggregation": "sum",
        "non_negative": False,
    },
    "order_count": {
        "unit": "orders",
        "label": {"en": "Order volume", "ar": "عدد الطلبات"},
        "aggregation": "count",
        "non_negative": True,
    },
    "avg_resolution_hours": {
        "unit": "hours",
        "label": {"en": "Resolution time", "ar": "زمن المعالجة"},
        "aggregation": "mean",
        "non_negative": True,
    },
    "operating_expense": {
        "unit": "JOD",
        "label": {"en": "Operating expense", "ar": "المصروف التشغيلي"},
        "aggregation": "sum",
        "non_negative": True,
    },
    "budget_variance": {
        "unit": "JOD",
        "label": {"en": "Budget variance", "ar": "انحراف الموازنة"},
        "aggregation": "sum",
        "non_negative": False,
    },
}


def _monthly_counts(
    db: Session, tenant_id: str, metric_id: str, department_ids: set[str] | None
) -> dict[str, float]:
    """Aggregate one metric into a month-keyed series."""

    def restrict(statement: Any, model: Any) -> Any:
        statement = statement.where(model.organization_id == tenant_id)
        if department_ids is not None:
            statement = statement.where(model.department_id.in_(department_ids or {"__none__"}))
        return statement

    buckets: dict[str, float] = {}
    if metric_id in {"support_case_count", "avg_resolution_hours"}:
        rows = db.execute(
            restrict(select(SupportCase.opened_at, SupportCase.resolved_at), SupportCase)
        ).all()
        if metric_id == "support_case_count":
            for opened, _resolved in rows:
                buckets[opened.strftime("%Y-%m")] = buckets.get(opened.strftime("%Y-%m"), 0.0) + 1
        else:
            durations: dict[str, list[float]] = defaultdict(list)
            for opened, resolved in rows:
                if resolved is not None:
                    durations[resolved.strftime("%Y-%m")].append(
                        (resolved - opened).total_seconds() / 3600
                    )
            buckets = {k: sum(v) / len(v) for k, v in durations.items() if v}
    elif metric_id in {"net_revenue", "gross_margin", "order_count"}:
        rows = db.execute(
            restrict(select(SalesOrder.order_date, SalesOrder.revenue, SalesOrder.cost), SalesOrder)
        ).all()
        for order_date, revenue, cost in rows:
            key = order_date.strftime("%Y-%m")
            if metric_id == "order_count":
                buckets[key] = buckets.get(key, 0.0) + 1
            elif metric_id == "net_revenue":
                buckets[key] = buckets.get(key, 0.0) + float(revenue or 0.0)
            elif cost is not None:
                buckets[key] = buckets.get(key, 0.0) + float(revenue or 0.0) - float(cost)
    elif metric_id in {"operating_expense", "budget_variance"}:
        rows = db.execute(
            restrict(select(Expense.expense_date, Expense.actual, Expense.budget), Expense)
        ).all()
        for expense_date, actual, budget in rows:
            key = expense_date.strftime("%Y-%m")
            value = float(actual or 0.0) - (
                float(budget or 0.0) if metric_id == "budget_variance" else 0.0
            )
            buckets[key] = buckets.get(key, 0.0) + value
    return buckets


def forecast_company_metric(
    db: Session,
    tenant_id: str,
    metric_id: str,
    horizon: int,
    department_ids: set[str] | None = None,
    interval: float = 0.90,
) -> dict[str, Any]:
    """Forecast a governed company metric on its monthly history."""
    definition = FORECASTABLE_METRICS.get(metric_id)
    if definition is None:
        raise AppError(
            422,
            "forecast_metric_unsupported",
            f"{metric_id!r} cannot be forecast. Forecasting needs a metric with a dated "
            "history in the company model.",
            details={"supported_metrics": sorted(FORECASTABLE_METRICS)},
        )
    periods, values = monthly_series(_monthly_counts(db, tenant_id, metric_id, department_ids))
    result = forecast_series(
        periods,
        values,
        horizon,
        seasonal_period=12,
        interval=interval,
        label=metric_id,
        unit=definition["unit"],
        non_negative=bool(definition["non_negative"]),
        period_step=monthly_step,
    )
    result["metric_id"] = metric_id
    result["metric_label"] = definition["label"]
    if definition["aggregation"] == "count":
        result["gap_policy"] = "months_with_no_recorded_rows_are_treated_as_zero"
    else:
        result["gap_policy"] = (
            "months_with_no_recorded_rows_are_treated_as_zero_which_can_understate_"
            "a_metric_that_is_merely_unreported"
        )
    return result


def forecast_support_cases(
    db: Session, tenant_id: str, horizon: int, department_ids: set[str] | None = None
) -> dict[str, Any]:
    """Retained entry point; support cases are one of several forecastable metrics."""
    return forecast_company_metric(db, tenant_id, "support_case_count", horizon, department_ids)


def forecast_dataset_column(
    rows: list[dict[str, Any]],
    date_column: str,
    value_column: str | None,
    horizon: int,
    aggregation: str = "sum",
    interval: float = 0.90,
) -> dict[str, Any]:
    """Forecast a column of an uploaded dataset, aggregated by month."""
    if aggregation not in {"sum", "mean", "count"}:
        raise AppError(
            422,
            "invalid_aggregation",
            "Aggregation must be sum, mean or count.",
            details={"supported": ["sum", "mean", "count"]},
        )
    if aggregation != "count" and not value_column:
        raise AppError(
            422,
            "value_column_required",
            f"A {aggregation} needs a value column to aggregate.",
        )
    pattern, _name, ambiguous = detect_date_format([row.get(date_column) for row in rows])
    if pattern is None:
        raise AppError(
            422,
            "date_column_not_parsable",
            f"{date_column!r} does not hold recognisable dates, so it cannot order a series.",
            details={"column": date_column},
        )
    if ambiguous:
        raise AppError(
            409,
            "ambiguous_date_order",
            f"{date_column!r} is written in a format where day and month cannot be told "
            "apart. Parse it into ISO dates first so the ordering is unambiguous.",
            details={"column": date_column},
        )
    grouped: dict[str, list[float]] = defaultdict(list)
    unparsable = 0
    for row in rows:
        parsed = parse_date_value(row.get(date_column), pattern)
        if parsed is None:
            unparsable += 1
            continue
        key = parsed[:7]
        if aggregation == "count":
            grouped[key].append(1.0)
            continue
        # value_column is required above for every aggregation except count.
        number, _note = coerce_number(row.get(value_column or ""))
        if number is None:
            continue
        grouped[key].append(number)
    buckets = {
        key: (sum(items) if aggregation != "mean" else sum(items) / len(items))
        for key, items in grouped.items()
        if items
    }
    periods, values = monthly_series(buckets)
    result = forecast_series(
        periods,
        values,
        horizon,
        seasonal_period=12,
        interval=interval,
        label=value_column or date_column,
        non_negative=aggregation == "count",
        period_step=monthly_step,
    )
    result["source"] = {
        "date_column": date_column,
        "value_column": value_column,
        "aggregation": aggregation,
        "rows_considered": len(rows),
        "rows_with_unreadable_dates": unparsable,
        "detected_date_format": pattern,
    }
    if unparsable:
        result.setdefault("warnings", []).append(
            f"{unparsable} rows had an unreadable value in {date_column!r} and were excluded "
            "from the series."
        )
        result.setdefault("warnings_ar", []).append(
            f"استُبعد {unparsable} صفًا من السلسلة بسبب تعذّر قراءة التاريخ في {date_column!r}."
        )
    return result


def analyze_process(db: Session, tenant_id: str) -> dict[str, Any]:
    events = db.scalars(
        select(ProcessEvent)
        .where(ProcessEvent.organization_id == tenant_id)
        .order_by(ProcessEvent.case_id, ProcessEvent.occurred_at, ProcessEvent.id)
    ).all()
    grouped: dict[str, list[ProcessEvent]] = defaultdict(list)
    for event in events:
        grouped[event.case_id].append(event)
    path_counts = Counter(
        " → ".join(event.activity for event in group) for group in grouped.values()
    )
    durations = [
        (group[-1].occurred_at - group[0].occurred_at).total_seconds() / 3600
        for group in grouped.values()
        if len(group) > 1
    ]
    return {
        "case_count": len(grouped),
        "event_count": len(events),
        "paths": [{"path": path, "case_count": count} for path, count in path_counts.most_common()],
        "median_cycle_hours": round(float(np.median(durations)), 2) if durations else None,
        "limitations": [
            "The map reflects recorded event order only.",
            "Resource references are pseudonymous and are not performance ratings.",
        ],
    }


def optimize_assignments(
    workers: list[dict[str, Any]], tasks: list[dict[str, Any]]
) -> dict[str, Any]:
    cp_model: Any | None
    try:
        from ortools.sat.python import cp_model as imported_cp_model
    except ImportError:
        cp_model = None
    else:
        cp_model = imported_cp_model
    if cp_model is not None:
        model = cp_model.CpModel()
        capacities = [math.floor(float(worker["capacity_hours"]) * 1000) for worker in workers]
        hours = [math.ceil(float(task["hours"]) * 1000) for task in tasks]
        assignments = {}
        for task_index, task in enumerate(tasks):
            choices = []
            for worker_index, worker in enumerate(workers):
                if (
                    task["required_skill"] in worker["skills"]
                    and capacities[worker_index] >= hours[task_index]
                ):
                    variable = model.new_bool_var(f"assign_{task_index}_{worker_index}")
                    assignments[task_index, worker_index] = variable
                    choices.append(variable)
            model.add(sum(choices) == 1)
        utilizations = []
        for worker_index, capacity in enumerate(capacities):
            load = model.new_int_var(0, capacity, f"load_{worker_index}")
            model.add(
                load
                == sum(
                    hours[task_index] * variable
                    for (task_index, wi), variable in assignments.items()
                    if wi == worker_index
                )
            )
            if capacity:
                utilization = model.new_int_var(0, 10000, f"utilization_{worker_index}")
                model.add_division_equality(utilization, load * 10000, capacity)
                utilizations.append(utilization)
        maximum = model.new_int_var(0, 10000, "maximum_utilization")
        minimum = model.new_int_var(0, 10000, "minimum_utilization")
        if utilizations:
            model.add_max_equality(maximum, utilizations)
            model.add_min_equality(minimum, utilizations)
            model.minimize(maximum - minimum)
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = 5.0
        solver.parameters.num_search_workers = 1
        solver.parameters.random_seed = 2026
        status = solver.solve(model)
        feasible = status in {cp_model.OPTIMAL, cp_model.FEASIBLE}
        return {
            "feasibility": "feasible"
            if feasible
            else "infeasible"
            if status == cp_model.INFEASIBLE
            else "unknown",
            "assignments": [
                {
                    "task_id": tasks[ti]["id"],
                    "worker_id": workers[wi]["id"],
                    "hours": float(tasks[ti]["hours"]),
                }
                for (ti, wi), variable in assignments.items()
                if feasible and solver.value(variable)
            ],
            "violations": []
            if feasible
            else [
                {
                    "reason": "skill_or_capacity_constraints"
                    if status == cp_model.INFEASIBLE
                    else "solver_time_limit"
                }
            ],
            "solver": {
                "name": "ortools_cp_sat",
                "status": solver.status_name(status).lower(),
                "optimality_proven": status == cp_model.OPTIMAL,
                "claim": (
                    "optimal_for_bounded_search"
                    if status == cp_model.OPTIMAL
                    else "feasible_solution_not_proven"
                    if feasible
                    else "no_feasible_solution_returned"
                ),
                "objective": "minimize_utilization_range",
                "time_limit_seconds": 5,
                "precision_hours": 0.001,
                "rounding": "conservative_capacity_floor_task_ceiling",
            },
        }
    worker_ids = [str(worker["id"]) for worker in workers]
    eligible = [
        [
            str(worker["id"])
            for worker in workers
            if task["required_skill"] in worker.get("skills", [])
            and float(worker.get("capacity_hours", 0)) >= float(task["hours"])
        ]
        for task in tasks
    ]
    violations = [
        {"task_id": tasks[index]["id"], "reason": "no_worker_with_skill_and_capacity"}
        for index, choices in enumerate(eligible)
        if not choices
    ]
    if violations:
        return {
            "feasibility": "infeasible",
            "assignments": [],
            "violations": violations,
            "solver": {"name": "bounded_enumeration", "claim": "infeasibility_witness"},
        }
    if len(tasks) > 12 or math.prod(max(1, len(items)) for items in eligible) > 250_000:
        return {
            "feasibility": "unsupported",
            "assignments": [],
            "violations": [{"reason": "bounded_search_limit_exceeded"}],
            "solver": {"name": "bounded_enumeration", "claim": "no_optimality_claim"},
        }
    capacity_by_worker = {str(worker["id"]): float(worker["capacity_hours"]) for worker in workers}
    best: tuple[float, tuple[str, ...]] | None = None
    for candidate in itertools.product(*eligible):
        used = dict.fromkeys(worker_ids, 0.0)
        for assignment, task in zip(candidate, tasks, strict=True):
            used[assignment] += float(task["hours"])
        if any(used[key] > capacity_by_worker[key] for key in used):
            continue
        imbalance = max((used[key] / capacity_by_worker[key] for key in used), default=0) - min(
            (used[key] / capacity_by_worker[key] for key in used), default=0
        )
        score = (imbalance, candidate)
        if best is None or score < best:
            best = score
    if best is None:
        return {
            "feasibility": "infeasible",
            "assignments": [],
            "violations": [{"reason": "combined_capacity_exceeded"}],
            "solver": {"name": "bounded_enumeration", "claim": "infeasibility_witness"},
        }
    return {
        "feasibility": "feasible",
        "assignments": [
            {"task_id": task["id"], "worker_id": worker_id, "hours": float(task["hours"])}
            for task, worker_id in zip(tasks, best[1], strict=True)
        ],
        "violations": [],
        "solver": {"name": "bounded_enumeration", "claim": "optimal_for_bounded_search"},
    }


def simulate_queue(payload: dict[str, Any]) -> dict[str, Any]:
    seed = int(payload["seed"])
    replications = int(payload["replications"])
    hours = float(payload["hours"])
    arrival_rate = float(payload["arrival_rate_per_hour"])
    service_rate = float(payload["service_rate_per_hour"])

    def scenario(agents: int, offset: int) -> dict[str, Any]:
        waits: list[float] = []
        completions: list[int] = []
        for replication in range(replications):
            rng = random.Random(seed + offset + replication * 10_007)
            free_at = [0.0] * agents
            heapq.heapify(free_at)
            clock = 0.0
            completed = 0
            while arrival_rate > 0:
                clock += rng.expovariate(arrival_rate)
                if clock > hours:
                    break
                available = heapq.heappop(free_at)
                start = max(clock, available)
                service = rng.expovariate(service_rate)
                finish = start + service
                heapq.heappush(free_at, finish)
                waits.append(start - clock)
                if finish <= hours:
                    completed += 1
            completions.append(completed)
        return {
            "agents": agents,
            "mean_wait_hours": round(float(np.mean(waits)), 4) if waits else 0.0,
            "p95_wait_hours": round(float(np.percentile(waits, 95)), 4) if waits else 0.0,
            "mean_completed": round(float(np.mean(completions)), 2),
        }

    baseline = scenario(int(payload["baseline_agents"]), 0)
    proposed = scenario(int(payload["proposed_agents"]), 1_000_003)
    return {
        "classification": "calculated_scenario",
        "baseline": baseline,
        "proposed": proposed,
        "assumptions": {
            "arrival_distribution": "exponential",
            "service_distribution": "exponential",
            "replications": replications,
            "seed": seed,
        },
        "model_boundary": (
            "A bounded single-queue capacity model; it excludes priorities, abandonment, breaks, "
            "skill routing, and downstream work."
        ),
    }


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None
