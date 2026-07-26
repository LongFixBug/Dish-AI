"""Deterministic, source-labelled nutrition goal estimates.

This service deliberately keeps the algorithm transparent:

1. Mifflin–St Jeor estimates resting energy.
2. An activity multiplier estimates maintenance energy.
3. The requested weight change is converted to a daily energy adjustment
   using a labelled, capped product heuristic.
4. Macro ranges use WHO healthy-diet ranges and a weight-based protein floor.

The output is an estimate for healthy adults, not a clinical prescription.
"""

from schemas.nutrition_goals import (
    NutritionGoalRequest,
    NutritionGoalResponse,
    NutritionReference,
    MacroTarget,
)

ALGORITHM_VERSION = "mifflin_goal_rate_v1"
STANDARD = "VN_NCDD_2016"
STANDARD_SOURCE_URL = (
    "https://viendinhduong.vn/vi/cong-cu-va-tien-ich/nhu-cau-dinh-duong"
)
MACRO_SOURCE_URL = "https://www.who.int/news-room/fact-sheets/detail/healthy-diet"
GOAL_MODEL_SOURCE_URL = "https://www.niddk.nih.gov/bwp."
GOAL_MODEL_METHOD = (
    "Ước tính theo chênh lệch cân nặng và thời hạn; điều chỉnh tối đa "
    "500 kcal/ngày theo chính sách an toàn của sản phẩm, không phải công thức "
    "nội bộ của NIDDK."
)
STANDARD_USAGE = (
    "Đã snapshot bảng tham chiếu Việt Nam vào nutrition_reference_targets để tra "
    "cứu theo nhóm tuổi, giới tính và mức lao động. Bộ tính mục tiêu hiện tại "
    "vẫn dùng Mifflin–St Jeor + WHO để tạo con số cá nhân hóa; bảng NCDD là "
    "nguồn đối chiếu, không tự động thay thế công thức này."
)
SCOPE = "Người trưởng thành khỏe mạnh; giá trị tham khảo, không thay thế tư vấn y tế."

_ACTIVITY_FACTORS = {
    "sedentary": 1.2,
    "light": 1.375,
    "moderate": 1.55,
    "very_active": 1.725,
}
_KCAL_PER_KG = 7700.0
_MAX_DAILY_ADJUSTMENT = 500.0
_MIN_CALORIES = 1200
_MAX_CALORIES = 4000


def calculate_nutrition_goal(
    request: NutritionGoalRequest,
) -> NutritionGoalResponse:
    """Calculate transparent daily targets from a validated adult profile."""
    warnings: list[str] = []
    _validate_goal_direction(request)

    bmr = _calculate_bmr(request)
    maintenance = round(bmr * _ACTIVITY_FACTORS[request.activity_level])
    raw_delta = _raw_goal_delta(request)
    goal_delta = _bounded_delta(raw_delta, warnings)
    requested_target = maintenance + goal_delta
    target_calories = _bounded_calories(requested_target, warnings)

    if request.target_days < 30 and request.goal != "maintain":
        warnings.append(
            "Thời hạn ngắn; nên trao đổi với chuyên gia trước khi theo mục tiêu này."
        )

    safety_status = "normal"
    if request.pregnancy_status != "none" or request.medical_conditions:
        safety_status = "review_required"
        warnings.append(
            "Hồ sơ có tình trạng sinh lý hoặc bệnh nền; cần chuyên gia dinh dưỡng "
            "kiểm tra trước khi áp dụng."
        )
    if target_calories != requested_target:
        safety_status = "review_required"

    macros = _calculate_macros(target_calories, request.weight_kg)
    return NutritionGoalResponse(
        maintenance_calories=maintenance,
        target_calories=target_calories,
        goal_delta_calories=target_calories - maintenance,
        protein_g=macros[0],
        carbohydrate_g=macros[1],
        fat_g=macros[2],
        safety_status=safety_status,
        warnings=warnings,
        reference=NutritionReference(
            standard=STANDARD,
            standard_source_url=STANDARD_SOURCE_URL,
            macro_source_url=MACRO_SOURCE_URL,
            goal_model_source_url=GOAL_MODEL_SOURCE_URL,
            goal_model_method=GOAL_MODEL_METHOD,
            standard_usage=STANDARD_USAGE,
            algorithm_version=ALGORITHM_VERSION,
            scope=SCOPE,
        ),
    )


def _calculate_bmr(request: NutritionGoalRequest) -> float:
    """Estimate resting energy with Mifflin–St Jeor."""
    sex_offset = {"male": 5.0, "female": -161.0, "other": -78.0}[request.sex]
    return (
        10 * request.weight_kg
        + 6.25 * request.height_cm
        - 5 * request.age
        + sex_offset
    )


def _validate_goal_direction(request: NutritionGoalRequest) -> None:
    if request.goal == "lose" and request.target_weight_kg >= request.weight_kg:
        raise ValueError("target_weight_kg phải thấp hơn weight_kg khi mục tiêu là lose.")
    if request.goal == "gain" and request.target_weight_kg <= request.weight_kg:
        raise ValueError("target_weight_kg phải cao hơn weight_kg khi mục tiêu là gain.")


def _raw_goal_delta(request: NutritionGoalRequest) -> float:
    if request.goal == "maintain":
        return 0.0
    weight_delta = request.target_weight_kg - request.weight_kg
    return weight_delta * _KCAL_PER_KG / request.target_days


def _bounded_delta(raw_delta: float, warnings: list[str]) -> int:
    bounded = max(-_MAX_DAILY_ADJUSTMENT, min(_MAX_DAILY_ADJUSTMENT, raw_delta))
    if bounded != raw_delta:
        warnings.append(
            "Mức điều chỉnh calo đã bị giới hạn để tránh mục tiêu quá cực đoan; "
            "đây là chính sách an toàn của sản phẩm."
        )
    return round(bounded)


def _bounded_calories(requested: float, warnings: list[str]) -> int:
    bounded = max(_MIN_CALORIES, min(_MAX_CALORIES, requested))
    if bounded != requested:
        warnings.append(
            f"Mục tiêu calo đã được giới hạn trong khoảng {_MIN_CALORIES}–{_MAX_CALORIES} kcal."
        )
    return round(bounded)


def _calculate_macros(calories: int, weight_kg: float) -> tuple[MacroTarget, ...]:
    """Return WHO-informed ranges plus a weight-based protein floor."""
    protein_min = max(0.8 * weight_kg, calories * 0.10 / 4)
    protein_target = max(protein_min, calories * 0.15 / 4)
    protein_max = max(protein_min, calories * 0.25 / 4)

    fat_min = calories * 0.15 / 9
    fat_target = calories * 0.25 / 9
    fat_max = calories * 0.30 / 9

    carb_min = calories * 0.45 / 4
    carb_target = max(carb_min, (calories - protein_target * 4 - fat_target * 9) / 4)
    carb_max = calories * 0.75 / 4

    return (
        _macro(protein_min, protein_target, protein_max),
        _macro(carb_min, carb_target, carb_max),
        _macro(fat_min, fat_target, fat_max),
    )


def _macro(minimum: float, target: float, maximum: float) -> MacroTarget:
    return MacroTarget(
        min=round(minimum, 1),
        target=round(target, 1),
        max=round(maximum, 1),
    )
