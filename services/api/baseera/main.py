from __future__ import annotations

# FastAPI dependency declarations intentionally call Depends/Header/File in signatures.
# ruff: noqa: B008
import hashlib
import io
import math
import os
import re
import threading
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Literal, cast

from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    Header,
    Query,
    Request,
    Response,
    UploadFile,
)
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .analytics import (
    FORECASTABLE_METRICS,
    METRIC_DEFINITIONS,
    analyze_process,
    company_metrics,
    dataset_metric,
    forecast_company_metric,
    forecast_dataset_column,
    optimize_assignments,
    simulate_queue,
)
from .auth import (
    CSRF_HEADER,
    SESSION_COOKIE,
    AuthContext,
    authenticate,
    create_session,
    get_auth_context,
    get_db,
    require_csrf,
    rotate_csrf,
)
from .cleaning import STEP_KINDS, run_recipe
from .config import Settings, load_settings
from .connectors import (
    credential_state,
    delete_credentials,
    run_source_fetch,
    store_credentials,
    sync_records,
    validate_connector_destination,
)
from .credentials import SecretBox
from .database import Base, build_engine, build_session_factory
from .deliverables import brief_export, build_brief
from .errors import AppError, not_found
from .ingestion import (
    ArtifactStore,
    parse_upload,
    profile_rows,
    stable_hash,
)
from .insights import analyze_dataset
from .jobs import cancel_job, create_job, job_payload, recover_interrupted_jobs
from .models import (
    AuthSession,
    CleaningRun,
    Connector,
    ConnectorRecord,
    Customer,
    Dashboard,
    DashboardVersion,
    Dataset,
    DatasetProfile,
    DatasetVersion,
    Decision,
    Employee,
    Expense,
    IdempotencyRecord,
    Job,
    MetricResult,
    Objective,
    Organization,
    Project,
    RejectedRecord,
    Report,
    ReportExport,
    ReportVersion,
    SalesOrder,
    Schedule,
    Supplier,
    SupportCase,
    utcnow,
)
from .reports import EXPORT_MEDIA_TYPES, export_filename, render_report_export
from .seed import seed_demo as populate_demo
from .source_adapters import SourceLimits, SourcePolicy

API_PREFIX = "/api/v1"


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LoginRequest(StrictModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=1024)


# The cleaning vocabulary, described once so the workspace and the API cannot drift apart.
CLEANING_STEP_CATALOG: list[dict[str, Any]] = [
    {
        "kind": "trim_whitespace",
        "scope": "cells",
        "reversible": True,
        "label": {"en": "Trim whitespace", "ar": "إزالة المسافات الطرفية"},
        "detail": {
            "en": "Removes leading, trailing and invisible characters.",
            "ar": "يزيل المسافات الطرفية والمحارف غير المرئية.",
        },
        "options": [],
    },
    {
        "kind": "collapse_whitespace",
        "scope": "cells",
        "reversible": True,
        "label": {"en": "Collapse repeated spaces", "ar": "دمج المسافات المتكررة"},
        "detail": {
            "en": "Replaces runs of internal whitespace with a single space.",
            "ar": "يستبدل المسافات الداخلية المتكررة بمسافة واحدة.",
        },
        "options": [],
    },
    {
        "kind": "normalize_digits",
        "scope": "cells",
        "reversible": True,
        "label": {"en": "Normalize Arabic-Indic digits", "ar": "توحيد الأرقام العربية-الهندية"},
        "detail": {
            "en": "Converts ٠-٩ to 0-9 so numbers parse consistently.",
            "ar": "يحوّل ٠-٩ إلى 0-9 لتُقرأ الأرقام بشكل موحّد.",
        },
        "options": [],
    },
    {
        "kind": "standardize_case",
        "scope": "cells",
        "reversible": False,
        "label": {"en": "Standardize letter case", "ar": "توحيد حالة الأحرف"},
        "detail": {
            "en": "Merges values that differ only by capitalization.",
            "ar": "يدمج القيم التي تختلف في حالة الأحرف فقط.",
        },
        "options": [
            {
                "name": "case",
                "type": "choice",
                "choices": ["lower", "upper", "title"],
                "default": "title",
                "required": True,
            }
        ],
    },
    {
        "kind": "cast_number",
        "scope": "cells",
        "reversible": False,
        "label": {"en": "Convert text to number", "ar": "تحويل النص إلى رقم"},
        "detail": {
            "en": "Reads thousands separators, currency symbols, percentages, "
            "parenthesised negatives and Arabic-Indic digits. Cells that cannot "
            "be read are reported, never guessed.",
            "ar": "يقرأ فواصل الآلاف ورموز العملة والنسب والسالب بين قوسين والأرقام "
            "العربية-الهندية. تُبلَّغ الخلايا غير المقروءة ولا تُخمَّن.",
        },
        "options": [],
    },
    {
        "kind": "round_number",
        "scope": "cells",
        "reversible": False,
        "label": {"en": "Round numbers", "ar": "تقريب الأرقام"},
        "detail": {
            "en": "Rounds numeric cells to a fixed number of decimals.",
            "ar": "يقرّب الخلايا الرقمية إلى عدد ثابت من المنازل العشرية.",
        },
        "options": [{"name": "digits", "type": "integer", "min": 0, "max": 10, "default": 2}],
    },
    {
        "kind": "cast_boolean",
        "scope": "cells",
        "reversible": False,
        "label": {"en": "Convert to true/false", "ar": "تحويل إلى صح/خطأ"},
        "detail": {
            "en": "Recognises yes/no, 1/0, نعم/لا and true/false.",
            "ar": "يتعرّف على yes/no و1/0 ونعم/لا وtrue/false.",
        },
        "options": [],
    },
    {
        "kind": "parse_date",
        "scope": "cells",
        "reversible": False,
        "label": {"en": "Parse dates to ISO 8601", "ar": "تحويل التواريخ إلى ISO 8601"},
        "detail": {
            "en": "Detects the format, and refuses to guess when day/month order is ambiguous.",
            "ar": "يكتشف النمط، ويرفض التخمين عندما يكون ترتيب اليوم/الشهر ملتبسًا.",
        },
        "options": [
            {"name": "format", "type": "text", "required": False},
            {"name": "day_first_confirmed", "type": "boolean", "default": False},
        ],
    },
    {
        "kind": "replace_missing",
        "scope": "cells",
        "reversible": False,
        "label": {"en": "Fill blanks with a fixed value", "ar": "تعبئة الفراغات بقيمة ثابتة"},
        "detail": {
            "en": "The value is coerced to the column's own type; an empty value is "
            "rejected because it changes nothing.",
            "ar": "تُحوَّل القيمة إلى نوع العمود؛ وتُرفض القيمة الفارغة لأنها لا تغيّر شيئًا.",
        },
        "options": [{"name": "value", "type": "text", "required": True}],
    },
    {
        "kind": "fill_missing_statistic",
        "scope": "cells",
        "reversible": False,
        "label": {"en": "Impute blanks from the column", "ar": "تعويض الفراغات من العمود"},
        "detail": {
            "en": "Fills blanks with the mean, median or mode. Imputed cells are "
            "estimates and are labelled as such.",
            "ar": "يملأ الفراغات بالمتوسط أو الوسيط أو المنوال. الخلايا المعوّضة تقديرات "
            "وتُوسم بذلك.",
        },
        "options": [
            {
                "name": "statistic",
                "type": "choice",
                "choices": ["mean", "median", "mode"],
                "default": "median",
                "required": True,
            }
        ],
    },
    {
        "kind": "map_values",
        "scope": "cells",
        "reversible": False,
        "label": {"en": "Recode values", "ar": "إعادة ترميز القيم"},
        "detail": {
            "en": "Applies an explicit old-to-new mapping you define.",
            "ar": "يطبّق خريطة صريحة من القيمة القديمة إلى الجديدة.",
        },
        "options": [{"name": "mapping", "type": "mapping", "required": True}],
    },
    {
        "kind": "clip_outliers",
        "scope": "cells",
        "reversible": False,
        "label": {"en": "Bound extreme values", "ar": "حصر القيم المتطرفة"},
        "detail": {
            "en": "Keeps the row but rewrites the measurement. Totals will no longer "
            "match the source system.",
            "ar": "يُبقي الصف لكنه يعيد كتابة القياس. لن تطابق المجاميع النظام المصدر.",
        },
        "options": [
            {
                "name": "method",
                "type": "choice",
                "choices": ["iqr", "percentile", "absolute"],
                "default": "iqr",
            },
            {"name": "factor", "type": "number", "default": 1.5},
            {"name": "lower", "type": "number", "required": False},
            {"name": "upper", "type": "number", "required": False},
        ],
    },
    {
        "kind": "deduplicate",
        "scope": "rows",
        "reversible": False,
        "label": {"en": "Remove duplicate keys", "ar": "إزالة المفاتيح المكررة"},
        "detail": {
            "en": "Keeps one row per key. Rows are removed, so review is required.",
            "ar": "يُبقي صفًا واحدًا لكل مفتاح. تُحذف صفوف، لذا المراجعة مطلوبة.",
        },
        "options": [
            {"name": "keep", "type": "choice", "choices": ["first", "last"], "default": "first"}
        ],
    },
    {
        "kind": "drop_duplicate_rows",
        "scope": "rows",
        "reversible": False,
        "label": {"en": "Remove fully identical rows", "ar": "إزالة الصفوف المتطابقة تمامًا"},
        "detail": {
            "en": "Removes rows that repeat across every column.",
            "ar": "يحذف الصفوف المتكررة في جميع الأعمدة.",
        },
        "options": [
            {"name": "keep", "type": "choice", "choices": ["first", "last"], "default": "first"}
        ],
    },
    {
        "kind": "drop_missing_rows",
        "scope": "rows",
        "reversible": False,
        "label": {"en": "Remove rows missing a value", "ar": "حذف الصفوف الناقصة"},
        "detail": {
            "en": "Removes any row with no value in the selected columns.",
            "ar": "يحذف أي صف بلا قيمة في الأعمدة المختارة.",
        },
        "options": [],
    },
    {
        "kind": "filter_rows",
        "scope": "rows",
        "reversible": False,
        "label": {"en": "Keep rows matching a rule", "ar": "إبقاء الصفوف المطابقة لشرط"},
        "detail": {
            "en": "Restricts the dataset to rows that satisfy one explicit comparison.",
            "ar": "يقصر البيانات على الصفوف التي تحقق مقارنة صريحة واحدة.",
        },
        "options": [
            {
                "name": "operator",
                "type": "choice",
                "choices": [
                    "eq",
                    "ne",
                    "gt",
                    "gte",
                    "lt",
                    "lte",
                    "in",
                    "not_in",
                    "contains",
                    "not_null",
                ],
                "required": True,
            },
            {"name": "value", "type": "text", "required": False},
        ],
    },
    {
        "kind": "drop_column",
        "scope": "schema",
        "reversible": False,
        "label": {"en": "Remove a column", "ar": "حذف عمود"},
        "detail": {
            "en": "Removes the column from the new version. The source version keeps it.",
            "ar": "يحذف العمود من الإصدار الجديد. الإصدار الأصلي يحتفظ به.",
        },
        "options": [],
    },
    {
        "kind": "rename_column",
        "scope": "schema",
        "reversible": True,
        "label": {"en": "Rename a column", "ar": "إعادة تسمية عمود"},
        "detail": {
            "en": "Renames columns; duplicate names are rejected.",
            "ar": "يعيد تسمية الأعمدة؛ وتُرفض الأسماء المكررة.",
        },
        "options": [{"name": "names", "type": "mapping", "required": True}],
    },
]


