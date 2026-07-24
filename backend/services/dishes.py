"""Service lookup món + auto-add món mới — chỉ dùng vn_dishes & vn_ingredients.

Phiên bản mới (Jul 23): bỏ Dish/DishIngredient/NutritionIngredient/ConversionRate.
  - lookup_dish: tra vn_dishes (ILIKE → Qdrant vector fallback). Trả per-gram.
  - lookup_ingredient: tra vn_ingredients (ILIKE → vector). Dùng cho món ăn kèm
    (sữa hộp, nước uống) khi vn_dishes không có.
  - auto_add_dish: Vision nhận món mới → INSERT tên, gram và tổng dinh dưỡng
    vào vn_dishes (source=vision_auto).
"""

import re
import unicodedata

from sqlalchemy import func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import VnDish, VnIngredient
from schemas.nutrition import NutritionPerGram, NutritionPerIngredient


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


def _has_nutrition(vn: VnDish) -> bool:
    """Bản ghi có số dinh dưỡng thực, không chỉ là tên Vision đã lưu trước đó."""
    return any(
        (value or 0) > 0
        for value in (
            vn.total_calories,
            vn.total_protein_g,
            vn.total_fat_g,
            vn.total_carbs_g,
            vn.total_fiber_g,
        )
    )


# ─── Tier 1: Lookup vn_dishes ────────────────────────────────────────────────


_DISH_FAMILY_TOKENS = {
    "banh", "bun", "canh", "chao", "com", "goi", "hu", "lau", "mi",
    "pho", "tieu", "xoi",
}
_MENU_STOP_TOKENS = {"cac", "kem", "kep", "loai", "mon", "va", "voi"}
QDRANT_CANDIDATE_LIMIT = 10


def _menu_tokens(name: str) -> set[str]:
    """Chuẩn hóa tên món thành token không dấu để so khớp lexical."""
    normalized = unicodedata.normalize("NFKD", name.casefold())
    ascii_name = "".join(
        char for char in normalized if not unicodedata.combining(char)
    ).replace("đ", "d")
    return set(re.findall(r"[a-z0-9]+", ascii_name)) - _MENU_STOP_TOKENS


def _is_semantic_candidate_compatible(query: str, candidate: str) -> bool:
    """Chỉ nhận vector candidate cùng họ món và chia sẻ đủ token menu."""
    query_tokens = _menu_tokens(query)
    candidate_tokens = _menu_tokens(candidate)
    if not query_tokens or not candidate_tokens:
        return False

    query_families = query_tokens & _DISH_FAMILY_TOKENS
    candidate_families = candidate_tokens & _DISH_FAMILY_TOKENS
    if query_families and candidate_families and query_families.isdisjoint(
        candidate_families
    ):
        return False

    required_shared = min(2, len(query_tokens))
    return len(query_tokens & candidate_tokens) >= required_shared


async def _lookup_institute_exact(
    session: AsyncSession, name: str
) -> VnDish | None:
    """Tìm món trong vn_dishes exact (vn_norm ==) — không phân biệt dấu/hoa."""
    exact = await session.execute(
        select(VnDish)
        .where(func.vn_norm(VnDish.dish_name) == func.vn_norm(literal(name)))
        .order_by(
            (VnDish.total_calories > 0).desc(),
            (VnDish.source == "vnmeal").desc(),
            VnDish.created_at.asc(),
        )
        .limit(1)
    )
    return exact.scalar_one_or_none()


async def _lookup_institute_by_qdrant(
    session: AsyncSession, name: str
) -> VnDish | None:
    """Qdrant vector search → tra lại vn_dishes exact bằng tên match."""
    try:
        from backend.services.qdrant_dishes import search_dish

        hits = await search_dish(name, limit=QDRANT_CANDIDATE_LIMIT)
        for hit in hits:
            matched = hit["dish_name"]
            if not _is_semantic_candidate_compatible(name, matched):
                continue
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
        VnDish | None. Bản ghi có dinh dưỡng được ưu tiên trước bản vision_auto rỗng.
    """
    if not name or not name.strip():
        return None
    name = name.strip()

    vn = await _lookup_institute_exact(session, name)
    if vn is not None:
        return vn

    return await _lookup_institute_by_qdrant(session, name)


async def lookup_dish_exact(session: AsyncSession, name: str) -> VnDish | None:
    """Tìm đúng tên món, dùng cho món phụ để tránh match sang món composite khác."""
    if not name or not name.strip():
        return None
    return await _lookup_institute_exact(session, name.strip())


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


async def _lookup_ingredient_exact(
    session: AsyncSession, name: str
) -> VnIngredient | None:
    """Tìm đúng tên ingredient, tránh tên ngắn match vào giữa từ khác."""
    stmt = (
        select(VnIngredient)
        .where(
            VnIngredient.item_type.in_(["ingredient", "fruit", "product"])
            & (
                func.vn_norm(VnIngredient.ingredient_name)
                == func.vn_norm(literal(name))
            )
        )
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


async def lookup_ingredient_text(
    session: AsyncSession, name: str
) -> VnIngredient | None:
    """Chỉ exact text cho món phụ; không substring/vector sang tên khác."""
    if not name or not name.strip():
        return None
    return await _lookup_ingredient_exact(session, name.strip())


# ─── Auto-add món mới vào vn_dishes ──────────────────────────────────────────


async def auto_add_dish(
    session: AsyncSession,
    dish_name: str,
    typical_grams: float | None,
    *,
    nutrition: NutritionPerIngredient | None = None,
) -> VnDish:
    """Vision nhận món chưa có DB → INSERT vào vn_dishes.

    Args:
        session: DB session.
        dish_name: tên món Vision nhận.
        typical_grams: gram Vision ước cho món (dùng làm khẩu phần chuẩn).
        nutrition: Tổng dinh dưỡng Vision ước lượng cho đúng khẩu phần trong ảnh.

    Returns:
        VnDish vừa insert hoặc bản vision_auto rỗng vừa được bổ sung nutrition.
    """
    g = typical_grams if typical_grams and typical_grams > 0 else None

    if nutrition is not None:
        total_cal = nutrition.calories
        total_p = nutrition.protein_g
        total_f = nutrition.fat_g
        total_c = nutrition.carbs_g
        total_fb = nutrition.fiber_g
    else:
        total_cal = total_p = total_f = total_c = total_fb = 0.0

    dish = await _lookup_institute_exact(session, dish_name)
    if dish is None:
        dish = VnDish(dish_name=dish_name)
        session.add(dish)

    if not _has_nutrition(dish):
        dish.total_calories = round(total_cal, 1)
        dish.total_protein_g = round(total_p, 1)
        dish.total_fat_g = round(total_f, 1)
        dish.total_carbs_g = round(total_c, 1)
        dish.total_fiber_g = round(total_fb, 1)
        dish.typical_grams = g
        dish.source = "vision_auto"

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
