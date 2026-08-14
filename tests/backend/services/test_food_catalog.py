"""Tests for the shared three-catalog food resolver."""

from types import SimpleNamespace

import pytest

from backend.services import food_catalog


def _dish(name: str = "Phở bò") -> SimpleNamespace:
    return SimpleNamespace(
        id="dish-id",
        dish_name=name,
        source="vnmeal",
        typical_grams=350.0,
        total_calories=420.0,
        total_protein_g=25.0,
        total_fat_g=12.0,
        total_carbs_g=55.0,
        total_fiber_g=2.0,
    )


def _ingredient(name: str = "Sữa bò tươi") -> SimpleNamespace:
    return SimpleNamespace(
        id="ingredient-id",
        ingredient_name=name,
        source="vnfood",
        gram=100.0,
        calories_per_g=0.6,
        protein_per_g=0.032,
        fat_per_g=0.035,
        carbs_per_g=0.048,
        fiber_per_g=0.0,
    )


def _nri_food(name: str = "Gạo tẻ") -> SimpleNamespace:
    return SimpleNamespace(
        id="nri-id",
        source_food_id=12,
        name_vi=name,
        food_code="01001",
        basis_grams=100.0,
        energy_kcal_per_100g=350.0,
        protein_g_per_100g=8.0,
        fat_g_per_100g=1.0,
        carbs_g_per_100g=78.0,
    )


@pytest.mark.asyncio
async def test_lookup_food_matches_queries_all_three_tables(monkeypatch) -> None:
    async def dish_exact(*_args, **_kwargs):
        return _dish()

    async def ingredient_exact(*_args, **_kwargs):
        return _ingredient()

    async def nri_exact(*_args, **_kwargs):
        return _nri_food()

    monkeypatch.setattr(food_catalog, "lookup_dish_exact", dish_exact)
    monkeypatch.setattr(food_catalog, "lookup_ingredient_text", ingredient_exact)
    monkeypatch.setattr(food_catalog, "lookup_nrihcm_food_exact", nri_exact)

    matches = await food_catalog.lookup_food_matches(object(), "món ăn")

    assert {match.catalog_type for match in matches} == {
        "vn_dish",
        "vn_ingredient",
        "nrihcm_food",
    }


def test_choose_food_match_prefers_reviewed_dish_over_raw_source() -> None:
    matches = [
        food_catalog.FoodMatch.from_row(_nri_food(), "nrihcm_food"),
        food_catalog.FoodMatch.from_row(_dish(), "vn_dish"),
    ]

    selected = food_catalog.choose_food_match(matches)

    assert selected.catalog_type == "vn_dish"


def test_choose_food_match_returns_none_for_same_priority_ambiguity() -> None:
    matches = [
        food_catalog.FoodMatch.from_row(_nri_food("Gạo tẻ A"), "nrihcm_food"),
        food_catalog.FoodMatch.from_row(_nri_food("Gạo tẻ B"), "nrihcm_food"),
    ]

    assert food_catalog.choose_food_match(matches) is None


def test_nrihcm_food_is_converted_from_100g_to_per_gram() -> None:
    match = food_catalog.FoodMatch.from_row(_nri_food(), "nrihcm_food")

    per_gram = food_catalog.match_to_per_gram(match)

    assert per_gram.calories_per_g == 3.5
    assert per_gram.protein_per_g == 0.08
    assert per_gram.source == "nrihcm_raw"
