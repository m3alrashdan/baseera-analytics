"""Shared working memory of one analysis run: evidence, findings and the event log."""

from __future__ import annotations

import time
import traceback
from collections.abc import Callable
from typing import Any

import structlog

from ..errors import AppError
from .common import bi, clean, confidence_label
from .frame import AnalysisFrame
from .registry import TOOLS, execute

log = structlog.get_logger("baseera.agents")

Emit = Callable[[dict[str, Any]], None]


class Cancelled(Exception):
    """Raised inside a run when the user asked to stop it."""


class Workspace:
    def __init__(
        self,
        frame: AnalysisFrame,
        emit: Emit | None = None,
        cancelled: Callable[[], bool] | None = None,
    ) -> None:
        self.frame = frame
        self._emit = emit or (lambda event: None)
        self._cancelled = cancelled or (lambda: False)
        self.evidence: dict[str, dict[str, Any]] = {}
        self.findings: list[dict[str, Any]] = []
        self.started = time.monotonic()
        self.tool_calls = 0
        self.last_error: str | None = None

    # ----------------------------------------------------------------------- events
    def emit(
        self,
        agent: str,
        kind: str,
        title: dict[str, str],
        detail: dict[str, Any] | None = None,
    ) -> None:
        if self._cancelled():
            raise Cancelled()
        event = {
            "t": round(time.monotonic() - self.started, 2),
            "agent": agent,
            "type": kind,
            "title": title,
            "detail": clean(detail or {}),
        }
        self._emit(event)

    # ------------------------------------------------------------------------ tools
    def run(
        self, agent: str, tool: str, arguments: dict[str, Any] | None = None, quiet: bool = False
    ) -> tuple[str | None, dict[str, Any] | None]:
        arguments = arguments or {}
        spec = TOOLS[tool]
        if not quiet:
            self.emit(
                agent,
                "tool_call",
                bi(f"{spec.title_en}", f"{spec.title_ar}"),
                {"tool": tool, "arguments": arguments},
            )
        self.tool_calls += 1
        started = time.monotonic()
        try:
            result = execute(self.frame, tool, arguments)
        except AppError as error:
            self.last_error = error.message
            self.emit(
                agent,
                "tool_error",
                bi(f"{spec.title_en}: skipped", f"{spec.title_ar}: تم التخطي"),
                {"tool": tool, "code": error.code, "message": error.message},
            )
            return None, None
        except Exception as error:  # noqa: BLE001 - one failing analysis must not sink the run
            self.last_error = type(error).__name__
            log.warning(
                "agent_tool_failed", tool=tool, error=repr(error), trace=traceback.format_exc()
            )
            self.emit(
                agent,
                "tool_error",
                bi(f"{spec.title_en}: failed", f"{spec.title_ar}: تعذّر"),
                {"tool": tool, "code": "tool_failed", "message": type(error).__name__},
            )
            return None, None
        evidence_id = f"ev-{len(self.evidence) + 1}"
        self.evidence[evidence_id] = {
            "id": evidence_id,
            "tool": tool,
            "agent": agent,
            "title": bi(spec.title_en, spec.title_ar),
            "arguments": clean(arguments),
            "result": result,
            "elapsed_seconds": round(time.monotonic() - started, 3),
        }
        if not quiet:
            summary = result.get("summary") if isinstance(result, dict) else None
            self.emit(
                agent,
                "tool_result",
                bi(f"{spec.title_en}: done", f"{spec.title_ar}: اكتمل"),
                {"tool": tool, "evidence_id": evidence_id, "summary": summary},
            )
        return evidence_id, result

    # --------------------------------------------------------------------- findings
    def add(
        self,
        *,
        agent: str,
        kind: str,
        title: dict[str, str],
        summary: dict[str, str],
        importance: float,
        confidence: float,
        evidence_id: str | None,
        metrics: list[dict[str, Any]] | None = None,
        chart: dict[str, Any] | None = None,
        evidence: dict[str, Any] | None = None,
        details: list[dict[str, str]] | None = None,
        caveats: list[dict[str, str]] | None = None,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        finding = {
            "id": f"f-{len(self.findings) + 1}",
            "agent": agent,
            "kind": kind,
            "title": title,
            "summary": summary,
            "details": details or [],
            "importance": round(max(0.0, min(1.0, importance)), 3),
            "confidence_score": round(confidence, 2),
            "confidence": confidence_label(confidence),
            "metrics": clean(metrics or []),
            "chart": clean(chart) if chart else None,
            "evidence_id": evidence_id,
            "evidence": clean(evidence or {}),
            "caveats": caveats or [],
            "tags": tags or [],
        }
        self.findings.append(finding)
        self.emit(agent, "finding", title, {"finding_id": finding["id"], "kind": kind})
        return finding

    def by_kind(self, kind: str) -> list[dict[str, Any]]:
        return [f for f in self.findings if f["kind"] == kind]


def metric(
    label_en: str, label_ar: str, value: Any, fmt: str = "number", delta: float | None = None
) -> dict[str, Any]:
    return {"label": bi(label_en, label_ar), "value": value, "format": fmt, "delta": delta}
