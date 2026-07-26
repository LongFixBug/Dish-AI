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
