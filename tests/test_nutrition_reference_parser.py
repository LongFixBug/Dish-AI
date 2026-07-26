"""Tests for parsing the Institute's HTML nutrition table snapshot."""

import json
from pathlib import Path

from backend.services.nutrition_references import parse_nutrition_table_html


def test_parser_extracts_scalar_and_range_values() -> None:
    html = """
    <table>
      <tr><th>STT</th><th>Nhu cầu</th><th>Đơn vị</th><th>Giá trị</th></tr>
      <tr class="group-row"><td colspan="5">Năng lượng</td></tr>
      <tr><td>1</td><td>Năng lượng</td><td>Kcal/ngày</td><td>2570,0</td></tr>
      <tr><td>2</td><td>Chất béo</td><td>g/ngày</td><td>57,1 - 71,4</td></tr>
      <tr><td>3</td><td>Sắt</td><td>mg/ngày</td><td>Mức hấp thu 10% *</td><td>11,9</td></tr>
      <tr><td>Mức hấp thu 15% **</td><td>7,9</td></tr>
    </table>
    """

    rows = parse_nutrition_table_html(html)

    assert rows[0]["nutrient_code"] == "nang_luong"
    assert rows[0]["value_min"] == 2570.0
    assert rows[0]["value_max"] == 2570.0
    assert rows[1]["value_min"] == 57.1
    assert rows[1]["value_max"] == 71.4
    assert rows[2]["value_text"] == "Mức hấp thu 10% * 11,9"
    assert rows[3]["nutrient_code"] == "sat"
    assert rows[3]["unit"] == "mg/ngày"


def test_checked_in_snapshot_has_provenance_and_multiple_age_groups() -> None:
    path = Path(__file__).parents[1] / "data/vn_nutrition_reference_targets.json"
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["metadata"]["standard"] == "VN_NCDD_2016"
    assert payload["metadata"]["record_count"] == len(payload["records"])
    assert payload["metadata"]["record_count"] > 1000
    assert {row["sex"] for row in payload["records"]} == {"male", "female"}
    assert payload["records"][0]["source_endpoint"].endswith(
        "getNutritionNeedsTable"
    )
