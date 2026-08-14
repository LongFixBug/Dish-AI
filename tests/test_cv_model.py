"""Regression tests for local CV model loading."""

import base64
import json
from pathlib import Path
from types import SimpleNamespace

from ml.inference import cv


def test_missing_checkpoint_keeps_cv_disabled(tmp_path, monkeypatch) -> None:
    """A randomly initialized network must never be marked ready for inference."""
    mapping_path = tmp_path / "class_mapping.json"
    mapping_path.write_text(json.dumps({"classes": ["pho_bo"]}), encoding="utf-8")
    monkeypatch.setattr(cv, "CLASS_MAPPING", mapping_path)

    model = cv.CVModel(checkpoint_path=tmp_path / "missing.pth", device="cpu")
    model.load()

    assert model.is_loaded is False
    assert model.model is None


def test_checkpoint_supplies_version_and_calibrated_serving_threshold() -> None:
    version, threshold = cv._resolve_serving_metadata(
        {
            "model_version": "2026-07-25-e18",
            "cv_confidence_threshold": 0.88,
        }
    )

    assert version == "2026-07-25-e18"
    assert threshold == 0.88


def test_checkpoint_keeps_high_calibrated_threshold_above_point_99() -> None:
    _, threshold = cv._resolve_serving_metadata(
        {"cv_confidence_threshold": 0.996}
    )

    assert threshold == 0.996


def test_remote_cv_model_warms_up_and_predicts_without_local_torch(
    tmp_path: Path,
) -> None:
    calls: list[tuple[str, str, dict | None]] = []

    class FakeResponse:
        def __init__(self, payload: dict) -> None:
            self._payload = payload

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return self._payload

    class FakeClient:
        def post(self, url: str, *, json: dict | None = None) -> FakeResponse:
            calls.append(("POST", url, json))
            if url.endswith("/v1/warmup"):
                return FakeResponse({
                    "cv_loaded": True,
                    "cv_model_version": "cv-remote-v1",
                    "cv_serving_threshold": 0.996,
                    "image_embed_loaded": True,
                })
            return FakeResponse({
                "dish_name": "Bun Bo Hue",
                "confidence": 0.999,
                "all_predictions": [],
                "source": "local",
                "model_version": "cv-remote-v1",
            })

        def close(self) -> None:
            return None

    image_path = tmp_path / "food.jpg"
    image_path.write_bytes(b"jpeg-bytes")
    model = cv.RemoteCVModel(
        "http://local-vision.railway.internal:8082",
        client=FakeClient(),
    )

    model.load()
    result = model.predict(image_path)

    assert model.is_loaded is True
    assert model.model_version == "cv-remote-v1"
    assert model.serving_threshold == 0.996
    assert result["dish_name"] == "Bun Bo Hue"
    assert calls[0][1].endswith("/v1/warmup")
    assert base64.b64decode(calls[1][2]["image"]) == b"jpeg-bytes"


def test_remote_cv_model_stays_disabled_when_warmup_is_incomplete() -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {"cv_loaded": True, "image_embed_loaded": False}

    client = SimpleNamespace(post=lambda *_args, **_kwargs: FakeResponse())
    model = cv.RemoteCVModel("http://local-vision:8082", client=client)

    model.load()

    assert model.is_loaded is False
