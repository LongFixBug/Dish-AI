"""Service lookup món + auto-add món mới — chỉ dùng vn_dishes & vn_ingredients.

Phiên bản mới (Jul 23): bỏ Dish/DishIngredient/NutritionIngredient/ConversionRate.
  - lookup_dish: tra vn_dishes (ILIKE → Qdrant vector fallback). Trả per-gram.
  - lookup_ingredient: tra vn_ingredients (ILIKE → vector). Dùng cho món ăn kèm
    (sữa hộp, nước uống) khi vn_dishes không có.
  - auto_add_dish: Vision nhận món mới → INSERT vào vn_dishes (source=vision_auto).
    Nutrition ước = 0 (chưa biết) — user/admin bổ sung sau. typical_grams theo Vision.
"""

from sqlalchemy import func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import VnDish, VnIngredient
from schemas.nutrition import NutritionPerGram


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _vn_dish_to_per_gram(vn: VnDish) -> NutritionPerGram:
    """Map VnDish → NutritionPerGram.

    Nếu typical_grams có → chia ra per-gram chính xác.
    Nếu typical_grams NULL → giữ nguyên RAW (per-serving), ghi source kèm note.
    """
    if vn.typical_grams and vn.typical_grams > 0:
        g = vn.typical_grams
        return NutritionPerGram(
            name=vn.dish_name,
            calories_per_g=vn.total_calories / g,
            protein_per_g=vn.total_protein_g / g,
            fat_per_g=vn.total_fat_g / g,
            carbs_per_g=vn.total_carbs_g / g,
            fiber_per_g=vn.total_fiber_g / g,
            source=vn.source,
        )
    # Không biết trọng lượng → giữ RAW (giá trị thực là per-serving)
    return NutritionPerGram(
        name=vn.dish_name,
        calories_per_g=vn.total_calories,
        protein_per_g=vn.total_protein_g,
        fat_per_g=vn.total_fat_g,
        carbs_per_g=vn.total_carbs_g,
        fiber_per_g=vn.total_fiber_g,
        source=f"{vn.source} (per serving)",
    )


def _vn_ingredient_to_per_gram(ing: VnIngredient) -> NutritionPerGram:
    """Map VnIngredient → NutritionPerGram (đã per-gram sẵn)."""
    return NutritionPerGram(
        name=ing.ingredient_name,
        calories_per_g=ing.calories_per_g,
        protein_per_g=ing.protein_per_g,
        fat_per_g=ing.fat_per_g,
        carbs_per_g=ing.carbs_per_g,
        fiber_per_g=ing.fiber_per_g,
        source=ing.source,
    )


def _has_weight(vn: VnDish) -> bool:
    """VnDish có trọng lượng chuẩn (typical_grams) không."""
    return bool(vn.typical_grams and vn.typical_grams > 0)


# ─── Tier 1: Lookup vn_dishes ────────────────────────────────────────────────


async def _lookup_institute_exact(
    session: AsyncSession, name: str
) -> VnDish | None:
    """Tìm món trong vn_dishes exact (vn_norm ==) — không phân biệt dấu/hoa."""
    exact = await session.execute(
        select(VnDish)
        .where(func.vn_norm(VnDish.dish_name) == func.vn_norm(literal(name)))
        .limit(1)
    )
    return exact.scalar_one_or_none()


async def _lookup_institute_by_qdrant(
    session: AsyncSession, name: str
) -> VnDish | None:
    """Qdrant vector search → tra lại vn_dishes exact bằng tên match."""
    try:
        from backend.services.qdrant_dishes import search_dish

        hits = await search_dish(name, limit=3)
        for hit in hits:
            matched = hit["dish_name"]
            vn = await _lookup_institute_exact(session, matched)
            if vn is not None:
                return vn
    except Exception:
        # Qdrant offline / embed server lỗi → bỏ qua yên lặng
        pass
    return None


async def lookup_dish(session: AsyncSession, name: str) -> VnDish | None:
    """Tìm món trong vn_dishes: exact → Qdrant semantic fallback.

    Không dùng ILIKE substring (tránh 'Phở bò' trúng 'Phở bò xào' sai món).
    Miss cả 2 → caller auto-add món mới.

    Returns:
        VnDish | None. None khi không có món exact và Qdrant cũng miss.
    """
    if not name or not name.strip():
        return None
    name = name.strip()

    vn = await _lookup_institute_exact(session, name)
    if vn is not None:
        return vn

    return await _lookup_institute_by_qdrant(session, name)


