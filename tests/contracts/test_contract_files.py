from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTRACT_DIR = ROOT / "packages" / "contracts" / "schemas"


def load_contract(name: str) -> dict:
    return json.loads((CONTRACT_DIR / f"{name}.schema.json").read_text(encoding="utf-8"))


def test_required_evidence_contracts_exist_and_are_objects() -> None:
    for name in ("analysis-request", "result", "finding", "recommendation", "change-proposal"):
        contract = load_contract(name)
        assert contract["$schema"] == "https://json-schema.org/draft/2020-12/schema"
        assert contract["type"] == "object"
        assert contract["additionalProperties"] is False
        assert contract["required"]


def test_result_contract_requires_scope_provenance_and_warnings() -> None:
    contract = load_contract("result")
    assert {
        "resultId",
        "runId",
        "status",
        "coverage",
        "schema",
        "data",
        "unit",
        "provenance",
        "warnings",
    } <= set(contract["required"])


def test_finding_cannot_hide_its_classification_or_evidence() -> None:
    contract = load_contract("finding")
    classification = contract["properties"]["classification"]
    assert classification["enum"] == ["fact", "forecast", "hypothesis", "recommendation"]
    assert {"claim", "evidenceIds", "classification", "assumptions", "limitations"} <= set(
        contract["required"]
    )


def test_change_proposal_uses_optimistic_versioning_and_typed_operations() -> None:
    contract = load_contract("change-proposal")
    assert "expectedVersion" in contract["required"]
    operations = contract["properties"]["operations"]
    assert operations["type"] == "array"
    assert operations["items"]["$ref"] == "#/$defs/operation"
