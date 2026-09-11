from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from .analytics import METRIC_DEFINITIONS, company_metrics
from .errors import AppError
from .ingestion import stable_hash
from .models import Job, Membership, MetricResult, Organization, User, utcnow


def create_job(
    db: Session,
    *,
    organization_id: str,
    user_id: str,
    kind: str,
    payload: dict[str, Any],
    idempotency_key: str | None,
) -> tuple[Job, bool]:
    if kind not in {"metric_refresh", "report_export", "connector_sync"}:
        raise AppError(422, "unsupported_job_kind", "This durable job kind is not implemented")
    request_fingerprint = stable_hash({"kind": kind, "payload": payload})
    if idempotency_key:
        existing = db.scalar(
            select(Job).where(
                Job.organization_id == organization_id,
                Job.user_id == user_id,
                Job.idempotency_key == idempotency_key,
            )
        )
        if existing is not None:
            existing_fingerprint = stable_hash(
                {"kind": existing.kind, "payload": existing.payload or {}}
            )
            if existing_fingerprint != request_fingerprint:
                raise AppError(
                    409,
                    "idempotency_conflict",
                    "This idempotency key was already used for another job request.",
                )
            return existing, True
    job = Job(
        id=f"job-{uuid.uuid4().hex}",
        organization_id=organization_id,
        user_id=user_id,
        kind=kind,
        status="queued",
        payload=payload,
        idempotency_key=idempotency_key,
        progress_current=0,
        progress_total=1,
        max_attempts=3,
    )
    db.add(job)
    db.commit()
    return job, False


def cancel_job(db: Session, job: Job) -> Job:
    if job.status in {"completed", "failed", "cancelled"}:
        return job
    job.cancellation_requested = True
    if job.status == "queued":
        job.status = "cancelled"
        job.finished_at = utcnow()
    db.commit()
    return job


def recover_interrupted_jobs(db: Session, *, stale_after: timedelta = timedelta(minutes=5)) -> int:
    cutoff = utcnow() - stale_after
    jobs = db.scalars(
        select(Job).where(
            Job.status == "running",
            (Job.heartbeat_at.is_(None)) | (Job.heartbeat_at < cutoff),
        )
    ).all()
    for job in jobs:
        job.error = {
            "code": "worker_interrupted",
            "message": "The previous worker stopped before recording a terminal state.",
        }
        job.started_at = None
        job.heartbeat_at = None
        if job.cancellation_requested:
            job.status = "cancelled"
            job.finished_at = utcnow()
        elif job.attempt < job.max_attempts:
            job.status = "queued"
        else:
            job.status = "failed"
            job.finished_at = utcnow()
    if jobs:
        db.commit()
    return len(jobs)


def claim_next_job(db: Session) -> Job | None:
    statement = select(Job).where(Job.status == "queued").order_by(Job.created_at, Job.id).limit(1)
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        statement = statement.with_for_update(skip_locked=True)
    job = db.scalar(statement)
    if job is None:
        return None
    if job.cancellation_requested:
        job.status = "cancelled"
        job.finished_at = utcnow()
        db.commit()
        return None
    job.status = "running"
    job.attempt += 1
    job.started_at = utcnow()
    job.heartbeat_at = utcnow()
    job.error = None
    db.commit()
    return job


def execute_job(db: Session, job: Job) -> None:
    # These built-in jobs are intentionally bounded. Complex analysis adapters resolve only opaque
    # IDs inside their own isolated worker and are not represented as arbitrary Python execution.
    if job.cancellation_requested:
        job.status = "cancelled"
    elif job.kind == "metric_refresh":
        try:
            job.result_ref = _refresh_metric(db, job)
            job.progress_current = 1
            job.status = "completed"
        except AppError as exc:
            job.result_ref = None
            job.error = {"code": exc.code, "message": exc.message}
            job.status = "failed"
    elif job.kind in {"report_export", "connector_sync"}:
        job.error = {
            "code": "worker_adapter_required",
            "message": "The job requires an explicit artifact/source adapter configuration.",
        }
        job.status = "failed"
    else:
        job.error = {"code": "unsupported_job_kind", "message": "Unsupported job kind"}
        job.status = "failed"
    job.heartbeat_at = utcnow()
    job.finished_at = utcnow()
    db.commit()


def _refresh_metric(db: Session, job: Job) -> str:
    """Reauthorize at execution time and persist a real scoped metric snapshot."""
    user = db.get(User, job.user_id)
    membership = db.scalar(
        select(Membership).where(
            Membership.user_id == job.user_id,
            Membership.organization_id == job.organization_id,
            Membership.active.is_(True),
        )
    )
    if user is None or not user.active or membership is None:
        raise AppError(403, "permission_revoked", "Job owner no longer has workspace access.")
    permissions = set(membership.permissions or [])
    if "*" not in permissions and not {"analytics:read", "artifacts:write"}.issubset(permissions):
        raise AppError(403, "permission_denied", "Job owner no longer has analysis/write access.")
    payload = job.payload or {}
    metric_id = payload.get("metric_id", "net_revenue")
    if (
        set(payload) - {"metric_id"}
        or not isinstance(metric_id, str)
        or metric_id not in METRIC_DEFINITIONS
    ):
        raise AppError(422, "unsupported_job_parameters", "Choose an approved company metric only.")
    organization = db.get(Organization, job.organization_id)
    if organization is None:
        raise AppError(404, "not_found", "Workspace not found.")
    departments = (
        set(membership.department_ids or []) if membership.role == "department_manager" else None
    )
    end = organization.reporting_date + timedelta(days=1) if organization.reporting_date else None
    calculation = company_metrics(db, job.organization_id, departments, end_date=end)[metric_id]
    scope = {
        "tenant_id": job.organization_id,
        "department_ids": sorted(departments) if departments is not None else None,
        "end_date_exclusive": end.isoformat() if end else None,
        "timezone": organization.timezone,
    }
    fingerprint = stable_hash(
        {
            "scope": scope,
            "metric_id": metric_id,
            "calculation": calculation,
            "metric_version": 1,
            "job_owner": job.user_id,
        }
    )
    result_id = f"result-{fingerprint[:32]}"
    if db.get(MetricResult, result_id) is None:
        db.add(
            MetricResult(
                id=result_id,
                organization_id=job.organization_id,
                metric_id=metric_id,
                input_hash=fingerprint,
                payload={
                    "result_id": result_id,
                    "metric_id": metric_id,
                    **calculation,
                    "status": "completed"
                    if calculation["value"] is not None
                    else "insufficient_data",
                    "evidence": {
                        "scope": scope,
                        "input_hash": fingerprint,
                        "source": "canonical_company",
                        "metric_definition_version": 1,
                        "job_id": job.id,
                    },
                },
            )
        )
    return result_id


def job_payload(job: Job, *, deduplicated: bool = False) -> dict[str, Any]:
    return {
        "id": job.id,
        "kind": job.kind,
        "status": job.status,
        "progress": {"current": job.progress_current, "total": job.progress_total},
        "attempt": job.attempt,
        "max_attempts": job.max_attempts,
        "cancellation_requested": job.cancellation_requested,
        "result_ref": job.result_ref,
        "error": job.error,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
        "deduplicated": deduplicated,
    }
