#!/usr/bin/env python3
"""Exercise the local fictional demo with real Ollama, without provider API keys.

Creates two persisted demo conversations. Never target an external or production workspace.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

import httpx


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8100")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    target = urlsplit(args.url)
    if (
        target.hostname not in {"127.0.0.1", "localhost", "::1"}
        or target.scheme != "http"
        or target.username
        or target.password
        or target.query
        or target.fragment
        or target.path not in {"", "/"}
    ):
        parser.error("Only a local HTTP demo origin is allowed")
    started = datetime.now(UTC).isoformat()
    with httpx.Client(base_url=args.url, timeout=190, trust_env=False) as client:
        login = client.post(
            "/api/v1/auth/login",
            json={"email": "executive@demo.baseera.local", "password": "BaseeraDemo!2026"},
        )
        login.raise_for_status()
        client.headers["X-CSRF-Token"] = login.json()["csrf_token"]
        context = client.get("/api/v1/auth/context")
        context.raise_for_status()
        tenant = context.json()["tenant"]
        if tenant.get("id") != "tenant-demo" or tenant.get("is_demo") is not True:
            raise RuntimeError("Refusing to execute outside the fictional demo workspace")
        availability = client.get("/api/v1/assistant/status")
        availability.raise_for_status()
        availability_data = availability.json()
        assert availability_data["status"] == "available", "Ollama model is unavailable"
        overview = client.get("/api/v1/overview")
        overview.raise_for_status()
        expected = overview.json()["metrics"]["net_revenue"]["value"]
        assert expected is not None, "The fictional seed is required"
        results = []
        for locale, question in [
            ("ar", "اعرض صافي الإيرادات لكل التاريخ المتاح"),
            ("en", "Show net revenue for all available history"),
        ]:
            clock = time.perf_counter()
            response = client.post(
                "/api/v1/assistant/query", json={"question": question, "locale": locale}
            )
            response.raise_for_status()
            body = response.json()
            assert body["status"] == "completed", "Model did not complete a valid plan"
            assert body["provider"].get("live_verified") is True, "Live inference is required"
            assert body["provider"].get("mode") == "ollama", "Ollama must execute the request"
            assert body["plan"]["period"] == "all_history", "Unexpected reporting period"
            assert len(body["results"]) == 1
            result = body["results"][0]
            assert result["metric_id"] == "net_revenue"
            assert result["value"] == expected, "Assistant and overview disagree"
            results.append(
                {
                    "locale": locale,
                    "question": question,
                    "status": body["status"],
                    "provider": body["provider"],
                    "plan": body["plan"],
                    "result": result,
                    "elapsed_seconds": round(time.perf_counter() - clock, 3),
                }
            )
        client.post("/api/v1/auth/logout")
    evidence = {
        "kind": "local_ollama_bilingual_smoke",
        "startedAt": started,
        "finishedAt": datetime.now(UTC).isoformat(),
        "status": "passed",
        "availability": availability_data,
        "expected_overview_net_revenue": expected,
        "runs": results,
        "limitations": [
            "Two real queries on a fictional local seed, not a held-out accuracy benchmark.",
            "Question/history are sent to local Ollama; numerical facts are calculated in Python.",
            "No throughput, general Arabic accuracy, or production readiness is inferred.",
        ],
    }
    rendered = json.dumps(evidence, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
