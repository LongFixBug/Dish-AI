"""Tests for text-based nutrition analysis."""

from types import SimpleNamespace

import pytest

from backend.services import text_analysis
from backend.services.food_catalog import FoodMatch


def _ingredient_match() -> FoodMatch:
    row = SimpleNamespace(
        id="ingredient-id",
        ingredient_name="Sữa bò tươi",
        source="vnfood",
        gram=100.0,
        calories_per_g=0.6,
        protein_per_g=0.032,
        fat_per_g=0.035,
        carbs_per_g=0.048,
        fiber_per_g=0.0,
    )
    return FoodMatch.from_row(row, "vn_ingredient")


@pytest.mark.asyncio
async def test_analyze_text_scales_catalog_nutrition_to_user_grams(monkeypatch) -> None:
    monkeypatch.setattr(
        text_analysis,
        "lookup_food_matches",
        lambda *_args, **_kwargs: _resolved(_ingredient_match()),
    )

    response = await text_analysis.analyze_text_food(object(), "sữa bò", 200.0)

    assert response.source == "text_catalog"
    assert response.dishes[0].grams == 200.0
    assert response.dishes[0].portion_source == "user_input"
    assert response.nutrition is not None
    assert response.nutrition.total_calories == 120.0
    assert response.reference_only is False


@pytest.mark.asyncio
async def test_analyze_text_uses_ai_estimate_as_reference_when_catalog_misses(
    monkeypatch,
) -> None:
    monkeypatch.setattr(text_analysis, "lookup_food_matches", _empty_matches)

    async def suggested(*_args, **_kwargs):
        return _suggested_nutrition()

    monkeypatch.setattr(
        text_analysis,
        "suggest_nutrition",
        suggested,
    )

    response = await text_analysis.analyze_text_food(object(), "món lạ", 100.0)

    assert response.source == "text_ai_estimate"
    assert response.reference_only is True
    assert "tham khảo" in (response.warning or "").lower()
    assert response.nutrition is not None
    assert response.nutrition.items[0].found_in_db is False
    assert response.nutrition.items[0].nutrition_basis == "vision_estimate"


@pytest.mark.asyncio
async def test_analyze_text_reports_not_found_when_ai_returns_no_sources(monkeypatch) -> None:
    monkeypatch.setattr(text_analysis, "lookup_food_matches", _empty_matches)

    async def no_suggestion(*_args, **_kwargs):
        return {"sources": []}

    monkeypatch.setattr(
        text_analysis,
        "suggest_nutrition",
        no_suggestion,
    )

    response = await text_analysis.analyze_text_food(object(), "không có", 100.0)

    assert response.source == "text_not_found"
    assert response.nutrition is None
    assert response.error is not None


async def _resolved(match: FoodMatch) -> list[FoodMatch]:
    return [match]


async def _empty_matches(*_args, **_kwargs) -> list[FoodMatch]:
    return []


def _suggested_nutrition() -> dict:
    return {
        "sources": [
            {
                "source_label": "Nguồn tham khảo",
                "per_10g_calories": 20,
                "per_10g_protein": 1,
                "per_10g_fat": 0.5,
                "per_10g_carbs": 2,
                "per_10g_fiber": 0.2,
            }
        ]
    }
