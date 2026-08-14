"""Regression tests for the dish lookup API contract."""

from types import SimpleNamespace

from backend.api import dishes
from backend.api.dependencies import CurrentUser
from backend.services.food_catalog import FoodMatch

CALLER = CurrentUser(id="00000000-0000-0000-0000-000000000001", role="user")


async def test_lookup_preserves_vision_source_and_estimated_status(monkeypatch) -> None:
    """Vision-derived records must not be presented as verified institute data."""
    record = SimpleNamespace(
        id="dish-id",
        dish_name="Món Vision",
        typical_grams=200.0,
        total_calories=320.0,
        total_protein_g=15.0,
        total_fat_g=10.0,
        total_carbs_g=40.0,
        total_fiber_g=3.0,
        source="vision_auto",
    )

    match = FoodMatch.from_row(record, "vn_dish")

    async def fake_matches(*_args, **_kwargs):
        return [match]

    monkeypatch.setattr(dishes, "lookup_food_matches", fake_matches)

    response = await dishes.get_dish_lookup(CALLER, "Món Vision", object())

    assert response["source"] == "vision_auto"
    assert response["status"] == "estimated"


async def test_lookup_without_weight_does_not_invent_per_100g_values(
    monkeypatch,
) -> None:
    """Per-serving nutrition cannot be converted to per-100 g without a weight."""
    record = SimpleNamespace(
        id="dish-id",
        dish_name="Món chưa có khối lượng",
        typical_grams=None,
        total_calories=250.0,
        total_protein_g=12.0,
        total_fat_g=8.0,
        total_carbs_g=30.0,
        total_fiber_g=2.0,
        source="vnmeal",
    )

    match = FoodMatch.from_row(record, "vn_dish")

    async def fake_matches(*_args, **_kwargs):
        return [match]

    monkeypatch.setattr(dishes, "lookup_food_matches", fake_matches)

    response = await dishes.get_dish_lookup(CALLER, record.dish_name, object())
    nutrition = response["nutrition"]

    assert nutrition.total_calories == 250.0
    assert nutrition.total_grams == 0.0
    assert nutrition.per_100g_available is False
    assert nutrition.per_100g_calories == 0.0
    assert nutrition.catalog_coverage_score == nutrition.confidence_score == 1.0


async def test_lookup_returns_vn_ingredient_nutrition_at_100g(monkeypatch) -> None:
    record = SimpleNamespace(
        id="ingredient-id",
        ingredient_name="Sữa bò tươi",
        source="vnfood",
        gram=100.0,
        calories_per_g=0.6,
        protein_per_g=0.032,
        fat_per_g=0.035,
        carbs_per_g=0.048,
        fiber_per_g=0.0,
    )
    match = FoodMatch.from_row(record, "vn_ingredient")

    async def fake_matches(*_args, **_kwargs):
        return [match]

    monkeypatch.setattr(dishes, "lookup_food_matches", fake_matches)

    response = await dishes.get_dish_lookup(CALLER, "sữa bò tươi", object())

    assert response["catalog_type"] == "vn_ingredient"
    assert response["status"] == "reviewed"
    assert response["nutrition"].total_calories == 60.0


async def test_lookup_labels_crawled_nrihcm_data_as_raw(monkeypatch) -> None:
    record = SimpleNamespace(
        id="nri-id",
        source_food_id=12,
        name_vi="Gạo tẻ",
        basis_grams=100.0,
        energy_kcal_per_100g=350.0,
        protein_g_per_100g=8.0,
        fat_g_per_100g=1.0,
        carbs_g_per_100g=78.0,
    )
    match = FoodMatch.from_row(record, "nrihcm_food")

    async def fake_matches(*_args, **_kwargs):
        return [match]

    monkeypatch.setattr(dishes, "lookup_food_matches", fake_matches)

    response = await dishes.get_dish_lookup(CALLER, "gạo tẻ", object())

    assert response["source"] == "nrihcm_raw"
    assert response["status"] == "raw"
    assert response["nutrition"].total_calories == 350.0
