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


def test_training_allowlist_ignores_unreviewed_class_folders(tmp_path) -> None:
    for class_name in ("pho_bo", "com_tam", "noisy_web_class"):
        _write_image(tmp_path / "train" / class_name / "train.jpg")
        _write_image(tmp_path / "val" / class_name / "val.jpg")

    train_ds, val_ds = train.load_training_datasets(
        tmp_path,
        classes=["pho_bo", "com_tam"],
    )

    assert train_ds.classes == ["com_tam", "pho_bo"]
    assert val_ds.classes == ["com_tam", "pho_bo"]
    assert len(train_ds) == 2


def test_training_allowlist_requires_selected_class_in_both_splits(tmp_path) -> None:
    _write_image(tmp_path / "train" / "pho_bo" / "train.jpg")
    _write_image(tmp_path / "val" / "other_class" / "val.jpg")

    with pytest.raises(ValueError, match="Selected classes missing"):
        train.load_training_datasets(tmp_path, classes=["pho_bo"])


def test_load_class_allowlist_reads_versioned_config(tmp_path) -> None:
    path = tmp_path / "tier_a.json"
    path.write_text(
        '{"schema_version": 1, "classes": ["pho_bo", "com_tam"]}',
        encoding="utf-8",
    )

    assert train.load_class_allowlist(path) == ["com_tam", "pho_bo"]


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
            classes_file=None,
            no_class_weight=True,
            output_dir=None,
        )
    )

    assert captured["use_class_weight"] is False


def test_cli_passes_isolated_output_dir_to_main(monkeypatch, tmp_path) -> None:
    captured: dict[str, object] = {}

    def fake_main(**kwargs) -> None:
        captured.update(kwargs)

    monkeypatch.setattr(train, "main", fake_main)
    output_dir = tmp_path / "experiments" / "leakage_fixed_46class"
    train.run_from_args(
        Namespace(
            resume=False,
            ckpt=None,
            data_dir=None,
            classes_file=None,
            no_class_weight=False,
            output_dir=str(output_dir),
        )
    )

    assert captured["output_dir"] == str(output_dir)


def test_cli_passes_class_allowlist_to_main(monkeypatch, tmp_path) -> None:
    captured: dict[str, object] = {}
    classes_file = tmp_path / "tier_a.json"

    monkeypatch.setattr(train, "main", lambda **kwargs: captured.update(kwargs))
    train.run_from_args(
        Namespace(
            resume=False,
            ckpt=None,
            data_dir=None,
            classes_file=str(classes_file),
            no_class_weight=False,
            output_dir=None,
        )
    )

    assert captured["classes_file"] == str(classes_file)


def test_isolated_output_dir_keeps_training_artifacts_out_of_serving_dir(
    monkeypatch, tmp_path
) -> None:
    serving_dir = tmp_path / "checkpoints"
    experiment_dir = serving_dir / "experiments" / "leakage_fixed_46class"
    monkeypatch.setattr(train, "CHECKPOINT_DIR", serving_dir)

    output_dir = train.resolve_training_output_dir(experiment_dir)

    assert output_dir == experiment_dir
    assert train.training_class_mapping_path(output_dir) == (
        experiment_dir / "class_mapping.json"
    )
    assert train.training_history_path(output_dir, "20260730_010203") == (
        experiment_dir / "history_20260730_010203.json"
    )
    assert train.training_epoch_checkpoint_path(output_dir, "20260730_010203", 1) == (
        experiment_dir / "efficientnet_vietfood_20260730_010203_epoch1.pth"
    )
    assert train.training_class_mapping_path(output_dir) != (
        serving_dir / "class_mapping.json"
    )
    assert train.training_epoch_checkpoint_path(output_dir, "20260730_010203", 1) != (
        serving_dir / "best_model.pth"
    )


def test_isolated_output_dir_rejects_serving_checkpoint_directory(
    monkeypatch, tmp_path
) -> None:
    serving_dir = tmp_path / "checkpoints"
    monkeypatch.setattr(train, "CHECKPOINT_DIR", serving_dir)

    with pytest.raises(ValueError, match="must not be the serving checkpoint directory"):
        train.resolve_training_output_dir(serving_dir)


def test_training_writes_every_artifact_inside_the_isolated_output_dir(
    monkeypatch, tmp_path
) -> None:
    data_dir = tmp_path / "images"
    for class_name in ("pho_bo", "com_tam"):
        _write_image(data_dir / "train" / class_name / "train.jpg")
        _write_image(data_dir / "val" / class_name / "val.jpg")

    serving_dir = tmp_path / "checkpoints"
    serving_dir.mkdir()
    serving_checkpoint = serving_dir / "best_model.pth"
    serving_manifest = serving_dir / "best_model.manifest.json"
    serving_checkpoint.write_bytes(b"serving-checkpoint")
    serving_manifest.write_text('{"serving": true}', encoding="utf-8")
    experiment_dir = serving_dir / "experiments" / "leakage_fixed_46class"

    metrics = {
        "macro_precision": 100.0,
        "macro_recall": 100.0,
        "macro_f1": 100.0,
        "confusion_matrix": [[1, 0], [0, 1]],
        "ece": 0.01,
        "selective_accuracy": 100.0,
        "selective_coverage": 1.0,
        "recommended_threshold": 0.9,
    }
    monkeypatch.setattr(train, "CHECKPOINT_DIR", serving_dir)
    monkeypatch.setattr(train, "NUM_EPOCHS", 1)
    monkeypatch.setattr(train, "NUM_WORKERS", 0)
    monkeypatch.setattr(train, "create_model", lambda *_: torch.nn.Linear(1, 2))
    monkeypatch.setattr(train, "train_epoch", lambda *_: (0.1, 100.0))
    monkeypatch.setattr(
        train,
        "evaluate",
        lambda *args, **kwargs: (0.1, 100.0, {0: 100.0, 1: 100.0}, metrics),
    )

    train.main(data_dir=str(data_dir), output_dir=str(experiment_dir))

    assert len(list(experiment_dir.glob("efficientnet_vietfood_*.pth"))) == 1
    assert (experiment_dir / "class_mapping.json").exists()
    assert len(list(experiment_dir.glob("history_*.json"))) == 1
    assert serving_checkpoint.read_bytes() == b"serving-checkpoint"
    assert serving_manifest.read_text(encoding="utf-8") == '{"serving": true}'


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
