from __future__ import annotations

import io
import json

import pandas as pd
import pytest
from fastapi.testclient import TestClient

DIRTY_CSV = b"""order_id,order_date,revenue,cost,department,customer_id
0001,2026-06-01,100,60, Sales ,C01
0002,01/06/2026,200,,Support,C02
0002,01/06/2026,200,,Support,C02
0003,2026-06-02,-20,-12,Sales,C01
broken,2026-06-03,50,20,Sales,C03,unexpected
"""


def test_upload_profile_clean_apply_metric_dashboard_report_and_rollback(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    upload = client.post(
        "/api/v1/datasets/upload",
        files={"file": ("dirty-orders.csv", DIRTY_CSV, "text/csv")},
        data={"name": "Dirty orders"},
        headers={**auth_headers, "Idempotency-Key": "upload-dirty-orders"},
    )
    assert upload.status_code == 201, upload.text
    uploaded = upload.json()
    dataset_id = uploaded["dataset"]["id"]
    raw_version_id = uploaded["version"]["id"]
    assert uploaded["coverage"] == {
        "rows_discovered": 5,
        "rows_parsed": 4,
        "rows_accepted": 4,
        "rows_rejected": 1,
        "rows_sampled": 4,
        "rows_analyzed": 4,
    }

    profile = client.get(f"/api/v1/dataset-versions/{raw_version_id}/profile").json()
    assert profile["row_count"] == 4
    assert profile["column_profiles"]["order_id"]["inferred_type"] == "identifier"
    assert "0001" in profile["column_profiles"]["order_id"]["examples"]
    assert profile["quality_issues"]["duplicate_business_keys"]["count"] == 1
    assert profile["quality_issues"]["missing_values"]["count"] == 2
    assert profile["quality_issues"]["legitimate_negative_candidates"]["count"] == 1
    assert profile["quality_issues"]["ambiguous_dates"]["count"] == 2

    recipe = {
        "steps": [
            {"kind": "trim_whitespace", "columns": ["department"]},
            {"kind": "deduplicate", "columns": ["order_id"], "keep": "first"},
        ]
    }
    preview = client.post(
        f"/api/v1/dataset-versions/{raw_version_id}/cleaning/preview",
        json=recipe,
        headers=auth_headers,
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["before"]["row_count"] == 4
    assert preview.json()["after"]["row_count"] == 3
    assert preview.json()["reconciliation"]["revenue_before"] == 480.0
    assert preview.json()["reconciliation"]["revenue_after"] == 280.0
    assert preview.json()["requires_review"] is True

    applied = client.post(
        f"/api/v1/dataset-versions/{raw_version_id}/cleaning/apply",
        json={**recipe, "expected_version": 1, "approved": True},
        headers={**auth_headers, "Idempotency-Key": "apply-cleaning-1"},
    )
    assert applied.status_code == 201, applied.text
    clean_version_id = applied.json()["version"]["id"]
    assert applied.json()["version"]["version_number"] == 2
    assert applied.json()["version"]["row_count"] == 3

    raw_profile_again = client.get(f"/api/v1/dataset-versions/{raw_version_id}/profile").json()
    assert raw_profile_again["row_count"] == 4

    revenue = client.post(
        "/api/v1/metrics/query",
        json={"metric_id": "net_revenue", "dataset_version_id": clean_version_id},
        headers=auth_headers,
    )
    assert revenue.status_code == 200, revenue.text
    result = revenue.json()
    assert result["status"] == "completed"
    assert result["value"] == 280.0
    assert result["unit"] == "JOD"
    assert result["coverage"]["rows_analyzed"] == 3
    assert result["evidence"]["dataset_version_id"] == clean_version_id
    assert result["evidence"]["metric_definition_version"] == 1

    same_query = client.post(
        "/api/v1/metrics/query",
        json={"metric_id": "net_revenue", "dataset_version_id": clean_version_id},
        headers=auth_headers,
    ).json()
    assert same_query["result_id"] == result["result_id"]

    margin = client.post(
        "/api/v1/metrics/query",
        json={"metric_id": "gross_margin", "dataset_version_id": clean_version_id},
        headers=auth_headers,
    ).json()
    assert margin["status"] == "insufficient_data"
    assert margin["value"] is None
    assert "cost" in margin["warnings"][0].lower()

    dashboard = client.post(
        "/api/v1/dashboards",
        json={
            "title": "June operating review",
            "widgets": [{"kind": "metric", "result_id": result["result_id"]}],
        },
        headers=auth_headers,
    )
    assert dashboard.status_code == 201
    assert dashboard.json()["version"] == 1
    assert dashboard.json()["widgets"][0]["result"]["value"] == 280.0

    report = client.post(
        "/api/v1/reports",
        json={
            "title": "June executive report",
            "language": "en",
            "sections": [
                {
                    "kind": "linked_metric",
                    "title": "Net revenue",
                    "result_id": result["result_id"],
                }
            ],
        },
        headers=auth_headers,
    )
    assert report.status_code == 201
    assert report.json()["sections"][0]["result"]["value"] == 280.0

    rollback = client.post(
        f"/api/v1/datasets/{dataset_id}/rollback",
        json={"version_id": raw_version_id},
        headers=auth_headers,
    )
    assert rollback.status_code == 200
    assert rollback.json()["published_version_id"] == raw_version_id
    versions = client.get(f"/api/v1/datasets/{dataset_id}/versions").json()["items"]
    assert [item["version_number"] for item in versions] == [1, 2]


def _format_file(kind: str) -> tuple[str, bytes, str]:
    rows = [{"id": "0007", "value": 12.5}, {"id": "0008", "value": -2.0}]
    if kind == "csv":
        return "sample.csv", b"id,value\n0007,12.5\n0008,-2\n", "text/csv"
    if kind == "tsv":
        return "sample.tsv", b"id\tvalue\n0007\t12.5\n0008\t-2\n", "text/tab-separated-values"
    if kind == "json":
        return "sample.json", json.dumps(rows).encode(), "application/json"
    if kind == "jsonl":
        return (
            "sample.jsonl",
            b"{" + b'"id":"0007","value":12.5}\n{"id":"0008","value":-2}\n',
            "application/x-ndjson",
        )
    frame = pd.DataFrame(rows)
    buffer = io.BytesIO()
    if kind == "xlsx":
        with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
            frame.to_excel(writer, index=False, sheet_name="Orders")
            frame.assign(value=frame["value"] * 2).to_excel(
                writer, index=False, sheet_name="Hidden detail"
            )
    else:
        frame.to_parquet(buffer, index=False)
    media = (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        if kind == "xlsx"
        else "application/vnd.apache.parquet"
    )
    return f"sample.{kind}", buffer.getvalue(), media


@pytest.mark.parametrize("kind", ["csv", "tsv", "json", "jsonl", "xlsx", "parquet"])
def test_supported_upload_formats_preserve_identifier_text(
    kind: str, client: TestClient, auth_headers: dict[str, str]
) -> None:
    filename, content, media = _format_file(kind)
    response = client.post(
        "/api/v1/datasets/upload",
        files={"file": (filename, content, media)},
        headers=auth_headers,
    )

    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["coverage"]["rows_accepted"] >= 2
    profile = client.get(f"/api/v1/dataset-versions/{payload['version']['id']}/profile").json()
    assert profile["column_profiles"]["id"]["inferred_type"] == "identifier"
    assert "0007" in profile["column_profiles"]["id"]["examples"]
    if kind == "xlsx":
        assert payload["extraction"]["sheets"] == ["Orders", "Hidden detail"]


def test_legacy_xls_is_explicitly_unsupported(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    response = client.post(
        "/api/v1/datasets/upload",
        files={"file": ("legacy.xls", b"not-an-xls", "application/vnd.ms-excel")},
        headers=auth_headers,
    )

    assert response.status_code == 415
    assert response.json()["error"]["code"] == "unsupported_format"
    assert "xlsx" in response.json()["error"]["message"].lower()


def test_upload_idempotency_does_not_duplicate_artifacts(
    client: TestClient, auth_headers: dict[str, str]
) -> None:
    headers = {**auth_headers, "Idempotency-Key": "same-upload"}
    first = client.post(
        "/api/v1/datasets/upload",
        files={"file": ("orders.csv", b"id,value\n001,1\n", "text/csv")},
        headers=headers,
    )
    second = client.post(
        "/api/v1/datasets/upload",
        files={"file": ("orders.csv", b"id,value\n001,1\n", "text/csv")},
        headers=headers,
    )

    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["deduplicated"] is True
    assert first.json()["dataset"]["id"] == second.json()["dataset"]["id"]
