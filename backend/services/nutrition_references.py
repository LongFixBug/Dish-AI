"""Parse and snapshot the National Institute of Nutrition's HTML tables."""

from __future__ import annotations

import json
import re
import unicodedata
from html.parser import HTMLParser
from functools import lru_cache
from pathlib import Path
from typing import Any

_NUMBER_PATTERN = re.compile(r"(?<!\d)(?:\d+[.,]\d+|\d+)")


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "tr":
            self._row = []
        elif tag in {"td", "th"} and self._row is not None:
            self._cell = []

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self._row is not None and self._cell is not None:
            self._row.append(" ".join("".join(self._cell).split()))
            self._cell = None
        elif tag == "tr" and self._row:
            self.rows.append(self._row)
            self._row = None

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)


def parse_nutrition_table_html(html: str) -> list[dict[str, object]]:
    """Convert the site's table markup into normalized, audit-friendly rows."""
    parser = _TableParser()
    parser.feed(html)
    records: list[dict[str, object]] = []
    section = ""
    nutrient_name = ""
    unit = ""
    for row in parser.rows[1:]:
        if len(row) == 1:
            section = row[0]
            continue
        parsed = _parse_row(row, nutrient_name, unit)
        if parsed is None:
            continue
        nutrient_name = str(parsed["nutrient_name"])
        unit = str(parsed["unit"])
        parsed["section"] = section
        records.append(parsed)
    return records


def _parse_row(
    row: list[str],
    previous_nutrient: str,
    previous_unit: str,
) -> dict[str, object] | None:
    if len(row) >= 4 and row[0].isdigit():
        nutrient_name, unit, values = row[1], row[2], row[3:]
    elif len(row) >= 3 and not row[0].isdigit():
        nutrient_name, unit, values = row[0], row[1], row[2:]
    elif len(row) >= 2 and previous_nutrient:
        nutrient_name, unit, values = previous_nutrient, previous_unit, row
    else:
        return None
    value_text = " ".join(part for part in values if part).strip()
    if not nutrient_name or not unit or not value_text:
        return None
    value_min, value_max = _parse_bounds(value_text)
    return {
        "nutrient_code": _slug(nutrient_name),
        "nutrient_name": nutrient_name,
        "unit": unit,
        "value_text": value_text,
        "value_min": value_min,
        "value_max": value_max,
    }


def _parse_bounds(value_text: str) -> tuple[float | None, float | None]:
    if value_text.rstrip().endswith("-"):
        return None, None
    numbers = [
        float(value.replace(",", "."))
        for value in _NUMBER_PATTERN.findall(value_text)
    ]
    if not numbers:
        return None, None
    if value_text.lstrip().startswith(("<", "≤")):
        return None, numbers[-1]
    if len(numbers) >= 2 and "-" in value_text:
        return numbers[-2], numbers[-1]
    return numbers[-1], numbers[-1]


def _slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    without_marks = "".join(
        char for char in normalized if not unicodedata.combining(char)
    )
    return re.sub(r"[^a-z0-9]+", "_", without_marks.lower()).strip("_")


_REFERENCE_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "vn_nutrition_reference_targets.json"
)
_LABOR_LEVELS = {
    "sedentary": "light",
    "light": "light",
    "moderate": "moderate",
    "very_active": "heavy",
}


@lru_cache(maxsize=1)
def _load_reference_snapshot() -> dict[str, Any]:
    """Load the checked-in, provenance-labelled NCDD snapshot once per process."""
    return json.loads(_REFERENCE_PATH.read_text(encoding="utf-8"))


def lookup_nutrition_reference_targets(
    *,
    age: int,
    sex: str,
    activity_level: str,
) -> list[dict[str, Any]]:
    """Return adult reference rows matching the normalized profile.

    The public calculator is intentionally independent from PostgreSQL so its
    preview endpoint remains deterministic. The same snapshot is seeded into
    ``nutrition_reference_targets`` for database-backed reporting.
    """
    if age < 18:
        return []
    age_group = _age_group_for_adult(age)
    if sex not in {"male", "female"}:
        return []
    reference_sex = sex
    labor_level = _LABOR_LEVELS[activity_level]
    rows = _load_reference_snapshot()["records"]
    return [
        row
        for row in rows
        if row["age_group_name"] == age_group
        and row["sex"] == reference_sex
        and row["labor_level"] == labor_level
        and row["physiological_condition_id"] is None
    ]


def reference_snapshot_metadata() -> dict[str, str]:
    """Return source metadata for response provenance."""
    return _load_reference_snapshot()["metadata"]


def adult_age_group(age: int) -> str:
    """Return the snapshot's adult age-group label."""
    return _age_group_for_adult(age)


def _age_group_for_adult(age: int) -> str:
    if age <= 29:
        return "18-29 tuổi"
    if age <= 49:
        return "30-49 tuổi"
    if age <= 64:
        return "50-64 tuổi"
    if age <= 74:
        return "65-74 tuổi"
    return "≥75 tuổi"
