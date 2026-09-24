"""HTTP surface of the AI analyst team.

Runs execute on a bounded in-process pool so the browser can follow the team live:
each run persists its event log as it goes, and the client polls with ``?since=`` to
receive only new events. Every run re-checks the owner's access before touching data.
"""

# FastAPI dependency declarations intentionally call Depends/Query in signatures.
# ruff: noqa: B008
from __future__ import annotations

import hashlib
import re
import threading
import time
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Literal

import structlog
from fastapi import Depends, FastAPI, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from ..auth import AuthContext, get_auth_context, get_db, require_csrf
from ..config import Settings
from ..errors import AppError, not_found
from ..ingestion import ArtifactStore, canonical_json, profile_rows
from ..models import (
    AgentRun,
    Dataset,
    DatasetProfile,
    DatasetVersion,
    Membership,
    User,
    utcnow,
)
from . import exports, samples
from .frame import build_frame
from .llm import engine_status, select_provider
from .orchestrator import run_autopilot, run_question
from .registry import TOOLS
from .team import TEAM
from .workspace import Cancelled

log = structlog.get_logger("baseera.agents")
PREFIX = "/api/v1/analyst"


class RunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset_version_id: str = Field(min_length=1, max_length=64)
    mode: Literal["autopilot", "question"] = "autopilot"
    question: str | None = Field(default=None, max_length=4000)
    locale: Literal["en", "ar"] = "en"
    thread_id: str | None = Field(default=None, max_length=64)


class SampleRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    locale: Literal["en", "ar"] = "en"


