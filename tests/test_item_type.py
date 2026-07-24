"""Integration tests for the current dish/ingredient table boundary."""

from sqlalchemy import func, select

from backend.db.models import VnDish, VnIngredient
from backend.services.dishes import lookup_dish, lookup_ingredient


async def test_catalogs_are_stored_in_separate_tables(db_session) -> None:
    """Both catalogs must contain data after the current seed pipeline runs."""
    ingredient_count = await db_session.scalar(
        select(func.count()).select_from(VnIngredient)
    )
    dish_count = await db_session.scalar(select(func.count()).select_from(VnDish))

    assert ingredient_count and ingredient_count > 0
    assert dish_count and dish_count > 0


async def test_ingredient_lookup_excludes_dish_rows(db_session) -> None:
    """Ingredient lookup must return only supported ingredient item types."""
    result = await lookup_ingredient(db_session, "sua bo")

    assert result is not None
    assert result.item_type in {"ingredient", "fruit", "product"}


async def test_dish_lookup_returns_vn_dish_model(db_session) -> None:
    """Accent-insensitive dish lookup must stay inside the dish catalog."""
    result = await lookup_dish(db_session, "com suon")

    assert isinstance(result, VnDish)
    assert "sườn" in result.dish_name.casefold()
