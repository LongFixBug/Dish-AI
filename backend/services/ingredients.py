"""Service tìm nguyên liệu: ILIKE trước, thiếu → vector search fallback.

2-tier search theo plan:
  1. ILIKE substring — nhanh, bắt chính xác tên có chứa query.
  2. Nếu < threshold kết quả → sinh embedding query + cosine_distance → móc theo nghĩa.
Merge + dedupe theo id, giữ ILIKE lên đầu (ưu tiên match chính xác).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from sqlalchemy import func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import NutritionIngredient
from backend.services.embeddings import embed_query

# Số kết quả tối đa mặc định
DEFAULT_LIMIT = 8
# ILIKE cho ít hơn ngưỡng này mới fallback vector (tránh gọi embed khi đã đủ)
ILIKE_FALLBACK_THRESHOLD = 5


async def _search_ilike(
    session: AsyncSession, q: str, limit: int
) -> list[NutritionIngredient]:
    """Tier 1: ILIKE substring — nhanh, match tên chứa query."""
    stmt = (
        select(NutritionIngredient)
        .where(
            NutritionIngredient.item_type.in_(["ingredient", "fruit"])
            & func.vn_norm(NutritionIngredient.ingredient_name).op("ILIKE")(
                func.vn_norm(literal(f"%{q}%"))
            )
        )
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def _search_vector(
    session: AsyncSession, q: str, limit: int
) -> list[NutritionIngredient]:
    """Tier 2: vector theo nghĩa (cosine_distance).

    Bỏ qua yên lặng nếu embedding server không chạy — không crash API,
    ILIKE vẫn trả kết quả.
    """
    try:
        vec = await embed_query(q)
    except Exception:
        return []

    stmt = (
        select(NutritionIngredient)
        .where(
            NutritionIngredient.embedding.isnot(None)
            & NutritionIngredient.item_type.in_(["ingredient", "fruit"])
        )
        .order_by(NutritionIngredient.embedding.cosine_distance(vec))
        .limit(limit)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def search_ingredients(
    session: AsyncSession, q: str, limit: int = DEFAULT_LIMIT
) -> list[NutritionIngredient]:
    """Tìm nguyên liệu 2-tier: ILIKE + vector fallback, dedupe theo id.

    Args:
        q: text user gõ (1-2 chữ cũng OK).
        limit: số kết quả tối đa.

    Returns:
        list nguyên liệu, ILIKE hits lên đầu, vector hits bổ sung phía sau.
    """
    q = q.strip()
    if not q:
        return []

    ilike_hits = await _search_ilike(session, q, limit)

    if len(ilike_hits) >= ILIKE_FALLBACK_THRESHOLD:
        return ilike_hits[:limit]

    # Fallback vector để bổ sung kết quả theo nghĩa
    seen_ids = {ing.id for ing in ilike_hits}
    need = limit - len(ilike_hits)
    # Lấy dư một chút rồi dedupe (vector có thể trùng ILIKE hoặc nhau)
    vector_hits = await _search_vector(session, q, need + 5)

    merged = list(ilike_hits)
    for ing in vector_hits:
        if ing.id not in seen_ids:
            merged.append(ing)
            seen_ids.add(ing.id)
        if len(merged) >= limit:
            break

    return merged[:limit]