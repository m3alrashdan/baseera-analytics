from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ALLOWED_STATUSES = {
    "implemented_tested",
    "implemented_unverified",
    "configuration_blocked",
    "unimplemented",
}
REQUIRED_FIELDS = {"id", "area", "title", "status", "summary", "evidence", "blockers"}


def test_capability_manifest_has_unique_complete_entries() -> None:
    manifest = json.loads((ROOT / "capabilities.json").read_text(encoding="utf-8"))
    capabilities = manifest["capabilities"]
    assert len(capabilities) >= 40
    assert len({item["id"] for item in capabilities}) == len(capabilities)
    for item in capabilities:
        assert item.keys() >= REQUIRED_FIELDS, item.get("id")
        assert item["status"] in ALLOWED_STATUSES
        assert item["summary"]
        assert isinstance(item["evidence"], list)
        assert isinstance(item["blockers"], list)


def test_tested_capabilities_always_link_passing_evidence() -> None:
    manifest = json.loads((ROOT / "capabilities.json").read_text(encoding="utf-8"))
    for item in manifest["capabilities"]:
        if item["status"] == "implemented_tested":
            assert item["evidence"], item["id"]
            assert any(record["status"] == "passed" for record in item["evidence"]), item["id"]


def test_blocked_capabilities_explain_the_external_gate() -> None:
    manifest = json.loads((ROOT / "capabilities.json").read_text(encoding="utf-8"))
    for item in manifest["capabilities"]:
        if item["status"] == "configuration_blocked":
            assert item["blockers"], item["id"]
