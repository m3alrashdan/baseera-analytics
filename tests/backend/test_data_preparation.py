"""Cleaning, profiling and analyst-finding behaviour.

Each test here pins a defect that shipped once: a control total that hid unreadable
cells, a replacement value that broke a column's type, an error that named neither the
offending column nor the valid ones.
"""

from __future__ import annotations

from typing import Any

import pytest
from baseera.cleaning import control_totals, run_recipe
from baseera.insights import analyze_dataset
from baseera.forecasting import detect_level_shift
from baseera.profiling import coerce_number, profile_dataset
from fastapi.testclient import TestClient

# Thousands separators, case drift, a duplicate row, a blank and an unreadable cell.
MESSY_CSV = b"""order_id,order_date,region,revenue,cost
A-1,2025-01-05,North, 1200.50 ,800
A-2,2025-02-05,north,"1,300.00",900
A-1,2025-01-05,North, 1200.50 ,800
A-3,2025-03-11,South,,700
A-4,2025-04-20,EAST,1 500,n/a
"""

COLUMNS = ["order_id", "order_date", "region", "revenue", "cost"]
ROWS: list[dict[str, Any]] = [
    {"order_id": "A-1", "order_date": "2025-01-05", "region": "North", "revenue": " 1200.50 ", "cost": 800},
    {"order_id": "A-2", "order_date": "2025-02-05", "region": "north", "revenue": "1,300.00", "cost": 900},
    {"order_id": "A-1", "order_date": "2025-01-05", "region": "North", "revenue": " 1200.50 ", "cost": 800},
    {"order_id": "A-3", "order_date": "2025-03-11", "region": "South", "revenue": None, "cost": 700},
    {"order_id": "A-4", "order_date": "2025-04-20", "region": "EAST", "revenue": "1 500", "cost": "n/a"},
]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("1,300.00", 1300.0),
        ("1.234,56", 1234.56),
        ("1.234.567", 1234567.0),
        ("1.234", 1.234),
        (" 1200.50 ", 1200.5),
        ("1 500", 1500.0),
        ("(450.25)", -450.25),
        ("250-", -250.0),
        ("12%", 0.12),
        ("JOD 900", 900.0),
        ("٣٤٥٫٥", 345.5),
        ("abc", None),
        ("", None),
    ],
)
def test_number_coercion_reads_real_world_notation(text: str, expected: float | None) -> None:
    value, _note = coerce_number(text)
    if expected is None:
        assert value is None
    else:
        assert value == pytest.approx(expected)


def test_control_total_reports_cells_it_could_not_read() -> None:
    # Summing float(x) or 0.0 lets a third of a column fall out while the total still
    # claims to reconcile. The count of unreadable cells is what makes that visible.
    totals = control_totals(ROWS, COLUMNS)
    assert totals["revenue"]["unreadable_cells"] == 2
    assert totals["revenue"]["count"] == 2
    assert totals["cost"]["unreadable_cells"] == 1


def test_casting_numbers_explains_why_the_total_moved() -> None:
    rows, columns, preview = run_recipe(
        ROWS,
        COLUMNS,
        {"steps": [{"kind": "trim_whitespace", "columns": ["revenue"]},
                   {"kind": "cast_number", "columns": ["revenue"]}]},
    )
    assert columns == COLUMNS
    revenue = next(c for c in preview["control_totals"]["changes"] if c["column"] == "revenue")
    assert revenue["cells_recovered"] == 2
    assert revenue["note"] == "difference_explained_by_newly_readable_cells"
    assert preview["requires_review"] is True
    assert "control_total_changed" in preview["review_reasons"]
    assert any("could not be read" in line or "text cell" in line
               for line in preview["summary"]["steps"]["en"])


def test_a_step_that_changes_nothing_is_reported_not_hidden() -> None:
    _rows, _columns, preview = run_recipe(
        ROWS, COLUMNS, {"steps": [{"kind": "trim_whitespace", "columns": ["order_id"]}]}
    )
    assert preview["steps"][0]["no_effect"] is True
    assert any("changed nothing" in item for item in preview["summary"]["caveats"]["en"])


