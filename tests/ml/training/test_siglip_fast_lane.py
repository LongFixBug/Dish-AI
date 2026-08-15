"""Tests for the SigLIP fast-lane training setup."""

import json
from pathlib import Path

import pytest
from PIL import Image

from ml.training.siglip_fast_lane import (
    FastLaneDatasetError,
    _metrics,
    configure_trainable_layers,
    load_fast_lane_config,
    resolve_device,
    validate_dataset_layout,
)


def _write_image(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (24, 24), color=(80, 120, 160)).save(path)


def test_load_fast_lane_config_normalizes_and_rejects_duplicate_classes(tmp_path) -> None:
    path = tmp_path / "fast_lane.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "base_model": "google/siglip2-base-patch16-224",
                "classes": ["pho_bo", "com_tam"],
            }
        ),
        encoding="utf-8",
    )

    config = load_fast_lane_config(path)

    assert config.classes == ("com_tam", "pho_bo")
    assert config.base_model == "google/siglip2-base-patch16-224"
    assert config.image_size == 224

    path.write_text(
        json.dumps({"schema_version": 1, "classes": ["pho_bo", "pho_bo"]}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="duplicate"):
        load_fast_lane_config(path)


def test_dataset_layout_reports_counts_and_allows_missing_test_for_initial_train(
    tmp_path,
) -> None:
    for split in ("train", "val"):
        for class_name in ("pho_bo", "com_tam"):
            _write_image(tmp_path / split / class_name / f"{split}.jpg")
    for class_name in ("pho_bo", "com_tam"):
        (tmp_path / "test" / class_name).mkdir(parents=True)

    report = validate_dataset_layout(
        tmp_path,
        ("com_tam", "pho_bo"),
        require_test=False,
    )

    assert report["train"] == {"com_tam": 1, "pho_bo": 1}
    assert report["val"] == {"com_tam": 1, "pho_bo": 1}
    assert report["test"] == {}


def test_dataset_layout_requires_every_class_in_val_and_test_when_requested(tmp_path) -> None:
    _write_image(tmp_path / "train" / "pho_bo" / "train.jpg")
    _write_image(tmp_path / "train" / "com_tam" / "train.jpg")
    _write_image(tmp_path / "val" / "pho_bo" / "val.jpg")
    _write_image(tmp_path / "test" / "pho_bo" / "test.jpg")

    with pytest.raises(FastLaneDatasetError, match="com_tam"):
        validate_dataset_layout(
            tmp_path,
            ("com_tam", "pho_bo"),
            require_test=True,
        )


def test_resolve_device_honours_explicit_cpu_and_rejects_unknown_values() -> None:
    assert resolve_device("cpu", mps_available=True, cuda_available=True) == "cpu"
    assert resolve_device("auto", mps_available=True, cuda_available=False) == "mps"
    assert resolve_device("auto", mps_available=False, cuda_available=True) == "cuda"
    assert resolve_device("auto", mps_available=False, cuda_available=False) == "cpu"

    with pytest.raises(ValueError, match="auto, cpu"):
        resolve_device("tpu", mps_available=False, cuda_available=False)


def test_metrics_reports_macro_scores_for_each_fast_lane_class() -> None:
    metrics = _metrics(
        predictions=[0, 0, 1, 2],
        labels=[0, 1, 1, 2],
        num_classes=3,
    )

    assert metrics["accuracy"] == pytest.approx(0.75)
    assert metrics["macro_recall"] == pytest.approx((1.0 + 0.5 + 1.0) / 3)
    assert metrics["macro_f1"] == pytest.approx((2 / 3 + 2 / 3 + 1.0) / 3)


def test_configure_trainable_layers_keeps_early_siglip_blocks_frozen() -> None:
    torch = pytest.importorskip("torch")
    from transformers import SiglipVisionConfig, SiglipVisionModel

    class Model(torch.nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.encoder = SiglipVisionModel(
                SiglipVisionConfig(
                    hidden_size=32,
                    intermediate_size=64,
                    num_hidden_layers=3,
                    num_attention_heads=4,
                    patch_size=16,
                    image_size=32,
                )
            )
            self.classifier = torch.nn.Linear(32, 2)

    model = Model()
    trainable = configure_trainable_layers(model, last_blocks=2)

    assert trainable > 0
    early_block = model.encoder.encoder.layers[0]
    late_block = model.encoder.encoder.layers[-1]
    assert not any(parameter.requires_grad for parameter in early_block.parameters())
    assert all(parameter.requires_grad for parameter in late_block.parameters())
