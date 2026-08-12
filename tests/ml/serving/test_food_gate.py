from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from ml.inference.food_gate import FoodGatePrediction, FoodGateSettings, create_app


def _jpeg_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGB", (16, 16), (180, 120, 60)).save(output, format="JPEG")
    return output.getvalue()


def test_food_gate_blocks_only_at_or_above_configured_threshold() -> None:
    settings = FoodGateSettings(block_threshold=0.90)

    assert settings.decide(non_food_score=0.899) == "vision"
    assert settings.decide(non_food_score=0.90) == "block"


def test_food_gate_rejects_out_of_range_scores() -> None:
    settings = FoodGateSettings()

    with pytest.raises(ValueError):
        settings.decide(non_food_score=1.01)


def test_predict_endpoint_sanitizes_upload_and_returns_scores() -> None:
    class FakePredictor:
        def predict(self, image: Image.Image) -> FoodGatePrediction:
            assert image.mode == "RGB"
            assert image.size == (16, 16)
            return FoodGatePrediction(food_score=0.07, non_food_score=0.93)

    app = create_app(
        settings=FoodGateSettings(block_threshold=0.90),
        predictor_factory=lambda _settings: FakePredictor(),
    )

    with TestClient(app) as client:
        response = client.post(
            "/predict",
            files={"file": ("desk.jpg", _jpeg_bytes(), "image/jpeg")},
        )

    assert response.status_code == 200
    assert response.json() == {
        "action": "block",
        "food_score": 0.07,
        "non_food_score": 0.93,
        "block_threshold": 0.90,
    }


def test_predict_endpoint_rejects_spoofed_image() -> None:
    class FakePredictor:
        def predict(self, image: Image.Image) -> FoodGatePrediction:
            raise AssertionError("spoofed content must never reach the model")

    app = create_app(
        settings=FoodGateSettings(),
        predictor_factory=lambda _settings: FakePredictor(),
    )

    with TestClient(app) as client:
        response = client.post(
            "/predict",
            files={"file": ("fake.jpg", b"not-an-image", "image/jpeg")},
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "File tải lên không phải ảnh hợp lệ."
