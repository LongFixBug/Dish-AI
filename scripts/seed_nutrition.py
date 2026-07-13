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

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
BATCH_SIZE = 500


def _resolve_json_path() -> Path:
    """Lấy đường dẫn JSON từ tham số dòng lệnh, mặc định usda_ingredients.json.

    Cho phép seed nhiều nguồn (USDA, VN) mà không phải sửa code.
    """
    if len(sys.argv) > 1:
        # Tham số có thể là tên file hoặc đường dẫn tuyệt đối
        arg = Path(sys.argv[1])
        return arg if arg.is_absolute() else DATA_DIR / arg
    return DATA_DIR / "usda_ingredients.json"


async def seed() -> None:
    """Đọc JSON → INSERT vào DB theo batch."""
    json_path = _resolve_json_path()
    if not json_path.exists():
        print(f"❌ Không tìm thấy {json_path}")
        print("   Cách dùng: python scripts/seed_nutrition.py [ten_file.json]")
        sys.exit(1)

    # Đọc JSON
    with open(json_path, encoding="utf-8") as f:
        ingredients: list[dict] = json.load(f)

    print(f"📦 Đọc {len(ingredients)} ingredients từ {json_path.name}")

    async with async_session() as session:
        # Lấy danh sách tên đã có trong DB để tránh trùng lặp
        existing_result = await session.execute(
            select(NutritionIngredient.ingredient_name)
        )
        existing_names = {row[0] for row in existing_result}
        if existing_names:
            print(f"  ℹ️  DB đã có {len(existing_names)} ingredients — chỉ INSERT món mới.")

        # Lọc ra các ingredient chưa có trong DB
        new_ingredients = [
            item for item in ingredients
            if item["ingredient_name"] not in existing_names
        ]
        skipped = len(ingredients) - len(new_ingredients)
        if skipped:
            print(f"  ⏭️  Bỏ qua {skipped} ingredient đã tồn tại.")

        if not new_ingredients:
            print("✅ Không có ingredient nào mới để seed.")
            return

        # INSERT theo batch
        total_inserted = 0
        total = len(new_ingredients)
        for i in range(0, total, BATCH_SIZE):
            batch = new_ingredients[i : i + BATCH_SIZE]
            batch_num = i // BATCH_SIZE + 1
            total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE

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
