"""Regression tests for local CV model loading."""

import json

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