# ─── Lookup vn_ingredients (món ăn kèm / đồ uống) ────────────────────────────


async def _lookup_ingredient_ilike(
    session: AsyncSession, name: str
) -> VnIngredient | None:
    """ILIKE search trên vn_ingredients."""
    stmt = (
        select(VnIngredient)
        .where(
            VnIngredient.item_type.in_(["ingredient", "fruit", "product"])
            & func.vn_norm(VnIngredient.ingredient_name).op("ILIKE")(
                func.vn_norm(literal(f"%{name}%"))
            )
        )
        .order_by(func.char_length(VnIngredient.ingredient_name).asc())
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def _lookup_ingredient_vector(
    session: AsyncSession, name: str
) -> VnIngredient | None:
    """Vector fallback trên vn_ingredients (cosine_distance)."""
    try:
        from backend.services.embeddings import embed_query

        vec = await embed_query(name)
    except Exception:
        return None

    stmt = (
        select(VnIngredient)
        .where(
            VnIngredient.embedding.isnot(None)
            & VnIngredient.item_type.in_(["ingredient", "fruit", "product"])
        )
        .order_by(VnIngredient.embedding.cosine_distance(vec))
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def lookup_ingredient(session: AsyncSession, name: str) -> VnIngredient | None:
    """Tìm nguyên liệu / đồ uống trong vn_ingredients: ILIKE → vector."""
    if not name or not name.strip():
        return None

    ing = await _lookup_ingredient_ilike(session, name.strip())
    if ing is not None:
        return ing
    return await _lookup_ingredient_vector(session, name.strip())


# ─── Auto-add món mới vào vn_dishes ──────────────────────────────────────────


async def auto_add_dish(
    session: AsyncSession,
    dish_name: str,
    typical_grams: float | None,
    *,
    per_gram: NutritionPerGram | None = None,
) -> VnDish:
    """Vision nhận món chưa có DB → INSERT vào vn_dishes.

    Args:
        session: DB session.
        dish_name: tên món Vision nhận.
        typical_grams: gram Vision ước cho món (dùng làm khẩu phần chuẩn).
        per_gram: Vision ước lượng nutrition per-gram (tùy chọn). None → toàn 0.

    Returns:
        VnDish vừa insert (nutrition 0 nếu không ước được).
    """
    g = typical_grams if typical_grams and typical_grams > 0 else None

    if per_gram is not None and g:
        # bottom_dish lưu total = per_g × typical_grams (đảo ngược _vn_dish_to_per_gram)
        total_cal = per_gram.calories_per_g * g
        total_p = per_gram.protein_per_g * g
        total_f = per_gram.fat_per_g * g
        total_c = per_gram.carbs_per_g * g
        total_fb = per_gram.fiber_per_g * g
    else:
        total_cal = total_p = total_f = total_c = total_fb = 0.0

    dish = VnDish(
        dish_name=dish_name,
        total_calories=round(total_cal, 1),
        total_protein_g=round(total_p, 1),
        total_fat_g=round(total_f, 1),
        total_carbs_g=round(total_c, 1),
        total_fiber_g=round(total_fb, 1),
        typical_grams=g,
        source="vision_auto",
    )
    session.add(dish)
    await session.flush()

    # Index vào Qdrant (fire-and-forget) để lần sau vector search tìm được
    try:
        import asyncio as _asyncio

        from backend.services.qdrant_dishes import index_one_dish

        _asyncio.create_task(index_one_dish(str(dish.id), dish_name))
    except Exception:
        pass

    return dish


# ─── Auto-update typical_grams cho món DB thiếu trọng lượng ──────────────────


async def auto_update_grams(
    session: AsyncSession, vn: VnDish, gram_vision: float
) -> None:
    """Món có trong DB nhưng thiếu typical_grams → lưu gram_vision làm chuẩn.

    Per plan: Vision luôn chốt gram. DB thiếu gram → gram Vision thành typical_grams
    cho món đó (lần sau có sẵn, không phải đoán lại). Nutrition giữ raw = total
    (coi gram_vision = 1 khẩu phần chuẩn).
    """
    if not gram_vision or gram_vision <= 0:
        return
    await session.execute(
        VnDish.__table__.update()
        .where(VnDish.id == vn.id)
        .where(VnDish.typical_grams.is_(None))
        .values(typical_grams=round(gram_vision, 1))
    )
    vn.typical_grams = round(gram_vision, 1)