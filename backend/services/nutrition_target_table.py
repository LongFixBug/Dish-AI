"""Build the display-ready daily nutrition target table."""

from schemas.nutrition_goals import (
    DailyNutritionTarget,
    MacroTarget,
    NutritionGoalRequest,
)


def build_daily_targets(
    request: NutritionGoalRequest,
    target_calories: int,
    macros: tuple[MacroTarget, ...],
    reference_rows: list[dict[str, object]],
) -> list[DailyNutritionTarget]:
    """Combine calculated macros with the versioned reference snapshot."""
    protein, carbs, fat = macros
    targets = [
        _target(
            "energy",
            "Năng lượng",
            "kcal/day",
            "energy",
            target_calories,
            target_calories,
            "=",
            source="mifflin_goal_rate_v1",
        ),
        _target(
            "water",
            "Nước",
            "lít/day",
            "water",
            1.5,
            2.5,
            "range",
            source="VN_NCDD_2016_display_rule",
        ),
        _macro_target("protein", "Chất Đạm", protein),
        _macro_target("fat", "Chất Béo", fat),
        _macro_target("carbohydrate", "Chất bột đường", carbs),
        _target(
            "fiber",
            "Chất xơ",
            "g/day",
            "limit",
            round(target_calories * 0.014, 1),
            None,
            ">=",
            source="WHO_healthy_diet",
        ),
        _target(
            "sugar",
            "Đường tổng số",
            "g/day",
            "limit",
            round(target_calories * 0.05 / 4, 1),
            round(target_calories * 0.10 / 4, 1),
            "range",
            source="WHO_healthy_diet",
        ),
        _target(
            "cholesterol",
            "Cholesterol",
            "mg/day",
            "limit",
            None,
            200 if request.nutrition_group == "overweight_obesity" else 300,
            "<",
            source="product_safety_rule_v1",
        ),
    ]
    seen_codes = {row.code for row in targets}
    for row in reference_rows:
        code = _REFERENCE_CODE_MAP.get(str(row["nutrient_code"]))
        if code is None or code in seen_codes:
            continue
        targets.append(_reference_target(row, code))
        seen_codes.add(code)
    return targets


def _macro_target(
    code: str,
    name: str,
    macro: MacroTarget,
) -> DailyNutritionTarget:
    return _target(
        code,
        name,
        "g/day",
        "macronutrient",
        macro.min,
        macro.max,
        "range",
        display_value=f"{macro.min:.1f} - {macro.max:.1f}",
        source="WHO_healthy_diet",
    )


def _reference_target(row: dict[str, object], code: str) -> DailyNutritionTarget:
    value_text = str(row["value_text"]).strip()
    minimum = _as_float(row.get("value_min"))
    maximum = _as_float(row.get("value_max"))
    comparator = _comparator(value_text, minimum, maximum)
    if comparator in {">", ">="}:
        maximum = None
    elif comparator in {"<", "<="}:
        minimum = None
    return DailyNutritionTarget(
        code=code,
        name_vi=str(row["nutrient_name"]),
        category="micronutrient",
        unit=_display_unit(str(row["unit"])),
        minimum=minimum,
        maximum=maximum,
        comparator=comparator,
        display_value=_display_value(value_text, minimum, maximum, comparator),
        variant=value_text if code in {"iron", "zinc"} else None,
        source=str(row["source_url"]),
    )


def _target(
    code: str,
    name_vi: str,
    unit: str,
    category: str,
    minimum: float | None,
    maximum: float | None,
    comparator: str,
    *,
    source: str,
    display_value: str | None = None,
) -> DailyNutritionTarget:
    return DailyNutritionTarget(
        code=code,
        name_vi=name_vi,
        category=category,
        unit=unit,
        minimum=minimum,
        maximum=maximum,
        comparator=comparator,
        display_value=display_value
        or _display_value("", minimum, maximum, comparator),
        source=source,
    )


def _display_value(
    raw: str,
    minimum: float | None,
    maximum: float | None,
    comparator: str,
) -> str:
    if raw and any(char.isalpha() for char in raw):
        return raw
    if comparator in {"<", "<="} and maximum is not None:
        return f"{comparator}{maximum:g}"
    if comparator in {">", ">="} and minimum is not None:
        return f"{comparator}{minimum:g}"
    if comparator == "=" and minimum is not None:
        return f"{minimum:g}"
    if minimum is not None and maximum is not None:
        return f"{minimum:g} - {maximum:g}"
    return raw or "-"


def _comparator(
    value_text: str,
    minimum: float | None,
    maximum: float | None,
) -> str:
    stripped = value_text.lstrip()
    if stripped.startswith("≥"):
        return ">="
    if stripped.startswith(">"):
        return ">"
    if stripped.startswith("≤"):
        return "<="
    if stripped.startswith("<"):
        return "<"
    if minimum is not None and maximum is not None and minimum != maximum:
        return "range"
    return "="


def _as_float(value: object) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None


def _display_unit(unit: str) -> str:
    return unit.replace("/ngày", "/day")


_REFERENCE_CODE_MAP = {
    "nang_luong": "energy",
    "chat_am": "protein",
    "chat_beo": "fat",
    "chat_bot_uong": "carbohydrate",
    "canxi": "calcium",
    "magie": "magnesium",
    "sat": "iron",
    "kem": "zinc",
    "vitamin_a": "vitamin_a",
    "vitamin_d": "vitamin_d",
    "vitamin_b1": "vitamin_b1",
    "vitamin_b6": "vitamin_b6",
    "axit_folic": "folate",
    "vitamin_c": "vitamin_c",
    "natri": "sodium",
    "tuong_uong_muoi": "salt_equivalent",
}
