"""Migration: Tách nutrition_ingredients → 3 bảng riêng.

Trước: 1 bảng nutrition_ingredients chứa tất cả (USDA + VN ingredients + VN dishes).
Sau:
  1. nutrition_ingredients — chỉ USDA (sr legacy, foundation, manual)
  2. vn_ingredients       — nguyên liệu Việt (source=vnfood + item_type=ingredient/fruit/product)
  3. vn_dishes            — món ăn Việt (item_type=dish, cả vnmeal + vnfood)

Chạy: uv run python scripts/migrate_split_nutrition.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import asyncpg
from sqlalchemy import text

from backend.db.postgres import async_session
from backend.config import settings

async def main():
    print("=== Migration: Split nutrition_ingredients ===")

    async with async_session() as session:
        # ── 1. Tạo bảng vn_ingredients ───────────────────────────────────
        print("[1/5] Creating vn_ingredients...")
        await session.execute(text("""
            CREATE TABLE IF NOT EXISTS vn_ingredients (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                ingredient_name VARCHAR(500) NOT NULL,
                calories_per_g DOUBLE PRECISION DEFAULT 0.0,
                protein_per_g DOUBLE PRECISION DEFAULT 0.0,
                fat_per_g DOUBLE PRECISION DEFAULT 0.0,
                carbs_per_g DOUBLE PRECISION DEFAULT 0.0,
                fiber_per_g DOUBLE PRECISION DEFAULT 0.0,
                source VARCHAR(50) DEFAULT 'vnfood',
                item_type VARCHAR(20) DEFAULT 'ingredient',
                embedding VECTOR(1024),
                created_at TIMESTAMPTZ DEFAULT now()
            )
        """))

        # ── 2. Tạo bảng vn_dishes ────────────────────────────────────────
        print("[2/5] Creating vn_dishes...")
        await session.execute(text("""
            CREATE TABLE IF NOT EXISTS vn_dishes (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                dish_name VARCHAR(200) NOT NULL,
                calories_per_g DOUBLE PRECISION DEFAULT 0.0,
                protein_per_g DOUBLE PRECISION DEFAULT 0.0,
                fat_per_g DOUBLE PRECISION DEFAULT 0.0,
                carbs_per_g DOUBLE PRECISION DEFAULT 0.0,
                fiber_per_g DOUBLE PRECISION DEFAULT 0.0,
                source VARCHAR(50) DEFAULT 'vnmeal',
                created_at TIMESTAMPTZ DEFAULT now()
            )
        """))

        # ── 3. Migrate VN ingredients sang vn_ingredients ────────────────
        print("[3/5] Migrating VN ingredients...")
        result = await session.execute(text("""
            WITH migrated AS (
                INSERT INTO vn_ingredients (
                    ingredient_name, calories_per_g, protein_per_g,
                    fat_per_g, carbs_per_g, fiber_per_g, source, item_type, embedding
                )
                SELECT
                    ingredient_name, calories_per_g, protein_per_g,
                    fat_per_g, carbs_per_g, fiber_per_g, source, item_type, embedding
                FROM nutrition_ingredients
                WHERE source IN ('vnfood', 'vnmeal')
                  AND item_type IN ('ingredient', 'fruit', 'product')
                RETURNING id
            )
            SELECT COUNT(*) FROM migrated
        """))
        vn_ing_count = result.scalar()
        print(f"  → Migrated {vn_ing_count} rows to vn_ingredients")

        # ── 4. Migrate dishes sang vn_dishes ─────────────────────────────
        print("[4/5] Migrating VN dishes...")
        result = await session.execute(text("""
            WITH migrated AS (
                INSERT INTO vn_dishes (
                    dish_name, calories_per_g, protein_per_g,
                    fat_per_g, carbs_per_g, fiber_per_g, source
                )
                SELECT
                    ingredient_name, calories_per_g, protein_per_g,
                    fat_per_g, carbs_per_g, fiber_per_g, source
                FROM nutrition_ingredients
                WHERE item_type = 'dish'
                RETURNING id
            )
            SELECT COUNT(*) FROM migrated
        """))
        vn_dish_count = result.scalar()
        print(f"  → Migrated {vn_dish_count} rows to vn_dishes")

        # ── 5. Xóa rows đã migrate khỏi nutrition_ingredients ────────────
        print("[5/5] Cleaning up nutrition_ingredients...")
        result = await session.execute(text("""
            WITH deleted AS (
                DELETE FROM nutrition_ingredients
                WHERE source IN ('vnfood', 'vnmeal')
                   OR item_type = 'dish'
                RETURNING id
            )
            SELECT COUNT(*) FROM deleted
        """))
        deleted_count = result.scalar()
        print(f"  → Deleted {deleted_count} rows from nutrition_ingredients")
        await session.commit()

        # ── Verify ───────────────────────────────────────────────────────
        print()
        print("=== Verification ===")
        for table, label in [
            ("nutrition_ingredients", "nutrition_ingredients (USDA only)"),
            ("vn_ingredients", "vn_ingredients"),
            ("vn_dishes", "vn_dishes"),
        ]:
            r = await session.execute(text(f"SELECT COUNT(*) FROM {table}"))
            print(f"  {label}: {r.scalar()} rows")

        # Check no leftover VN data in nutrition_ingredients
        r = await session.execute(text("""
            SELECT COUNT(*) FROM nutrition_ingredients
            WHERE source IN ('vnfood', 'vnmeal') OR item_type = 'dish'
        """))
        leftover = r.scalar()
        if leftover > 0:
            print(f"  ⚠️  WARNING: {leftover} rows still have VN data in nutrition_ingredients!")
        else:
            print("  ✅ No VN data left in nutrition_ingredients")

    print()
    print("=== Migration complete! ===")

asyncio.run(main())
