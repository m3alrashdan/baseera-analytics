#!/usr/bin/env python3
"""Validate BASEERA's visible and held-out bilingual evaluation contracts.

This validator intentionally uses only the Python standard library so it can run
before application dependencies are installed.  It validates structure and
coverage; it does not execute an assistant or claim model quality.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DEVELOPMENT = ROOT / "tests/evaluation/development_cases.v1.json"
DEFAULT_HELD_OUT = ROOT / "tests/evaluation/held_out_cases.v1.jsonl"
DEFAULT_MANIFEST = ROOT / "tests/evaluation/held_out_manifest.v1.json"

TOPICS = {
    "sales",
    "people",
    "projects",
    "operations",
    "budgets",
    "sources",
    "ambiguity",
    "insufficient_data",
    "forecasts",
    "authorization",
    "cross_module",
    "follow_up",
}
LOCALES = {"en", "ar"}
OUTCOMES = {"answer", "clarify", "abstain_insufficient_data", "deny", "unavailable"}
CLAIM_TYPES = {"fact", "forecast", "recommendation", "mixed", "none"}
ROLES = {
    "administrator",
    "executive",
    "analyst",
    "department_manager",
    "hr_specialist",
    "viewer",
}
TOOLS = {
    "metric_query",
    "entity_query",
    "catalog",
    "forecast",
    "process",
    "optimization",
    "conversation_context",
}
CASE_ID = re.compile(r"^(DEV|HO)-(EN|AR)-[A-Z]+-[0-9]{3}$")
ARABIC = re.compile(r"[\u0600-\u06ff]")
LATIN = re.compile(r"[A-Za-z]")


class ValidationFailure(Exception):
    """Raised after collecting contract errors."""


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValidationFailure(f"missing file: {path.relative_to(ROOT)}") from exc
    except json.JSONDecodeError as exc:
        raise ValidationFailure(f"invalid JSON in {path.relative_to(ROOT)}: {exc}") from exc


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError as exc:
        raise ValidationFailure(f"missing file: {path.relative_to(ROOT)}") from exc

    records: list[dict[str, Any]] = []
    for number, raw in enumerate(lines, 1):
        if not raw.strip():
            continue
        try:
            value = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValidationFailure(
                f"invalid JSONL at {path.relative_to(ROOT)}:{number}: {exc}"
            ) from exc
        if not isinstance(value, dict):
            raise ValidationFailure(
                f"JSONL record at {path.relative_to(ROOT)}:{number} must be an object"
            )
        records.append(value)
    return records


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def validate_case(case: dict[str, Any], prefix: str, errors: list[str]) -> None:
    required = {"id", "locale", "topic", "prompt", "actor", "expected"}
    allowed = required | {"conversationContext"}
    case_id = str(case.get("id", prefix))
    missing = sorted(required - case.keys())
    unknown = sorted(case.keys() - allowed)
    require(not missing, f"{prefix}: missing fields {missing}", errors)
    require(not unknown, f"{prefix}: unknown fields {unknown}", errors)
    require(bool(CASE_ID.fullmatch(case_id)), f"{prefix}: invalid id {case_id!r}", errors)

    locale = case.get("locale")
    topic = case.get("topic")
    prompt = case.get("prompt")
    require(locale in LOCALES, f"{case_id}: unsupported locale {locale!r}", errors)
    require(topic in TOPICS, f"{case_id}: unsupported topic {topic!r}", errors)
    require(
        isinstance(prompt, str) and len(prompt.strip()) >= 8, f"{case_id}: short prompt", errors
    )
    if isinstance(prompt, str) and locale == "ar":
        require(
            bool(ARABIC.search(prompt)), f"{case_id}: Arabic prompt has no Arabic letters", errors
        )
    if isinstance(prompt, str) and locale == "en":
        require(
            bool(LATIN.search(prompt)), f"{case_id}: English prompt has no Latin letters", errors
        )

    actor = case.get("actor")
    require(isinstance(actor, dict), f"{case_id}: actor must be an object", errors)
    if isinstance(actor, dict):
        require(actor.get("role") in ROLES, f"{case_id}: invalid actor role", errors)
        require(bool(actor.get("tenantId")), f"{case_id}: actor tenantId is required", errors)

    expected = case.get("expected")
    require(isinstance(expected, dict), f"{case_id}: expected must be an object", errors)
    if not isinstance(expected, dict):
        return
    expected_required = {
        "outcome",
        "claimType",
        "toolFamilies",
        "evidenceReferences",
        "oracleKey",
        "requiredSignals",
    }
    require(
        not (expected_required - expected.keys()),
        f"{case_id}: expected is missing {sorted(expected_required - expected.keys())}",
        errors,
    )
    require(expected.get("outcome") in OUTCOMES, f"{case_id}: invalid outcome", errors)
    require(expected.get("claimType") in CLAIM_TYPES, f"{case_id}: invalid claimType", errors)
    tool_families = expected.get("toolFamilies")
    require(isinstance(tool_families, list), f"{case_id}: toolFamilies must be a list", errors)
    if isinstance(tool_families, list):
        invalid_tools = sorted(set(tool_families) - TOOLS)
        require(not invalid_tools, f"{case_id}: invalid tool families {invalid_tools}", errors)
    for field in ("evidenceReferences", "requiredSignals"):
        value = expected.get(field)
        require(
            isinstance(value, list) and all(isinstance(item, str) and item for item in value),
            f"{case_id}: {field} must contain non-empty strings",
            errors,
        )
    require(bool(expected.get("oracleKey")), f"{case_id}: oracleKey is required", errors)

    outcome = expected.get("outcome")
    if outcome == "clarify":
        require(
            bool(expected.get("clarificationFields")),
            f"{case_id}: clarificationFields required for clarify",
            errors,
        )
    if outcome == "deny":
        require(
            expected.get("claimType") == "none", f"{case_id}: denied claimType must be none", errors
        )
        require(
            not tool_families, f"{case_id}: denied case must execute no business-data tool", errors
        )
        require(
            bool(expected.get("prohibitedExposures")),
            f"{case_id}: denied case needs prohibitedExposures",
            errors,
        )
    if topic == "follow_up":
        context = case.get("conversationContext")
        require(
            isinstance(context, dict), f"{case_id}: follow_up needs conversationContext", errors
        )
        if isinstance(context, dict):
            require(bool(context.get("priorUser")), f"{case_id}: priorUser is required", errors)
            require(
                bool(context.get("priorAssistantResultId")),
                f"{case_id}: priorAssistantResultId is required",
                errors,
            )
        require(
            isinstance(tool_families, list) and "conversation_context" in tool_families,
            f"{case_id}: follow_up needs conversation_context tool family",
            errors,
        )


def validate() -> dict[str, Any]:
    development = load_json(DEFAULT_DEVELOPMENT)
    manifest = load_json(DEFAULT_MANIFEST)
    held_out = load_jsonl(DEFAULT_HELD_OUT)
    errors: list[str] = []

    require(isinstance(development, dict), "development suite must be an object", errors)
    development_cases = development.get("cases", []) if isinstance(development, dict) else []
    require(
        development.get("split") == "development", "development split must be development", errors
    )
    require(isinstance(development_cases, list), "development cases must be a list", errors)

    require(isinstance(manifest, dict), "held-out manifest must be an object", errors)
    require(manifest.get("split") == "held_out", "held-out manifest split must be held_out", errors)
    require(
        manifest.get("dataFile") == DEFAULT_HELD_OUT.name,
        "held-out manifest dataFile does not match validator input",
        errors,
    )
    require(
        manifest.get("recordSchema") == "./ai-case.schema.json#/$defs/case",
        "held-out manifest recordSchema must identify the case definition",
        errors,
    )
    require(
        manifest.get("expectedCaseCount") == len(held_out),
        "held-out manifest expectedCaseCount does not match JSONL records",
        errors,
    )
    fixture = manifest.get("fixture")
    require(isinstance(fixture, dict), "held-out manifest fixture must be an object", errors)
    if isinstance(fixture, dict):
        require(
            fixture.get("tenantId") == "tenant-demo", "fixture tenant must be tenant-demo", errors
        )
        require(fixture.get("reportingCutoff") == "2026-06-30", "unexpected cutoff", errors)
        require(fixture.get("timezone") == "Asia/Amman", "unexpected fixture timezone", errors)
        require(fixture.get("currency") == "JOD", "unexpected fixture currency", errors)

    for index, case in enumerate(development_cases, 1):
        if isinstance(case, dict):
            validate_case(case, f"development[{index}]", errors)
        else:
            errors.append(f"development[{index}] must be an object")
    for index, case in enumerate(held_out, 1):
        validate_case(case, f"held_out:{index}", errors)

    require(
        len(held_out) >= 60, f"held-out set has {len(held_out)} cases; need at least 60", errors
    )
    all_cases = [*development_cases, *held_out]
    ids = [case.get("id") for case in all_cases if isinstance(case, dict)]
    prompts = [
        " ".join(str(case.get("prompt", "")).casefold().split())
        for case in all_cases
        if isinstance(case, dict)
    ]
    duplicate_ids = sorted(key for key, count in Counter(ids).items() if count > 1)
    duplicate_prompts = sorted(key for key, count in Counter(prompts).items() if count > 1)
    require(not duplicate_ids, f"duplicate case IDs: {duplicate_ids}", errors)
    require(not duplicate_prompts, f"duplicate prompts: {duplicate_prompts}", errors)

    held_locale = Counter(case.get("locale") for case in held_out)
    held_topic_locale = Counter((case.get("topic"), case.get("locale")) for case in held_out)
    held_outcomes = Counter(case.get("expected", {}).get("outcome") for case in held_out)
    require(
        held_locale["en"] == held_locale["ar"], f"locale imbalance: {dict(held_locale)}", errors
    )
    for topic in sorted(TOPICS):
        for locale in sorted(LOCALES):
            require(
                held_topic_locale[(topic, locale)] >= 2,
                f"coverage needs >=2 cases for topic={topic}, locale={locale}",
                errors,
            )
    for outcome in sorted(OUTCOMES):
        require(held_outcomes[outcome] >= 1, f"held-out set lacks outcome={outcome}", errors)

    development_prompts = set(prompts[: len(development_cases)])
    held_prompts = set(prompts[len(development_cases) :])
    require(
        not (development_prompts & held_prompts),
        "held-out prompts overlap visible development prompts",
        errors,
    )

    if errors:
        rendered = "\n".join(f"- {error}" for error in errors)
        raise ValidationFailure(
            f"AI evaluation contract failed ({len(errors)} errors):\n{rendered}"
        )

    return {
        "status": "valid",
        "structuralOnly": True,
        "developmentCases": len(development_cases),
        "heldOutCases": len(held_out),
        "heldOutByLocale": dict(sorted(held_locale.items())),
        "heldOutByOutcome": dict(sorted(held_outcomes.items())),
        "topicsPerLocaleMinimum": min(held_topic_locale.values()),
        "note": "No assistant/model was executed; this is not a quality score.",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit compact machine-readable output")
    args = parser.parse_args()
    try:
        result = validate()
    except ValidationFailure as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=None if args.json else 2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
