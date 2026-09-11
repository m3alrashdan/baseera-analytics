#!/usr/bin/env python3
"""Measure a bounded HTTP smoke profile and emit reproducible JSON.

This is a harness check, not a load test or a product performance claim.  It
issues GET requests only and records the actual denominator, errors, and host.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import math
import os
import platform
import resource
import statistics
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    rank = max(0, math.ceil(fraction * len(ordered)) - 1)
    return round(ordered[rank], 3)


def sample(url: str, timeout: float, expected_status: int) -> dict[str, Any]:
    started = time.perf_counter()
    request = urllib.request.Request(
        url,
        method="GET",
        headers={"Accept": "application/json,text/plain,*/*", "User-Agent": "baseera-perf-smoke/1"},
    )
    status: int | None = None
    size = 0
    error: str | None = None
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = response.status
            size = len(response.read(1024 * 1024 + 1))
            if size > 1024 * 1024:
                error = "response_over_1_mib"
            elif status != expected_status:
                error = "unexpected_status"
    except urllib.error.HTTPError as exc:
        status = exc.code
        error = "http_error"
    except urllib.error.URLError:
        error = "connection_error"
    except TimeoutError:
        error = "timeout"
    return {
        "latencyMs": round((time.perf_counter() - started) * 1000, 3),
        "status": status,
        "bytes": size,
        "error": error,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    parsed = urllib.parse.urlsplit(args.url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("--url must be an absolute HTTP(S) URL")
    if parsed.username or parsed.password:
        raise ValueError("credentials in --url are forbidden")

    started_at = datetime.now(UTC)
    warmups = [sample(args.url, args.timeout, args.expected_status) for _ in range(args.warmup)]
    wall_started = time.perf_counter()
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        futures = [
            executor.submit(sample, args.url, args.timeout, args.expected_status)
            for _ in range(args.requests)
        ]
        samples = [future.result() for future in futures]
    wall_seconds = time.perf_counter() - wall_started
    finished_at = datetime.now(UTC)

    successes = [item for item in samples if item["error"] is None]
    success_latencies = [float(item["latencyMs"]) for item in successes]
    all_latencies = [float(item["latencyMs"]) for item in samples]
    errors = Counter(str(item["error"]) for item in samples if item["error"] is not None)
    statuses = Counter(str(item["status"]) for item in samples)
    max_rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

    return {
        "schemaVersion": "1.0",
        "kind": "http_smoke",
        "label": args.label,
        "startedAt": started_at.isoformat().replace("+00:00", "Z"),
        "finishedAt": finished_at.isoformat().replace("+00:00", "Z"),
        "target": {
            "url": urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", "")),
            "expectedStatus": args.expected_status,
            "method": "GET",
        },
        "profile": {
            "requests": args.requests,
            "concurrency": args.concurrency,
            "warmupRequests": args.warmup,
            "timeoutSeconds": args.timeout,
            "dataset": args.dataset_profile,
            "providerMode": args.provider_mode,
            "cacheState": args.cache_state,
        },
        "environment": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "logicalCpuCount": os.cpu_count(),
            "harnessPeakRssKiB": max_rss,
        },
        "result": {
            "attempted": len(samples),
            "succeeded": len(successes),
            "failed": len(samples) - len(successes),
            "errorRate": round((len(samples) - len(successes)) / len(samples), 6),
            "wallSeconds": round(wall_seconds, 6),
            "throughputRequestsPerSecond": round(len(samples) / wall_seconds, 3),
            "latencyMs": {
                "allP50": percentile(all_latencies, 0.50),
                "allP95": percentile(all_latencies, 0.95),
                "successP50": percentile(success_latencies, 0.50),
                "successP95": percentile(success_latencies, 0.95),
                "successMean": round(statistics.fmean(success_latencies), 3)
                if success_latencies
                else None,
            },
            "statuses": dict(sorted(statuses.items())),
            "errors": dict(sorted(errors.items())),
            "responseBytesTotal": sum(int(item["bytes"]) for item in samples),
        },
        "warmup": {
            "attempted": len(warmups),
            "failed": sum(item["error"] is not None for item in warmups),
        },
        "limitations": [
            "This measures one HTTP endpoint from the client harness host.",
            "Harness peak RSS is not server/container peak memory.",
            (
                "No database row count, queue backlog, browser rendering, or model quality is "
                "inferred."
            ),
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--requests", type=int, default=30)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--warmup", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=5.0)
    parser.add_argument("--expected-status", type=int, default=200)
    parser.add_argument("--label", default="local-health-smoke")
    parser.add_argument("--dataset-profile", default="not_applicable")
    parser.add_argument("--provider-mode", default="disabled")
    parser.add_argument(
        "--cache-state", choices=("cold", "warm", "mixed", "unknown"), default="unknown"
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not 1 <= args.requests <= 10_000:
        parser.error("--requests must be between 1 and 10000")
    if not 1 <= args.concurrency <= min(256, args.requests):
        parser.error("--concurrency must be between 1 and the request count (maximum 256)")
    if not 0 <= args.warmup <= 1_000:
        parser.error("--warmup must be between 0 and 1000")
    if not 0.1 <= args.timeout <= 120:
        parser.error("--timeout must be between 0.1 and 120 seconds")

    try:
        result = run(args)
    except (OSError, ValueError) as exc:
        print(f"performance smoke failed: {exc}", file=sys.stderr)
        return 2
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0 if result["result"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