def test_cleaning_summary_is_written_in_both_languages(client: TestClient,
                                                       auth_headers: dict[str, str]) -> None:
    upload = client.post(
        "/api/v1/datasets/upload",
        files={"file": ("messy.csv", MESSY_CSV, "text/csv")},
        headers=auth_headers,
    )
    assert upload.status_code == 201, upload.text
    version_id = upload.json()["version"]["id"]

    profile = client.get(f"/api/v1/dataset-versions/{version_id}/profile").json()
    assert profile["quality"]["score"] is not None
    assert profile["column_profiles"]["revenue"]["semantic_type"] == "number_text"
    assert profile["recommended_steps"], "the profile must propose the repairs it found"

    suggested = client.post(
        f"/api/v1/dataset-versions/{version_id}/cleaning/suggest", headers=auth_headers
    )
    assert suggested.status_code == 200
    steps = [item["step"] for item in suggested.json()["recommended_steps"]]

    preview = client.post(
        f"/api/v1/dataset-versions/{version_id}/cleaning/preview",
        json={"steps": steps},
        headers=auth_headers,
    )
    assert preview.status_code == 200, preview.text
    summary = preview.json()["summary"]
    assert summary["headline"]["en"] and summary["headline"]["ar"]
    assert len(summary["steps"]["en"]) == len(steps)
    assert len(summary["steps"]["ar"]) == len(steps)
    # Arabic must agree with its number rather than reading like machine output.
    joined = " ".join(summary["steps"]["ar"]) + summary["headline"]["ar"]
    assert "1 خلية" not in joined and "1 صف" not in joined
    assert summary["quality_before"]["score"] is not None
    assert summary["quality_after"]["score"] is not None


class TestCleaningRefusals:
    """Every refusal has to say what is wrong and what would be valid."""

    def test_unknown_column_names_the_column_and_the_alternatives(self) -> None:
        with pytest.raises(Exception) as error:
            run_recipe(ROWS, COLUMNS, {"steps": [{"kind": "trim_whitespace",
                                                  "columns": ["Revenue"]}]})
        details = error.value.details  # type: ignore[attr-defined]
        assert details["unknown_columns"] == ["Revenue"]
        assert "revenue" in details["available_columns"]
        assert details["did_you_mean"]["Revenue"] == ["revenue"]

    def test_a_step_with_no_column_is_refused(self) -> None:
        with pytest.raises(Exception) as error:
            run_recipe(ROWS, COLUMNS, {"steps": [{"kind": "trim_whitespace", "columns": []}]})
        assert "at least one column" in str(error.value.message)  # type: ignore[attr-defined]

    def test_filling_blanks_with_a_blank_is_refused(self) -> None:
        with pytest.raises(Exception) as error:
            run_recipe(ROWS, COLUMNS,
                       {"steps": [{"kind": "replace_missing", "columns": ["revenue"],
                                   "value": ""}]})
        assert error.value.code == "empty_replacement_value"  # type: ignore[attr-defined]

    def test_a_text_replacement_never_lands_in_a_numeric_column(self) -> None:
        rows = [{"cost": 800}, {"cost": None}, {"cost": 900}]
        cleaned, _columns, _preview = run_recipe(
            rows, ["cost"],
            {"steps": [{"kind": "replace_missing", "columns": ["cost"], "value": "0"}]},
        )
        # A string here would silently retype the column and break every metric over it.
        assert cleaned[1]["cost"] == 0.0
        assert isinstance(cleaned[1]["cost"], float)

        with pytest.raises(Exception) as error:
            run_recipe(rows, ["cost"],
                       {"steps": [{"kind": "replace_missing", "columns": ["cost"],
                                   "value": "unknown"}]})
        assert error.value.code == "replacement_type_mismatch"  # type: ignore[attr-defined]


