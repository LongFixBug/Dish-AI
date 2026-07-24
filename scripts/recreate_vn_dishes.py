"""Re-create vn_dishes từ file JSON + seed typical_grams + clean tên.

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

from sqlalchemy import text
from backend.db.postgres import async_session

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


async def main():
    json_path = Path(__file__).resolve().parent.parent / "data" / "vn_foods.json"
    with open(json_path) as f:
        all_items = json.load(f)

    dishes = [d for d in all_items if d.get("source") == "vnmeal"]
    print(f"Loaded {len(dishes)} dishes from vn_foods.json")

    # Clean + dedup
    seen: dict[str, dict] = {}
    cleaned_count = 0
    for d in dishes:
        name = d["ingredient_name"]
        cleaned = clean_dish_name(name)
        if cleaned != name:
            cleaned_count += 1
        if cleaned not in seen:
            seen[cleaned] = d

    print(f"Cleaned names: {cleaned_count}")
    print(f"Unique dishes (after dedup): {len(seen)}")

    async with async_session() as session:
        print("\n[1/3] Recreating vn_dishes...")
        await session.execute(text("DROP TABLE IF EXISTS vn_dishes CASCADE"))
        await session.execute(text("""
            CREATE TABLE vn_dishes (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                dish_name VARCHAR(300) NOT NULL,
                total_calories DOUBLE PRECISION DEFAULT 0.0,
                total_protein_g DOUBLE PRECISION DEFAULT 0.0,
                total_fat_g DOUBLE PRECISION DEFAULT 0.0,
                total_carbs_g DOUBLE PRECISION DEFAULT 0.0,
                total_fiber_g DOUBLE PRECISION DEFAULT 0.0,
                typical_grams DOUBLE PRECISION,
                source VARCHAR(50) DEFAULT 'vnmeal',
                created_at TIMESTAMPTZ DEFAULT now()
            )
        """))

        print("[2/3] Inserting dishes (cleaned)...")
        count = 0
        for cleaned_name, d in seen.items():
            cal = d["calories_per_g"] * 100
            p = d["protein_per_g"] * 100
            f_val = d["fat_per_g"] * 100
            c = d["carbs_per_g"] * 100
            fb = d["fiber_per_g"] * 100
            await session.execute(text("""
                INSERT INTO vn_dishes (dish_name, total_calories,
                    total_protein_g, total_fat_g, total_carbs_g, total_fiber_g, source)
                VALUES (:name, :cal, :p, :f, :c, :fb, 'vnmeal')
            """), {"name": cleaned_name, "cal": cal, "p": p, "f": f_val, "c": c, "fb": fb})
            count += 1
        print(f"  -> Inserted {count} dishes")

        print("[3/3] Seeding typical_grams...")
        known = {
            "Phở bò tái": 500, "Phở bò chín": 500, "Phở gà": 500,
            "Bún bò Huế": 550, "Bún chả": 400, "Bún riêu": 500,
            "Bún thịt nướng": 400, "Hủ tiếu": 500, "Mì Quảng": 450,
            "Cơm sườn": 400, "Cơm gà": 400, "Cơm tấm": 450,
            "Bánh mì": 250, "Bánh xèo": 200, "Bánh cuốn": 300,
            "Bánh bèo": 150, "Bánh bao": 150,
            "Bánh chưng": 800, "Bánh tét": 800,
            "Gỏi cuốn": 150, "Cháo": 450, "Chè": 300, "Xôi": 300,
            "Quẩy": 50, "Nem rán": 100, "Vịt quay": 1200,
        }
        updated = 0
        for kw, grams in known.items():
            r = await session.execute(text("""
                UPDATE vn_dishes SET typical_grams = :grams
                WHERE dish_name ILIKE '%' || :kw || '%'
            """), {"grams": grams, "kw": kw})
            updated += r.rowcount
        await session.commit()
        print(f"  -> Updated {updated} dishes with typical_grams")

        # Dedup group giống nhau sau clean (keep best nutrition)
        r = await session.execute(text("""
            SELECT dish_name, COUNT(*) as cnt
            FROM vn_dishes GROUP BY dish_name HAVING COUNT(*) > 1
        """))
        dups = list(r.fetchall())
        if dups:
            print(f"\nDedup {len(dups)} duplicate groups...")
            deleted = 0
            for name, cnt in dups:
                r2 = await session.execute(
                    text("SELECT id::text FROM vn_dishes WHERE dish_name = :nm ORDER BY typical_grams DESC NULLS LAST"),
                    {"nm": name},
                )
                ids = [row[0] for row in r2.fetchall()]
                keep = ids[0]
                for did in ids[1:]:
                    await session.execute(text("DELETE FROM vn_dishes WHERE id = CAST(:uid AS uuid)"), {"uid": did})
                    deleted += 1
            await session.commit()
            print(f"  Deleted {deleted} duplicates")

        # Verify
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

asyncio.run(main())
