from __future__ import annotations

import csv
import io
from pathlib import Path

import openpyxl
import pytest
from baseera.connectors import validate_connector_destination, validate_resolved_addresses
from baseera.errors import AppError
from baseera.ingestion import ArtifactStore
from baseera.reports import render_report_export
from fastapi.testclient import TestClient

from .conftest import login

DANGEROUS_SPREADSHEET_PREFIXES = ("=", "+", "-", "@", "\t", "\r")


def _malicious_report() -> dict[str, object]:
    return {
        "id": "report-security",
        "title": "Security export",
        "language": "en",
        "version": 1,
        "sections": [
            {
                "kind": "narrative",
                "title": '=HYPERLINK("https://attacker.invalid","Open")',
                "content": '<img src=x onerror="alert(1)">',
            }
        ],
    }


def test_csv_export_neutralizes_formula_cells() -> None:
    rendered = render_report_export(_malicious_report(), "csv").decode("utf-8-sig")
    rows = list(csv.reader(io.StringIO(rendered)))

    assert rows[1][0]
    assert not rows[1][0].startswith(DANGEROUS_SPREADSHEET_PREFIXES)


def test_xlsx_export_writes_untrusted_values_as_strings_not_formulas() -> None:
    rendered = render_report_export(_malicious_report(), "xlsx")
    workbook = openpyxl.load_workbook(io.BytesIO(rendered), data_only=False, read_only=True)
    try:
        section_title = workbook["Report data"]["A4"]
        assert section_title.data_type != "f"
        assert str(section_title.value).startswith("'")
    finally:
        workbook.close()


def test_html_export_escapes_untrusted_narrative_and_title() -> None:
    rendered = render_report_export(_malicious_report(), "html").decode("utf-8")

    assert "<img src=x" not in rendered
    assert "&lt;img src=x" in rendered
    assert "<script" not in rendered.lower()


def test_artifact_store_rejects_parent_and_symlink_escape(tmp_path: Path) -> None:
    root = tmp_path / "artifacts"
    outside = tmp_path / "outside"
    outside.mkdir()
    root.mkdir()
    (root / "link").symlink_to(outside, target_is_directory=True)
    store = ArtifactStore(root)

    with pytest.raises(ValueError, match="escapes artifact root"):
        store.write_bytes("../outside.txt", b"blocked")
    with pytest.raises(ValueError, match="escapes artifact root"):
        store.write_bytes("link/outside.txt", b"blocked")
    assert not (outside / "outside.txt").exists()


@pytest.mark.parametrize(
    "url",
    [
        "http://erp.example.test/api",
        "https://erp.example.test.attacker.invalid/api",
        "https://erp.example.test@169.254.169.254/latest/meta-data",
        "https://127.0.0.1/",
        "file:///etc/passwd",
    ],
)
def test_connector_destination_rejects_ssrf_shapes(url: str) -> None:
    with pytest.raises(AppError) as caught:
        validate_connector_destination(url, ("erp.example.test",))
    assert caught.value.code == "connector_destination_denied"


def test_connector_resolution_rejects_private_and_metadata_addresses() -> None:
    for address in ("127.0.0.1", "10.0.0.4", "169.254.169.254", "::1"):
        with pytest.raises(AppError) as caught:
            validate_resolved_addresses([address])
        assert caught.value.code == "connector_destination_denied"


def test_upload_rejects_an_executable_media_type_even_with_csv_suffix(
    security_client: TestClient,
) -> None:
    headers = login(security_client)

    response = security_client.post(
        "/api/v1/datasets/upload",
        files={
            "file": (
                "misleading.csv",
                b"id,revenue\n1,10\n",
                "application/x-msdownload",
            )
        },
        headers=headers,
    )

    assert response.status_code == 415
    assert response.json()["error"]["code"] == "unsupported_media_type"


def test_request_schema_rejects_unknown_fields_without_echoing_values(
    security_client: TestClient,
) -> None:
    secret_marker = "do-not-reflect-this-secret"
    response = security_client.post(
        "/api/v1/auth/login",
        json={
            "email": "executive@demo.baseera.local",
            "password": "wrong",
            "unexpected": secret_marker,
        },
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_failed"
    assert secret_marker not in response.text
