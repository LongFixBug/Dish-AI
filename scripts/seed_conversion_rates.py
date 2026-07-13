"""Seed bảng conversion_rates: vài chất lỏng phổ biến VN + fallback nước.

Chạy sau khi đã migrate + tạo bảng conversion_rates.

Usage:
    python scripts/seed_conversion_rates.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import func, select  # noqa: E402

from backend.db.models import ConversionRate, NutritionIngredient  # noqa: E402
from backend.db.postgres import async_session  # noqa: E402

# ─── Dữ liệu seed ────────────────────────────────────────────────────────────
# (ingredient_name_pattern, grams_per_unit_per_ml)
# unit_name cố định = 'ml' cho tất cả
LIQUID_RATES = [
    ("Sữa bò tươi%", 1.03),        # sữa bò: 1 ml ≈ 1.03 g
    ("Dầu%", 0.92),               # dầu ăn chung: 1 ml ≈ 0.92 g
    ("Dầu cám gạo%", 0.92),
    ("Dầu thảo mộc%", 0.92),
    ("Nước mắm loại I%", 1.20),    # nước mắm đậm: 1 ml ≈ 1.2 g
    ("Nước mắm cá%", 1.20),
    ("Nước cam tươi%", 1.04),
]

# Fallback chung: 1 ml nước = 1.0 g (rate riêng khi không tra được)
FALLBACK_WATER_RATE = 1.0


async def _find_ingredient_id(session, pattern: str) -> str | None:
    """Tìm ingredient_id đầu tiên có tên khớp ILIKE pattern (ưu tiên source vnfood)."""
    stmt = (
        select(NutritionIngredient.id)
        .where(NutritionIngredient.ingredient_name.ilike(pattern))
        .order_by(
            # Ưu tiên vnfood lên trước (true = 1 sort sau, nên NOT优先)
            (NutritionIngredient.source == "vnfood").desc(),
            func.length(NutritionIngredient.ingredient_name).asc(),  # tên ngắn trước
        )
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def seed() -> None:
    async with async_session() as session:
        # 1. Fallback nước (ingredient_id = NULL) — chỉ insert 1 lần
        existing_fallback = await session.execute(
            select(ConversionRate).where(
                ConversionRate.ingredient_id.is_(None),
                ConversionRate.unit_name == "ml",
            )
        )
        if existing_fallback.scalar_one_or_none() is None:
            session.add(
                ConversionRate(
                    ingredient_id=None,
                    unit_name="ml",
                    grams_per_unit=FALLBACK_WATER_RATE,
                )
            )
            print("✅ Fallback nước: 1 ml = 1.0 g")

        # 2. Rate riêng cho từng chất lỏng
        for pattern, rate in LIQUID_RATES:
            ingredient_id = await _find_ingredient_id(session, pattern)
            if ingredient_id is None:
                print(f"  ⚠️  Không tìm thấy nguyên liệu khớp '{pattern}' — bỏ qua")
                continue

            # Tránh insert trùng (cùng ingredient_id + unit_name)
            dup = await session.execute(
                select(ConversionRate).where(
                    ConversionRate.ingredient_id == ingredient_id,
                    ConversionRate.unit_name == "ml",
                )
            )
            if dup.scalar_one_or_none() is not None:
                print(f"  ⏭️  {pattern} đã có rate — bỏ qua")
                continue

            session.add(
                ConversionRate(
                    ingredient_id=ingredient_id,
                    unit_name="ml",
                    grams_per_unit=rate,
                )
            )
            print(f"✅ {pattern[:-1]} → 1 ml = {rate} g (id={ingredient_id[:8]})")

        await session.commit()
        print("\n✅ Seed xong conversion_rates")


if __name__ == "__main__":
    asyncio.run(seed())