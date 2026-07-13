"""Integration tests: trust-score Option 1 (tăng usage_count + trust_score runtime).

Mỗi lookup user-recipe trúng → usage_count +1 (commit explicit vì get_session
không auto-commit). trust_score = compute_trust(usage_count, status):
  verified → 1.0
  draft   → min(0.9, 0.3 + usage_count×0.03)  (cap 0.9, draft < verified luôn)

trust_score (DishLookupResponse) ≠ confidence_score (NutritionTotals, data-coverage).
"""

import pytest
from sqlalchemy import delete, select

from backend.db.models import Dish, DishIngredient
from backend.services.dishes import compute_trust, contribute_dish, lookup_dish
from backend.services.ingredients import search_ingredients
from tests.conftest import db_session  # noqa: F401  (fixture)

CLEANUP_TAG = "test-trust-cleanup"


async def _cleanup(session) -> None:
    """Xóa mọi Dish test theo contributor_id tag (DishIngredient trước, Dish sau)."""
    test_ids = select(Dish.id).where(Dish.contributor_id == CLEANUP_TAG)
    await session.execute(
        delete(DishIngredient).where(DishIngredient.dish_id.in_(test_ids))
    )
    await session.execute(delete(Dish).where(Dish.contributor_id == CLEANUP_TAG))
    await session.commit()


async def _get_ingredient_id(session) -> str:
    """Lấy 1 ingredient_id thật (thịt nạc) để contribute hợp lệ."""
    found = await search_ingredients(session, "thịt nạc", limit=1)
    assert len(found) > 0, "cần ingredient 'thịt nạc' để test contribute"
    return str(found[0].id)


# ─── Helper pure function ─────────────────────────────────────────────────────


def test_compute_trust_ordering() -> None:
    """compute_trust: draft+0 < draft+5 < draft+20(cap 0.9) < verified."""
    assert compute_trust(0, "draft") == pytest.approx(0.3)
    assert compute_trust(5, "draft") == pytest.approx(0.45)
    assert compute_trust(20, "draft") == pytest.approx(0.9)
    assert compute_trust(99, "draft") == pytest.approx(0.9)  # cap
    assert compute_trust(0, "verified") == 1.0
    assert compute_trust(100, "verified") == 1.0
    # ordering
    assert compute_trust(0, "draft") < compute_trust(5, "draft")
    assert compute_trust(99, "draft") < compute_trust(0, "verified")


def test_compute_trust_unknown_status() -> None:
    """Status lạ → fallback 0.3."""
    assert compute_trust(10, None) == 0.3
    assert compute_trust(10, "weird") == 0.3


# ─── Lookup tăng usage_count + trust_score ────────────────────────────────────


async def test_contribute_then_lookup_increments_usage(db_session) -> None:
    """Contribute dish mới → lookup → usage_count=1, trust_score≈0.33."""
    ing_id = await _get_ingredient_id(db_session)
    dish_name = "test trust bun chay 9f3k"
    dish_id, _t, _a = await contribute_dish(
        db_session,
        dish_name=dish_name,
        description="pytest trust cleanup",
        items=[__import__("schemas.dish", fromlist=["RecipeItemInput"]).RecipeItemInput(
            ingredient_id=ing_id, amount=100, unit="g"
        )],
        contributor_id=CLEANUP_TAG,
    )
    assert dish_id is not None

    # Tag dish bằng contributor_id để cleanup (contribute đã set contributor_id)
    result = await lookup_dish(db_session, dish_name)
    assert result["source"] == "user_recipe"
    assert result["status"] == "draft"
    assert result["trust_score"] == pytest.approx(0.3 + 1 * 0.03)  # 0.33

    # Re-query Dish: usage_count=1 (increment + commit thành công)
    row = (
        await db_session.execute(
            select(Dish.usage_count).where(Dish.id == dish_id)
        )
    ).scalar_one()
    assert row == 1

    await _cleanup(db_session)


async def test_second_lookup_increments_again(db_session) -> None:
    """Lookup lần 2 → usage_count=2, trust_score tăng (0.36 > 0.33)."""
    ing_id = await _get_ingredient_id(db_session)
    dish_name = "test trust pho bo 2k7"
    dish_id, _t, _a = await contribute_dish(
        db_session,
        dish_name=dish_name,
        description="pytest trust cleanup",
        items=[__import__("schemas.dish", fromlist=["RecipeItemInput"]).RecipeItemInput(
            ingredient_id=ing_id, amount=100, unit="g"
        )],
        contributor_id=CLEANUP_TAG,
    )

    await lookup_dish(db_session, dish_name)  # usage 0→1, trust 0.33
    result2 = await lookup_dish(db_session, dish_name)  # usage 1→2, trust 0.36

    assert result2["trust_score"] == pytest.approx(0.3 + 2 * 0.03)  # 0.36
    assert result2["trust_score"] > 0.33  # tăng so với lookup lần 1

    row = (
        await db_session.execute(
            select(Dish.usage_count).where(Dish.id == dish_id)
        )
    ).scalar_one()
    assert row == 2

    await _cleanup(db_session)


# ─── Institute: trust=1.0, KHÔNG increment ────────────────────────────────────


async def test_institute_lookup_trust_1(db_session) -> None:
    """Lookup institute ('cơm sườn') → trust_score=1.0, source=institute.

    Institute là NutritionIngredient (item_type=dish), không phải Dish row →
    không có usage_count để tăng.
    """
    result = await lookup_dish(db_session, "com suon")
    assert result["source"] == "institute"
    assert result["trust_score"] == 1.0


# ─── Not found: trust=None ────────────────────────────────────────────────────


async def test_trust_none_when_not_found(db_session) -> None:
    """Lookup món không tồn tại → exists=False, trust_score=None, source=None."""
    result = await lookup_dish(db_session, "zzz món không tồn tại xyz 9f3k")
    assert result["exists"] is False
    assert result["trust_score"] is None
    assert result["source"] is None
