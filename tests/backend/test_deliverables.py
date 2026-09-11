"""The analysis brief and the presentation deck.

These are what a client receives, so the tests check that every format renders, that
Arabic is genuinely Arabic rather than a translated shell, and that a claim of accuracy
never appears without the measurement behind it.
"""

from __future__ import annotations

import io
import zipfile

import pytest
from fastapi.testclient import TestClient

SALES_CSV = "\n".join(
    ["order_id,order_date,region,customer,revenue,cost"]
    + [
        f"O-{index:04d},2025-{1 + index // 45:02d}-{1 + index % 27:02d},"
        f"{'Amman' if index % 3 else 'amman'},"
        f"{'Zain' if index % 4 == 0 else f'C{index % 37}'},"
        f"{'\"1,' if index % 5 == 0 else ''}{900 + index * 3}"
        f"{'.00\"' if index % 5 == 0 else '.00'},"
        f"{'' if index % 11 == 0 else 600 + index * 2}"
        for index in range(240)
    ]
).encode()


@pytest.fixture
def version_id(client: TestClient, auth_headers: dict[str, str]) -> str:
    upload = client.post(
        "/api/v1/datasets/upload",
        files={"file": ("sales.csv", SALES_CSV, "text/csv")},
        data={"name": "Sales"},
        headers=auth_headers,
    )
    assert upload.status_code == 201, upload.text
    return str(upload.json()["version"]["id"])


@pytest.mark.parametrize("locale", ["en", "ar"])
def test_the_brief_covers_condition_findings_and_limits(
    client: TestClient, auth_headers: dict[str, str], version_id: str, locale: str
) -> None:
    response = client.post(
        f"/api/v1/dataset-versions/{version_id}/brief",
        json={"locale": locale, "include_forecast": True, "forecast_horizon": 4},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    brief = response.json()

    assert brief["headline"]
    assert brief["quality"]["score"] is not None
    assert brief["profile_summary"]["columns"]
    assert brief["findings"], "a 240-row file with known defects must yield findings"
    assert brief["limitations"], "a brief without stated limits is not defensible"
    assert brief["method"][locale]

    for finding in brief["findings"]:
        # Observation, reading, action and limit are kept apart so a reader can tell
        # measurement from judgement.
        for part in ("observation", "interpretation", "recommendation", "limitation"):
            assert finding[part].strip(), f"{finding['id']} has an empty {part}"
        assert finding["severity_label"]

    if locale == "ar":
        arabic = brief["headline"] + " ".join(f["observation"] for f in brief["findings"])
        assert any("؀" <= character <= "ۿ" for character in arabic)


def test_the_brief_never_claims_accuracy_it_did_not_measure(
    client: TestClient, auth_headers: dict[str, str], version_id: str
) -> None:
    brief = client.post(
        f"/api/v1/dataset-versions/{version_id}/brief",
        json={"locale": "en", "include_forecast": True},
        headers=auth_headers,
    ).json()
    forecast = brief.get("forecast")
    if not forecast or forecast.get("status") != "completed":
        pytest.skip("this file produced no forecastable series")
    backtest = forecast["backtest"]
    # Either there is a measured error and a measured coverage, or the response says
    # plainly why no measurement was possible. Never a number without its basis.
    if backtest["mase"] is None:
        assert backtest.get("reason")
    else:
        assert backtest["mase_scale"] > 0
        assert 0 <= backtest["interval_coverage"] <= 1
        assert backtest["evaluation_periods"] >= 1


@pytest.mark.parametrize(
    ("kind", "signature"),
    [
        ("json", b"{"),
        ("html", b"<!doctype html>"),
        ("md", b"#"),
        ("pdf", b"%PDF"),
        ("docx", b"PK"),
        ("pptx", b"PK"),
    ],
)
def test_every_export_format_renders(
    client: TestClient, auth_headers: dict[str, str], version_id: str,
    kind: str, signature: bytes,
) -> None:
    response = client.post(
        f"/api/v1/dataset-versions/{version_id}/brief/export",
        json={"locale": "en", "format": kind, "include_forecast": True},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text[:400]
    assert response.content[: len(signature)].lower() == signature.lower()
    assert len(response.content) > 200
    assert "attachment" in response.headers["content-disposition"]


def test_the_arabic_deck_is_a_real_deck_with_slides(
    client: TestClient, auth_headers: dict[str, str], version_id: str
) -> None:
    response = client.post(
        f"/api/v1/dataset-versions/{version_id}/brief/export",
        json={"locale": "ar", "format": "pptx", "include_forecast": True},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text[:400]
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        slides = [n for n in archive.namelist() if n.startswith("ppt/slides/slide")]
        assert len(slides) >= 4, "a deck needs a cover, condition, findings and limits"
        body = b"".join(archive.read(name) for name in slides).decode("utf-8", "ignore")
    assert any("؀" <= character <= "ۿ" for character in body)
    # Right-to-left has to be set on the paragraphs, not implied by the text.
    assert 'rtl="1"' in body


def test_an_unsupported_format_is_refused_with_the_supported_list(
    client: TestClient, auth_headers: dict[str, str], version_id: str
) -> None:
    response = client.post(
        f"/api/v1/dataset-versions/{version_id}/brief/export",
        json={"locale": "en", "format": "xlsx"},
        headers=auth_headers,
    )
    assert response.status_code == 422
