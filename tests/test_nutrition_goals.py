"""Tests for the evidence-labelled nutrition goal calculator."""

import pytest
from pydantic import ValidationError

from backend.services.nutrition_goals import calculate_nutrition_goal
from schemas.nutrition_goals import NutritionGoalRequest


def _request(**overrides: object) -> NutritionGoalRequest:
    values: dict[str, object] = {
        "age": 30,
        "sex": "male",
        "height_cm": 170,
        "weight_kg": 70,
        "activity_level": "moderate",
        "goal": "lose",
        "target_weight_kg": 65,
        "target_days": 90,
    }
    values.update(overrides)
    return NutritionGoalRequest.model_validate(values)


def test_goal_calculation_uses_target_weight_and_duration() -> None:
    short = calculate_nutrition_goal(_request(target_days=45))
    long = calculate_nutrition_goal(_request(target_days=180))

    assert short.maintenance_calories == long.maintenance_calories
    assert short.target_calories < long.target_calories
    assert short.goal_delta_calories < long.goal_delta_calories


def test_maintenance_goal_does_not_apply_weight_delta() -> None:
    result = calculate_nutrition_goal(
        _request(goal="maintain", target_weight_kg=90, target_days=30)
    )

    assert result.target_calories == result.maintenance_calories
    assert result.goal_delta_calories == 0


def test_macro_targets_depend_on_body_weight_and_target_calories() -> None:
    lighter = calculate_nutrition_goal(_request(weight_kg=55, target_weight_kg=50))
    heavier = calculate_nutrition_goal(_request(weight_kg=90, target_weight_kg=85))

    assert heavier.protein_g.target > lighter.protein_g.target
    assert heavier.target_calories > lighter.target_calories


def test_non_matching_goal_and_target_weight_is_rejected() -> None:
    with pytest.raises(ValueError, match="target_weight_kg"):
        calculate_nutrition_goal(
            _request(goal="lose", weight_kg=70, target_weight_kg=75)
        )


def test_medical_or_pregnancy_flags_require_review() -> None:
    result = calculate_nutrition_goal(
        _request(medical_conditions=["tiểu đường"])
    )

    assert result.safety_status == "review_required"
    assert result.warnings


def test_adult_boundary_is_valid_but_child_is_rejected() -> None:
    assert NutritionGoalRequest.model_validate(
        _request(age=18).model_dump()
    ).age == 18

    with pytest.raises(ValidationError):
        NutritionGoalRequest.model_validate(_request(age=17).model_dump())


def test_target_calories_are_bounded_and_emit_warning() -> None:
    result = calculate_nutrition_goal(
        _request(weight_kg=150, target_weight_kg=50, target_days=1)
    )

    assert result.target_calories >= 1200
    assert any("giới hạn" in warning.lower() for warning in result.warnings)


def test_macro_ranges_remain_ordered_for_a_large_body_weight() -> None:
    result = calculate_nutrition_goal(
        _request(weight_kg=300, target_weight_kg=290, target_days=180)
    )

    assert result.protein_g.min <= result.protein_g.target <= result.protein_g.max


def test_capping_the_daily_rate_also_requires_review() -> None:
    """Giảm 30 kg trong 7 ngày không thể trả về safety_status='normal'.

    Mức điều chỉnh bị cắt về -500 kcal/ngày làm target rơi vào khoảng hợp lệ,
    nhưng client gate giao diện theo safety_status chứ không đọc warnings.
    """
    result = calculate_nutrition_goal(
        _request(goal="lose", target_weight_kg=40.0, target_days=7)
    )

    assert result.safety_status == "review_required"
    assert result.warnings


def test_response_contains_clear_profile_and_daily_nutrient_table() -> None:
    result = calculate_nutrition_goal(
        _request(
            age=25,
            height_cm=165,
            weight_kg=75,
            goal="maintain",
            target_weight_kg=75,
        )
    )

    assert result.profile.age == 25
    assert result.profile.bmi == pytest.approx(27.5, abs=0.1)
    assert result.profile.bmi_category == "overweight"
    assert result.daily_targets
    assert result.daily_targets[0].code == "energy"
    assert result.daily_targets[0].unit == "kcal/day"
    protein = next(row for row in result.daily_targets if row.code == "protein")
    assert protein.minimum > 0
    assert protein.maximum > protein.minimum
    assert protein.display_value
    assert result.reference.standard == "VN_NCDD_2016"


def test_reference_snapshot_supplies_micronutrients_and_comparators() -> None:
    result = calculate_nutrition_goal(
        _request(age=36, sex="male", goal="maintain", target_weight_kg=70)
    )

    codes = {row.code for row in result.daily_targets}
    assert {"water", "fiber", "calcium", "iron", "vitamin_c"}.issubset(codes)
    sodium = next(row for row in result.daily_targets if row.code == "sodium")
    assert sodium.comparator == "<"
    assert sodium.maximum == 2000
    assert sodium.minimum is None


def test_explicit_nutrition_group_is_exposed_and_requires_review_for_non_normal() -> None:
    result = calculate_nutrition_goal(
        _request(
            nutrition_group="overweight_obesity",
            goal="lose",
            target_weight_kg=65,
        )
    )

    assert result.profile.nutrition_group == "overweight_obesity"
    assert result.safety_status == "review_required"
    assert any("nhóm thể trạng" in warning.lower() for warning in result.warnings)


def test_other_sex_does_not_silently_use_male_micronutrient_rows() -> None:
    result = calculate_nutrition_goal(
        _request(sex="other", goal="maintain", target_weight_kg=70)
    )

    reference_rows = [
        row
        for row in result.daily_targets
        if row.source.startswith("https://viendinhduong.vn")
    ]
    assert reference_rows == []
    assert result.safety_status == "review_required"
    assert any("nam/nữ" in warning for warning in result.warnings)
