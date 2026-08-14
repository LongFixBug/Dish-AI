"""HTTP contract tests for name-based nutrition analysis."""

from backend.api import analyze as analyze_api
from schemas.analyze import AnalyzeResponse


def test_text_analyze_requires_authentication(anonymous_client) -> None:
    response = anonymous_client.post(
        "/api/v1/analyze/text",
        json={"food_name": "phở bò", "grams": 100},
    )

    assert response.status_code in {401, 403}


def test_text_analyze_rejects_invalid_name_or_grams(client) -> None:
    empty_name = client.post(
        "/api/v1/analyze/text",
        json={"food_name": "   ", "grams": 100},
    )
    zero_grams = client.post(
        "/api/v1/analyze/text",
        json={"food_name": "phở bò", "grams": 0},
    )

    assert empty_name.status_code == 422
    assert zero_grams.status_code == 422


def test_text_analyze_passes_normalized_input_to_service(client, monkeypatch) -> None:
    received: dict[str, object] = {}

    async def fake_analyze(_session, food_name: str, grams: float) -> AnalyzeResponse:
        received.update(food_name=food_name, grams=grams)
        return AnalyzeResponse(source="text_catalog", dish_name=food_name)

    monkeypatch.setattr(analyze_api, "analyze_text_food", fake_analyze)

    response = client.post(
        "/api/v1/analyze/text",
        json={"food_name": "  phở   bò ", "grams": 250},
    )

    assert response.status_code == 200
    assert received == {"food_name": "phở bò", "grams": 250.0}
    assert response.json()["source"] == "text_catalog"
