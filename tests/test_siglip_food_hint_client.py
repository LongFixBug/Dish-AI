import pytest

from backend.config import settings
from backend.services import siglip_food_hints


class _Response:
    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict[str, object]:
        return {
            "model_version": "siglip-food-v1",
            "candidates": [{"slug": "pho-bo", "name": "Phở bò", "score": 0.95}],
        }


@pytest.mark.asyncio
async def test_siglip_food_hint_client_sends_service_token(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class _Client:
        def __init__(self, **kwargs: object) -> None:
            captured["timeout"] = kwargs["timeout"]

        async def __aenter__(self) -> "_Client":
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def post(self, url: str, **kwargs: object) -> _Response:
            captured["url"] = url
            captured["headers"] = kwargs["headers"]
            return _Response()

    monkeypatch.setattr(settings, "siglip_food_hint_mode", "hint")
    monkeypatch.setattr(settings, "siglip_food_hint_url", "https://gpu.example.com/siglip")
    monkeypatch.setattr(settings, "siglip_food_hint_service_token", "sidecar-token")
    monkeypatch.setattr(settings, "siglip_food_hint_min_score", 0.5)
    monkeypatch.setattr(settings, "siglip_food_hint_top_k", 3)
    monkeypatch.setattr(siglip_food_hints.httpx, "AsyncClient", _Client)

    result = await siglip_food_hints.predict_siglip_food_hints(b"image", "image/jpeg")

    assert result is not None
    assert captured["url"] == "https://gpu.example.com/siglip/predict"
    assert captured["headers"] == {"X-Food-Gate-Token": "sidecar-token"}
