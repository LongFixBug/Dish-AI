"""Tests for cleaning source ingredient display names."""

from backend.services.ingredient_names import (
    clean_ingredient_name,
    clean_ingredient_name_batch,
)
from scripts.parse_vn_foods import parse_food_item


def test_clean_ingredient_name_removes_nested_english_parenthetical() -> None:
    assert clean_ingredient_name("Sữa bò tươi (Milk cow, fresh (Fluid))") == "Sữa bò tươi"


def test_clean_ingredient_name_keeps_vietnamese_parenthetical() -> None:
    name = "Bánh đa (đỏ, trắng), luộc (Vietnamese style rice noodles (flat), boiled)"

    assert clean_ingredient_name(name) == "Bánh đa (đỏ, trắng), luộc"


def test_clean_ingredient_name_keeps_vietnamese_qualifier_before_english() -> None:
    name = "Nước mắm cá (loại đặc biệt) (Fish sauce (high quality))"

    assert clean_ingredient_name(name) == "Nước mắm cá (loại đặc biệt)"


def test_clean_ingredient_name_removes_mixed_english_translation() -> None:
    name = "Ốc bươu, luộc (Snail, bươu, boiled)"

    assert clean_ingredient_name(name) == "Ốc bươu, luộc"


def test_clean_ingredient_name_keeps_mixed_vietnamese_qualifier() -> None:
    name = "Nhút (dưa muối từ mít non, lá đậu xanh non...)"

    assert clean_ingredient_name(name) == name


def test_clean_ingredient_name_normalizes_whitespace_without_english() -> None:
    assert clean_ingredient_name("  Lá me,   tươi ") == "Lá me, tươi"


def test_clean_ingredient_name_does_not_translate_or_drop_brand_names() -> None:
    assert clean_ingredient_name("Kem que Merino Cacao - Sô cô la") == (
        "Kem que Merino Cacao - Sô cô la"
    )


def test_clean_ingredient_name_batch_disambiguates_collisions_without_dropping_rows() -> None:
    records = [
        ("id-a", "Mít khô (Dried jackfruit)", "vnfood"),
        ("id-b", "Mít khô (Jackfruit, dried)", "vnfood"),
    ]

    assert clean_ingredient_name_batch(records) == {
        "id-a": "Mít khô",
        "id-b": "Mít khô [mẫu 2]",
    }


def test_vn_food_parser_emits_clean_name_and_100g_basis() -> None:
    item = {
        "name_vi": "Sữa bò tươi",
        "name_en": "Milk cow, fresh (Fluid)",
        "nutrition": [
            {"name_en": "Protein", "value": 3.2, "unit": "g"},
            {"name_en": "Total lipid (Fat)", "value": 3.5, "unit": "g"},
            {"name_en": "Carbohydrate by difference", "value": 4.8, "unit": "g"},
        ],
    }

    parsed = parse_food_item(item)

    assert parsed["ingredient_name"] == "Sữa bò tươi"
    assert parsed["gram"] == 100.0
