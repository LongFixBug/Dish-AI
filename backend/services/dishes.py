"""Look up reviewed dishes and ingredients in the local catalogs."""

import re
import unicodedata
import logging

from sqlalchemy import func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import VnDish, VnIngredient
from backend.services.vector_catalog import CatalogType, search_catalog
from schemas.nutrition import NutritionPerGram

logger = logging.getLogger("foodai")

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


CATALOG_PORTION_CONFIDENCE_THRESHOLD = 0.85
BANH_MI_PORTION_RANGE = (150.0, 200.0)


def resolve_catalog_portion_grams(
    dish_name: str,
    catalog_grams: float,
    vision_grams: float,
    vision_confidence: float,
) -> tuple[float, str]:
    """Choose a safe portion source for a known catalog dish.

    Catalog serving is the default. Vision may adjust it only when it reports
    a high-confidence portion inside a family bound. Bánh mì is intentionally
    capped at 150–200 g; a guess such as 250 g is ignored.
    """
    default = max(0.0, float(catalog_grams))
    candidate = max(0.0, float(vision_grams))
    if (
        candidate <= 0
        or vision_confidence < CATALOG_PORTION_CONFIDENCE_THRESHOLD
    ):
        return default, "catalog_default"

    normalized = unicodedata.normalize("NFKD", dish_name.casefold())
    normalized = "".join(
        char for char in normalized if not unicodedata.combining(char)
    ).replace("đ", "d")
    if "banh mi" in normalized:
        minimum, maximum = BANH_MI_PORTION_RANGE
    else:
        minimum, maximum = default * 0.75, default * 1.25

    if minimum <= candidate <= maximum:
        return round(candidate, 1), "vision"
    return default, "catalog_default"


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
_CANONICAL_FAMILY_NAMES = {
    ("banh", "mi"): "Bánh mì",
    ("banh", "cuon"): "Bánh cuốn",
    ("banh", "xeo"): "Bánh xèo",
    ("bun", "cha"): "Bún chả",
    ("com", "tam"): "Cơm tấm",
    ("pho", "bo"): "Phở bò",
    ("pho", "ga"): "Phở gà",
    ("xoi", "xeo"): "Xôi xéo",
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


def dish_family_query(name: str) -> str:
    """Extract the broad menu family used to build a visual shortlist.

    ``Bánh mì thịt nguội`` becomes ``Bánh mì`` and ``Bánh cuốn thịt`` becomes
    ``Bánh cuốn``. The query is intentionally kept in Vietnamese so the
    embedding model can retrieve all reviewed variants in that family.
    """
    words = re.findall(r"\S+", name.strip())
    # Two leading menu words are a stable broad prior for Vietnamese dish
    # names: “bánh mì”, “bánh cuốn”, “bún bò”, “cơm tấm”, “phở bò”, ...
    # Keeping only this prefix prevents fillings such as “thịt nguội chà bông”
    # from over-constraining the Qdrant shortlist.
    if len(words) < 2:
        return name.strip()
    normalized_prefix = tuple(
        "".join(
            char
            for char in unicodedata.normalize("NFKD", word.casefold())
            if not unicodedata.combining(char)
        ).replace("đ", "d")
        for word in words[:2]
    )
    return _CANONICAL_FAMILY_NAMES.get(
        normalized_prefix,
        " ".join(words[:2]),
    )


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
    candidates = await _lookup_institute_candidates_by_vector(session, name)
    return candidates[0] if candidates else None


async def _lookup_institute_candidates_by_vector(
    session: AsyncSession,
    name: str,
    *,
    limit: int = QDRANT_CANDIDATE_LIMIT,
) -> list[VnDish]:
    """Return compatible reviewed dish candidates in Qdrant score order.

    Chỉ nuốt lỗi của Qdrant/embedding server — đó là index phụ, hỏng thì vẫn
    còn đường tra chính xác. Lỗi PostgreSQL phải nổi lên: nuốt luôn sẽ biến sự
    cố DB thành "món này không có trong catalog" và trả về số Vision đoán bừa.
    """
    try:
        hits = await search_catalog(
            name,
            CatalogType.DISH,
            limit=limit,
        )
    except Exception:
        logger.warning(
            "Semantic dish lookup unavailable for %r; continuing without candidates",
            name,
            exc_info=True,
        )
        return []

    compatible_hits = [
        hit for hit in hits if _is_semantic_candidate_compatible(name, hit.name)
    ]
    if not compatible_hits:
        return []
    result = await session.execute(select(VnDish).where(
        VnDish.id.in_([hit.record_id for hit in compatible_hits])
    ))
    by_id = {str(candidate.id): candidate for candidate in result.scalars().all()}
    return [by_id[hit.record_id] for hit in compatible_hits if hit.record_id in by_id]


async def lookup_dish_candidates(
    session: AsyncSession,
    family_name: str,
    *,
    limit: int = QDRANT_CANDIDATE_LIMIT,
) -> list[VnDish]:
    """Return a short catalog shortlist for a broad dish family."""
    if not family_name or not family_name.strip():
        return []
    return await _lookup_institute_candidates_by_vector(
        session,
        family_name.strip(),
        limit=limit,
    )


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
        logger.warning(
            "Semantic ingredient lookup unavailable for %r; continuing without it",
            name,
            exc_info=True,
        )
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
