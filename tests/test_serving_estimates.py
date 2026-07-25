"""Serving-size estimates must be reproducible and explicitly low-confidence."""

from backend.services.serving_estimates import (
    estimate_catalog_serving,
    estimate_serving_grams,
)


def test_noodle_soup_uses_a_large_bowl_profile() -> None:
    estimate = estimate_serving_grams("Phở bò tái", total_calories=450.0)

    assert estimate.category == "noodle_soup"
    assert 450.0 <= estimate.grams <= 650.0
    assert estimate.source == "nutrition_heuristic_v1"
    assert estimate.confidence < 0.7


def test_total_energy_adjusts_portion_inside_category_bounds() -> None:
    light = estimate_serving_grams("Cơm rau", total_calories=150.0)
    dense = estimate_serving_grams("Cơm chiên", total_calories=700.0)

    assert light.category == dense.category == "rice_meal"
    assert dense.grams > light.grams
    assert 300.0 <= dense.grams <= 550.0


def test_accented_dessert_name_selects_dessert_profile() -> None:
    estimate = estimate_serving_grams("Chè đậu đen", total_calories=260.0)

    assert estimate.category == "dessert"
    assert 120.0 <= estimate.grams <= 350.0


def test_dry_bun_is_not_misclassified_as_a_noodle_soup() -> None:
    estimate = estimate_serving_grams("Bún chả", total_calories=518.0)

    assert estimate.category == "dry_noodles"
    assert estimate.grams <= 450.0


def test_pha_lau_is_not_misclassified_as_hotpot() -> None:
    estimate = estimate_serving_grams("Phá lấu", total_calories=306.0)

    assert estimate.category == "protein_dish"
    assert estimate.grams < 500.0


def test_packaged_snack_uses_a_small_portion() -> None:
    estimate = estimate_serving_grams("Bim bim", total_calories=35.0)

    assert estimate.category == "snack"
    assert estimate.grams <= 75.0


def test_invalid_energy_uses_category_base_portion() -> None:
    estimate = estimate_serving_grams("Bánh bông lan", total_calories=0.0)

    assert estimate.category == "pastry"
    assert estimate.grams == 125.0


def test_unknown_dish_has_bounded_fallback_and_low_confidence() -> None:
    estimate = estimate_serving_grams("Món thử nghiệm", total_calories=350.0)

    assert estimate.category == "fallback"
    assert 100.0 <= estimate.grams <= 450.0
    assert estimate.confidence <= 0.25


def test_catalog_estimate_raises_coherent_portion_to_physical_floor() -> None:
    estimate = estimate_catalog_serving(
        "Bánh gà Hồng Mai",
        total_calories=1603.0,
        protein_g=70.0,
        fat_g=91.0,
        carbs_g=78.5,
        fiber_g=0.0,
    )

    assert estimate is not None
    assert estimate.grams == 250.0
    assert estimate.source == "nutrition_physical_floor_v1"
    assert estimate.confidence == 0.15
    assert 1603.0 / estimate.grams <= 8.5
    assert 70.0 + 91.0 + 78.5 <= estimate.grams


def test_catalog_estimate_keeps_normal_family_estimate() -> None:
    estimate = estimate_catalog_serving(
        "Phở bò",
        total_calories=450.0,
        protein_g=25.0,
        fat_g=12.0,
        carbs_g=60.0,
        fiber_g=4.0,
    )

    assert estimate is not None
    assert estimate.source == "nutrition_heuristic_v1"
    assert estimate.grams >= 450.0


def test_catalog_estimate_uses_low_confidence_floor_for_conflicting_nutrition() -> None:
    estimate = estimate_catalog_serving(
        "Kẹo sô cô la",
        total_calories=27.0,
        protein_g=3.0,
        fat_g=4.0,
        carbs_g=85.0,
        fiber_g=0.2,
    )

    assert estimate is not None
    assert estimate.grams == 100.0
    assert estimate.source == "nutrition_conflict_floor_v1"
    assert estimate.category == "physical_floor_energy_macro_mismatch"
    assert estimate.confidence == 0.05


def test_catalog_estimate_refuses_an_unbounded_conflict_floor() -> None:
    estimate = estimate_catalog_serving(
        "Món lỗi nguồn",
        total_calories=100.0,
        protein_g=3500.0,
        fat_g=0.0,
        carbs_g=0.0,
        fiber_g=0.0,
    )

    assert estimate is None
