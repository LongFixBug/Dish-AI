"""Ensure image analysis can use the crawled NRIHCM table as the third tier."""

from types import SimpleNamespace

import pytest

from backend.api import analyze


@pytest.mark.asyncio
async def test_image_item_resolution_uses_nrihcm_after_catalog_miss(monkeypatch) -> None:
    raw_food = SimpleNamespace(
        name_vi="Gạo tẻ",
        basis_grams=100.0,
        energy_kcal_per_100g=350.0,
        protein_g_per_100g=8.0,
        fat_g_per_100g=1.0,
        carbs_g_per_100g=78.0,
    )

    async def no_dish(*_args, **_kwargs):
        return None

    async def no_ingredient(*_args, **_kwargs):
        return None

    async def nri_match(*_args, **_kwargs):
        return raw_food

    monkeypatch.setattr(analyze, "lookup_dish", no_dish)
    monkeypatch.setattr(analyze, "lookup_ingredient_text", no_ingredient)
    monkeypatch.setattr(analyze, "lookup_nrihcm_food_exact", nri_match)

    item, resolved_name, portion_source = await analyze._resolve_dish_item(
        object(), "Gạo tẻ", 200.0, False
    )

    assert resolved_name == "Gạo tẻ"
    assert portion_source == "vision"
    assert item is not None
    assert item.found_in_db is True
    assert item.calories == 700.0


@pytest.mark.asyncio
async def test_image_item_resolution_uses_ingredient_for_main_item(monkeypatch) -> None:
    ingredient = SimpleNamespace(
        ingredient_name="Xoài chín",
        calories_per_g=0.6,
        protein_per_g=0.008,
        fat_per_g=0.004,
        carbs_per_g=0.15,
        fiber_per_g=0.018,
        source="vnfood",
    )

    async def no_dish(*_args, **_kwargs):
        return None

    async def ingredient_match(*_args, **_kwargs):
        return ingredient

    async def nri_must_not_run(*_args, **_kwargs):
        raise AssertionError("Đã tìm thấy vn_ingredients thì không cần raw fallback")

    monkeypatch.setattr(analyze, "lookup_dish", no_dish)
    monkeypatch.setattr(analyze, "lookup_ingredient_text", ingredient_match)
    monkeypatch.setattr(analyze, "lookup_nrihcm_food_exact", nri_must_not_run)

    item, resolved_name, portion_source = await analyze._resolve_dish_item(
        object(), "Xoài chín", 150.0, False
    )

    assert resolved_name == "Xoài chín"
    assert portion_source == "vision"
    assert item is not None
    assert item.found_in_db is True
    assert item.calories == 90.0
