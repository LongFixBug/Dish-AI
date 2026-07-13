"""Service 2-tier dish: lookup, compute, contribute.

Lookup: tìm institute (nutrition_ingredients source=vnmeal) trước, fallback
user-recipe (dishes JOIN dish_ingredients). Tái sử dụng calculate_totals
từ schemas/nutrition.py.

Compute/Contribute: ingredient_id + amount + unit → to_grams → NutritionPerGram →
calculate_ingredient_nutrition → calculate_totals.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from dataclasses import dataclass

from sqlalchemy import func, literal, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import Dish, DishIngredient, NutritionIngredient
from backend.services.conversions import to_grams
from schemas.nutrition import (
    Ingredient,
    NutritionPerGram,
    calculate_ingredient_nutrition,
    calculate_totals,
)


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _ingredient_to_per_gram(ing: NutritionIngredient) -> NutritionPerGram:
    """Map 1 dòng ORM NutritionIngredient → NutritionPerGram schema."""
    return NutritionPerGram(
        ingredient_name=ing.ingredient_name,
        calories_per_g=ing.calories_per_g,
        protein_per_g=ing.protein_per_g,
        fat_per_g=ing.fat_per_g,
        carbs_per_g=ing.carbs_per_g,
        fiber_per_g=ing.fiber_per_g,
        source=ing.source,
    )


@dataclass
class ComputedItem:
    """Kết quả tính cho 1 item: kèm flag assumed (fallback chuyển mL→g)."""

    ingredient_name: str
    grams: float
    per_gram: NutritionPerGram
    assumed: bool


# ─── Tier 1: Lookup ───────────────────────────────────────────────────────────


async def _lookup_institute(
    session: AsyncSession, name: str
) -> NutritionIngredient | None:
    """Tìm món ăn trong nutrition_ingredients (source=vnmeal) — authoritative."""
    stmt = (
        select(NutritionIngredient)
        .where(
            (NutritionIngredient.source == "vnmeal")
            & func.vn_norm(NutritionIngredient.ingredient_name).op("ILIKE")(
                func.vn_norm(literal(f"%{name}%"))
            )
        )
        .limit(1)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def _lookup_user_recipe(
    session: AsyncSession, name: str
) -> tuple[Dish, list[DishIngredient]] | None:
    """Tìm món trong dishes (user-contributed) + list DishIngredient của nó."""
    stmt_dish = (
        select(Dish)
        .where(
            func.vn_norm(Dish.dish_name).op("ILIKE")(
                func.vn_norm(literal(f"%{name}%"))
            )
        )
        .order_by(Dish.usage_count.desc())  # ưu tiên recipe được reuse nhiều
        .limit(1)
    )
    result = await session.execute(stmt_dish)
    dish = result.scalar_one_or_none()
    if dish is None:
        return None

    stmt_items = select(DishIngredient).where(DishIngredient.dish_id == dish.id)
    items = (await session.execute(stmt_items)).scalars().all()
    return dish, list(items)


async def lookup_dish(
    session: AsyncSession, name: str
) -> dict:
    """Tier 1: institute-first, fallback user-recipe. Trả dict match DishLookupResponse.

    Returns:
        dict với keys: exists, dish_name, source, status, dish_id, nutrition.
    """
    name = name.strip()

    # 1. Institute (dinh dưỡng tổng, gram chưa rõ — tính cho 100g mặc định)
    institute = await _lookup_institute(session, name)
    if institute is not None:
        per_gram = _ingredient_to_per_gram(institute)
        # Institute chỉ có per-gram; hiển thị cho 1 khẩu phần giả định 100g
        ing =Ingredient(name=institute.ingredient_name, estimated_grams=100.0)
        per_ing = calculate_ingredient_nutrition(ing, per_gram)
        totals = calculate_totals(institute.ingredient_name, [per_ing])
        return {
            "exists": True,
            "dish_name": institute.ingredient_name,
            "source": "institute",
            "status": "verified",
            "dish_id": None,
            "nutrition": totals,
        }

    # 2. User recipe (có công thức → tính tổng)
    recipe = await _lookup_user_recipe(session, name)
    if recipe is not None:
        dish, items = recipe
        return await _build_recipe_response(session, dish, items)

    # 3. Không có
    return {
        "exists": False,
        "dish_name": name,
        "source": None,
        "status": None,
        "dish_id": None,
        "nutrition": None,
    }


async def _build_recipe_response(
    session: AsyncSession, dish: Dish, items: list[DishIngredient]
) -> dict:
    """JOIN dish_ingredient → nutrition_ingredients, tính totals, trả dict."""
    per_ingredients = []
    missing: list[str] = []

    for di in items:
        # Lấy dinh dưỡng per-gram của ingredient
        r = await session.execute(
            select(NutritionIngredient).where(NutritionIngredient.id == di.ingredient_id)
        )
        ing = r.scalar_one_or_none()
        if ing is None:
            missing.append(f"<ingredient_id={di.ingredient_id}>")
            continue
        per_gram = _ingredient_to_per_gram(ing)
        i = Ingredient(name=ing.ingredient_name, estimated_grams=di.grams)
        per_ingredients.append(calculate_ingredient_nutrition(i, per_gram))

    totals = calculate_totals(dish.dish_name, per_ingredients, missing)
    return {
        "exists": True,
        "dish_name": dish.dish_name,
        "source": "user_recipe",
        "status": dish.status,
        "dish_id": dish.id,
        "nutrition": totals,
    }


# ─── Tier 2: Compute + Contribute ────────────────────────────────────────────


async def compute_nutrition(
    session: AsyncSession,
    dish_name: str,
    items: list,
) -> tuple:
    """Tính nutrition từ list RecipeItemInput (không lưu).

    Returns:
        (totals: NutritionTotals, assumed: list[tên nguyên liệu dùng fallback mL→g])
    """
    computed = await _resolve_items(session, items)
    per_ingredients = []
    assumed_names: list[str] = []

    for c in computed:
        i = Ingredient(name=c.ingredient_name, estimated_grams=c.grams)
        per_ingredients.append(calculate_ingredient_nutrition(i, c.per_gram))
        if c.assumed:
            assumed_names.append(c.ingredient_name)

    totals = calculate_totals(dish_name, per_ingredients)
    return totals, assumed_names


async def _resolve_items(
    session: AsyncSession, items: list
) -> list[ComputedItem]:
    """Mỗi RecipeItemInput → (grams + NutritionPerGram + assumed)."""
    out: list[ComputedItem] = []

    for item in items:
        r = await session.execute(
            select(NutritionIngredient).where(
                NutritionIngredient.id == item.ingredient_id
            )
        )
        ing = r.scalar_one_or_none()
        if ing is None:
            # Nguyên liệu không có trong DB → bỏ qua + ghi missing phía totals
            out.append(
                ComputedItem(
                    ingredient_name=f"<id={item.ingredient_id}>",
                    grams=0.0,
                    per_gram=NutritionPerGram(
                        ingredient_name="<not found>",
                        calories_per_g=0,
                        protein_per_g=0,
                        fat_per_g=0,
                        carbs_per_g=0,
                        fiber_per_g=0,
                    ),
                    assumed=False,
                )
            )
            continue

        grams, assumed = await to_grams(
            session, ing.id, item.amount, item.unit
        )
        out.append(
            ComputedItem(
                ingredient_name=ing.ingredient_name,
                grams=grams,
                per_gram=_ingredient_to_per_gram(ing),
                assumed=assumed,
            )
        )
    return out


async def contribute_dish(
    session: AsyncSession,
    dish_name: str,
    description: str | None,
    items: list,
    contributor_id: str | None,
) -> tuple:
    """Lưu recipe mới (status=draft) + tính nutrition.

    Returns:
        (dish_id, totals, assumed_names) hoặc raise ValueError nếu trùng tên.
    """
    # Check unique — equality sau vn_norm (không phân biệt dấu/hoa).
    # Dùng == (không ILIKE) vì không có wildcard, semantic đúng + sẵn sàng
    # expression index sau này.
    existing = await session.execute(
        select(Dish)
        .where(func.vn_norm(Dish.dish_name) == func.vn_norm(literal(dish_name)))
        .limit(1)
    )
    if existing.scalar_one_or_none() is not None:
        raise ValueError(f"Dish '{dish_name}' đã tồn tại")

    # INSERT Dish
    dish = Dish(
        dish_name=dish_name,
        description=description,
        status="draft",
        contributor_id=contributor_id,
        usage_count=0,
    )
    session.add(dish)
    await session.flush()  # lấy dish.id

    # Resolve grams cho từng item (trước khi INSERT để có totals chính xác)
    computed = await _resolve_items(session, items)

    # INSERT DishIngredient + tính totals song song (skip nguyên liệu không có)
    per_ingredients = []
    assumed_names: list[str] = []
    for item, c in zip(items, computed):
        if c.grams <= 0:
            continue
        session.add(
            DishIngredient(
                dish_id=dish.id,
                ingredient_id=item.ingredient_id,
                grams=c.grams,
            )
        )
        i = Ingredient(name=c.ingredient_name, estimated_grams=c.grams)
        per_ingredients.append(calculate_ingredient_nutrition(i, c.per_gram))
        if c.assumed:
            assumed_names.append(c.ingredient_name)

    totals = calculate_totals(dish_name, per_ingredients)
    await session.commit()

    return dish.id, totals, assumed_names