def test_a_column_mixing_date_conventions_is_flagged() -> None:
    rows = [{"d": "2026-06-01"}, {"d": "01/06/2026"}, {"d": "2026-06-02"}, {"d": "05/06/2026"}]
    profile = profile_dataset(rows, ["d"])
    temporal = profile["column_profiles"]["d"]["temporal"]
    assert temporal["mixed_formats"] is True
    assert temporal["ambiguous_cells"] == 2
    assert profile["quality_issues"]["mixed_date_formats"]["columns"] == ["d"]


def test_an_identifier_is_not_counted_as_an_invalid_number() -> None:
    # "ORD-00001" is a perfectly good identifier. Counting it as an unreadable number
    # marks every row in the file as defective and destroys the validity score.
    rows = [{"order_id": f"ORD-{index:05d}", "revenue": 100 + index} for index in range(40)]
    profile = profile_dataset(rows, ["order_id", "revenue"])
    assert profile["quality"]["counts"]["invalid_cells"] == 0
    assert profile["quality"]["dimensions"]["validity"] == 1.0
    assert "numeric_parse" not in profile["column_profiles"]["order_id"]


def test_concentration_is_judged_against_an_even_split() -> None:
    # With three categories every share is large by construction; reporting that as
    # concentration is a tautology, not a finding.
    even = [{"region": ["N", "S", "E"][index % 3], "revenue": 100} for index in range(90)]
    profile = profile_dataset(even, ["region", "revenue"])
    findings = analyze_dataset(even, ["region", "revenue"], profile)["findings"]
    assert not [f for f in findings if f["kind"] == "concentration"]

    skewed = [
        {"customer": "Dominant" if index < 60 else f"C{index}", "revenue": 100}
        for index in range(100)
    ]
    profile = profile_dataset(skewed, ["customer", "revenue"])
    findings = analyze_dataset(skewed, ["customer", "revenue"], profile)["findings"]
    concentration = [f for f in findings if f["kind"] == "concentration"]
    assert concentration, "a genuinely dominant category must be reported"
    assert concentration[0]["evidence"]["leader"] == "Dominant"
    for language in ("en", "ar"):
        for part in ("observation", "interpretation", "recommendation", "limitation"):
            assert concentration[0][part][language].strip()


def test_missing_data_that_clusters_in_one_segment_is_flagged() -> None:
    rows = [
        {"region": "Aqaba" if index % 4 == 0 else "Amman",
         "cost": None if index % 4 == 0 else 100 + index,
         "revenue": 200 + index}
        for index in range(120)
    ]
    columns = ["region", "cost", "revenue"]
    findings = analyze_dataset(rows, columns, profile_dataset(rows, columns))["findings"]
    missingness = [f for f in findings if f["kind"] == "missingness"]
    assert missingness
    assert missingness[0]["evidence"]["worst_segment"] == "Aqaba"
    assert missingness[0]["severity"] == "high"


@pytest.mark.parametrize(
    ("label", "values", "expected"),
    [
        ("a genuine step", [10.0] * 15 + [40.0] * 15, True),
        ("a genuine drop", [200.0] * 15 + [120.0] * 15, True),
        ("a steady climb", [100.0 + 5 * index for index in range(30)], False),
        ("flat and quiet", [100.0, 101.0, 99.0, 100.5] * 8, False),
        (
            "a smooth low-noise climb",
            [35293.0, 36533, 36941, 37349, 38540, 37942, 39380, 39800, 41136, 41568,
             40797, 42432, 43913, 44357, 44801, 43856, 46871, 47327, 45031, 45461,
             45522, 47646, 48088, 48529],
            False,
        ),
    ],
)
def test_level_shift_detection_separates_a_break_from_a_trend(
    label: str, values: list[float], expected: bool
) -> None:
    # Tiny residuals make almost any split statistically significant, so the size of the
    # fitted step has to clear the noise and several periods of ordinary trend as well.
    assert (detect_level_shift(values) is not None) is expected, label
