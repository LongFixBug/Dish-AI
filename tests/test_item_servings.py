"""Tính lại dinh dưỡng khi user chỉnh khẩu phần riêng từng món."""

import pytest

from schemas.nutrition import calculate_adjusted_totals


BASE_ITEMS = [
    {
        "item_name": "Cơm sườn",
        "grams": 350.0,
        "calories": 539.0,
        "protein_g": 21.4,
        "fat_g": 14.2,
        "carbs_g": 81.4,
        "fiber_g": 0.7,
        "found_in_db": True,
    },
    {
        "item_name": "Canh cải trắng",
        "grams": 150.0,
        "calories": 45.0,
        "protein_g": 2.0,
        "fat_g": 1.0,
        "carbs_g": 8.0,
        "fiber_g": 1.0,
        "found_in_db": False,
    },
]


def test_adjusting_one_item_only_scales_that_items_nutrition() -> None:
    adjusted = calculate_adjusted_totals(BASE_ITEMS, [700.0, 150.0])

    assert adjusted["items"][0]["calories"] == 1078.0
    assert adjusted["items"][1]["calories"] == 45.0
    assert adjusted["total_grams"] == 850.0
    assert adjusted["total_calories"] == 1123.0
    assert adjusted["total_protein_g"] == 44.8


def test_adjusting_every_item_scales_each_from_its_own_original_weight() -> None:
    adjusted = calculate_adjusted_totals(BASE_ITEMS, [700.0, 300.0])

    assert adjusted["total_grams"] == 1000.0
    assert adjusted["total_calories"] == 1168.0
    assert adjusted["total_fat_g"] == 30.4
    assert adjusted["total_carbs_g"] == 178.8


def test_zero_original_weight_does_not_divide_by_zero() -> None:
    zero_item = {**BASE_ITEMS[0], "grams": 0.0}

    adjusted = calculate_adjusted_totals([zero_item], [100.0])

    assert adjusted["items"][0]["grams"] == 100.0
    assert adjusted["items"][0]["calories"] == 0.0


def test_adjusted_grams_must_match_item_count() -> None:
    with pytest.raises(ValueError, match="khớp số món"):
        calculate_adjusted_totals(BASE_ITEMS, [350.0])


def test_source_serving_without_weight_cannot_be_rescaled() -> None:
    source_serving = {
        **BASE_ITEMS[0],
        "nutrition_basis": "source_serving",
    }

    with pytest.raises(ValueError, match="thiếu khối lượng chuẩn"):
        calculate_adjusted_totals([source_serving], [500.0])
