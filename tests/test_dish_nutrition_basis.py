"""Institute dish nutrition is stored as source serving totals."""

from types import SimpleNamespace

from backend.services.dishes import _vn_dish_to_per_gram


def test_serving_totals_convert_using_the_recorded_serving_weight() -> None:
    dish = SimpleNamespace(
        dish_name="Phở bò",
        total_calories=600.0,
        total_protein_g=40.0,
        total_fat_g=20.0,
        total_carbs_g=75.0,
        total_fiber_g=7.5,
        typical_grams=500.0,
        source="vnmeal",
    )

    nutrition = _vn_dish_to_per_gram(dish)

    assert nutrition.calories_per_g == 1.2
    assert nutrition.protein_per_g == 0.08
    assert nutrition.carbs_per_g == 0.15
