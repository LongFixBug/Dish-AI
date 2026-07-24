"""Integration tests for accent-insensitive catalog lookup."""

from backend.services.dishes import lookup_dish, lookup_ingredient


async def test_lookup_dish_ignores_vietnamese_diacritics(db_session) -> None:
    result = await lookup_dish(db_session, "com suon")

    assert result is not None
    assert "sườn" in result.dish_name.casefold()


async def test_lookup_ingredient_ignores_vietnamese_diacritics(db_session) -> None:
    result = await lookup_ingredient(db_session, "sua bo")

    assert result is not None
    assert "sữa bò" in result.ingredient_name.casefold()
