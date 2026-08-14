"""Nutrition analysis for a user-provided food name."""

from __future__ import annotations

import math

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from backend.services.food_catalog import (
    FoodMatch,
    choose_food_match,
    lookup_food_matches,
    match_to_per_gram,
)
from ml.inference.vision import VisionError, suggest_nutrition
from schemas.analyze import AnalyzeDish, AnalyzeMatch, AnalyzeResponse
from schemas.nutrition import (
    NutritionPerIngredient,
    calculate_item_nutrition,
    calculate_totals,
)

REFERENCE_WARNING = (
    "Không tìm thấy món trong 3 bảng dữ liệu. Đây là thông tin AI ước tính, "
    "chỉ mang tính tham khảo."
)
RAW_WARNING = "Dữ liệu được lấy từ bảng craw Viện Dinh dưỡng, chưa qua review catalog."


async def analyze_text_food(
    session: AsyncSession,
    food_name: str,
    grams: float,
) -> AnalyzeResponse:
    """Resolve a name through all catalogs, then fall back to text AI estimate."""
    matches = await lookup_food_matches(session, food_name)
    selected = choose_food_match(matches)
    if selected is not None:
        return _catalog_response(selected, grams, matches)
    if matches:
        return AnalyzeResponse(
            dish_name=food_name,
            source="text_ambiguous",
            matches=[AnalyzeMatch(**match.as_dict()) for match in matches],
            warning="Có nhiều món phù hợp. Vui lòng chọn đúng món để phân tích.",
        )

    return await _ai_estimate_response(food_name, grams)


def _catalog_response(
    match: FoodMatch,
    grams: float,
    matches: list[FoodMatch],
) -> AnalyzeResponse:
    item = calculate_item_nutrition(
        match.canonical_name,
        grams,
        match_to_per_gram(match),
    )
    totals = calculate_totals(match.canonical_name, [item])
    return AnalyzeResponse(
        dish_name=match.canonical_name,
        source=(
            "text_nrihcm_raw"
            if match.catalog_type == "nrihcm_food"
            else "text_catalog"
        ),
        nutrition=totals,
        dishes=[
            AnalyzeDish(
                dish_name=match.canonical_name,
                grams=grams,
                found_in_db=True,
                portion_source="user_input",
            )
        ],
        matches=[AnalyzeMatch(**match.as_dict()) for match in matches],
        warning=RAW_WARNING if match.catalog_type == "nrihcm_food" else None,
    )


async def _ai_estimate_response(food_name: str, grams: float) -> AnalyzeResponse:
    try:
        suggestion = await suggest_nutrition(food_name)
    except (VisionError, httpx.HTTPError, OSError):
        return _not_found_response(food_name)

    source = _first_suggestion_source(suggestion)
    if source is None:
        return _not_found_response(food_name)

    scale = grams / 10.0
    item = NutritionPerIngredient(
        item_name=food_name,
        grams=grams,
        calories=round(_safe_number(source.get("per_10g_calories")) * scale, 1),
        protein_g=round(_safe_number(source.get("per_10g_protein")) * scale, 1),
        fat_g=round(_safe_number(source.get("per_10g_fat")) * scale, 1),
        carbs_g=round(_safe_number(source.get("per_10g_carbs")) * scale, 1),
        fiber_g=round(_safe_number(source.get("per_10g_fiber")) * scale, 1),
        found_in_db=False,
        nutrition_basis="vision_estimate",
    )
    return AnalyzeResponse(
        dish_name=food_name,
        source="text_ai_estimate",
        nutrition=calculate_totals(food_name, [item]),
        dishes=[
            AnalyzeDish(
                dish_name=food_name,
                grams=grams,
                found_in_db=False,
                portion_source="user_input",
            )
        ],
        reference_only=True,
        warning=REFERENCE_WARNING,
    )


def _first_suggestion_source(payload: object) -> dict | None:
    if not isinstance(payload, dict):
        return None
    sources = payload.get("sources")
    if not isinstance(sources, list):
        return None
    for source in sources:
        if not isinstance(source, dict):
            continue
        values = [
            _safe_number(source.get(key))
            for key in (
                "per_10g_calories",
                "per_10g_protein",
                "per_10g_fat",
                "per_10g_carbs",
                "per_10g_fiber",
            )
        ]
        if any(value > 0 for value in values):
            return source
    return None


def _safe_number(value: object) -> float:
    try:
        number = float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0
    return min(10_000.0, max(0.0, number)) if math.isfinite(number) else 0.0


def _not_found_response(food_name: str) -> AnalyzeResponse:
    return AnalyzeResponse(
        dish_name=food_name,
        source="text_not_found",
        error=(
            "Chưa tìm thấy dữ liệu cho món này và dịch vụ AI tham khảo đang "
            "không sẵn sàng. Bạn có thể thử tên món cụ thể hơn."
        ),
    )
