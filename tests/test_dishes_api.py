"""Regression tests for the dish lookup API contract."""

from types import SimpleNamespace

from backend.api import dishes


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

    async def fake_lookup(_session, _name):
        return record

    monkeypatch.setattr(dishes, "lookup_dish", fake_lookup)

    response = await dishes.get_dish_lookup("Món Vision", object())

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

    async def fake_lookup(_session, _name):
        return record

    monkeypatch.setattr(dishes, "lookup_dish", fake_lookup)

    response = await dishes.get_dish_lookup(record.dish_name, object())
    nutrition = response["nutrition"]

    assert nutrition.total_calories == 250.0
    assert nutrition.total_grams == 0.0
    assert nutrition.per_100g_calories == 0.0
