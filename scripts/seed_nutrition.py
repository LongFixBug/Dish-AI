"""Seed script — đọc usda_ingredients.json, INSERT vào bảng nutrition_ingredients.

Chạy 1 lần duy nhất sau khi parse_usda.py tạo xong JSON.

Usage:
    python scripts/seed_nutrition.py

Yêu cầu: PostgreSQL + pgvector phải chạy trước (docker compose up -d postgres).
"""

import asyncio
import json
import sys
from pathlib import Path

# Thêm project root vào sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select, text

from backend.db.models import NutritionIngredient  # noqa: E402
from backend.db.postgres import async_session  # noqa: E402

JSON_PATH = Path(__file__).resolve().parent.parent / "data" / "usda_ingredients.json"
BATCH_SIZE = 500


async def seed() -> None:
    """Đọc JSON → INSERT vào DB theo batch."""
    if not JSON_PATH.exists():
        print(f"❌ Không tìm thấy {JSON_PATH}")
        print("   Chạy python scripts/parse_usda.py trước để tạo file này.")
        sys.exit(1)

    # Đọc JSON
    with open(JSON_PATH, encoding="utf-8") as f:
        ingredients: list[dict] = json.load(f)

    print(f"📦 Đọc {len(ingredients)} ingredients từ {JSON_PATH.name}")

    async with async_session() as session:
        # Kiểm tra bảng đã có dữ liệu chưa
        result = await session.execute(
            select(NutritionIngredient).limit(1)
        )
        existing = result.scalars().first()
        if existing:
            print(f"⚠️  Bảng nutrition_ingredients đã có dữ liệu. Xoá hết để seed mới?")
            print("   (gõ 'yes' để tiếp tục, phím khác để huỷ)")
            if input("> ").strip().lower() != "yes":
                print("👋 Huỷ seed.")
                return
            await session.execute(text("TRUNCATE nutrition_ingredients"))
            await session.commit()
            print("🧹 Đã xoá dữ liệu cũ.")

        # INSERT theo batch
        total_inserted = 0
        for i in range(0, len(ingredients), BATCH_SIZE):
            batch = ingredients[i : i + BATCH_SIZE]
            batch_num = i // BATCH_SIZE + 1
            total_batches = (len(ingredients) + BATCH_SIZE - 1) // BATCH_SIZE

            rows = [
                NutritionIngredient(
                    ingredient_name=item["ingredient_name"],
                    calories_per_g=item.get("calories_per_g", 0.0),
                    protein_per_g=item.get("protein_per_g", 0.0),
                    fat_per_g=item.get("fat_per_g", 0.0),
                    carbs_per_g=item.get("carbs_per_g", 0.0),
                    fiber_per_g=item.get("fiber_per_g", 0.0),
                    source=item.get("source", "unknown"),
                )
                for item in batch
            ]

            session.add_all(rows)
            await session.commit()

            total_inserted += len(rows)
            print(
                f"  batch {batch_num}/{total_batches}: "
                f"+{len(rows)} rows (tổng: {total_inserted})"
            )

    print(f"\n✅ Đã seed {total_inserted} ingredients vào PostgreSQL!\n")


if __name__ == "__main__":
    asyncio.run(seed())