class BriefRequest(StrictModel):
    locale: str = Field(default="en", pattern="^(ar|en)$")
    include_forecast: bool = True
    forecast_date_column: str | None = Field(default=None, max_length=240)
    forecast_value_column: str | None = Field(default=None, max_length=240)
    forecast_horizon: int = Field(default=6, ge=1, le=24)
    cleaning_run_id: str | None = Field(default=None, max_length=120)


class BriefExportRequest(BriefRequest):
    format: str = Field(default="pdf", pattern="^(pdf|html|docx|json|md|pptx)$")


class CleaningRecipeRequest(StrictModel):
    steps: list[dict[str, Any]] = Field(min_length=1, max_length=50)


class CleaningApplyRequest(CleaningRecipeRequest):
    expected_version: int = Field(ge=1)
    approved: bool = False


class MetricQueryRequest(StrictModel):
    metric_id: str = Field(min_length=1, max_length=80)
    dataset_version_id: str
    filters: dict[str, Any] = Field(default_factory=dict)


class DashboardCreateRequest(StrictModel):
    title: str = Field(min_length=1, max_length=240)
    widgets: list[dict[str, Any]] = Field(max_length=100)
    filters: dict[str, Any] = Field(default_factory=dict)


class DashboardUpdateRequest(DashboardCreateRequest):
    expected_version: int = Field(ge=1)


class ReportCreateRequest(StrictModel):
    title: str = Field(min_length=1, max_length=240)
    language: Literal["en", "ar"] = "en"
    sections: list[dict[str, Any]] = Field(max_length=200)


class ReportUpdateRequest(StrictModel):
    expected_version: int = Field(ge=1)
    title: str | None = Field(default=None, min_length=1, max_length=240)
    sections: list[dict[str, Any]] | None = Field(default=None, max_length=200)


class ReportPatchRequest(StrictModel):
    expected_version: int = Field(ge=1)
    operations: list[dict[str, Any]] = Field(min_length=1, max_length=100)


class RollbackRequest(StrictModel):
    version_id: str


class AssistantRequest(StrictModel):
    question: str = Field(min_length=1, max_length=8_000)
    metric_id: str | None = None
    conversation_id: str | None = None
    dataset_version_id: str | None = None
    locale: Literal["en", "ar"] = "en"


class ForecastRequest(StrictModel):
    metric_id: str
    horizon: int = Field(ge=1, le=24)
    interval: float = Field(default=0.90, ge=0.5, le=0.99)


class DatasetForecastRequest(StrictModel):
    date_column: str = Field(min_length=1, max_length=240)
    value_column: str | None = Field(default=None, max_length=240)
    horizon: int = Field(ge=1, le=24)
    aggregation: str = Field(default="sum", pattern="^(sum|mean|count)$")
    interval: float = Field(default=0.90, ge=0.5, le=0.99)


class WorkerInput(StrictModel):
    id: str
    skills: list[str] = Field(max_length=100)
    capacity_hours: float = Field(ge=0, le=10_000)


class TaskInput(StrictModel):
    id: str
    required_skill: str
    hours: float = Field(gt=0, le=10_000)


class OptimizationRequest(StrictModel):
    workers: list[WorkerInput] = Field(min_length=1, max_length=50)
    tasks: list[TaskInput] = Field(min_length=1, max_length=50)

    @model_validator(mode="after")
    def unique_identifiers(self) -> OptimizationRequest:
        if len({item.id for item in self.workers}) != len(self.workers) or len(
            {item.id for item in self.tasks}
        ) != len(self.tasks):
            raise ValueError("Worker and task identifiers must each be unique")
        return self


class SimulationRequest(StrictModel):
    arrival_rate_per_hour: float = Field(gt=0, le=10_000)
    service_rate_per_hour: float = Field(gt=0, le=10_000)
    baseline_agents: int = Field(ge=1, le=1_000)
    proposed_agents: int = Field(ge=1, le=1_000)
    hours: float = Field(gt=0, le=24 * 366)
    replications: int = Field(ge=1, le=2_000)
    seed: int = Field(ge=0, le=2**31 - 1)

    @model_validator(mode="after")
    def bounded_work(self) -> SimulationRequest:
        if self.arrival_rate_per_hour * self.hours * self.replications * 2 > 500_000:
            raise ValueError(
                "Simulation exceeds the 500000 expected-event budget; reduce horizon, "
                "arrivals, or replications"
            )
        return self


class CausalRequest(StrictModel):
    treatment: str
    outcome: str
    time_ordering: str | None = None
    assumptions: list[str] = Field(default_factory=list)
    confounders: list[str] = Field(default_factory=list)
    identification_strategy: str | None = None
    observations: list[dict[str, Any]] = Field(default_factory=list, max_length=10000)


class DecisionRequest(StrictModel):
    title: str = Field(min_length=1, max_length=240)
    problem: str | None = Field(default=None, max_length=10_000)
    owner: str | None = Field(default=None, max_length=180)
    review_date: date | None = None
    status: Literal["draft", "open", "approved", "closed"] = "draft"
    evidence_ids: list[str] = Field(default_factory=list, max_length=100)
    expected_result: str | None = Field(default=None, max_length=10_000)


class ScheduleRequest(StrictModel):
    name: str = Field(min_length=1, max_length=240)
    kind: Literal["source_sync", "quality_check", "metric_refresh", "report", "alert"]
    cron: str = Field(min_length=5, max_length=100)
    timezone: str = Field(min_length=1, max_length=64)

    @field_validator("cron")
    @classmethod
    def validate_cron(cls, value: str) -> str:
        if len(value.split()) != 5:
            raise ValueError("A five-field cron expression is required")
        return value


class ConnectorCreateRequest(StrictModel):
    kind: Literal["rest", "postgresql", "mysql", "sqlserver", "odoo_json2"]
    name: str = Field(min_length=1, max_length=160)
    base_url: str
    primary_key: str = "id"
    incremental_field: str = "updated_at"


class ConnectorCredentialsRequest(StrictModel):
    credentials: dict[str, str] = Field(min_length=1, max_length=12)


class ConnectorFetchRequest(StrictModel):
    max_rows: int | None = Field(default=None, ge=1, le=100_000)


class ConnectorSyncRequest(StrictModel):
    schema_: dict[str, str] = Field(alias="schema", min_length=1, max_length=500)
    records: list[dict[str, Any]] = Field(max_length=10_000)
    checkpoint: dict[str, Any]
    checkpoint_mode: Literal["watermark", "keyset", "opaque"] = "watermark"


class JobCreateRequest(StrictModel):
    kind: Literal["metric_refresh", "report_export", "connector_sync"]
    payload: dict[str, Any] = Field(default_factory=dict)


def create_app(
    *,
    database_url: str | None = None,
    artifact_root: Path | None = None,
    testing: bool = False,
    seed_demo: bool = False,
    connector_allow_hosts: tuple[str, ...] | None = None,
    login_rate_limit: int | None = None,
    api_rate_limit: int | None = None,
    rate_limit_window_seconds: int | None = None,
    agent_provider: str | None = None,
) -> FastAPI:
    base_settings = load_settings()
    # Tests must never reach a hosted model because a developer has a key exported:
    # they use the deterministic engine and run analyses inline unless told otherwise.
    resolved_agent_provider = agent_provider or (
        "deterministic"
        if testing and not os.getenv("BASEERA_AGENT_PROVIDER")
        else base_settings.agent_provider
    )
    settings = replace(
        base_settings,
        database_url=database_url or base_settings.database_url,
        artifact_root=artifact_root or base_settings.artifact_root,
        environment="test" if testing else base_settings.environment,
        connector_allow_hosts=(
            connector_allow_hosts
            if connector_allow_hosts is not None
            else base_settings.connector_allow_hosts
        ),
        agent_provider=resolved_agent_provider,
        agent_inline=base_settings.agent_inline or testing,
    )
    engine = build_engine(settings.database_url)
    session_factory = build_session_factory(engine)
    store = ArtifactStore(settings.artifact_root)
    # Outside development this raises when no key is configured, so a deployment can never
    # start in a state where it would accept credentials it cannot protect.
    secret_box = SecretBox.from_environment(settings.environment)
    from .agents.routes import AgentRunner, recover_interrupted_runs, register_agent_routes

    agent_runner = AgentRunner(session_factory, store, settings, inline=settings.agent_inline)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        Base.metadata.create_all(engine)
        if seed_demo:
            with session_factory() as db:
                populate_demo(db)
        with session_factory() as db:
            recover_interrupted_jobs(db)
            recover_interrupted_runs(db)
        yield
        agent_runner.shutdown()
        engine.dispose()

    application = FastAPI(
        title="BASEERA API",
        version="0.1.0",
        docs_url=f"{API_PREFIX}/docs",
        openapi_url=f"{API_PREFIX}/openapi.json",
        lifespan=lifespan,
    )
    application.state.settings = settings
    application.state.engine = engine
    application.state.session_factory = session_factory
    application.state.artifact_store = store
    application.state.secret_box = secret_box
    application.state.agent_runner = agent_runner
    application.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.allowed_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", CSRF_HEADER, "Idempotency-Key", "X-Correlation-ID"],
    )
    rate_lock = threading.Lock()
    rate_buckets: dict[tuple[str, str], tuple[float, int]] = {}
    window = rate_limit_window_seconds or settings.rate_limit_window_seconds

    @application.middleware("http")
    async def security_headers(request: Request, call_next):
        correlation_id = request.headers.get("X-Correlation-ID") or uuid.uuid4().hex
        request.state.correlation_id = correlation_id[:64]
        origin = request.headers.get("origin")
        if (origin and origin not in settings.allowed_origins) or request.headers.get(
            "sec-fetch-site"
        ) == "cross-site":
            response = JSONResponse(
                status_code=403,
                content={
                    "error": {
                        "code": "origin_denied",
                        "message": "Request origin is not permitted",
                        "details": {},
                    }
                },
            )
        else:
            expensive = request.url.path in {
                f"{API_PREFIX}/{path}"
                for path in (
                    "simulations",
                    "forecasts",
                    "optimizations",
                    "assistant/query",
                    "process/analyze",
                    "causal/analyze",
                    "analyst/runs",
                )
            }
            bucket = (
                "login"
                if request.url.path == f"{API_PREFIX}/auth/login"
                else "expensive"
                if expensive
                else "api"
            )
            limit = (
                (login_rate_limit or settings.login_rate_limit)
                if bucket == "login"
                else (api_rate_limit or settings.api_rate_limit)
            )
            if expensive:
                limit = min(limit, 12)
            key = (request.client.host if request.client else "unknown", bucket)
            now = time.monotonic()
            with rate_lock:
                started, count = rate_buckets.get(key, (now, 0))
                if now - started >= window:
                    started, count = now, 0
                limited = count >= limit
                rate_buckets[key] = (started, count + (not limited))
                if len(rate_buckets) > 10000:
                    for old_key, (timestamp, _) in list(rate_buckets.items()):
                        if now - timestamp >= window:
                            rate_buckets.pop(old_key, None)
            if limited:
                response = JSONResponse(
                    status_code=429,
                    content={
                        "error": {
                            "code": "rate_limit_exceeded",
                            "message": "Request limit reached; retry after the indicated delay",
                            "details": {},
                        }
                    },
                    headers={"Retry-After": str(max(1, math.ceil(window - (now - started))))},
                )
            else:
                response = await call_next(request)
            response.headers["X-RateLimit-Limit"] = str(limit)
            response.headers["X-RateLimit-Remaining"] = str(max(0, limit - count - 1))
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Correlation-ID"] = request.state.correlation_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'self'"
        )
        return response

    @application.exception_handler(AppError)
    async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": exc.code, "message": exc.message, "details": exc.details}},
        )

    @application.exception_handler(RequestValidationError)
    async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        errors = []
        for error in exc.errors():
            errors.append(
                {
                    "location": [str(item) for item in error.get("loc", ())],
                    "message": error.get("msg", "Invalid input"),
                    "type": error.get("type", "validation_error"),
                }
            )
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_failed",
                    "message": "The request did not match the API contract.",
                    "details": {"fields": errors},
                }
            },
        )

    register_routes(application, settings, store)
    # Assistant conversation history is intentionally registered separately from
    # the mutable analytics routes: it has its own tenant/user ownership checks.
    from .assistant import register_assistant_routes

    register_assistant_routes(application)
    # The AI analyst team: autonomous full analyses and evidence-backed conversation.
    register_agent_routes(application, agent_runner)
    return application


