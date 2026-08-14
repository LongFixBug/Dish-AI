"""Crawl the public NRIHCM nutrition API into a separate PostgreSQL table.

The source page uses an Angular frontend, but its public API is hosted at
``app.thucdongiadinh.vn``. This importer keeps the source payload alongside
normalized common nutrients and never writes to FoodAI's reviewed catalog.

Usage:
    uv run python scripts/crawl_nrihcm_foods.py       # fetch-only dry run
    uv run python scripts/crawl_nrihcm_foods.py --apply
"""

from __future__ import annotations

import argparse
import asyncio
import math
import sys
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.db.models import NrihcmFood  # noqa: E402
from backend.db.postgres import async_session  # noqa: E402


SOURCE_PAGE_URL = "https://thucdongiadinh.vn/app/tra-cuu/thanh-phan-dinh-duong-thuc-pham"
API_URL = "https://app.thucdongiadinh.vn/api/services/app/TraCuuDinhDuong/TraCuuDinhDuongThucPham"
DEFAULT_PAGE_SIZE = 500
DB_BATCH_SIZE = 500
DEFAULT_TIMEOUT_SECONDS = 60.0
HEADERS = {
    "Accept": "text/plain, application/json",
    "Content-Type": "application/json-patch+json",
    "User-Agent": "FoodAI-NRIHCM-importer/1.0",
}


def _required_int(item: Mapping[str, Any], key: str) -> int:
    value = item.get(key)
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"missing or invalid {key}") from exc
    if result <= 0:
        raise ValueError(f"missing or invalid {key}")
    return result


def _number(value: Any, *, key: str, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid numeric field {key}") from exc
    if not math.isfinite(result):
        raise ValueError(f"invalid numeric field {key}")
    return result


def parse_food_item(
    item: Mapping[str, Any],
    *,
    fetched_at: datetime | None = None,
) -> dict[str, Any]:
    """Convert one API item into a row for ``nrihcm_foods``."""
    if not isinstance(item, Mapping):
        raise ValueError("food item must be an object")

    nutrient_facts = item.get("thanhPhanDinhDuong") or []
    if not isinstance(nutrient_facts, list):
        raise ValueError("thanhPhanDinhDuong must be a list")

    facts_by_id: dict[int, Mapping[str, Any]] = {}
    for fact in nutrient_facts:
        if not isinstance(fact, Mapping):
            raise ValueError("nutrition fact must be an object")
        fact_id = _required_int(fact, "dinhDuongId")
        facts_by_id[fact_id] = fact

    def nutrient_amount(nutrient_id: int) -> float:
        fact = facts_by_id.get(nutrient_id)
        return _number(fact.get("hamLuong") if fact else None, key="hamLuong")

    source_food_id = _required_int(item, "thucPhamId")
    name_vi = str(item.get("tenThucPham") or "").strip()
    if not name_vi:
        raise ValueError("missing or invalid tenThucPham")

    return {
        "source_food_id": source_food_id,
        "food_code": str(item.get("maThucPham") or "").strip(),
        "name_vi": name_vi,
        "name_en": str(item["tenThucPhamEn"]).strip() if item.get("tenThucPhamEn") else None,
        "group_name": str(item.get("nhomThucPham") or item.get("strNhomThucPham") or "").strip(),
        "group_id": int(item["nhomThucPhamId"]) if item.get("nhomThucPhamId") else None,
        "energy_kcal_per_100g": _number(item.get("nangLuongKcal"), key="nangLuongKcal"),
        "energy_kj_per_100g": _number(item.get("nangLuongKJ"), key="nangLuongKJ"),
        "edible_waste_percent": _number(item.get("tyLeThaiBo"), key="tyLeThaiBo"),
        "basis_grams": _number(item.get("khoiLuong"), key="khoiLuong", default=100.0),
        "water_g_per_100g": nutrient_amount(1),
        "protein_g_per_100g": nutrient_amount(2),
        "fat_g_per_100g": nutrient_amount(3),
        "carbs_g_per_100g": nutrient_amount(4),
        "nutrition_facts": list(nutrient_facts),
        "raw_payload": dict(item),
        "source_url": SOURCE_PAGE_URL,
        "fetched_at": fetched_at or datetime.now(timezone.utc),
    }


def fetch_all_foods(
    client: httpx.Client,
    *,
    page_size: int = DEFAULT_PAGE_SIZE,
    api_url: str = API_URL,
) -> list[dict[str, Any]]:
    """Fetch every page reported by the API and return normalized rows."""
    if page_size <= 0:
        raise ValueError("page_size must be positive")

    rows: list[dict[str, Any]] = []
    skip_count = 0
    total_count: int | None = None
    fetched_at = datetime.now(timezone.utc)

    while total_count is None or skip_count < total_count:
        payload = {
            "listOfNhomThucPhamId": None,
            "filter": None,
            "maxResultCount": page_size,
            "skipCount": skip_count,
        }
        response = client.post(api_url, json=payload, headers=HEADERS)
        response.raise_for_status()
        body = response.json()
        result = body.get("result") if isinstance(body, dict) else None
        if not isinstance(result, dict) or not isinstance(result.get("items"), list):
            raise RuntimeError("NRIHCM API response has no result.items list")

        page_items = result["items"]
        total_count = int(result.get("totalCount", 0))
        if not page_items:
            if skip_count < total_count:
                raise RuntimeError("NRIHCM API returned an empty page before totalCount")
            break

        rows.extend(parse_food_item(item, fetched_at=fetched_at) for item in page_items)
        skip_count += len(page_items)

    return rows


async def upsert_rows(session: AsyncSession, rows: list[dict[str, Any]]) -> int:
    """Upsert a crawled snapshot by the source's stable food ID."""
    if not rows:
        return 0

    unique_rows = list({row["source_food_id"]: row for row in rows}.values())
    for offset in range(0, len(unique_rows), DB_BATCH_SIZE):
        batch = unique_rows[offset : offset + DB_BATCH_SIZE]
        statement = insert(NrihcmFood).values(batch)
        update_columns = {
            column: getattr(statement.excluded, column)
            for column in (
                "food_code",
                "name_vi",
                "name_en",
                "group_name",
                "group_id",
                "energy_kcal_per_100g",
                "energy_kj_per_100g",
                "edible_waste_percent",
                "basis_grams",
                "water_g_per_100g",
                "protein_g_per_100g",
                "fat_g_per_100g",
                "carbs_g_per_100g",
                "nutrition_facts",
                "raw_payload",
                "source_url",
                "fetched_at",
            )
        }
        update_columns["updated_at"] = statement.excluded.fetched_at
        await session.execute(
            statement.on_conflict_do_update(
                index_elements=[NrihcmFood.source_food_id],
                set_=update_columns,
            )
        )
    await session.commit()
    return len(unique_rows)


async def store_rows(rows: list[dict[str, Any]]) -> int:
    async with async_session() as session:
        return await upsert_rows(session, rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Upsert rows into PostgreSQL.")
    parser.add_argument("--page-size", type=int, default=DEFAULT_PAGE_SIZE)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    args = parser.parse_args()

    with httpx.Client(timeout=args.timeout) as client:
        rows = fetch_all_foods(client, page_size=args.page_size)

    print(f"Fetched {len(rows)} NRIHCM food records from the public API")
    if args.apply:
        stored = asyncio.run(store_rows(rows))
        print(f"Upserted {stored} records into nrihcm_foods")
    else:
        print("Dry run: database was not changed (pass --apply to persist)")


if __name__ == "__main__":
    main()
