"""Migration: thêm cột item_type + backfill heuristic (nguyên liệu vs món).

Bảng nutrition_ingredients (10148 rows) lẫn 4 loại: nguyên liệu thô, món ăn,
trái cây, sản phẩm. source không đủ tin cậy (vnmeal lẫn trái cây, vnfood lẫn
sản phẩm). Thêm cột item_type để phân biệt semantic.

item_type ∈ {ingredient, dish, fruit, product}:
- ingredient: nguyên liệu thô (dùng trong công thức) — sr legacy, foundation, vnfood mặc định
- dish: món ăn thành phẩm (lookup institute) — vnmeal mặc định
- fruit: trái cây (dùng được trong công thức như nguyên liệu)
- product: sản phẩm chế biến/thành phẩm (Bánh, Kẹo, Sushi...)

Backfill 3 bước (idempotent — set cùng giá trị, rerun không đổi):
  1. ADD COLUMN DEFAULT 'ingredient' (toàn bộ rows = ingredient)
  2. UPDATE vnmeal → dish
  3. UPDATE product (vnfood prefix) — chạy TRƯỚC fruit
  4. UPDATE fruit (vnmeal prefix exact) — chạy SAU product

Heuristic dùng vn_norm(ingredient_name) (đã có, bỏ dấu+lower) để match không dấu.
List trái cây dùng exact (vd 'dua hau' không 'dua' — tránh dính 'Dưa chuột' vegetable).
List sản phẩm bỏ 'com' (vn_norm Cơm=Cốm collision).

Kỳ vọng count: ingredient=8818, dish=1226, product=80, fruit=24.

Lưu ý: heuristic dựa source + tên, ~0% sai sau refine. Metadata gốc đã MẤT trong
JSON (parse chỉ giữ tên+nutrition+source). Nếu sau này re-parse giữ metadata gốc
(foodCategory/food_group) → UPDATE item_type chính xác hơn.

Usage:
    DEBUG=false python scripts/migrate_item_type.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402

from backend.db.postgres import engine  # noqa: E402


# ─── SQL ────────────────────────────────────────────────────────────────────

# Bước 0: ADD COLUMN — DEFAULT 'ingredient' gán toàn bộ rows hiện có
ADD_COLUMN_SQL = """
ALTER TABLE nutrition_ingredients
    ADD COLUMN IF NOT EXISTS item_type VARCHAR(20) NOT NULL DEFAULT 'ingredient';
"""

# Bước 1: vnmeal → dish (đè default ingredient)
UPDATE_DISH_SQL = """
UPDATE nutrition_ingredients
SET item_type = 'dish'
WHERE source = 'vnmeal';
"""

# Bước 2: product (vnfood prefix) — chạy TRƯỚC fruit
# Bỏ 'com' (vn_norm Cơm=Cốm collision). 'thach' cho Thạch, 'tao pho' cho Tào phớ.
UPDATE_PRODUCT_SQL = """
UPDATE nutrition_ingredients
SET item_type = 'product'
WHERE source = 'vnfood'
  AND vn_norm(ingredient_name) ~ '^(banh|keo|caramen|sushi|burger|pizza|bim bim|hamburger|snack|popcorn|thach|tao pho|sui din|pha lau|socola)';
"""

# Bước 3: fruit (vnmeal prefix exact) — chạy SAU product
# Dùng exact thay prefix rộng: 'dua hau' không 'dua' (tránh Dưa chuột vegetable),
# 'tao ta'/'tao tay' không 'tao' (tránh Tào phớ product).
UPDATE_FRUIT_SQL = """
UPDATE nutrition_ingredients
SET item_type = 'fruit'
WHERE source = 'vnmeal'
  AND vn_norm(ingredient_name) ~ '^(tao ta|tao tay|sau rieng|quyt|cam|buoi|dua hau|dua le|dua vang|dua ta|du du|mit dai|mit kho|nhan|vai|vai thieu|xoai|oi|thanh long|mang cut|na|le|dao|nho ngot|hong xiem|chom chom|kiwi)';
"""


async def migrate() -> None:
    """Chạy ADD COLUMN + 3 UPDATE backfill (thứ tự: dish → product → fruit)."""
    async with engine.begin() as conn:
        await conn.execute(text(ADD_COLUMN_SQL))
        print("✅ Thêm cột item_type (DEFAULT 'ingredient')")

        await conn.execute(text(UPDATE_DISH_SQL))
        print("✅ Bước 1: vnmeal → dish")

        await conn.execute(text(UPDATE_PRODUCT_SQL))
        print("✅ Bước 2: vnfood prefix → product (chạy trước fruit)")

        await conn.execute(text(UPDATE_FRUIT_SQL))
        print("✅ Bước 3: vnmeal prefix exact → fruit (chạy sau product)")

        # Verify count
        result = await conn.execute(
            text(
                "SELECT item_type, count(*) "
                "FROM nutrition_ingredients GROUP BY item_type ORDER BY 1;"
            )
        )
        print("\n📊 Count theo item_type:")
        for item_type, count in result.all():
            print(f"   {item_type:12s} {count}")

    print("\n👉 Mong đợi: ingredient=8818, dish=1226, product=80, fruit=24")
    print("👉 Query autocomplete/lookup cần lọc theo item_type (xem plan).")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(migrate())
