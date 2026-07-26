"""Snapshot the National Institute of Nutrition's reference tables.

The website exposes HTML endpoints for its own frontend rather than a stable
public API. This script intentionally runs offline during deploy/maintenance,
stores the response with provenance, and keeps runtime requests independent of
the website.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from backend.services.nutrition_references import parse_nutrition_table_html

BASE_URL = "https://viendinhduong.vn"
PAGE_URL = f"{BASE_URL}/vi/cong-cu-va-tien-ich/nhu-cau-dinh-duong"
AGE_ENDPOINT = f"{BASE_URL}/api/fe/age"
PHYSIOLOGY_ENDPOINT = f"{BASE_URL}/api/fe/physiologicalCondition/list"
TABLE_ENDPOINT = f"{BASE_URL}/api/fe/nutrition-needs/getNutritionNeedsTable"
SEXES = {"0": "male", "1": "female"}
LABOR_LEVELS = {"0": "light", "1": "moderate", "2": "heavy"}


def main() -> None:
    args = _parse_args()
    ages = _get_json_url(f"{AGE_ENDPOINT}/false") + _get_json_url(f"{AGE_ENDPOINT}/true")
    physiology = {
        item["_id"]: item for item in _get_json_url(PHYSIOLOGY_ENDPOINT)
    }
    records: list[dict[str, object]] = []
    fetched_at = datetime.now(UTC).isoformat()

    for age in sorted(ages, key=lambda item: item.get("ord", 9999)):
        conditions = age.get("physiological_conditions") or []
        for gender, sex in SEXES.items():
            if gender == "1" and conditions:
                combinations = [
                    (labor, condition_id)
                    for condition_id in conditions
                    for labor in ("1",)
                ]
            else:
                combinations = [
                    (labor, None) for labor in LABOR_LEVELS
                ]
            for labor, condition_id in combinations:
                params = {
                    "ageGroupId": age["_id"],
                    "gender": gender,
                    "laborLevel": labor,
                    "locale": "vi",
                }
                if condition_id:
                    params["physiological"] = condition_id
                html = _get_html(TABLE_ENDPOINT, params)
                parsed = parse_nutrition_table_html(html)
                for row in parsed:
                    records.append(
                        {
                            **row,
                            "standard": "VN_NCDD_2016",
                            "source_url": PAGE_URL,
                            "source_endpoint": TABLE_ENDPOINT,
                            "fetched_at": fetched_at,
                            "age_group_id": age["_id"],
                            "age_group_name": age["name"],
                            "sex": sex,
                            "labor_level": LABOR_LEVELS[labor],
                            "physiological_condition_id": condition_id,
                            "physiological_condition_name": (
                                physiology.get(condition_id, {}).get("name")
                                if condition_id
                                else None
                            ),
                        }
                    )
                print(
                    age["name"],
                    sex,
                    LABOR_LEVELS[labor],
                    condition_id or "-",
                    len(parsed),
                )
                time.sleep(args.delay_seconds)

    output = {
        "metadata": {
            "standard": "VN_NCDD_2016",
            "source_url": PAGE_URL,
            "source_endpoint": TABLE_ENDPOINT,
            "fetched_at": fetched_at,
            "record_count": len(records),
        },
        "records": records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(records)} records to {args.output}")


def _get_json_url(url: str) -> list[dict[str, object]]:
    request = Request(
        url,
        headers={"Accept": "application/json"},
    )
    with urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def _get_html(url: str, params: dict[str, str]) -> str:
    request = Request(
        f"{url}?{urlencode(params)}",
        headers={
            "Accept": "text/html, */*",
            "Referer": PAGE_URL,
        },
    )
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/vn_nutrition_reference_targets.json"),
    )
    parser.add_argument("--delay-seconds", type=float, default=0.05)
    return parser.parse_args()


if __name__ == "__main__":
    main()
