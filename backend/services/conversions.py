"""Service chuyển đổi đơn vị thể tích → gram cho nguyên liệu.

VD: 1 ml sữa ≈ 1.03 g, 1 ml dầu ≈ 0.92 g.

Tra bảng conversion_rates theo ingredient_id + unit.
Không tìm thấy → fallback nước (1.0 g/ml) + flag assumed=True để API báo user.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import ConversionRate

# 1 ml nước ≈ 1.0 g (fallback khi không có rate riêng)
WATER_GRAMS_PER_ML = 1.0
# Đơn vị khối lượng — không cần chuyển, trả luôn
MASS_UNITS = {"g", "kg", "gram", "grams"}


async def to_grams(
    session: AsyncSession,
    ingredient_id: str,
    amount: float,
    unit: str,
) -> tuple[float, bool]:
    """Chuyển (amount, unit) sang gram.

    Args:
        ingredient_id: ID nguyên liệu để tra rate riêng (VD sữa).
        amount: số lượng (100, 150...).
        unit: 'g' | 'ml' | 'kg' ...

    Returns:
        (grams, assumed):
          - grams: số gram tương đương.
          - assumed: True nếu phải dùng fallback Wasser → cảnh báo user ước lượng.
    """
    unit = unit.strip().lower()

    # Đơn vị khối lượng → trả thẳng (kg → g)
    if unit in {"kg"}:
        return amount * 1000.0, False
    if unit in MASS_UNITS:
        return amount, False

    # Đơn vị thể tích (ml) → tra rate
    if unit in {"ml", "milliliter", "l", "liter"}:
        return await _convert_volume(session, ingredient_id, amount, unit)

    # Đơn vị không nhận diện → coi như gram, yên lặng
    # (sau này có thể mở rộng muỗng/chén)
    return amount, False


async def _convert_volume(
    session: AsyncSession,
    ingredient_id: str,
    amount: float,
    unit: str,
) -> tuple[float, bool]:
    """Tra conversion_rates → ước lượng nếu thiếu."""
    # Quy về ml trước (1 L = 1000 ml)
    if unit in {"l", "liter"}:
        ml = amount * 1000.0
    else:
        ml = amount

    # Tra rate riêng cho nguyên liệu này
    stmt = (
        select(ConversionRate)
        .where(
            (ConversionRate.ingredient_id == ingredient_id)
            & (ConversionRate.unit_name == "ml")
        )
        .limit(1)
    )
    result = await session.execute(stmt)
    rate = result.scalar_one_or_none()

    if rate is not None:
        return ml * rate.grams_per_unit, False

    # Không có rate riêng → tra fallback chung (ingredient_id IS NULL)
    stmt_fallback = (
        select(ConversionRate)
        .where(
            (ConversionRate.ingredient_id.is_(None))
            & (ConversionRate.unit_name == "ml")
        )
        .limit(1)
    )
    result = await session.execute(stmt_fallback)
    fallback = result.scalar_one_or_none()

    if fallback is not None:
        return ml * fallback.grams_per_unit, False

    # Tẹo rate → giả định nước (1.0 g/ml) + flag assumed
    return ml * WATER_GRAMS_PER_ML, True