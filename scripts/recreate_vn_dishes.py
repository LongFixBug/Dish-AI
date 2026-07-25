"""Refresh institute dish nutrition from JSON without deleting serving metadata.

- Strip tiếng Anh trong ngoặc khỏi dish_name
- Dedup: nếu nhiều dòng cùng tên -> giữ nutrition tốt nhất

Chạy: uv run python scripts/recreate_vn_dishes.py
"""

import asyncio
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, text

from backend.db.models import VnDish
from backend.db.postgres import async_session
from backend.services.catalog_quality import canonical_name_key, deduplicate_catalog_rows

_HAS_EN = re.compile(r"[A-Za-z]{3,}")


def clean_dish_name(name: str) -> str:
    """Strip từng lớp ngoặc CUỐI nếu chứa >=3 alphabet liên tiếp."""
    name = name.strip()
    while name.endswith(")"):
        depth = 0
        open_idx = -1
        for i in range(len(name) - 1, -1, -1):
            if name[i] == ")":
                depth += 1
            elif name[i] == "(":
                depth -= 1
                if depth == 0:
                    open_idx = i
                    break
        if open_idx < 0:
            break
        content = name[open_idx + 1 : -1]
        if _HAS_EN.search(content):
            name = name[:open_idx].strip()
        else:
            break
    return name


def serving_totals(item: dict) -> tuple[float, float, float, float, float]:
    """Read explicit serving totals, with compatibility for the legacy export.

    The first exports encoded meal totals as misleading ``*_per_g`` values
    divided by 100. Keeping this fallback lets existing data be refreshed
    safely, while all newly parsed exports use explicit serving fields.
    """
    if "calories_per_serving" in item:
        return (
            float(item["calories_per_serving"]),
            float(item["protein_per_serving_g"]),
            float(item["fat_per_serving_g"]),
            float(item["carbs_per_serving_g"]),
            float(item["fiber_per_serving_g"]),
        )

    return (
        float(item["calories_per_g"]) * 100,
        float(item["protein_per_g"]) * 100,
        float(item["fat_per_g"]) * 100,
        float(item["carbs_per_g"]) * 100,
        float(item["fiber_per_g"]) * 100,
    )


async def main() -> None:
    json_path = Path(__file__).resolve().parent.parent / "data" / "vn_foods.json"
    with open(json_path, encoding="utf-8") as f:
        all_items = json.load(f)

    dishes = [d for d in all_items if d.get("source") == "vnmeal"]
    print(f"Loaded {len(dishes)} dishes from vn_foods.json")

    # Clean + dedup bằng cùng quy tắc với migration/audit.
    normalized: list[dict[str, object]] = []
    cleaned_count = 0
    for d in dishes:
        name = d["ingredient_name"]
        cleaned = clean_dish_name(name)
        if cleaned != name:
            cleaned_count += 1
        cal, p, f_val, c, fb = serving_totals(d)
        normalized.append({
            "dish_name": cleaned,
            "total_calories": cal,
            "total_protein_g": p,
            "total_fat_g": f_val,
            "total_carbs_g": c,
            "total_fiber_g": fb,
            "source": "vnmeal",
        })
    selected = list(deduplicate_catalog_rows(normalized, entity_type="dish"))

    print(f"Cleaned names: {cleaned_count}")
    print(f"Unique dishes (after dedup): {len(selected)}")

    async with async_session() as session:
        print("\n[1/2] Upserting institute nutrition (preserving serving metadata)...")
        current = list((await session.scalars(select(VnDish))).all())
        existing = {canonical_name_key(row.dish_name): row for row in current}
        for item in selected:
            key = canonical_name_key(str(item["dish_name"]))
            row = existing.get(key)
            if row is None:
                row = VnDish(dish_name=str(item["dish_name"]))
                session.add(row)
                existing[key] = row
            row.total_calories = float(item["total_calories"])
            row.total_protein_g = float(item["total_protein_g"])
            row.total_fat_g = float(item["total_fat_g"])
            row.total_carbs_g = float(item["total_carbs_g"])
            row.total_fiber_g = float(item["total_fiber_g"])
            row.source = "vnmeal"
        print(f"  -> Upserted {len(selected)} dishes")
        await session.commit()

        print("[2/2] Verifying serving-size coverage...")
        r = await session.execute(text("SELECT COUNT(*) FROM vn_dishes"))
        total = r.scalar()
        r = await session.execute(text(
            "SELECT COUNT(*) FROM vn_dishes WHERE typical_grams IS NOT NULL"
        ))
        with_grams = r.scalar()
        print(f"\nTotal: {total} dishes, {with_grams} with typical_grams")

        print("\nSample:")
        r = await session.execute(text("""
            SELECT dish_name, total_calories, typical_grams
            FROM vn_dishes WHERE typical_grams IS NOT NULL
            ORDER BY RANDOM() LIMIT 5
        """))
        for row in r:
            print(f"  {row[0]:50s} {row[1]:8.0f} cal  typical={row[2]}g")

    print("\n=== Done! ===")

if __name__ == "__main__":
    asyncio.run(main())