class AgentRunner:
    """Bounded executor; inline mode runs synchronously (tests, single-process tools)."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        store: ArtifactStore,
        settings: Settings,
        inline: bool,
    ) -> None:
        self.session_factory = session_factory
        self.store = store
        self.settings = settings
        self.inline = inline
        self.pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="baseera-agent")

    def submit(self, run_id: str) -> None:
        if self.inline:
            self.execute(run_id)
        else:
            self.pool.submit(self.execute, run_id)

    def shutdown(self) -> None:
        self.pool.shutdown(wait=False, cancel_futures=True)

    # ------------------------------------------------------------------ execution
    def execute(self, run_id: str) -> None:
        with self.session_factory() as db:
            run = db.get(AgentRun, run_id)
            if run is None or run.status not in {"queued"}:
                return
            events: list[dict[str, Any]] = []
            lock = threading.Lock()
            last_flush = [0.0]

            def flush(force: bool = False) -> None:
                now = time.monotonic()
                if not force and now - last_flush[0] < 0.4:
                    return
                with lock:
                    run.events = list(events)
                    db.commit()
                    last_flush[0] = now

            def emit(event: dict[str, Any]) -> None:
                events.append(event)
                flush(event.get("type") in {"finding", "done", "plan", "warning"})

            def cancelled() -> bool:
                flag = db.scalar(
                    select(AgentRun.cancellation_requested).where(AgentRun.id == run_id)
                )
                return bool(flag)

            run.status = "running"
            run.started_at = utcnow()
            db.commit()
            try:
                self._authorize(db, run)
                version = db.get(DatasetVersion, run.dataset_version_id)
                if version is None or version.organization_id != run.organization_id:
                    raise not_found("Dataset version")
                dataset = db.get(Dataset, version.dataset_id)
                rows = self.store.read_rows(version.data_object_key)
                stored = db.scalar(
                    select(DatasetProfile).where(DatasetProfile.dataset_version_id == version.id)
                )
                frame = build_frame(rows, version.columns, stored.payload if stored else None)
                provider = select_provider(self.settings)
                meta = {
                    "id": dataset.id if dataset else None,
                    "name": dataset.name if dataset else version.id,
                    "version_id": version.id,
                    "version_number": version.version_number,
                    "rows": version.row_count,
                    "filename": dataset.filename if dataset else None,
                }
                if run.mode == "autopilot":
                    result = run_autopilot(
                        frame, meta, run.locale, provider, self.settings, emit, cancelled
                    )
                else:
                    history, prior = self._context(db, run)
                    result = run_question(
                        frame,
                        meta,
                        run.question or "",
                        run.locale,
                        provider,
                        self.settings,
                        history,
                        prior,
                        emit,
                        cancelled,
                    )
                run.result = result
                run.engine = result.get("engine", {})
                run.status = "completed"
            except Cancelled:
                run.status = "cancelled"
            except AppError as error:
                run.status = "failed"
                run.error = {"code": error.code, "message": error.message}
            except Exception as error:  # noqa: BLE001 - a run must end in a terminal state
                log.error(
                    "agent_run_failed",
                    run_id=run_id,
                    error=repr(error),
                    trace=traceback.format_exc(),
                )
                run.status = "failed"
                run.error = {"code": "run_failed", "message": "The analysis failed unexpectedly."}
            run.events = list(events)
            run.finished_at = utcnow()
            db.commit()

    def _authorize(self, db: Session, run: AgentRun) -> None:
        # The run may start long after it was requested: re-check access now.
        user = db.get(User, run.user_id)
        membership = db.scalar(
            select(Membership).where(
                Membership.user_id == run.user_id,
                Membership.organization_id == run.organization_id,
                Membership.active.is_(True),
            )
        )
        if user is None or not user.active or membership is None:
            raise AppError(403, "permission_revoked", "Access was revoked before the run started.")
        permissions = set(membership.permissions or [])
        if "*" not in permissions and "analytics:read" not in permissions:
            raise AppError(403, "permission_denied", "Analytics access is required.")

    def _context(
        self, db: Session, run: AgentRun
    ) -> tuple[list[dict[str, str]], list[dict[str, Any]] | None]:
        history: list[dict[str, str]] = []
        if run.thread_id:
            earlier = db.scalars(
                select(AgentRun)
                .where(
                    AgentRun.organization_id == run.organization_id,
                    AgentRun.user_id == run.user_id,
                    AgentRun.thread_id == run.thread_id,
                    AgentRun.mode == "question",
                    AgentRun.status == "completed",
                    AgentRun.id != run.id,
                )
                .order_by(AgentRun.created_at)
                .limit(12)
            ).all()
            for item in earlier[-6:]:
                history.append({"role": "user", "content": item.question or ""})
                history.append(
                    {"role": "assistant", "content": (item.result or {}).get("answer", "")}
                )
        latest = db.scalar(
            select(AgentRun)
            .where(
                AgentRun.organization_id == run.organization_id,
                AgentRun.dataset_version_id == run.dataset_version_id,
                AgentRun.mode == "autopilot",
                AgentRun.status == "completed",
            )
            .order_by(AgentRun.created_at.desc())
            .limit(1)
        )
        prior = (latest.result or {}).get("findings", [])[:14] if latest else None
        return history, prior


def recover_interrupted_runs(db: Session) -> int:
    """In-process runs do not survive a restart; mark them so the user can rerun."""

    rows = db.scalars(select(AgentRun).where(AgentRun.status.in_(["queued", "running"]))).all()
    for run in rows:
        run.status = "failed"
        run.error = {
            "code": "interrupted",
            "message": "The service restarted while this analysis was running. Run it again.",
        }
        run.finished_at = utcnow()
    if rows:
        db.commit()
    return len(rows)


def _run_payload(run: AgentRun, include_result: bool = True, since: int = 0) -> dict[str, Any]:
    events = run.events or []
    elapsed = None
    if run.started_at:
        end = run.finished_at or utcnow()
        elapsed = round((end - run.started_at).total_seconds(), 1)
    payload: dict[str, Any] = {
        "id": run.id,
        "dataset_version_id": run.dataset_version_id,
        "thread_id": run.thread_id,
        "mode": run.mode,
        "locale": run.locale,
        "question": run.question,
        "status": run.status,
        "engine": run.engine or {},
        "events": events[since:] if include_result else [],
        "events_total": len(events),
        "error": run.error,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "elapsed_seconds": elapsed,
    }
    if include_result:
        payload["result"] = run.result
    elif run.result and run.mode == "question":
        payload["answer_preview"] = (run.result.get("answer") or "")[:280]
    elif run.result and run.mode == "autopilot":
        payload["summary"] = {
            "findings": len(run.result.get("findings", [])),
            "recommendations": len(run.result.get("recommendations", [])),
        }
    return payload


def _version_for(db: Session, context: AuthContext, version_id: str) -> DatasetVersion:
    version = db.scalar(
        select(DatasetVersion).where(
            DatasetVersion.id == version_id,
            DatasetVersion.organization_id == context.tenant_id,
        )
    )
    if version is None:
        raise not_found("Dataset version")
    # Uploaded files carry no department mapping; scoped managers see only their own.
    if context.scoped_departments is not None and version.created_by != context.user.id:
        raise not_found("Dataset version")
    return version


def _owned_run(db: Session, context: AuthContext, run_id: str) -> AgentRun:
    run = db.scalar(
        select(AgentRun).where(
            AgentRun.id == run_id,
            AgentRun.organization_id == context.tenant_id,
            AgentRun.user_id == context.user.id,
        )
    )
    if run is None:
        raise not_found("Analysis run")
    return run


def register_agent_routes(application: FastAPI, runner: AgentRunner) -> None:
    settings: Settings = application.state.settings
    store: ArtifactStore = application.state.artifact_store

    @application.get(f"{PREFIX}/team")
    def team(context: AuthContext = Depends(get_auth_context)) -> dict[str, Any]:
        return {
            "team": TEAM,
            "engine": engine_status(settings),
            "tools": [
                {
                    "name": tool.name,
                    "agent": tool.agent,
                    "title": {"en": tool.title_en, "ar": tool.title_ar},
                }
                for tool in TOOLS.values()
            ],
            "principles": [
                {
                    "en": "Every number is computed by deterministic, reproducible tools.",
                    "ar": "كل رقم تحسبه أدوات حتمية قابلة لإعادة الإنتاج.",
                },
                {
                    "en": "Every figure a model writes is verified against the evidence.",
                    "ar": "كل رقم يكتبه النموذج يُتحقق منه مقابل الأدلة.",
                },
                {
                    "en": "Raw rows never leave the server; models see aggregates and schema only.",
                    "ar": "الصفوف الخام لا تغادر الخادم؛ النماذج ترى المجاميع والبنية فقط.",
                },
            ],
        }

    @application.get(f"{PREFIX}/samples")
    def list_samples(context: AuthContext = Depends(get_auth_context)) -> dict[str, Any]:
        return {"items": [{"id": key, **meta} for key, meta in samples.SAMPLES.items()]}

    @application.post(f"{PREFIX}/samples/{{sample_id}}", status_code=201)
    def load_sample(
        sample_id: str,
        payload: SampleRequest,
        context: AuthContext = Depends(require_csrf),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        if sample_id not in samples.SAMPLES:
            raise not_found("Sample dataset")
        columns, rows = samples.generate(sample_id, payload.locale)
        content = canonical_json(rows).encode("utf-8")
        dataset_id = f"dataset-{uuid.uuid4().hex}"
        version_id = f"dataset-version-{uuid.uuid4().hex}"
        raw_key = f"{context.tenant_id}/datasets/{dataset_id}/original.json"
        data_key = f"{context.tenant_id}/datasets/{dataset_id}/versions/1.json"
        store.write_bytes(raw_key, content)
        store.write_rows(data_key, rows)
        title = samples.SAMPLES[sample_id]["title"][payload.locale]
        dataset = Dataset(
            id=dataset_id,
            organization_id=context.tenant_id,
            name=title[:240],
            filename=f"{sample_id}.json",
            format="json",
            checksum=hashlib.sha256(content).hexdigest(),
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
            row_count=len(rows),
            columns=columns,
            coverage={"rows_accepted": len(rows), "rows_rejected": 0, "sample": sample_id},
            extraction={"format": "json", "source": "sample"},
            recipe=None,
            created_by=context.user.id,
        )
        db.add_all([dataset, version])
        db.flush()
        db.add(
            DatasetProfile(
                id=f"profile-{uuid.uuid4().hex}",
                organization_id=context.tenant_id,
                dataset_version_id=version_id,
                payload=profile_rows(rows, columns),
            )
        )
        db.commit()
        return {
            "dataset": {"id": dataset.id, "name": dataset.name, "filename": dataset.filename},
            "version": {
                "id": version.id,
                "version_number": 1,
                "row_count": version.row_count,
                "columns": columns,
            },
        }

    @application.get(f"{PREFIX}/workspace")
    def workspace(
        context: AuthContext = Depends(get_auth_context), db: Session = Depends(get_db)
    ) -> dict[str, Any]:
        query = select(Dataset).where(Dataset.organization_id == context.tenant_id)
        if context.scoped_departments is not None:
            query = query.where(Dataset.created_by == context.user.id)
        datasets = db.scalars(query.order_by(Dataset.created_at.desc()).limit(100)).all()
        items = []
        for dataset in datasets:
            versions = db.scalars(
                select(DatasetVersion)
                .where(DatasetVersion.dataset_id == dataset.id)
                .order_by(DatasetVersion.version_number.desc())
            ).all()
            if not versions:
                continue
            latest = versions[0]
            last_run = db.scalar(
                select(AgentRun)
                .where(
                    AgentRun.organization_id == context.tenant_id,
                    AgentRun.user_id == context.user.id,
                    AgentRun.dataset_version_id.in_([v.id for v in versions]),
                    AgentRun.mode == "autopilot",
                )
                .order_by(AgentRun.created_at.desc())
                .limit(1)
            )
            items.append(
                {
                    "id": dataset.id,
                    "name": dataset.name,
                    "filename": dataset.filename,
                    "created_at": dataset.created_at.isoformat() if dataset.created_at else None,
                    "versions": [
                        {
                            "id": v.id,
                            "version_number": v.version_number,
                            "kind": v.kind,
                            "row_count": v.row_count,
                            "columns": len(v.columns or []),
                        }
                        for v in versions
                    ],
                    "latest_version_id": latest.id,
                    "last_analysis": _run_payload(last_run, include_result=False)
                    if last_run
                    else None,
                }
            )
        return {"items": items, "engine": engine_status(settings)}

    @application.post(f"{PREFIX}/runs", status_code=202)
    def create_run(
        payload: RunRequest,
        context: AuthContext = Depends(require_csrf),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        if not context.can("analytics:read"):
            raise AppError(403, "permission_denied", "Analytics access is required.")
        version = _version_for(db, context, payload.dataset_version_id)
        question = (payload.question or "").strip()
        if payload.mode == "question" and not question:
            raise AppError(422, "question_required", "Ask a question for the analyst team.")
        active = db.scalars(
            select(AgentRun).where(
                AgentRun.organization_id == context.tenant_id,
                AgentRun.user_id == context.user.id,
                AgentRun.status.in_(["queued", "running"]),
            )
        ).all()
        if len(active) >= 3:
            raise AppError(
                429, "too_many_runs", "Three analyses are already running; wait for one to finish."
            )
        thread_id = payload.thread_id
        if (
            payload.mode == "question"
            and thread_id
            and not re.fullmatch(r"thread-[0-9a-f]{32}", thread_id)
        ):
            raise AppError(422, "invalid_thread", "Unknown conversation thread.")
        if payload.mode == "question" and not thread_id:
            thread_id = f"thread-{uuid.uuid4().hex}"
        run = AgentRun(
            id=f"run-{uuid.uuid4().hex}",
            organization_id=context.tenant_id,
            user_id=context.user.id,
            dataset_version_id=version.id,
            thread_id=thread_id if payload.mode == "question" else None,
            mode=payload.mode,
            locale=payload.locale,
            question=question or None,
            status="queued",
            engine={},
            events=[],
        )
        db.add(run)
        db.commit()
        runner.submit(run.id)
        db.expire_all()
        refreshed = db.get(AgentRun, run.id)
        return _run_payload(refreshed or run)

    @application.get(f"{PREFIX}/runs")
    def list_runs(
        dataset_version_id: str | None = Query(default=None, max_length=64),
        mode: Literal["autopilot", "question"] | None = None,
        thread_id: str | None = Query(default=None, max_length=64),
        limit: int = Query(default=30, ge=1, le=100),
        context: AuthContext = Depends(get_auth_context),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        query = select(AgentRun).where(
            AgentRun.organization_id == context.tenant_id,
            AgentRun.user_id == context.user.id,
        )
        if dataset_version_id:
            query = query.where(AgentRun.dataset_version_id == dataset_version_id)
        if mode:
            query = query.where(AgentRun.mode == mode)
        if thread_id:
            query = query.where(AgentRun.thread_id == thread_id)
        rows = db.scalars(query.order_by(AgentRun.created_at.desc()).limit(limit)).all()
        return {"items": [_run_payload(row, include_result=False) for row in rows]}

    @application.get(f"{PREFIX}/runs/{{run_id}}")
    def get_run(
        run_id: str,
        since: int = Query(default=0, ge=0),
        context: AuthContext = Depends(get_auth_context),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        run = _owned_run(db, context, run_id)
        # Stored results are re-served only while the reader can still open the dataset.
        _version_for(db, context, run.dataset_version_id)
        return _run_payload(run, include_result=True, since=since)

    @application.post(f"{PREFIX}/runs/{{run_id}}/cancel")
    def cancel_run(
        run_id: str,
        context: AuthContext = Depends(require_csrf),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        run = _owned_run(db, context, run_id)
        if run.status in {"queued", "running"}:
            run.cancellation_requested = True
            if run.status == "queued":
                run.status = "cancelled"
                run.finished_at = utcnow()
            db.commit()
        return _run_payload(run, include_result=False)

    @application.get(f"{PREFIX}/runs/{{run_id}}/export")
    def export_run(
        run_id: str,
        format: Literal["html", "pdf", "docx", "pptx", "md", "json"] = "pdf",
        locale: Literal["en", "ar"] | None = None,
        context: AuthContext = Depends(get_auth_context),
        db: Session = Depends(get_db),
    ) -> Response:
        run = _owned_run(db, context, run_id)
        _version_for(db, context, run.dataset_version_id)
        if run.mode != "autopilot" or run.status != "completed" or not run.result:
            raise AppError(409, "not_exportable", "Only a completed full analysis can be exported.")
        language = locale or run.locale
        content, media_type, extension = exports.export(run.result, format, language)
        meta = run.result.get("dataset", {})
        name = re.sub(r"[^A-Za-z0-9_-]+", "-", str(meta.get("name") or "")).strip("-")[:60]
        if not name:
            stem = str(meta.get("filename") or "analysis").rsplit(".", 1)[0]
            name = re.sub(r"[^A-Za-z0-9_-]+", "-", stem).strip("-")[:60] or "analysis"
        return Response(
            content=content,
            media_type=media_type,
            headers={
                "Content-Disposition": f'attachment; filename="baseera-analysis-{name}-{language}.{extension}"',
                "Cache-Control": "no-store",
            },
        )

    @application.get(f"{PREFIX}/threads")
    def threads(
        dataset_version_id: str = Query(max_length=64),
        context: AuthContext = Depends(get_auth_context),
        db: Session = Depends(get_db),
    ) -> dict[str, Any]:
        rows = db.scalars(
            select(AgentRun)
            .where(
                AgentRun.organization_id == context.tenant_id,
                AgentRun.user_id == context.user.id,
                AgentRun.dataset_version_id == dataset_version_id,
                AgentRun.mode == "question",
            )
            .order_by(AgentRun.created_at)
            .limit(300)
        ).all()
        grouped: dict[str, dict[str, Any]] = {}
        for row in rows:
            thread = grouped.setdefault(
                row.thread_id or row.id,
                {
                    "id": row.thread_id,
                    "title": (row.question or "")[:90],
                    "turns": 0,
                    "updated_at": None,
                },
            )
            thread["turns"] += 1
            thread["updated_at"] = row.created_at.isoformat() if row.created_at else None
        return {
            "items": sorted(grouped.values(), key=lambda t: t["updated_at"] or "", reverse=True)
        }