def register_routes(application: FastAPI, settings: Settings, store: ArtifactStore) -> None:
    @application.get(f"{API_PREFIX}/health/live")
    def live() -> dict[str, str]:
        return {"status": "live"}

    @application.get(f"{API_PREFIX}/health/ready")
    def ready(db: Session = Depends(get_db)) -> dict[str, Any]:
        db.execute(text("SELECT 1"))
        return {"status": "ready", "database": "available", "artifact_store": "available"}

    @application.post(f"{API_PREFIX}/auth/login")
    def login(
        payload: LoginRequest, response: Response, db: Session = Depends(get_db)
    ) -> dict[str, Any]:
        authenticated = authenticate(db, payload.email, payload.password)
        if authenticated is None:
            raise AppError(401, "invalid_credentials", "Email or password is incorrect")
        user, membership = authenticated
        organization = db.get(Organization, membership.organization_id)
        if organization is None:
            raise AppError(401, "invalid_credentials", "Email or password is incorrect")
        token, csrf, _ = create_session(db, membership, settings.session_hours)
        response.set_cookie(
            SESSION_COOKIE,
            token,
            max_age=settings.session_hours * 3600,
            httponly=True,
            secure=settings.secure_cookies,
            samesite="lax",
            path="/",
        )
        return {
            "user": {"id": user.id, "email": user.email, "display_name": user.display_name},
            "membership": {
                "role": membership.role,
                "department_ids": membership.department_ids or [],
                "permissions": membership.permissions or [],
            },
            "tenant": _organization(organization),
            "csrf_token": csrf,
        }

    @application.post(f"{API_PREFIX}/auth/logout")
    def logout(
        response: Response,
        context: AuthContext = Depends(require_csrf),
        db: Session = Depends(get_db),
    ) -> dict[str, str]:
        session = db.get(AuthSession, context.auth_session.token_hash)
        if session is not None:
            session.revoked_at = utcnow()
            db.commit()
        response.delete_cookie(SESSION_COOKIE, path="/")
        return {"status": "logged_out"}

    @application.get(f"{API_PREFIX}/auth/context")
    def auth_context(context: AuthContext = Depends(get_auth_context)) -> dict[str, Any]:
        return {
            "user": {
                "id": context.user.id,
                "email": context.user.email,
                "display_name": context.user.display_name,
            },
            "membership": {
                "role": context.membership.role,
                "department_ids": context.membership.department_ids or [],
                "permissions": context.membership.permissions or [],
            },
            "tenant": _organization(context.organization),
        }

    @application.get(f"{API_PREFIX}/auth/csrf")
    def csrf_token(
        context: AuthContext = Depends(get_auth_context), db: Session = Depends(get_db)
    ) -> dict[str, str]:
        return {"csrf_token": rotate_csrf(db, context)}

    @application.get(f"{API_PREFIX}/datasets")
    def datasets(
        page: int = Query(default=1, ge=1),
        limit: int = Query(default=50, ge=1, le=100),
        context: AuthContext = Depends(get_auth_context),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        statement = select(Dataset).where(Dataset.organization_id == context.tenant_id)
        if context.scoped_departments is not None:
            statement = statement.where(Dataset.created_by == context.user.id)
        items = db.scalars(
            statement.order_by(Dataset.created_at.desc(), Dataset.id)
            .offset((page - 1) * limit)
            .limit(limit + 1)
        ).all()
        return {
            "items": [_dataset(item) for item in items[:limit]],
            "page": page,
            "limit": limit,
            "has_more": len(items) > limit,
        }

    @application.get(f"{API_PREFIX}/reports")
    def reports(
        page: int = Query(default=1, ge=1),
        limit: int = Query(default=50, ge=1, le=100),
        context: AuthContext = Depends(get_auth_context),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        statement = select(Report).where(Report.organization_id == context.tenant_id)
        if context.scoped_departments is not None:
            statement = statement.where(Report.created_by == context.user.id)
        items = db.scalars(
            statement.order_by(Report.created_at.desc(), Report.id)
            .offset((page - 1) * limit)
            .limit(limit + 1)
        ).all()
        return {
            "items": [
                {
                    "id": item.id,
                    "title": item.title,
                    "language": item.language,
                    "version": item.current_version,
                }
                for item in items[:limit]
            ],
            "page": page,
            "limit": limit,
            "has_more": len(items) > limit,
        }

    @application.get(f"{API_PREFIX}/metrics")
    def metrics(_: AuthContext = Depends(get_auth_context)) -> dict[str, Any]:
        return {
            "items": [{"id": key, **definition} for key, definition in METRIC_DEFINITIONS.items()]
        }

    @application.get(f"{API_PREFIX}/capabilities")
    def capabilities(_: AuthContext = Depends(get_auth_context)) -> dict[str, Any]:
        return {
            "items": [
                *_file_capabilities(),
                {
                    "id": "llm.ollama",
                    "status": "configured"
                    if settings.llm_provider == "ollama" and settings.llm_base_url
                    else "needs_configuration",
                    "model": settings.llm_model,
                    "verification_endpoint": "/api/v1/assistant/status",
                },
                {"id": "analysis.arbitrary_python", "status": "unsupported"},
            ]
        }

    @application.post(f"{API_PREFIX}/datasets/upload", status_code=201)
    async def upload_dataset(
        response: Response,
        file: UploadFile = File(...),
        name: str | None = Form(default=None),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        context: AuthContext = Depends(require_csrf),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        accepted_media_types = {
            "text/csv",
            "text/plain",
            "text/tab-separated-values",
            "application/json",
            "application/x-ndjson",
            "application/octet-stream",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.apache.parquet",
            "application/vnd.ms-excel",
        }
        if file.content_type and file.content_type.split(";", 1)[0] not in accepted_media_types:
            raise AppError(415, "unsupported_media_type", "The upload media type is not supported")
        content = await file.read(settings.upload_max_bytes + 1)
        if len(content) > settings.upload_max_bytes:
            raise AppError(
                413,
                "upload_too_large",
                "The upload exceeds the configured size limit.",
                details={"max_bytes": settings.upload_max_bytes},
            )
        filename = Path(file.filename or "upload").name
        checksum = hashlib.sha256(content).hexdigest()
        request_hash = stable_hash({"checksum": checksum, "filename": filename, "name": name})
        if idempotency_key:
            existing = _idempotency(db, context.tenant_id, "dataset_upload", idempotency_key)
            if existing is not None:
                if existing.request_hash != request_hash:
                    raise AppError(
                        409,
                        "idempotency_conflict",
                        "This idempotency key was already used for another upload.",
                    )
                response.status_code = 200
                return {**existing.response_payload, "deduplicated": True}

        kind, parsed = parse_upload(filename, content)
        dataset_id = f"dataset-{uuid.uuid4().hex}"
        version_id = f"dataset-version-{uuid.uuid4().hex}"
        raw_key = f"{context.tenant_id}/datasets/{dataset_id}/original.{kind}"
        data_key = f"{context.tenant_id}/datasets/{dataset_id}/versions/1.json"
        store.write_bytes(raw_key, content)
        store.write_rows(data_key, parsed.rows)
        dataset = Dataset(
            id=dataset_id,
            organization_id=context.tenant_id,
            name=(name or Path(filename).stem)[:240],
            filename=filename[:300],
            format=kind,
            checksum=checksum,
            raw_object_key=raw_key,
            published_version_id=version_id,
            created_by=context.user.id,
        )
        version = DatasetVersion(
            id=version_id,
            organization_id=context.tenant_id,
            dataset_id=dataset_id,
            version_number=1,
            parent_version_id=None,
            kind="raw",
            data_object_key=data_key,
            row_count=len(parsed.rows),
            columns=parsed.columns,
            coverage=parsed.coverage,
            extraction=parsed.extraction,
            recipe=None,
            created_by=context.user.id,
        )
        profile = profile_rows(parsed.rows, parsed.columns)
        db.add_all([dataset, version])
        db.flush()
        db.add(
            DatasetProfile(
                id=f"profile-{uuid.uuid4().hex}",
                organization_id=context.tenant_id,
                dataset_version_id=version_id,
                payload=profile,
            )
        )
        for rejected in parsed.rejected:
            db.add(
                RejectedRecord(
                    id=f"rejected-{uuid.uuid4().hex}",
                    organization_id=context.tenant_id,
                    dataset_version_id=version_id,
                    source_location=rejected["source_location"],
                    error_code=rejected["error_code"],
                    raw_payload=rejected["raw_payload"],
                )
            )
        result = {
            "dataset": _dataset(dataset),
            "version": _dataset_version(version),
            "coverage": parsed.coverage,
            "extraction": parsed.extraction,
            "deduplicated": False,
        }
        if idempotency_key:
            db.add(
                IdempotencyRecord(
                    id=f"idempotency-{uuid.uuid4().hex}",
                    organization_id=context.tenant_id,
                    operation="dataset_upload",
                    key=idempotency_key,
                    request_hash=request_hash,
                    response_payload=result,
                )
            )
        db.commit()
        return result

    @application.get(f"{API_PREFIX}/datasets/{{dataset_id}}")
    def get_dataset(
        dataset_id: str,
        context: AuthContext = Depends(get_auth_context),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        return _dataset(_owned(db, Dataset, dataset_id, context.tenant_id, "Dataset"))

    @application.get(f"{API_PREFIX}/datasets/{{dataset_id}}/versions")
    def list_dataset_versions(
        dataset_id: str,
        context: AuthContext = Depends(get_auth_context),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        _owned(db, Dataset, dataset_id, context.tenant_id, "Dataset")
        rows = db.scalars(
            select(DatasetVersion)
            .where(
                DatasetVersion.organization_id == context.tenant_id,
                DatasetVersion.dataset_id == dataset_id,
            )
            .order_by(DatasetVersion.version_number)
        ).all()
        return {"items": [_dataset_version(item) for item in rows]}

    @application.get(f"{API_PREFIX}/dataset-versions/{{version_id}}/profile")
    def get_profile(
        version_id: str,
        context: AuthContext = Depends(get_auth_context),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        version = _owned(db, DatasetVersion, version_id, context.tenant_id, "Dataset version")
        record = db.scalar(
            select(DatasetProfile).where(
                DatasetProfile.organization_id == context.tenant_id,
                DatasetProfile.dataset_version_id == version_id,
            )
        )
        if record is None:
            raise not_found("Dataset profile")
        # A profile stored by an earlier build predates the per-column statistics, the
        # quality score and the suggested repairs. Recompute it from the version's own
        # rows rather than serving a payload the workspace cannot read; the version is
        # immutable, so the result is identical to what a fresh upload would produce.
        if "quality" not in record.payload or "recommended_steps" not in record.payload:
            record.payload = profile_rows(store.read_rows(version.data_object_key), version.columns)
            db.commit()
        return record.payload

    @application.get(f"{API_PREFIX}/dataset-versions/{{version_id}}/rows")
    def get_version_rows(
        version_id: str,
        limit: int = 50,
        offset: int = 0,
        context: AuthContext = Depends(get_auth_context),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        """A bounded window onto the actual rows, so a reviewer can see the data."""
        version = _owned(db, DatasetVersion, version_id, context.tenant_id, "Dataset version")
        if not 1 <= limit <= 500 or offset < 0:
            raise AppError(
                422, "invalid_range", "limit must be 1-500 and offset must not be negative."
            )
        rows = store.read_rows(version.data_object_key)
        return {
            "version_id": version.id,
            "columns": version.columns,
            "row_count": len(rows),
            "offset": offset,
            "limit": limit,
            "items": rows[offset : offset + limit],
        }

    @application.get(f"{API_PREFIX}/cleaning/steps")
    def cleaning_step_catalog(
        context: AuthContext = Depends(get_auth_context),
    ) -> dict[str, Any]:
        """What the cleaning engine can actually do, with each step's options."""
        return {"items": CLEANING_STEP_CATALOG, "kinds": sorted(STEP_KINDS)}

    @application.post(f"{API_PREFIX}/dataset-versions/{{version_id}}/cleaning/suggest")
    def suggest_cleaning(
        version_id: str,
        context: AuthContext = Depends(require_csrf),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        """Propose a recipe from the profile. Proposals are never applied on their own."""
        version = _owned(db, DatasetVersion, version_id, context.tenant_id, "Dataset version")
        profile = profile_rows(store.read_rows(version.data_object_key), version.columns)
        return {
            "version_id": version.id,
            "quality": profile["quality"],
            "recommended_steps": profile["recommended_steps"],
            "note": (
                "These steps are proposals derived from the column profile. Preview and "
                "approve them before any new version is written."
            ),
        }

    @application.post(f"{API_PREFIX}/dataset-versions/{{version_id}}/brief")
    def dataset_brief(
        version_id: str,
        payload: BriefRequest,
        context: AuthContext = Depends(require_csrf),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        """The consulting deliverable: condition, repairs, findings, outlook, limits."""
        return _build_brief(db, store, context, version_id, payload)

    @application.post(f"{API_PREFIX}/dataset-versions/{{version_id}}/brief/export")
    def export_dataset_brief(
        version_id: str,
        payload: BriefExportRequest,
        context: AuthContext = Depends(require_csrf),
        db: Session = Depends(get_db),
    ) -> Response:
        """Download the brief as a document or a presentation deck."""
        brief = _build_brief(db, store, context, version_id, payload)
        content, media_type, extension = brief_export(brief, payload.format)
        raw = str(brief["dataset"].get("name") or "analysis")
        name = re.sub(r"[^A-Za-z0-9_.-]+", "-", raw)[:60].strip("-") or "analysis"
        return Response(
            content=content,
            media_type=media_type,
            headers={
                "Content-Disposition": (f'attachment; filename="baseera-brief-{name}.{extension}"'),
                "Cache-Control": "no-store",
            },
        )

    @application.post(f"{API_PREFIX}/dataset-versions/{{version_id}}/insights")
    def dataset_insights(
        version_id: str,
        context: AuthContext = Depends(require_csrf),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        """Deterministic analyst findings over one dataset version."""
        version = _owned(db, DatasetVersion, version_id, context.tenant_id, "Dataset version")
        rows = store.read_rows(version.data_object_key)
        profile = profile_rows(rows, version.columns)
        result = analyze_dataset(rows, version.columns, profile)
        result["dataset_version_id"] = version.id
        result["quality"] = profile["quality"]
        return result

    @application.post(f"{API_PREFIX}/dataset-versions/{{version_id}}/cleaning/preview")
    def preview_cleaning(
        version_id: str,
        payload: CleaningRecipeRequest,
        context: AuthContext = Depends(require_csrf),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        version = _owned(db, DatasetVersion, version_id, context.tenant_id, "Dataset version")
        _rows, _columns, preview = run_recipe(
            store.read_rows(version.data_object_key), version.columns, payload.model_dump()
        )
        return preview

    @application.post(
        f"{API_PREFIX}/dataset-versions/{{version_id}}/cleaning/apply", status_code=201
    )
    def apply_cleaning(
        version_id: str,
        payload: CleaningApplyRequest,
        response: Response,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        context: AuthContext = Depends(require_csrf),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        source = _owned(db, DatasetVersion, version_id, context.tenant_id, "Dataset version")
        recipe = {"steps": payload.steps}
        request_hash = stable_hash(payload.model_dump())
        operation = f"cleaning_apply:{version_id}"
        if idempotency_key:
            existing = _idempotency(db, context.tenant_id, operation, idempotency_key)
            if existing is not None:
                if existing.request_hash != request_hash:
                    raise AppError(
                        409, "idempotency_conflict", "The key belongs to another request"
                    )
                response.status_code = 200
                return {**existing.response_payload, "deduplicated": True}
        if payload.expected_version != source.version_number:
            raise AppError(
                409,
                "version_conflict",
                "The source version changed; refresh before applying the recipe.",
            )
        cleaned, cleaned_columns, preview = run_recipe(
            store.read_rows(source.data_object_key), source.columns, recipe
        )
        if preview["requires_review"] and not payload.approved:
            raise AppError(
                409,
                "review_required",
                "This recipe changes reconciliation totals and requires explicit approval.",
                details=preview,
            )
        next_number = (
            int(
                db.scalar(
                    select(func.max(DatasetVersion.version_number)).where(
                        DatasetVersion.dataset_id == source.dataset_id
                    )
                )
                or 0
            )
            + 1
        )
        new_id = f"dataset-version-{uuid.uuid4().hex}"
        # The DB's version number is claimed at commit time. Concurrent writers must never
        # share a physical key while that claim is unresolved, including with legacy versions.
        key = f"{context.tenant_id}/datasets/{source.dataset_id}/versions/{new_id}.json"
        store.write_rows(key, cleaned)
        version = DatasetVersion(
            id=new_id,
            organization_id=context.tenant_id,
            dataset_id=source.dataset_id,
            version_number=next_number,
            parent_version_id=source.id,
            kind="cleaned",
            data_object_key=key,
            row_count=len(cleaned),
            columns=cleaned_columns,
            coverage={
                **source.coverage,
                "rows_accepted": len(cleaned),
                "rows_analyzed": len(cleaned),
            },
            extraction=source.extraction,
            recipe=recipe,
            created_by=context.user.id,
        )
        run = CleaningRun(
            id=f"cleaning-{uuid.uuid4().hex}",
            organization_id=context.tenant_id,
            source_version_id=source.id,
            output_version_id=new_id,
            recipe=recipe,
            preview=preview,
            approved_by=context.user.id,
        )
        dataset = _owned(db, Dataset, source.dataset_id, context.tenant_id, "Dataset")
        dataset.published_version_id = new_id
        db.add(version)
        try:
            db.flush()
        except IntegrityError as exc:
            db.rollback()
            raise AppError(409, "version_conflict", "Another version was published first") from exc
        db.add_all(
            [
                run,
                DatasetProfile(
                    id=f"profile-{uuid.uuid4().hex}",
                    organization_id=context.tenant_id,
                    dataset_version_id=new_id,
                    payload=profile_rows(cleaned, cleaned_columns),
                ),
            ]
        )
        result = {
            "version": _dataset_version(version),
            "cleaning_run_id": run.id,
            "preview": preview,
            "deduplicated": False,
        }
        if idempotency_key:
            db.add(
                IdempotencyRecord(
                    id=f"idempotency-{uuid.uuid4().hex}",
                    organization_id=context.tenant_id,
                    operation=operation,
                    key=idempotency_key,
                    request_hash=request_hash,
                    response_payload=result,
                )
            )
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise AppError(409, "version_conflict", "Another version was published first") from exc
        return result

    @application.post(f"{API_PREFIX}/datasets/{{dataset_id}}/rollback")
    def rollback_dataset(
        dataset_id: str,
        payload: RollbackRequest,
        context: AuthContext = Depends(require_csrf),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        dataset = _owned(db, Dataset, dataset_id, context.tenant_id, "Dataset")
        version = _owned(
            db, DatasetVersion, payload.version_id, context.tenant_id, "Dataset version"
        )
        if version.dataset_id != dataset.id:
            raise not_found("Dataset version")
        dataset.published_version_id = version.id
        db.commit()
        return {"dataset_id": dataset.id, "published_version_id": version.id}

    @application.post(f"{API_PREFIX}/metrics/query")
    def query_metric(
        payload: MetricQueryRequest,
        context: AuthContext = Depends(require_csrf),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        version = _owned(
            db, DatasetVersion, payload.dataset_version_id, context.tenant_id, "Dataset version"
        )
        return _metric_result(
            db,
            store,
            context,
            payload.metric_id,
            version,
            payload.filters,
        )

    @application.get(f"{API_PREFIX}/overview")
    def overview(
        context: AuthContext = Depends(get_auth_context), db: Session = Depends(get_db)
    ) -> dict[str, Any]:
        cutoff = context.organization.reporting_date
        end = cutoff + timedelta(days=1) if cutoff else None
        metrics = company_metrics(db, context.tenant_id, context.scoped_departments, end_date=end)
        scope = {
            "tenant_id": context.tenant_id,
            "department_ids": sorted(context.scoped_departments)
            if context.scoped_departments is not None
            else None,
            "start_date": None,
            "end_date_exclusive": end.isoformat() if end else None,
            "timezone": context.organization.timezone,
        }
        for metric_id, calculation in metrics.items():
            fingerprint = stable_hash(
                {
                    "scope": scope,
                    "metric_id": metric_id,
                    "calculation": calculation,
                    "metric_version": 1,
                }
            )
            result_id = f"result-{fingerprint[:32]}"
            result = {
                "result_id": result_id,
                "metric_id": metric_id,
                **calculation,
                "status": "completed" if calculation["value"] is not None else "insufficient_data",
                "evidence": {
                    "scope": scope,
                    "input_hash": fingerprint,
                    "source": "canonical_company",
                    "snapshot_basis": "scoped_aggregate_values",
                    "metric_definition_version": 1,
                },
            }
            if db.get(MetricResult, result_id) is None:
                db.add(
                    MetricResult(
                        id=result_id,
                        organization_id=context.tenant_id,
                        metric_id=metric_id,
                        input_hash=fingerprint,
                        payload=result,
                    )
                )
            calculation.update(result_id=result_id)
        try:
            db.commit()
        except IntegrityError:
            # A concurrent request may already have cached these deterministic snapshots.
            db.rollback()
        trend = []
        if cutoff:
            order_scope = [
                SalesOrder.organization_id == context.tenant_id,
                SalesOrder.order_date <= cutoff,
            ]
            if context.scoped_departments is not None:
                order_scope.append(
                    SalesOrder.department_id.in_(context.scoped_departments or {"__none__"})
                )
            values: dict[str, list[float]] = {}
            for day, revenue in db.execute(
                select(SalesOrder.order_date, SalesOrder.revenue).where(*order_scope)
            ):
                values.setdefault(day.strftime("%Y-%m"), []).append(float(revenue))
            for offset in range(5, -1, -1):
                ordinal = cutoff.year * 12 + cutoff.month - 1 - offset
                year, month = divmod(ordinal, 12)
                period = f"{year:04d}-{month + 1:02d}"
                previous = f"{year - 1:04d}-{month + 1:02d}"
                trend.append(
                    {
                        "period": period,
                        "current": round(math.fsum(values[period]), 2)
                        if period in values
                        else None,
                        "comparison": round(math.fsum(values[previous]), 2)
                        if previous in values
                        else None,
                    }
                )
        attention: list[dict[str, Any]] = []
        delayed = db.scalar(
            select(func.count(Project.id)).where(
                Project.organization_id == context.tenant_id,
                Project.delay_days > 0,
                *(
                    [Project.department_id.in_(context.scoped_departments or {"__none__"})]
                    if context.scoped_departments is not None
                    else []
                ),
            )
        )
        overloaded = db.scalar(
            select(func.count(Employee.id)).where(
                Employee.organization_id == context.tenant_id,
                Employee.workload_hours > Employee.capacity_hours,
                *(
                    [Employee.department_id.in_(context.scoped_departments or {"__none__"})]
                    if context.scoped_departments is not None
                    else []
                ),
            )
        )
        if delayed:
            attention.append(
                {
                    "kind": "project_risk",
                    "count": delayed,
                    "message": "Projects have recorded delay.",
                }
            )
        if overloaded:
            attention.append(
                {
                    "kind": "capacity_exception",
                    "count": overloaded,
                    "message": "Recorded workload exceeds planned capacity.",
                }
            )
        return {
            "as_of": (
                context.organization.reporting_date.isoformat()
                if context.organization.reporting_date
                else None
            ),
            "is_demo": context.organization.is_demo,
            "tenant": _organization(context.organization),
            "timezone": context.organization.timezone,
            "currency": context.organization.currency,
            "metrics": metrics,
            "trend": trend,
            "period_kind": "all_history_through_cutoff",
            "attention": attention,
            "scope": scope,
        }

    @application.get(f"{API_PREFIX}/company/{{module}}")
    def company_module(
        module: str,
        context: AuthContext = Depends(get_auth_context),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        items = _company_items(db, context, module)
        return {
            "items": items,
            "scope": {
                "tenant_id": context.tenant_id,
                "department_ids": sorted(context.department_ids),
            },
        }

    @application.post(f"{API_PREFIX}/assistant/query")
    def assistant_query(
        payload: AssistantRequest,
        context: AuthContext = Depends(require_csrf),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        from .assistant import run_assistant

        return run_assistant(payload.model_dump(), context, db, settings, store)

    @application.get(f"{API_PREFIX}/metric-results/{{result_id}}")
    def get_metric_result(
        result_id: str,
        context: AuthContext = Depends(get_auth_context),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        return _owned(db, MetricResult, result_id, context.tenant_id, "Metric result").payload

    @application.get(f"{API_PREFIX}/dashboards")
    def list_dashboards(
        context: AuthContext = Depends(get_auth_context),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        statement = select(Dashboard).where(Dashboard.organization_id == context.tenant_id)
        if context.scoped_departments is not None:
            statement = statement.where(Dashboard.created_by == context.user.id)
        rows = db.scalars(
            statement.order_by(Dashboard.created_at.desc(), Dashboard.id).limit(101)
        ).all()
        return {
            "items": [
                {"id": row.id, "title": row.title, "version": row.current_version}
                for row in rows[:100]
            ],
            "has_more": len(rows) > 100,
        }

    @application.get(f"{API_PREFIX}/dashboards/{{dashboard_id}}")
    def get_dashboard(
        dashboard_id: str,
        version: int | None = Query(default=None, ge=1),
        context: AuthContext = Depends(get_auth_context),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        dashboard = _owned(db, Dashboard, dashboard_id, context.tenant_id, "Dashboard")
        snapshot = db.scalar(
            select(DashboardVersion).where(
                DashboardVersion.organization_id == context.tenant_id,
                DashboardVersion.dashboard_id == dashboard.id,
                DashboardVersion.version_number == (version or dashboard.current_version),
            )
        )
        if snapshot is None:
            raise not_found("Dashboard version")
        return {
            "id": dashboard.id,
            "title": dashboard.title,
            "version": snapshot.version_number,
            "widgets": _hydrate_result_blocks(db, context.tenant_id, snapshot.widgets),
            "filters": snapshot.filters,
        }

    @application.patch(f"{API_PREFIX}/dashboards/{{dashboard_id}}")
    def update_dashboard(
        dashboard_id: str,
        payload: DashboardUpdateRequest,
        context: AuthContext = Depends(require_csrf),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        dashboard = _owned(db, Dashboard, dashboard_id, context.tenant_id, "Dashboard")
        if dashboard.current_version != payload.expected_version:
            raise AppError(409, "version_conflict", "Reload the dashboard before saving changes.")
        widgets = _hydrate_result_blocks(db, context.tenant_id, payload.widgets)
        dashboard.title = payload.title
        dashboard.current_version += 1
        snapshot = DashboardVersion(
            id=f"dashboard-version-{uuid.uuid4().hex}",
            organization_id=context.tenant_id,
            dashboard_id=dashboard.id,
            version_number=dashboard.current_version,
            widgets=widgets,
            filters=payload.filters,
            created_by=context.user.id,
        )
        db.add(snapshot)
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise AppError(
                409, "version_conflict", "Another dashboard version was saved first."
            ) from exc
        return {
            "id": dashboard.id,
            "title": dashboard.title,
            "version": snapshot.version_number,
            "widgets": widgets,
            "filters": snapshot.filters,
        }

    @application.post(f"{API_PREFIX}/dashboards", status_code=201)
    def create_dashboard(
        payload: DashboardCreateRequest,
        context: AuthContext = Depends(require_csrf),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        widgets = _hydrate_result_blocks(db, context.tenant_id, payload.widgets)
        dashboard = Dashboard(
            id=f"dashboard-{uuid.uuid4().hex}",
            organization_id=context.tenant_id,
            title=payload.title,
            current_version=1,
            created_by=context.user.id,
        )
        version = DashboardVersion(
            id=f"dashboard-version-{uuid.uuid4().hex}",
            organization_id=context.tenant_id,
            dashboard_id=dashboard.id,
            version_number=1,
            widgets=widgets,
            filters=payload.filters,
            created_by=context.user.id,
        )
        db.add(dashboard)
        db.flush()
        db.add(version)
        db.commit()
        return {
            "id": dashboard.id,
            "title": dashboard.title,
            "version": 1,
            "widgets": widgets,
            "filters": payload.filters,
        }

    @application.post(f"{API_PREFIX}/reports", status_code=201)
    def create_report(
        payload: ReportCreateRequest,
        context: AuthContext = Depends(require_csrf),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        sections = _hydrate_result_blocks(db, context.tenant_id, payload.sections)
        report = Report(
            id=f"report-{uuid.uuid4().hex}",
            organization_id=context.tenant_id,
            title=payload.title,
            language=payload.language,
            current_version=1,
            created_by=context.user.id,
        )
        version = ReportVersion(
            id=f"report-version-{uuid.uuid4().hex}",
            organization_id=context.tenant_id,
            report_id=report.id,
            version_number=1,
            title=payload.title,
            sections=sections,
            created_by=context.user.id,
        )
        db.add(report)
        db.flush()
        db.add(version)
        db.commit()
        return _report_payload(report, version)

    @application.patch(f"{API_PREFIX}/reports/{{report_id}}")
    def update_report(
        report_id: str,
        payload: ReportUpdateRequest,
        context: AuthContext = Depends(require_csrf),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        report, current = _current_report(db, report_id, context.tenant_id)
        if payload.expected_version != report.current_version:
            raise AppError(409, "version_conflict", "The report was changed by another request")
        title = payload.title or current.title
        sections = (
            _hydrate_result_blocks(db, context.tenant_id, payload.sections)
            if payload.sections is not None
            else current.sections
        )
        return _save_report_version(db, report, title, sections, context.user.id)

    @application.post(f"{API_PREFIX}/reports/{{report_id}}/patches")
    def patch_report(
        report_id: str,
        payload: ReportPatchRequest,
        context: AuthContext = Depends(require_csrf),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        report, current = _current_report(db, report_id, context.tenant_id)
        if payload.expected_version != report.current_version:
            raise AppError(409, "version_conflict", "The report was changed by another request")
        title = current.title
        sections = [dict(section) for section in current.sections]
        for operation in payload.operations:
            name = operation.get("op")
            value = operation.get("value")
            if name == "replace_title" and isinstance(value, str) and value.strip():
                title = value[:240]
            elif name == "append_section" and isinstance(value, dict):
                sections.extend(_hydrate_result_blocks(db, context.tenant_id, [value]))
            elif name == "remove_section" and isinstance(value, int) and 0 <= value < len(sections):
                sections.pop(value)
            else:
                raise AppError(
                    422,
                    "invalid_report_patch",
                    "A report patch contains an unsupported or invalid operation.",
                )
        return _save_report_version(db, report, title, sections, context.user.id)

    @application.get(f"{API_PREFIX}/reports/{{report_id}}/versions")
    def report_versions(
        report_id: str,
        context: AuthContext = Depends(get_auth_context),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        report = _owned(db, Report, report_id, context.tenant_id, "Report")
        versions = db.scalars(
            select(ReportVersion)
            .where(
                ReportVersion.organization_id == context.tenant_id,
                ReportVersion.report_id == report.id,
            )
            .order_by(ReportVersion.version_number)
        ).all()
        items = []
        for version in versions:
            payload = _report_payload(report, version)
            payload["sections"] = _hydrate_result_blocks(db, context.tenant_id, version.sections)
            items.append(payload)
        return {"items": items}

    @application.get(f"{API_PREFIX}/reports/{{report_id}}/export")
    def export_report(
        report_id: str,
        format: str = Query(default="html"),
        version: int | None = Query(default=None, ge=1),
        context: AuthContext = Depends(get_auth_context),
        db: Session = Depends(get_db),
    ) -> StreamingResponse:
        report = _owned(db, Report, report_id, context.tenant_id, "Report")
        version_number = version or report.current_version
        snapshot = db.scalar(
            select(ReportVersion).where(
                ReportVersion.organization_id == context.tenant_id,
                ReportVersion.report_id == report.id,
                ReportVersion.version_number == version_number,
            )
        )
        if snapshot is None:
            raise not_found("Report version")
        payload = _report_payload(report, snapshot)
        payload["sections"] = _hydrate_result_blocks(db, context.tenant_id, snapshot.sections)
        kind = format.lower()
        rendered = render_report_export(payload, kind)
        checksum = hashlib.sha256(rendered).hexdigest()
        object_key = (
            f"{context.tenant_id}/reports/{report.id}/exports/"
            f"v{version_number}-{checksum[:16]}.{kind}"
        )
        store.write_bytes(object_key, rendered)
        db.add(
            ReportExport(
                id=f"export-{uuid.uuid4().hex}",
                organization_id=context.tenant_id,
                report_id=report.id,
                report_version_id=snapshot.id,
                format=kind,
                object_key=object_key,
                checksum=checksum,
                created_by=context.user.id,
            )
        )
        db.commit()
        filename = export_filename(snapshot.title, version_number, kind)
        return StreamingResponse(
            io.BytesIO(rendered),
            media_type=EXPORT_MEDIA_TYPES[kind],
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "X-BASEERA-Report-Version": str(version_number),
                "X-Content-SHA256": checksum,
            },
        )

    @application.get(f"{API_PREFIX}/forecasts/metrics")
    def forecastable_metrics(
        context: AuthContext = Depends(get_auth_context),
    ) -> dict[str, Any]:
        """Which metrics carry a dated history the forecaster can actually read."""
        return {
            "items": [
                {"metric_id": metric_id, **definition}
                for metric_id, definition in FORECASTABLE_METRICS.items()
            ]
        }

    @application.post(f"{API_PREFIX}/forecasts", status_code=201)
    def create_forecast(
        payload: ForecastRequest,
        context: AuthContext = Depends(require_csrf),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        return forecast_company_metric(
            db,
            context.tenant_id,
            payload.metric_id,
            payload.horizon,
            context.scoped_departments,
            interval=payload.interval,
        )

    @application.post(f"{API_PREFIX}/dataset-versions/{{version_id}}/forecast", status_code=201)
    def forecast_dataset(
        version_id: str,
        payload: DatasetForecastRequest,
        context: AuthContext = Depends(require_csrf),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        """Forecast a column of an uploaded dataset on its own monthly history."""
        version = _owned(db, DatasetVersion, version_id, context.tenant_id, "Dataset version")
        unknown = [
            column
            for column in (payload.date_column, payload.value_column)
            if column and column not in version.columns
        ]
        if unknown:
            raise AppError(
                422,
                "unknown_column",
                f"{', '.join(repr(c) for c in unknown)} is not a column in this version.",
                details={"unknown_columns": unknown, "available_columns": version.columns},
            )
        result = forecast_dataset_column(
            store.read_rows(version.data_object_key),
            payload.date_column,
            payload.value_column,
            payload.horizon,
            payload.aggregation,
            interval=payload.interval,
        )
        result["dataset_version_id"] = version.id
        return result

    @application.post(f"{API_PREFIX}/process/analyze")
    def process_analysis(
        _: dict[str, Any],
        context: AuthContext = Depends(require_csrf),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        if context.scoped_departments is not None:
            raise AppError(
                403, "permission_denied", "Process events have no approved department mapping"
            )
        return analyze_process(db, context.tenant_id)

    @application.post(f"{API_PREFIX}/optimizations", status_code=201)
    def optimization(
        payload: OptimizationRequest,
        _: AuthContext = Depends(require_csrf),
    ) -> dict[str, Any]:
        return optimize_assignments(
            [item.model_dump() for item in payload.workers],
            [item.model_dump() for item in payload.tasks],
        )

    @application.post(f"{API_PREFIX}/simulations", status_code=201)
    def simulation(
        payload: SimulationRequest,
        context: AuthContext = Depends(require_csrf),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        result = simulate_queue(payload.model_dump())
        from .models import Scenario

        scenario = Scenario(
            id=f"scenario-{uuid.uuid4().hex}",
            organization_id=context.tenant_id,
            name="Support queue capacity comparison",
            assumptions=result["assumptions"],
            result=result,
            classification="calculated_scenario",
            created_by=context.user.id,
        )
        db.add(scenario)
        db.commit()
        return {"id": scenario.id, **result}

    @application.post(f"{API_PREFIX}/causal/analyze")
    def causal_analysis(
        payload: CausalRequest,
        _: AuthContext = Depends(require_csrf),
    ) -> dict[str, Any]:
        missing = []
        if not payload.time_ordering:
            missing.append("time_ordering")
        if not payload.assumptions:
            missing.append("assumptions")
        if (
            not payload.confounders
            and payload.identification_strategy != "randomized_difference_in_means"
        ):
            missing.append("confounders")
        if not payload.identification_strategy:
            missing.append("identification_strategy")
        if missing:
            raise AppError(
                422,
                "causal_assumptions_required",
                "A causal estimate requires an explicit study design and assumptions.",
                details={"missing": missing},
            )
        if payload.identification_strategy == "randomized_difference_in_means":
            required = {"random_assignment", "consistency", "no_interference"}
            if (
                not required.issubset(payload.assumptions)
                or payload.time_ordering != "treatment_before_outcome"
            ):
                raise AppError(
                    422,
                    "causal_assumptions_required",
                    "Randomized analysis requires explicit random assignment, consistency, "
                    "no interference, and treatment before outcome",
                )
            groups: dict[int, list[float]] = {0: [], 1: []}
            for observation in payload.observations:
                treatment = observation.get(payload.treatment)
                outcome = observation.get(payload.outcome)
                if (
                    isinstance(treatment, bool)
                    or treatment not in (0, 1)
                    or isinstance(outcome, bool)
                    or not isinstance(outcome, (int, float))
                    or not math.isfinite(outcome)
                ):
                    raise AppError(
                        422,
                        "invalid_causal_observation",
                        "Observations require binary treatment and a finite numeric outcome",
                    )
                groups[int(treatment)].append(float(outcome))
            if min(map(len, groups.values())) < 10:
                return {
                    "status": "insufficient_data",
                    "classification": "causal_hypothesis",
                    "reason": "At least ten observations in each treatment arm are required",
                }
            from statistics import mean, variance

            from scipy.stats import t

            estimate = mean(groups[1]) - mean(groups[0])
            components = [variance(groups[index]) / len(groups[index]) for index in (0, 1)]
            standard_error = math.sqrt(sum(components))
            denominator = sum(components[index] ** 2 / (len(groups[index]) - 1) for index in (0, 1))
            degrees = (
                sum(components) ** 2 / denominator if denominator else len(payload.observations) - 2
            )
            radius = float(t.ppf(0.975, degrees)) * standard_error
            return {
                "status": "completed",
                "classification": "causal_estimate_under_assumptions",
                "treatment": payload.treatment,
                "outcome": payload.outcome,
                "estimate": {
                    "average_treatment_effect": estimate,
                    "lower_95": estimate - radius,
                    "upper_95": estimate + radius,
                    "standard_error": standard_error,
                },
                "diagnostics": {
                    "observations": len(payload.observations),
                    "control_count": len(groups[0]),
                    "treated_count": len(groups[1]),
                    "method": "welch_difference_in_means",
                    "degrees_of_freedom": degrees,
                },
                "assumption_status": "declared_not_verified",
                "assumptions": payload.assumptions,
                "limitations": [
                    "Random assignment and temporal ordering are declarations supplied by the "
                    "analyst, not verified by this service.",
                    "The interval assumes independent observations; selection, attrition, and "
                    "interference can invalidate the estimate.",
                    "This estimate concerns the supplied sample and does not establish external "
                    "validity.",
                ],
            }
        return {
            "status": "effect_unavailable",
            "classification": "causal_hypothesis",
            "treatment": payload.treatment,
            "outcome": payload.outcome,
            "reason": "No approved analysis dataset or identification diagnostic was supplied.",
        }

    @application.get(f"{API_PREFIX}/connectors/capabilities")
    def connector_capabilities(_: AuthContext = Depends(get_auth_context)) -> dict[str, Any]:
        return {
            "items": [
                {
                    "id": connector,
                    "mode": "read_only",
                    "status": "needs_configuration",
                    "live_verified": False,
                }
                for connector in ["postgresql", "mysql", "sqlserver", "rest", "odoo_json2"]
            ]
        }

    @application.post(f"{API_PREFIX}/connectors", status_code=201)
    def create_connector_endpoint(
        payload: ConnectorCreateRequest,
        context: AuthContext = Depends(require_csrf),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        if context.membership.role not in {"executive", "administrator"}:
            raise AppError(403, "permission_denied", "Only an administrator can configure sources")
        normalized_url = validate_connector_destination(
            payload.base_url, settings.connector_allow_hosts
        )
        connector = Connector(
            id=f"connector-{uuid.uuid4().hex}",
            organization_id=context.tenant_id,
            kind=payload.kind,
            name=payload.name,
            status="configured_unverified",
            configuration={
                "base_url": normalized_url,
                "primary_key": payload.primary_key,
                "incremental_field": payload.incremental_field,
                "mode": "read_only",
            },
            checkpoint={},
        )
        db.add(connector)
        db.commit()
        return _connector(connector)

    @application.get(f"{API_PREFIX}/connectors/{{connector_id}}")
    def get_connector(
        connector_id: str,
        context: AuthContext = Depends(get_auth_context),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        connector = _owned(db, Connector, connector_id, context.tenant_id, "Connector")
        return _connector(connector, credential_state(db, connector))

    @application.post(f"{API_PREFIX}/connectors/{{connector_id}}/sync")
    def sync_connector_endpoint(
        connector_id: str,
        payload: ConnectorSyncRequest,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        context: AuthContext = Depends(require_csrf),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        if not idempotency_key:
            raise AppError(
                422, "idempotency_key_required", "Connector sync requires Idempotency-Key"
            )
        connector = _owned(db, Connector, connector_id, context.tenant_id, "Connector")
        if context.membership.role not in {"executive", "administrator"}:
            raise AppError(403, "permission_denied", "Only a source administrator can sync records")
        batch = {
            "schema": payload.schema_,
            "records": payload.records,
            "checkpoint": payload.checkpoint,
            "checkpoint_mode": payload.checkpoint_mode,
        }
        return sync_records(db, connector, batch, idempotency_key)

    def _require_secret_box() -> SecretBox:
        box = application.state.secret_box
        if box is None:
            raise AppError(
                503,
                "credential_storage_unavailable",
                "Credential storage is not configured. Set BASEERA_SECRET_KEY and restart.",
            )
        return cast(SecretBox, box)

    def _require_source_admin(context: AuthContext) -> None:
        if context.membership.role not in {"executive", "administrator"}:
            raise AppError(403, "permission_denied", "Only a source administrator can do this")

    @application.put(f"{API_PREFIX}/connectors/{{connector_id}}/credentials")
    def put_connector_credentials(
        connector_id: str,
        payload: ConnectorCredentialsRequest,
        context: AuthContext = Depends(require_csrf),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        """Store the credentials this deployment uses to reach the customer's system.

        The values are encrypted before they reach the database and are never read back through
        the API; only a non-reversible fingerprint is returned so an operator can confirm a change.
        """

        _require_source_admin(context)
        box = _require_secret_box()
        connector = _owned(db, Connector, connector_id, context.tenant_id, "Connector")
        store_credentials(db, box, connector, payload.credentials)
        if connector.status == "needs_credentials":
            connector.status = "configured_unverified"
        db.commit()
        return {"connector_id": connector.id, "credentials": credential_state(db, connector)}

    @application.delete(f"{API_PREFIX}/connectors/{{connector_id}}/credentials")
    def remove_connector_credentials(
        connector_id: str,
        context: AuthContext = Depends(require_csrf),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        _require_source_admin(context)
        connector = _owned(db, Connector, connector_id, context.tenant_id, "Connector")
        removed = delete_credentials(db, connector)
        if removed:
            connector.status = "needs_credentials"
        db.commit()
        return {"connector_id": connector.id, "removed": removed}

    @application.post(f"{API_PREFIX}/connectors/{{connector_id}}/fetch")
    def fetch_connector_endpoint(
        connector_id: str,
        payload: ConnectorFetchRequest | None = None,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        context: AuthContext = Depends(require_csrf),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        """Pull one bounded batch from the source using the stored credentials.

        This is the server-side counterpart to ``/sync``: the deployment reaches the source
        itself instead of waiting for an operator to stage records.
        """

        if not idempotency_key:
            raise AppError(
                422, "idempotency_key_required", "Connector fetch requires Idempotency-Key"
            )
        _require_source_admin(context)
        box = _require_secret_box()
        connector = _owned(db, Connector, connector_id, context.tenant_id, "Connector")
        requested_rows = payload.max_rows if payload is not None else None
        policy = SourcePolicy(
            allowed_hosts=settings.connector_allow_hosts,
            private_hosts=settings.connector_private_hosts,
            postgres_sslmode=settings.connector_postgres_sslmode,
        )
        limits = SourceLimits(max_rows=requested_rows or settings.connector_max_rows)
        result = run_source_fetch(
            db,
            box,
            connector,
            policy=policy,
            idempotency_key=idempotency_key,
            limits=limits,
        )
        db.commit()
        return result

    @application.get(f"{API_PREFIX}/connectors/{{connector_id}}/records")
    def connector_records(
        connector_id: str,
        context: AuthContext = Depends(get_auth_context),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        _owned(db, Connector, connector_id, context.tenant_id, "Connector")
        records = db.scalars(
            select(ConnectorRecord)
            .where(
                ConnectorRecord.organization_id == context.tenant_id,
                ConnectorRecord.connector_id == connector_id,
                ConnectorRecord.deleted.is_(False),
            )
            .order_by(ConnectorRecord.source_key)
        ).all()
        return {
            "items": [
                {
                    "source_key": item.source_key,
                    "source_version": item.source_version,
                    "payload": item.payload,
                    "updated_at": item.updated_at.isoformat(),
                }
                for item in records
            ]
        }

    @application.post(f"{API_PREFIX}/decisions", status_code=201)
    def create_decision(
        payload: DecisionRequest,
        context: AuthContext = Depends(require_csrf),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        _verify_evidence(db, context.tenant_id, payload.evidence_ids)
        decision = Decision(
            id=f"decision-{uuid.uuid4().hex}",
            organization_id=context.tenant_id,
            title=payload.title,
            problem=payload.problem,
            owner=payload.owner,
            review_date=payload.review_date,
            status=payload.status,
            evidence_ids=payload.evidence_ids,
            expected_result=payload.expected_result,
            version=1,
            created_by=context.user.id,
        )
        db.add(decision)
        db.commit()
        return _decision(decision)

    @application.get(f"{API_PREFIX}/decisions")
    def list_decisions(
        context: AuthContext = Depends(get_auth_context), db: Session = Depends(get_db)
    ) -> dict[str, Any]:
        decisions = db.scalars(
            select(Decision)
            .where(Decision.organization_id == context.tenant_id)
            .order_by(Decision.created_at.desc(), Decision.id)
        ).all()
        return {"items": [_decision(item) for item in decisions]}

    @application.post(f"{API_PREFIX}/schedules", status_code=201)
    def create_schedule(
        payload: ScheduleRequest,
        context: AuthContext = Depends(require_csrf),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        schedule = Schedule(
            id=f"schedule-{uuid.uuid4().hex}",
            organization_id=context.tenant_id,
            user_id=context.user.id,
            name=payload.name,
            kind=payload.kind,
            cron=payload.cron,
            timezone=payload.timezone,
            active=True,
            version=1,
        )
        db.add(schedule)
        db.commit()
        return _schedule(schedule)

    @application.post(f"{API_PREFIX}/jobs", status_code=202)
    def submit_job(
        payload: JobCreateRequest,
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
        context: AuthContext = Depends(require_csrf),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        job, deduplicated = create_job(
            db,
            organization_id=context.tenant_id,
            user_id=context.user.id,
            kind=payload.kind,
            payload=payload.payload,
            idempotency_key=idempotency_key,
        )
        return job_payload(job, deduplicated=deduplicated)

    @application.get(f"{API_PREFIX}/jobs/{{job_id}}")
    def get_job(
        job_id: str,
        context: AuthContext = Depends(get_auth_context),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        job = _owned(db, Job, job_id, context.tenant_id, "Job")
        if job.user_id != context.user.id and context.membership.role not in {
            "executive",
            "administrator",
        }:
            raise not_found("Job")
        return job_payload(job)

    @application.post(f"{API_PREFIX}/jobs/{{job_id}}/cancel")
    def cancel_job_endpoint(
        job_id: str,
        context: AuthContext = Depends(require_csrf),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        job = _owned(db, Job, job_id, context.tenant_id, "Job")
        if job.user_id != context.user.id and context.membership.role not in {
            "executive",
            "administrator",
        }:
            raise not_found("Job")
        return job_payload(cancel_job(db, job))


def _build_brief(
    db: Session,
    store: ArtifactStore,
    context: AuthContext,
    version_id: str,
    payload: BriefRequest,
) -> dict[str, Any]:
    """Assemble a brief from one dataset version, its cleaning log and an optional forecast."""
    version = _owned(db, DatasetVersion, version_id, context.tenant_id, "Dataset version")
    dataset = _owned(db, Dataset, version.dataset_id, context.tenant_id, "Dataset")
    rows = store.read_rows(version.data_object_key)
    profile = profile_rows(rows, version.columns)
    insights = analyze_dataset(rows, version.columns, profile)

    # The cleaning log for the run that produced this version, when there was one.
    cleaning: dict[str, Any] | None = None
    run = db.scalar(
        select(CleaningRun).where(
            CleaningRun.organization_id == context.tenant_id,
            CleaningRun.output_version_id == version.id,
        )
    )
    if payload.cleaning_run_id:
        run = _owned(db, CleaningRun, payload.cleaning_run_id, context.tenant_id, "Cleaning run")
    if run is not None:
        cleaning = run.preview

    forecast: dict[str, Any] | None = None
    if payload.include_forecast:
        date_column = payload.forecast_date_column or next(
            (
                name
                for name, column in profile["column_profiles"].items()
                if column.get("temporal", {}).get("detected_format")
            ),
            None,
        )
        value_column = payload.forecast_value_column or next(
            (
                name
                for name, column in profile["column_profiles"].items()
                if column.get("semantic_type") in {"number", "number_text"}
            ),
            None,
        )
        if date_column and value_column:
            try:
                forecast = forecast_dataset_column(
                    rows, date_column, value_column, payload.forecast_horizon, "sum"
                )
            except AppError as error:
                # A brief is still worth producing without an outlook; say why it is absent.
                forecast = {
                    "status": "unavailable",
                    "forecast": [],
                    "reason": error.message,
                    "reason_code": error.code,
                    "limitations": [
                        "No outlook is included because the series could not be built."
                    ],
                }

    organization = db.scalar(select(Organization).where(Organization.id == context.tenant_id))
    return build_brief(
        dataset={
            "id": dataset.id,
            "name": dataset.name,
            "filename": dataset.filename,
            "version_id": version.id,
            "version_number": version.version_number,
            "kind": version.kind,
        },
        profile=profile,
        insights=insights,
        cleaning=cleaning,
        forecast=forecast,
        locale=payload.locale,
        organization=(
            (organization.name_ar if payload.locale == "ar" else organization.name_en)
            if organization
            else None
        ),
    )


def _owned(db: Session, model: Any, identifier: str, tenant_id: str, label: str) -> Any:
    value = db.scalar(
        select(model).where(model.id == identifier, model.organization_id == tenant_id)
    )
    if value is None:
        raise not_found(label)
    context = db.info.get("auth_context")
    if context is not None and context.scoped_departments is not None:
        if hasattr(value, "created_by") and value.created_by != context.user.id:
            raise not_found(label)
        if isinstance(value, MetricResult):
            if value.dataset_version_id:
                _owned(db, DatasetVersion, value.dataset_version_id, tenant_id, "Dataset version")
            else:
                scope = value.payload.get("evidence", {}).get("scope", {})
                allowed = scope.get("department_ids")
                if allowed is None or not set(allowed).issubset(context.scoped_departments):
                    raise not_found(label)
    return value


def _idempotency(db: Session, tenant_id: str, operation: str, key: str) -> IdempotencyRecord | None:
    return db.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.organization_id == tenant_id,
            IdempotencyRecord.operation == operation,
            IdempotencyRecord.key == key,
        )
    )


def _organization(organization: Organization) -> dict[str, Any]:
    return {
        "id": organization.id,
        "name_en": organization.name_en,
        "name_ar": organization.name_ar,
        "timezone": organization.timezone,
        "currency": organization.currency,
        "is_demo": organization.is_demo,
        "reporting_date": (
            organization.reporting_date.isoformat() if organization.reporting_date else None
        ),
    }


def _dataset(dataset: Dataset) -> dict[str, Any]:
    return {
        "id": dataset.id,
        "name": dataset.name,
        "filename": dataset.filename,
        "format": dataset.format,
        "checksum": dataset.checksum,
        "published_version_id": dataset.published_version_id,
        "created_at": dataset.created_at.isoformat() if dataset.created_at else None,
    }


def _dataset_version(version: DatasetVersion) -> dict[str, Any]:
    return {
        "id": version.id,
        "dataset_id": version.dataset_id,
        "version_number": version.version_number,
        "parent_version_id": version.parent_version_id,
        "kind": version.kind,
        "row_count": version.row_count,
        "columns": version.columns,
        "coverage": version.coverage,
        "extraction": version.extraction,
        "created_at": version.created_at.isoformat() if version.created_at else None,
    }


def _metric_result(
    db: Session,
    store: ArtifactStore,
    context: AuthContext,
    metric_id: str,
    version: DatasetVersion,
    filters: dict[str, Any],
) -> dict[str, Any]:
    if filters:
        raise AppError(
            422,
            "unsupported_filter",
            "Dataset-upload metrics currently accept an empty filter object only.",
        )
    input_hash = stable_hash(
        {
            "tenant_id": context.tenant_id,
            "membership_id": context.membership.id,
            "metric_id": metric_id,
            "metric_version": 1,
            "dataset_version_id": version.id,
            "filters": filters,
        }
    )
    existing = db.scalar(
        select(MetricResult).where(
            MetricResult.organization_id == context.tenant_id,
            MetricResult.input_hash == input_hash,
        )
    )
    if existing is not None:
        return existing.payload
    calculation = dataset_metric(metric_id, store.read_rows(version.data_object_key))
    result_id = f"result-{input_hash[:32]}"
    result = {
        "result_id": result_id,
        "metric_id": metric_id,
        **calculation,
        "coverage": {
            **(version.coverage or {}),
            "rows_analyzed": version.row_count,
        },
        "evidence": {
            "dataset_version_id": version.id,
            "metric_definition_version": 1,
            "input_hash": input_hash,
            "filters": filters,
        },
    }
    db.add(
        MetricResult(
            id=result_id,
            organization_id=context.tenant_id,
            metric_id=metric_id,
            dataset_version_id=version.id,
            input_hash=input_hash,
            payload=result,
        )
    )
    db.commit()
    return result


def _hydrate_result_blocks(
    db: Session, tenant_id: str, blocks: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    hydrated: list[dict[str, Any]] = []
    for source in blocks:
        block = dict(source)
        result_id = block.get("result_id")
        if result_id:
            result = _owned(db, MetricResult, str(result_id), tenant_id, "Metric result")
            block["result"] = result.payload
        elif "result" in block:
            raise AppError(
                422, "result_reference_required", "Embedded results require a result ID."
            )
        hydrated.append(block)
    return hydrated


def _current_report(db: Session, report_id: str, tenant_id: str) -> tuple[Report, ReportVersion]:
    report = _owned(db, Report, report_id, tenant_id, "Report")
    version = db.scalar(
        select(ReportVersion).where(
            ReportVersion.organization_id == tenant_id,
            ReportVersion.report_id == report.id,
            ReportVersion.version_number == report.current_version,
        )
    )
    if version is None:
        raise not_found("Report version")
    return report, version


def _save_report_version(
    db: Session,
    report: Report,
    title: str,
    sections: list[dict[str, Any]],
    user_id: str,
) -> dict[str, Any]:
    next_version = report.current_version + 1
    version = ReportVersion(
        id=f"report-version-{uuid.uuid4().hex}",
        organization_id=report.organization_id,
        report_id=report.id,
        version_number=next_version,
        title=title,
        sections=sections,
        created_by=user_id,
    )
    report.title = title
    report.current_version = next_version
    db.add(version)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise AppError(409, "version_conflict", "Another report version was saved first") from exc
    return _report_payload(report, version)


def _report_payload(report: Report, version: ReportVersion) -> dict[str, Any]:
    return {
        "id": report.id,
        "title": version.title,
        "language": report.language,
        "version": version.version_number,
        "sections": version.sections,
        "created_at": version.created_at.isoformat() if version.created_at else None,
    }


def _connector(connector: Connector, credentials: dict[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": connector.id,
        "kind": connector.kind,
        "name": connector.name,
        "status": connector.status,
        "configuration": connector.configuration,
        "checkpoint": connector.checkpoint,
        "schema_fingerprint": connector.schema_fingerprint,
        "last_checked_at": (
            connector.last_checked_at.isoformat() if connector.last_checked_at else None
        ),
    }
    if credentials is not None:
        payload["credentials"] = credentials
    return payload


def _company_items(db: Session, context: AuthContext, module: str) -> list[dict[str, Any]]:
    tenant = context.tenant_id
    departments = context.department_ids
    # Each module selects a different ORM model. These intentionally dynamic response
    # rows are serialized into public dictionaries below, not returned as ORM objects.
    statement: Any
    rows: Any
    if module == "customers":
        statement = select(Customer).where(Customer.organization_id == tenant)
        if context.scoped_departments is not None:
            customers = (
                select(SupportCase.customer_id)
                .where(
                    SupportCase.organization_id == tenant,
                    SupportCase.department_id.in_(departments or {"__none__"}),
                )
                .union(
                    select(SalesOrder.customer_id).where(
                        SalesOrder.organization_id == tenant,
                        SalesOrder.department_id.in_(departments or {"__none__"}),
                    )
                )
            )
            statement = statement.where(Customer.id.in_(customers))
        rows = db.scalars(statement.order_by(Customer.id).limit(250)).all()
        return [
            {
                "id": row.id,
                "name": row.name,
                "segment": row.segment,
                "region": row.region,
                "status": row.status,
            }
            for row in rows
        ]
    if module == "people":
        if not any(
            context.can(permission)
            for permission in ("people:approved", "people:department", "people:aggregate")
        ):
            raise AppError(403, "permission_denied", "People access is not granted")
        statement = select(Employee).where(Employee.organization_id == tenant)
        if context.scoped_departments is not None or (
            context.can("people:department") and not context.can("people:approved")
        ):
            statement = statement.where(Employee.department_id.in_(departments or {"__none__"}))
        rows = db.scalars(statement.order_by(Employee.id).limit(250)).all()
        if context.can("people:aggregate") and not context.can("people:approved"):
            grouped: dict[str, int] = {}
            for employee in rows:
                grouped[employee.department_id] = grouped.get(employee.department_id, 0) + 1
            return [
                {"department_id": department, "headcount": count}
                for department, count in sorted(grouped.items())
            ]
        return [
            {
                "id": row.id,
                "department_id": row.department_id,
                "name": row.name,
                "role_title": row.role_title,
                "skills": row.skills,
                "capacity_hours": row.capacity_hours,
                "workload_hours": row.workload_hours,
                "status": row.status,
            }
            for row in rows
        ]
    if module == "projects":
        statement = select(Project).where(Project.organization_id == tenant)
        if context.membership.role == "department_manager":
            statement = statement.where(Project.department_id.in_(departments or {"__none__"}))
        rows = db.scalars(statement.order_by(Project.id).limit(250)).all()
        return [
            {
                "id": row.id,
                "department_id": row.department_id,
                "name": row.name,
                "status": row.status,
                "progress": row.progress,
                "budget": row.budget,
                "actual_cost": row.actual_cost,
                "due_date": row.due_date.isoformat(),
                "delay_days": row.delay_days,
            }
            for row in rows
        ]
    if module == "operations":
        statement = select(SalesOrder).where(SalesOrder.organization_id == tenant)
        if context.scoped_departments is not None:
            statement = statement.where(SalesOrder.department_id.in_(departments or {"__none__"}))
        rows = db.scalars(
            statement.order_by(SalesOrder.order_date.desc(), SalesOrder.id).limit(250)
        ).all()
        return [
            {
                "id": row.id,
                "source_id": row.source_id,
                "customer_id": row.customer_id,
                "department_id": row.department_id,
                "order_date": row.order_date.isoformat(),
                "revenue": row.revenue,
                "cost": row.cost,
                "status": row.status,
            }
            for row in rows
        ]
    if module == "costs":
        statement = select(Expense).where(Expense.organization_id == tenant)
        if context.scoped_departments is not None:
            statement = statement.where(Expense.department_id.in_(departments or {"__none__"}))
        rows = db.scalars(
            statement.order_by(Expense.expense_date.desc(), Expense.id).limit(250)
        ).all()
        return [
            {
                "id": row.id,
                "department_id": row.department_id,
                "date": row.expense_date.isoformat(),
                "category": row.category,
                "actual": row.actual,
                "budget": row.budget,
            }
            for row in rows
        ]
    if module == "support":
        statement = select(SupportCase).where(SupportCase.organization_id == tenant)
        if context.membership.role == "department_manager":
            statement = statement.where(SupportCase.department_id.in_(departments or {"__none__"}))
        rows = db.scalars(
            statement.order_by(SupportCase.opened_at.desc(), SupportCase.id).limit(250)
        ).all()
        return [
            {
                "id": row.id,
                "customer_id": row.customer_id,
                "department_id": row.department_id,
                "opened_at": row.opened_at.isoformat(),
                "resolved_at": row.resolved_at.isoformat() if row.resolved_at else None,
                "priority": row.priority,
                "status": row.status,
                "reopened": row.reopened,
            }
            for row in rows
        ]
    if module == "suppliers":
        if context.scoped_departments is not None:
            return []
        rows = db.scalars(
            select(Supplier).where(Supplier.organization_id == tenant).order_by(Supplier.id)
        ).all()
        return [
            {
                "id": row.id,
                "name": row.name,
                "category": row.category,
                "on_time_rate": row.on_time_rate,
                "risk_level": row.risk_level,
            }
            for row in rows
        ]
    if module == "objectives":
        statement = select(Objective).where(Objective.organization_id == tenant)
        if context.membership.role == "department_manager":
            statement = statement.where(Objective.department_id.in_(departments or {"__none__"}))
        rows = db.scalars(statement.order_by(Objective.id)).all()
        return [
            {
                "id": row.id,
                "department_id": row.department_id,
                "title": row.title,
                "metric_id": row.metric_id,
                "target": row.target,
                "progress": row.progress,
                "owner": row.owner,
                "review_date": row.review_date.isoformat(),
            }
            for row in rows
        ]
    raise not_found("Company module")


def _decision(decision: Decision) -> dict[str, Any]:
    return {
        "id": decision.id,
        "title": decision.title,
        "problem": decision.problem,
        "owner": decision.owner,
        "review_date": decision.review_date.isoformat() if decision.review_date else None,
        "status": decision.status,
        "evidence_ids": decision.evidence_ids,
        "expected_result": decision.expected_result,
        "observed_result": decision.observed_result,
        "version": decision.version,
        "created_at": decision.created_at.isoformat() if decision.created_at else None,
    }


def _schedule(schedule: Schedule) -> dict[str, Any]:
    return {
        "id": schedule.id,
        "name": schedule.name,
        "kind": schedule.kind,
        "cron": schedule.cron,
        "timezone": schedule.timezone,
        "active": schedule.active,
        "version": schedule.version,
        "last_run_at": schedule.last_run_at.isoformat() if schedule.last_run_at else None,
        "next_run_at": schedule.next_run_at.isoformat() if schedule.next_run_at else None,
    }


def _verify_evidence(db: Session, tenant_id: str, evidence_ids: list[str]) -> None:
    if not evidence_ids:
        return
    found = set(
        db.scalars(
            select(MetricResult.id).where(
                MetricResult.organization_id == tenant_id,
                MetricResult.id.in_(evidence_ids),
            )
        ).all()
    )
    if found != set(evidence_ids):
        raise not_found("Evidence")


def _file_capabilities() -> list[dict[str, Any]]:
    ready = ["csv", "tsv", "json", "jsonl", "xlsx", "parquet"]
    return [
        *[{"id": f"file.{kind}", "status": "ready"} for kind in ready],
        {"id": "file.xls", "status": "unsupported", "alternative": "xlsx_or_csv"},
    ]


app = create_app()
