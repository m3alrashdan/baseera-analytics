#!/usr/bin/env python3
"""Summarize a BASEERA evaluation-result JSONL without hiding failures."""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter
from pathlib import Path
from typing import Any

BUCKETS = {
    "verified_automatic_completion",
    "completed_with_human_correction",
    "correct_abstention",
    "incorrect_abstention",
    "failed",
    "timed_out",
}
BOOLEAN_METRICS = (
    "numericCorrect",
    "evidenceSupported",
    "toolExecutionSucceeded",
    "clarificationCorrect",
    "unsupportedClaim",
    "accessPolicyCompliant",
)


def percentile(values: list[float], fraction: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    rank = max(0, math.ceil(fraction * len(ordered)) - 1)
    return ordered[rank]


def ratio(numerator: int, denominator: int) -> float | None:
    return round(numerator / denominator, 6) if denominator else None


def read_results(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        try:
            record = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"line {line_number}: invalid JSON: {exc}") from exc
        if not isinstance(record, dict):
            raise ValueError(f"line {line_number}: result must be an object")
        required = {"caseId", "attempt", "bucket", "providerMode"}
        missing = required - record.keys()
        if missing:
            raise ValueError(f"line {line_number}: missing {sorted(missing)}")
        if record["bucket"] not in BUCKETS:
            raise ValueError(f"line {line_number}: invalid bucket {record['bucket']!r}")
        if not isinstance(record["attempt"], int) or record["attempt"] < 1:
            raise ValueError(f"line {line_number}: attempt must be a positive integer")
        identity = (str(record["caseId"]), record["attempt"])
        if identity in seen:
            raise ValueError(f"line {line_number}: duplicate case/attempt {identity}")
        seen.add(identity)
        records.append(record)
    if not records:
        raise ValueError("result file contains no records")
    return records


def summarize(records: list[dict[str, Any]]) -> dict[str, Any]:
    buckets = Counter(record["bucket"] for record in records)
    attempted = len(records)
    verified = buckets["verified_automatic_completion"]
    correct_abstention = buckets["correct_abstention"]
    metrics: dict[str, Any] = {}
    for metric in BOOLEAN_METRICS:
        applicable = [record[metric] for record in records if isinstance(record.get(metric), bool)]
        expected_value = metric != "unsupportedClaim"
        positive = sum(value is expected_value for value in applicable)
        metrics[metric] = {
            "applicable": len(applicable),
            "meetingExpectation": positive,
            "rate": ratio(positive, len(applicable)),
        }

    latency = [
        float(record["latencyMs"]) for record in records if record.get("latencyMs") is not None
    ]
    tool_counts = [
        int(record["toolCount"]) for record in records if record.get("toolCount") is not None
    ]
    token_counts = [
        int(record["tokenCount"]) for record in records if record.get("tokenCount") is not None
    ]
    costs = [float(record["costUsd"]) for record in records if record.get("costUsd") is not None]
    modes = Counter(str(record["providerMode"]) for record in records)

    return {
        "attempted": attempted,
        "buckets": {bucket: buckets[bucket] for bucket in sorted(BUCKETS)},
        "verifiedAccuracy": ratio(verified + correct_abstention, attempted),
        "verifiedAutomation": ratio(verified, attempted),
        "providerModes": dict(sorted(modes.items())),
        "quality": metrics,
        "latencyMs": {
            "captured": len(latency),
            "p50": percentile(latency, 0.50),
            "p95": percentile(latency, 0.95),
        },
        "usage": {
            "toolCountCaptured": len(tool_counts),
            "toolCountTotal": sum(tool_counts),
            "tokenCountCaptured": len(token_counts),
            "tokenCountTotal": sum(token_counts),
            "costCaptured": len(costs),
            "costUsdTotal": round(math.fsum(costs), 6),
        },
        "warning": (
            "These figures summarize supplied records only. Provider doubles do not verify live "
            "model behavior, and missing optional observations are shown by captured counts."
        ),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("results", type=Path, help="evaluation-result JSONL")
    parser.add_argument("--output", type=Path, help="optional JSON output path")
    args = parser.parse_args()
    try:
        summary = summarize(read_results(args.results))
    except (OSError, ValueError) as exc:
        print(f"evaluation summary failed: {exc}", file=sys.stderr)
        return 1
    rendered = json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
