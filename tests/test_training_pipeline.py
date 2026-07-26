"""Training configuration must stay reproducible and keep class indices aligned."""

import os
from argparse import Namespace
from pathlib import Path

import pytest
import torch
from PIL import Image

from ml.inference.cv import _resolve_checkpoint_classes
from ml.training import train


def _write_image(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (16, 16), color=(120, 80, 40)).save(path)


def test_training_rejects_different_train_and_validation_class_sets(tmp_path) -> None:
    _write_image(tmp_path / "train" / "pho_bo" / "train.jpg")
    _write_image(tmp_path / "train" / "com_tam" / "train.jpg")
    _write_image(tmp_path / "val" / "pho_bo" / "val.jpg")

    with pytest.raises(ValueError, match="Validation class folders"):
        train.load_training_datasets(tmp_path)


def test_training_loads_validation_with_the_train_class_mapping(tmp_path) -> None:
    for class_name in ("pho_bo", "com_tam"):
        _write_image(tmp_path / "train" / class_name / "train.jpg")
        _write_image(tmp_path / "val" / class_name / "val.jpg")

    train_ds, val_ds = train.load_training_datasets(tmp_path)

    assert val_ds.classes == train_ds.classes
    assert val_ds.class_counts() == [1, 1]


def test_reproducible_seed_resets_torch_random_state() -> None:
    train.set_reproducible_seed(123)
    first = torch.rand(3)
    train.set_reproducible_seed(123)
    second = torch.rand(3)

    assert torch.equal(first, second)


def test_cli_passes_no_class_weight_to_main(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_main(**kwargs) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(train, "main", fake_main)
    train.run_from_args(
        Namespace(
            resume=False,
            ckpt=None,
            data_dir=None,
            no_class_weight=True,
        )
    )

    assert captured["use_class_weight"] is False


def test_checkpoint_classes_override_a_stale_legacy_mapping(tmp_path) -> None:
    mapping = tmp_path / "class_mapping.json"
    mapping.write_text('{"classes": ["wrong_class"]}', encoding="utf-8")

    classes = _resolve_checkpoint_classes(
        {"classes": ["pho_bo", "com_tam"]},
        mapping,
    )

    assert classes == ["pho_bo", "com_tam"]


def test_macro_metrics_expose_minority_class_quality() -> None:
    metrics = train.compute_classification_metrics(
        [[1, 1], [0, 2]],
        ["class_0", "class_1"],
    )

    assert metrics["accuracy"] == 75.0
    assert metrics["macro_precision"] == 83.33
    assert metrics["macro_recall"] == 75.0
    assert metrics["macro_f1"] == 73.33
    assert metrics["per_class"]["class_0"]["recall"] == 50.0


def test_calibration_recommends_threshold_for_selective_accuracy() -> None:
    metrics = train.compute_calibration_metrics(
        confidences=[0.95, 0.9, 0.7, 0.6],
        correctness=[True, True, False, True],
        target_accuracy=0.9,
    )

    assert metrics["recommended_threshold"] == 0.9
    assert metrics["selective_accuracy"] == 100.0
    assert metrics["selective_coverage"] == 0.5
    assert 0 <= metrics["ece"] <= 1


def test_latest_checkpoint_uses_mtime_not_filename_order(tmp_path, monkeypatch) -> None:
    """epoch18 mới hơn epoch9, dù sort chuỗi xếp '9' sau '1'."""
    monkeypatch.setattr(train, "CHECKPOINT_DIR", tmp_path)
    older = tmp_path / "efficientnet_vietfood_20260726_120000_epoch9.pth"
    newer = tmp_path / "efficientnet_vietfood_20260726_120000_epoch18.pth"
    older.write_bytes(b"old")
    newer.write_bytes(b"new")
    os.utime(older, (1_000, 1_000))
    os.utime(newer, (2_000, 2_000))

    assert train.find_latest_checkpoint() == newer
