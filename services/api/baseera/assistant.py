"""Persisted conversations and a typed plan/execute/render graph for local analytics."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import Annotated, Any, TypedDict

from fastapi import Depends, FastAPI, Request
from langgraph.graph import END, START, StateGraph
from sqlalchemy import select
from sqlalchemy.orm import Session

from .analytics import (
    METRIC_DEFINITIONS,
    analyze_process,
    company_metrics,
    dataset_metric,
    forecast_support_cases,
)
from .auth import AuthContext, get_auth_context, get_db
from .config import Settings
from .errors import AppError, not_found
from .ingestion import ArtifactStore, stable_hash
from .models import Conversation, DatasetVersion, Membership, Message, MetricResult
from .ollama import AnalysisPlan, OllamaPlanner

LABELS_AR = {
    "net_revenue": "صافي الإيرادات",
    "gross_margin": "الربح الإجمالي",
    "gross_margin_rate": "هامش الربح الإجمالي",
    "support_case_count": "عدد حالات الدعم",
    "avg_resolution_hours": "متوسط وقت الحل",
    "budget_variance": "المصروف الفعلي ناقص الموازنة",
    "project_delay_rate": "نسبة تأخر المشاريع",
}


class AssistantState(TypedDict, total=False):
    request: dict[str, Any]
    context: AuthContext
    db: Session
    settings: Settings
    store: ArtifactStore
    history: list[dict[str, str]]
    plan: AnalysisPlan
    provider: dict[str, Any]
    results: list[dict[str, Any]]
    response: dict[str, Any]


def _plan(state: AssistantState) -> dict[str, Any]:
    payload, context = state["request"], state["context"]
    if payload.get("metric_id"):
        if payload["metric_id"] not in METRIC_DEFINITIONS:
            raise AppError(422, "unknown_metric", "The requested metric is not approved.")
        return {
            "plan": AnalysisPlan(action="metric_query", metric_ids=[payload["metric_id"]]),
            "provider": {"mode": "deterministic_tool", "name": "governed_metric_query"},
        }
    planner = OllamaPlanner(state["settings"])
    try:
        plan, provider = planner.plan(
            payload["question"],
            locale=payload.get("locale", "en"),
            as_of=context.organization.reporting_date,
            history=state.get("history"),
        )
    except AppError as exc:
        # Invalid output must never silently discard a requested filter, date or comparison.
        # Let the user clarify or use the explicit governed-metric selector.
        if exc.code != "provider_output_invalid":
            raise
        plan = AnalysisPlan(
            action="clarify",
            clarification=(
                "لم ينتج النموذج خطة صالحة. أعد صياغة المؤشر والفترة، أو استخدم مساحة التحليل."
                if payload.get("locale") == "ar"
                else "The model did not produce a valid plan. Specify the metric and period, "
                "or use the analysis workspace."
            ),
        )
        provider = {
            "mode": "ollama",
            "model": state["settings"].llm_model,
            "status": "invalid_plan",
            "reason": "invalid_structured_plan",
            "live_verified": False,
            "execution": "local",
        }
    return {"plan": plan, "provider": provider}


def _period(plan: AnalysisPlan, as_of: date | None) -> tuple[date | None, date | None]:
    if plan.period == "all_history":
        return None, None
    if plan.period == "custom":
        return plan.start_date, plan.end_date
    if as_of is None:
        raise AppError(
            422, "reporting_cutoff_required", "Set a reporting cutoff for relative dates."
        )
    if plan.period == "this_year":
        return date(as_of.year, 1, 1), as_of + timedelta(days=1)
    if plan.period == "this_month":
        return as_of.replace(day=1), as_of + timedelta(days=1)
    previous = as_of.replace(day=1) - timedelta(days=1)
    return previous.replace(day=1), as_of.replace(day=1)


def _execute(state: AssistantState) -> dict[str, Any]:
    db, context, plan = state["db"], state["context"], state["plan"]
    # Inference can take time: re-read permissions before touching business facts.
    db.expire_all()
    membership = db.get(Membership, context.membership.id)
    if membership is None or not membership.active or not context.user.active:
        raise AppError(403, "permission_revoked", "Access was revoked while analysis was running.")
    if not context.can("analytics:read"):
        raise AppError(403, "permission_denied", "Analytics access is required.")
    if plan.action in {"clarify", "deny"}:
        return {"results": []}
    departments = context.scoped_departments
    start, end = _period(plan, context.organization.reporting_date)
    requested_version = state["request"].get("dataset_version_id")
    if (
        plan.action in {"metric_query", "overview"}
        and plan.period == "all_history"
        and not requested_version
        and context.organization.reporting_date is not None
    ):
        # Match the executive overview and scheduled refresh; future-dated records must not
        # silently enter an answer labeled with this workspace's reporting cutoff.
        end = context.organization.reporting_date + timedelta(days=1)
    if requested_version and plan.action not in {"metric_query", "overview"}:
        raise AppError(
            422, "dataset_tool_unsupported", "This tool requires canonical company data."
        )
    metrics: dict[str, Any] = {}
    if plan.action in {"metric_query", "overview"}:
        if requested_version:
            version = db.scalar(
                select(DatasetVersion).where(
                    DatasetVersion.id == requested_version,
                    DatasetVersion.organization_id == context.tenant_id,
                )
            )
            if version is None:
                raise not_found("Dataset version")
            # Uploaded files do not have an approved department/date mapping.
            if departments is not None and version.created_by != context.user.id:
                raise not_found("Dataset version")
            if start is not None or end is not None:
                raise AppError(
                    422,
                    "dataset_period_mapping_required",
                    "Map a date column before filtering this dataset.",
                )
            rows = state["store"].read_rows(version.data_object_key)
            metrics = {name: dataset_metric(name, rows) for name in plan.metric_ids}
        else:
            metrics = company_metrics(
                db,
                context.tenant_id,
                department_ids=departments,
                start_date=start,
                end_date=end,
            )
        names = plan.metric_ids if plan.action == "metric_query" else list(metrics)
        calculations = [(name, metrics[name]) for name in dict.fromkeys(names)]
    elif plan.action == "forecast":
        if start is not None or end is not None:
            raise AppError(
                422, "forecast_scope_unsupported", "Forecasts use complete available history."
            )
        calculation = forecast_support_cases(
            db, context.tenant_id, plan.horizon, department_ids=departments
        )
        calculations = [("forecast_support", calculation)]
    else:
        if departments is not None:
            raise AppError(
                403, "permission_denied", "Process analysis requires approved company scope."
            )
        if start is not None or end is not None:
            raise AppError(
                422, "process_scope_unsupported", "Process analysis currently uses full history."
            )
        calculations = [("process_cases", analyze_process(db, context.tenant_id))]
    results = []
    for name, calculation in calculations:
        scope = {
            "tenant_id": context.tenant_id,
            "department_ids": sorted(departments) if departments is not None else None,
            "start_date": start.isoformat() if start else None,
            "end_date_exclusive": end.isoformat() if end else None,
            "timezone": context.organization.timezone,
            "as_of": str(context.organization.reporting_date),
            "dataset_version_id": requested_version,
        }
        fingerprint = stable_hash(
            {
                "scope": scope,
                "metric_id": name,
                "calculation": calculation,
                "membership_id": membership.id,
                "permissions": sorted(membership.permissions),
                "metric_version": METRIC_DEFINITIONS.get(name, {}).get("version", 1),
            }
        )
        result_id = f"result-{fingerprint[:32]}"
        result = {
            "result_id": result_id,
            "metric_id": name,
            "status": calculation.get(
                "status",
                "completed"
                if calculation.get("value") is not None
                or name in {"forecast_support", "process_cases"}
                else "insufficient_data",
            ),
            **calculation,
            "evidence": {
                "scope": scope,
                "input_hash": fingerprint,
                "metric_definition_version": METRIC_DEFINITIONS.get(name, {}).get("version", 1),
                "source": "uploaded_dataset" if requested_version else "canonical_company",
            },
        }
        existing = db.scalar(
            select(MetricResult).where(
                MetricResult.organization_id == context.tenant_id,
                MetricResult.input_hash == fingerprint,
            )
        )
        if existing is None:
            db.add(
                MetricResult(
                    id=result_id,
                    organization_id=context.tenant_id,
                    metric_id=name,
                    dataset_version_id=requested_version,
                    input_hash=fingerprint,
                    payload=result,
                )
            )
        results.append(result)
    db.flush()
    return {"results": results}


def _render(state: AssistantState) -> dict[str, Any]:
    ar = state["request"].get("locale", "en") == "ar"
    plan, results = state["plan"], state["results"]
    findings = []
    for result in results:
        name = result["metric_id"]
        label = (
            LABELS_AR.get(name, name) if ar else METRIC_DEFINITIONS.get(name, {}).get("label", name)
        )
        classification = "observed_fact"
        if name == "forecast_support":
            classification = "forecast"
            values = ", ".join(str(row["value"]) for row in result.get("forecast", []))
            claim = (
                "توقع حالات الدعم للفترات المقبلة: "
                if ar
                else "Forecast support cases by future period: "
            ) + (values or ("بيانات غير كافية" if ar else "Insufficient data"))
        elif name == "process_cases":
            classification = "calculated_fact"
            claim = (
                f"عدد حالات العملية: {result.get('case_count')}؛ "
                f"وسيط الزمن بالساعات: {result.get('median_cycle_hours')}"
                if ar
                else (
                    f"Process cases: {result.get('case_count')}; "
                    f"median cycle hours: {result.get('median_cycle_hours')}"
                )
            )
        elif result.get("value") is None:
            classification = "insufficient_data"
            claim = f"{label}: " + (
                "غير متاح بسبب نقص البيانات المطلوبة."
                if ar
                else "Unavailable because required data is missing."
            )
        else:
            claim = (
                f"{label}: {result['value']:,.4f}".rstrip("0").rstrip(".")
                + f" {result.get('unit', '')}"
            )
        findings.append(
            {
                "claim": claim,
                "classification": classification,
                "evidence_ids": [result["result_id"]],
                "assumptions": [],
                "limitations": result.get("warnings", []) + result.get("limitations", []),
            }
        )
    if plan.action == "deny":
        answer = (
            "هذا الطلب خارج نطاق التحليل المسموح. يمكنني تحليل المؤشرات المجمّعة ضمن صلاحياتك."
            if ar
            else (
                "This request is outside the permitted analysis scope. "
                "I can analyze authorized aggregate metrics."
            )
        )
        status = "denied"
    elif plan.action == "clarify":
        answer = plan.clarification or (
            "حدد المؤشر والفترة المطلوبة، أو اختر مؤشرًا معتمدًا من القائمة."
            if ar
            else "Please specify the metric and period, or choose an approved metric."
        )
        status = "clarification_required"
    else:
        answer = "\n".join(item["claim"] for item in findings)
        status = (
            "completed"
            if any(row.get("status") == "completed" for row in results)
            else "insufficient_data"
        )
        scope_text = "كل التاريخ المتاح" if ar else "all available history"
        start, end = _period(plan, state["context"].organization.reporting_date)
        if results:
            scope = results[0].get("evidence", {}).get("scope", {})
            start = scope.get("start_date") or start
            end = scope.get("end_date_exclusive") or end
        if start or end:
            scope_text = f"{start or ('البداية' if ar else 'beginning')} → {end or '…'} " + (
                "(النهاية غير مشمولة)" if ar else "(end exclusive)"
            )
        answer += "\n" + ("النطاق: " if ar else "Scope: ") + scope_text
    return {
        "response": {
            "status": status,
            "answer": answer,
            "question": state["request"]["question"],
            "provider": state["provider"],
            "findings": findings,
            "results": results,
            "result_id": results[0]["result_id"] if results else None,
            "plan": plan.model_dump(mode="json"),
            "execution": {
                "engine": "langgraph",
                "steps": ["plan", "authorize_and_execute", "render_evidence"],
            },
        }
    }


_graph = StateGraph(AssistantState)
_graph.add_node("plan", _plan)
_graph.add_node("authorize_and_execute", _execute)
_graph.add_node("render_evidence", _render)
_graph.add_edge(START, "plan")
_graph.add_edge("plan", "authorize_and_execute")
_graph.add_edge("authorize_and_execute", "render_evidence")
_graph.add_edge("render_evidence", END)
_workflow = _graph.compile()


def run_assistant(
    payload: dict[str, Any],
    context: AuthContext,
    db: Session,
    settings: Settings,
    store: ArtifactStore,
) -> dict[str, Any]:
    if not context.can("analytics:read"):
        raise AppError(403, "permission_denied", "Analytics access is required.")
    conversation_id = payload.get("conversation_id")
    history: list[dict[str, str]] = []
    if conversation_id:
        conversation = _conversation(db, context, conversation_id)
        previous = db.scalars(
            select(Message)
            .where(
                Message.conversation_id == conversation_id,
                Message.organization_id == context.tenant_id,
                Message.role == "user",
            )
            .order_by(Message.created_at.desc(), Message.id.desc())
            .limit(2)
        ).all()
        # History contains user intent, not stale protected results from earlier policy scopes.
        history = [{"role": "user", "content": item.content[:2000]} for item in reversed(previous)]
    else:
        conversation = Conversation(
            id=f"conversation-{uuid.uuid4().hex}",
            organization_id=context.tenant_id,
            user_id=context.user.id,
            title=payload["question"][:240],
        )
    state = _workflow.invoke(
        {
            "request": payload,
            "context": context,
            "db": db,
            "settings": settings,
            "store": store,
            "history": history,
        },
        config={"recursion_limit": 6},
    )
    response = state["response"]
    db.add(conversation)
    db.flush()
    response["conversation_id"] = conversation.id
    for role, content, structured in [
        ("user", payload["question"], None),
        ("assistant", response["answer"], response),
    ]:
        db.add(
            Message(
                id=f"message-{uuid.uuid4().hex}",
                organization_id=context.tenant_id,
                conversation_id=conversation.id,
                role=role,
                content=content,
                structured_payload=structured,
            )
        )
    db.commit()
    return response


def _conversation(db: Session, context: AuthContext, conversation_id: str) -> Conversation:
    conversation = db.scalar(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.organization_id == context.tenant_id,
            Conversation.user_id == context.user.id,
        )
    )
    if conversation is None:
        raise not_found("Conversation")
    return conversation


def register_assistant_routes(application: FastAPI) -> None:
    @application.get("/api/v1/assistant/status")
    def status(
        request: Request, _: Annotated[AuthContext, Depends(get_auth_context)]
    ) -> dict[str, Any]:
        return OllamaPlanner(request.app.state.settings).status()

    @application.get("/api/v1/conversations")
    def conversations(
        context: Annotated[AuthContext, Depends(get_auth_context)],
        db: Annotated[Session, Depends(get_db)],
    ) -> dict[str, Any]:
        rows = db.scalars(
            select(Conversation)
            .where(
                Conversation.organization_id == context.tenant_id,
                Conversation.user_id == context.user.id,
            )
            .order_by(Conversation.created_at.desc())
            .limit(100)
        ).all()
        return {
            "items": [
                {"id": row.id, "title": row.title, "created_at": row.created_at.isoformat()}
                for row in rows
            ]
        }

    @application.get("/api/v1/conversations/{conversation_id}")
    def messages(
        conversation_id: str,
        context: Annotated[AuthContext, Depends(get_auth_context)],
        db: Annotated[Session, Depends(get_db)],
    ) -> dict[str, Any]:
        _conversation(db, context, conversation_id)
        rows = db.scalars(
            select(Message)
            .where(
                Message.organization_id == context.tenant_id,
                Message.conversation_id == conversation_id,
            )
            .order_by(Message.created_at, Message.id)
            .limit(200)
        ).all()
        # Current policy may differ, so historical business values need reauthorization.
        return {
            "id": conversation_id,
            "items": [
                {
                    "id": row.id,
                    "role": row.role,
                    "content": row.content
                    if row.role == "user"
                    else "Saved analysis. Rerun to verify current access and data.",
                    "rerun_required": row.role == "assistant",
                }
                for row in rows
            ],
        }
