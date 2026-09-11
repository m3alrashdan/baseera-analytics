#!/usr/bin/env python3
"""Parse and cross-check BASEERA JSON manifests and schema references.

The script is dependency-free.  It checks repository-specific invariants in
addition to JSON syntax; it is not a general JSON Schema implementation.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CAPABILITY_STATUSES = {
    "implemented_tested",
    "implemented_unverified",
    "configuration_blocked",
    "unimplemented",
}
EVIDENCE_STATUSES = {"passed", "failed", "not_run", "blocked"}
ID_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]*$")


def parse_json(path: Path, errors: list[str]) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{path.relative_to(ROOT)}: {exc}")
        return None


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def validate_schema_link(path: Path, document: Any, errors: list[str]) -> None:
    if not isinstance(document, dict):
        return
    schema_ref = document.get("$schema")
    if not isinstance(schema_ref, str) or not schema_ref.startswith("."):
        return
    schema_path = (path.parent / schema_ref.split("#", 1)[0]).resolve()
    require(schema_path.is_file(), f"{path.relative_to(ROOT)}: missing schema {schema_ref}", errors)
    try:
        schema_path.relative_to(ROOT.resolve())
    except ValueError:
        errors.append(f"{path.relative_to(ROOT)}: schema escapes repository: {schema_ref}")


def validate_capabilities(document: Any, errors: list[str]) -> None:
    path = "capabilities.json"
    require(isinstance(document, dict), f"{path}: root must be an object", errors)
    if not isinstance(document, dict):
        return
    require(
        set(document.get("statuses", [])) == CAPABILITY_STATUSES,
        f"{path}: statuses mismatch",
        errors,
    )
    capabilities = document.get("capabilities")
    require(isinstance(capabilities, list), f"{path}: capabilities must be a list", errors)
    if not isinstance(capabilities, list):
        return
    ids: set[str] = set()
    for index, capability in enumerate(capabilities):
        label = f"{path}:capabilities[{index}]"
        if not isinstance(capability, dict):
            errors.append(f"{label}: must be an object")
            continue
        capability_id = capability.get("id")
        require(
            isinstance(capability_id, str) and bool(ID_PATTERN.fullmatch(capability_id)),
            f"{label}: invalid id",
            errors,
        )
        require(capability_id not in ids, f"{label}: duplicate id {capability_id!r}", errors)
        if isinstance(capability_id, str):
            ids.add(capability_id)
        status = capability.get("status")
        require(status in CAPABILITY_STATUSES, f"{label}: invalid status {status!r}", errors)
        evidence = capability.get("evidence")
        blockers = capability.get("blockers")
        require(isinstance(evidence, list), f"{label}: evidence must be a list", errors)
        require(isinstance(blockers, list), f"{label}: blockers must be a list", errors)
        if status == "implemented_tested":
            passed = isinstance(evidence, list) and any(
                isinstance(item, dict) and item.get("status") == "passed" for item in evidence
            )
            require(passed, f"{label}: implemented_tested needs passed evidence", errors)
        if status == "configuration_blocked":
            require(bool(blockers), f"{label}: configuration_blocked needs a blocker", errors)
        if isinstance(evidence, list):
            for evidence_index, item in enumerate(evidence):
                require(
                    isinstance(item, dict) and item.get("status") in EVIDENCE_STATUSES,
                    f"{label}:evidence[{evidence_index}] has invalid status",
                    errors,
                )


def validate_evidence_index(document: Any, errors: list[str]) -> None:
    path = "docs/evidence/index.json"
    require(isinstance(document, dict), f"{path}: root must be an object", errors)
    if not isinstance(document, dict):
        return
    require(
        set(document.get("statuses", [])) == EVIDENCE_STATUSES, f"{path}: statuses mismatch", errors
    )
    entries = document.get("entries")
    require(isinstance(entries, list), f"{path}: entries must be a list", errors)
    if not isinstance(entries, list):
        return
    ids: set[str] = set()
    for index, entry in enumerate(entries):
        label = f"{path}:entries[{index}]"
        if not isinstance(entry, dict):
            errors.append(f"{label}: must be an object")
            continue
        entry_id = entry.get("id")
        require(
            isinstance(entry_id, str) and bool(ID_PATTERN.fullmatch(entry_id)),
            f"{label}: invalid id",
            errors,
        )
        require(entry_id not in ids, f"{label}: duplicate id {entry_id!r}", errors)
        if isinstance(entry_id, str):
            ids.add(entry_id)
        status = entry.get("status")
        require(status in EVIDENCE_STATUSES, f"{label}: invalid status", errors)
        require(bool(entry.get("command")), f"{label}: command is required", errors)
        require(
            isinstance(entry.get("artifactPaths"), list),
            f"{label}: artifactPaths must be a list",
            errors,
        )
        if status in {"passed", "failed"}:
            require(
                bool(entry.get("executedAt")), f"{label}: executed status needs executedAt", errors
            )
        if status == "passed":
            require(
                bool(entry.get("artifactPaths")),
                f"{label}: passed status needs retained artifacts",
                errors,
            )
        if status == "blocked":
            require(
                "blocked" in str(entry.get("notes", "")).casefold(),
                f"{label}: name blocker",
                errors,
            )


def main() -> int:
    json_paths = [ROOT / "capabilities.json"]
    for relative in ("docs", "packages/contracts", "tests/evaluation"):
        directory = ROOT / relative
        if directory.exists():
            json_paths.extend(sorted(directory.rglob("*.json")))
    json_paths = list(dict.fromkeys(json_paths))

    errors: list[str] = []
    parsed: dict[Path, Any] = {}
    for path in json_paths:
        document = parse_json(path, errors)
        if document is not None:
            parsed[path] = document
            validate_schema_link(path, document, errors)

    capabilities_path = ROOT / "capabilities.json"
    evidence_path = ROOT / "docs/evidence/index.json"
    validate_capabilities(parsed.get(capabilities_path), errors)
    validate_evidence_index(parsed.get(evidence_path), errors)

    for schema_path in [path for path in parsed if path.name.endswith("schema.json")]:
        schema = parsed[schema_path]
        require(
            isinstance(schema, dict),
            f"{schema_path.relative_to(ROOT)}: schema must be object",
            errors,
        )
        if isinstance(schema, dict):
            require(
                schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema",
                f"{schema_path.relative_to(ROOT)}: use JSON Schema draft 2020-12",
                errors,
            )

    jsonl_records = 0
    for path in sorted((ROOT / "tests/evaluation").glob("*.jsonl")):
        for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if not raw.strip():
                continue
            try:
                value = json.loads(raw)
            except json.JSONDecodeError as exc:
                errors.append(f"{path.relative_to(ROOT)}:{number}: {exc}")
                continue
            require(
                isinstance(value, dict),
                f"{path.relative_to(ROOT)}:{number}: must be object",
                errors,
            )
            jsonl_records += 1

    if errors:
        print(f"JSON contract validation failed ({len(errors)} errors):", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "status": "valid",
                "jsonDocuments": len(parsed),
                "jsonlRecords": jsonl_records,
                "note": (
                    "Repository invariants and syntax validated; runtime behavior was not "
                    "exercised."
                ),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
