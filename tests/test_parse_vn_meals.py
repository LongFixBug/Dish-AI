"""The Institute meal endpoint reports nutrition for a dish serving."""

from scripts.parse_vn_foods import parse_food_item, parse_meal_item
from scripts.recreate_vn_dishes import serving_totals


def test_meal_parser_preserves_source_serving_totals() -> None:
    parsed = parse_meal_item({
        "name_vi": "Phở thử nghiệm",
        "total_energy": 450,
        "nutritional_components": [
            {"nameEn": "Protein", "amount": 30, "unit_name": "g"},
            {"nameEn": "Lipid", "amount": 12, "unit_name": "g"},
            {"nameEn": "Carbohydrate", "amount": 60, "unit_name": "g"},
            {"nameEn": "Fiber", "amount": 3, "unit_name": "g"},
        ],
    })

    assert parsed is not None
    assert parsed["calories_per_serving"] == 450.0
    assert parsed["protein_per_serving_g"] == 30.0
    assert "calories_per_g" not in parsed


def test_recreate_supports_the_legacy_meal_export_without_reinterpreting_it() -> None:
    legacy_item = {
        "calories_per_g": 4.5,
        "protein_per_g": 0.3,
        "fat_per_g": 0.12,
        "carbs_per_g": 0.6,
        "fiber_per_g": 0.03,
    }

    assert serving_totals(legacy_item) == (450.0, 30.0, 12.0, 60.0, 3.0)


def test_food_parser_clamps_tiny_negative_rounding_artifacts() -> None:
    parsed = parse_food_item({
        "name_vi": "Thịt ngan luộc",
        "nutrition": [
            {"name_en": "Protein", "value": 23.68, "unit": "g"},
            {"name_en": "Total lipid (Fat)", "value": 33.96, "unit": "g"},
            {
                "name_en": "Carbohydrate by difference",
                "value": -0.03,
                "unit": "g",
            },
        ],
    })

    assert parsed is not None
    assert parsed["carbs_per_g"] == 0.0
