"""Look up reviewed dishes and ingredients in the local catalogs."""

import re
import unicodedata

from sqlalchemy import func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import VnDish, VnIngredient
from backend.services.vector_catalog import CatalogType, search_catalog
from schemas.nutrition import NutritionPerGram

# Nutrition mapping helpers


def _vn_dish_to_per_gram(vn: VnDish) -> NutritionPerGram:
    """Convert source serving totals to per-gram values when weight is known."""
    if not _has_weight(vn):
        raise ValueError("Không thể tính dinh dưỡng trên gram khi thiếu typical_grams")

    grams = float(vn.typical_grams)
    return NutritionPerGram(
        name=vn.dish_name,
        calories_per_g=vn.total_calories / grams,
        protein_per_g=vn.total_protein_g / grams,
        fat_per_g=vn.total_fat_g / grams,
        carbs_per_g=vn.total_carbs_g / grams,
        fiber_per_g=vn.total_fiber_g / grams,
        source=vn.source,
    )


def _vn_ingredient_to_per_gram(ing: VnIngredient) -> NutritionPerGram:
    """Map an ingredient row whose nutrients are already stored per gram."""
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
    """Return whether the dish has a usable reference serving weight."""
    return bool(vn.typical_grams and vn.typical_grams > 0)


def _has_nutrition(vn: VnDish) -> bool:
    """Return whether the row contains at least one positive nutrient value."""
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


# Reviewed dish lookup


_DISH_FAMILY_TOKENS = {
    "banh", "bun", "canh", "chao", "com", "goi", "hu", "lau", "mi",
    "pho", "tieu", "xoi",
}
_MENU_STOP_TOKENS = {"cac", "kem", "kep", "loai", "mon", "va", "voi"}
QDRANT_CANDIDATE_LIMIT = 10


def _menu_tokens(name: str) -> set[str]:
    """Normalize a Vietnamese dish name into accent-insensitive lexical tokens."""
    normalized = unicodedata.normalize("NFKD", name.casefold())
    ascii_name = "".join(
        char for char in normalized if not unicodedata.combining(char)
    ).replace("đ", "d")
    return set(re.findall(r"[a-z0-9]+", ascii_name)) - _MENU_STOP_TOKENS


def _is_semantic_candidate_compatible(query: str, candidate: str) -> bool:
    """Require semantic candidates to share a compatible lexical dish family."""
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
    """Find one reviewed dish by accent- and case-insensitive normalized name."""
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


async def _lookup_institute_by_vector(
    session: AsyncSession, name: str
) -> VnDish | None:
    """Resolve Qdrant candidates through authoritative PostgreSQL UUIDs."""
    try:
        hits = await search_catalog(
            name,
            CatalogType.DISH,
            limit=QDRANT_CANDIDATE_LIMIT,
        )
        compatible_ids = [
            hit.record_id
            for hit in hits
            if _is_semantic_candidate_compatible(name, hit.name)
        ]
        if not compatible_ids:
            return None
        result = await session.execute(
            select(VnDish)
            .where(VnDish.id.in_(compatible_ids))
        )
        by_id = {str(candidate.id): candidate for candidate in result.scalars().all()}
        for hit in hits:
            candidate = by_id.get(hit.record_id)
            if candidate and _is_semantic_candidate_compatible(name, candidate.dish_name):
                return candidate
    except Exception:
        # Embedding service unavailable → preserve the exact-lookup result path.
        pass
    return None


async def lookup_dish(session: AsyncSession, name: str) -> VnDish | None:
    """Search reviewed dishes using PostgreSQL, then a guarded Qdrant fallback.

    Substring matching is intentionally excluded because a base dish such as
    ``Phở bò`` must not silently resolve to the composite ``Phở bò xào``.

    Returns:
        The best reviewed catalog row, or ``None`` when no safe match exists.
    """
    if not name or not name.strip():
        return None
    name = name.strip()

    vn = await _lookup_institute_exact(session, name)
    if vn is not None:
        return vn

    return await _lookup_institute_by_vector(session, name)


async def lookup_dish_exact(session: AsyncSession, name: str) -> VnDish | None:
    """Look up an exact normalized name without semantic fallback."""
    if not name or not name.strip():
        return None
    return await _lookup_institute_exact(session, name.strip())


# Ingredient, fruit, and packaged-product lookup


async def _lookup_ingredient_ilike(
    session: AsyncSession, name: str
) -> VnIngredient | None:
    """Find the shortest ingredient containing the normalized query."""
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
    """Match a complete normalized ingredient name before substring search."""
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
    """Resolve Qdrant ingredient candidates through PostgreSQL UUIDs."""
    try:
        hits = await search_catalog(name, CatalogType.INGREDIENT, limit=5)
    except Exception:
        return None
    if not hits:
        return None

    stmt = (
        select(VnIngredient)
        .where(
            VnIngredient.id.in_([hit.record_id for hit in hits])
            & VnIngredient.item_type.in_(["ingredient", "fruit", "product"])
        )
    )
    result = await session.execute(stmt)
    by_id = {str(ingredient.id): ingredient for ingredient in result.scalars().all()}
    return next((by_id[hit.record_id] for hit in hits if hit.record_id in by_id), None)


async def lookup_ingredient(session: AsyncSession, name: str) -> VnIngredient | None:
    """Search ingredients using PostgreSQL text lookup, then Qdrant fallback."""
    if not name or not name.strip():
        return None

    ing = await _lookup_ingredient_ilike(session, name.strip())
    if ing is not None:
        return ing
    return await _lookup_ingredient_vector(session, name.strip())


async def lookup_ingredient_text(
    session: AsyncSession, name: str
) -> VnIngredient | None:
    """Require an exact normalized name for side items and beverages."""
    if not name or not name.strip():
        return None
    return await _lookup_ingredient_exact(session, name.strip())
