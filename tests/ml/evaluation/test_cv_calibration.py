"""Tests for EfficientNet solo-threshold calibration with known and OOD data."""

import json
from pathlib import Path

import pytest
import torch
from PIL import Image

from ml.evaluation.cv_calibration import (
    KnownObservation,
    _load_observations,
    build_report,
    confusion_summary,
    evaluate_threshold,
    parse_args,
    recommend,
    save_report,
    sweep_thresholds,
)


def _known(
    confidence: float,
    correct: bool,
    truth: str = "pho_bo",
    predicted: str = "pho_bo",
) -> KnownObservation:
    return KnownObservation(
        truth_slug=truth,
        predicted_slug=predicted,
        confidence=confidence,
        correct=correct,
    )


def _write_image(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (32, 32), color=(120, 80, 40)).save(path)


def test_evaluate_threshold_reports_known_precision_coverage_and_ood_false_accept() -> None:
    known = [
        _known(0.99, True),
        _known(0.96, True),
        _known(0.92, False, predicted="pho_ga"),
        _known(0.40, True),
    ]

    result = evaluate_threshold(known, [0.97, 0.80, 0.20], threshold=0.95)

    assert result.known_accepted == 2
    assert result.known_precision == pytest.approx(1.0)
    assert result.known_coverage == pytest.approx(0.5)
    assert result.ood_accepted == 1
    assert result.ood_false_accept_rate == pytest.approx(1 / 3, abs=1e-4)


def test_evaluate_threshold_uses_none_precision_when_no_known_image_is_accepted() -> None:
    result = evaluate_threshold([_known(0.50, True)], [0.40], threshold=0.90)

    assert result.known_accepted == 0
    assert result.known_precision is None
    assert result.known_coverage == 0.0
    assert result.ood_false_accept_rate == 0.0


def test_missing_ood_data_cannot_look_like_zero_false_accept_rate() -> None:
    results = sweep_thresholds([_known(0.95, True)], [], thresholds=[0.90])

    assert results[0].ood_false_accept_rate is None
    assert recommend(
        results,
        min_known_precision=0.98,
        max_ood_false_accept_rate=0.02,
        min_known_accepted=1,
    ) is None


def test_recommend_requires_both_precision_and_ood_gate_then_maximizes_coverage() -> None:
    known = [
        _known(0.99, True),
        _known(0.91, True),
        _known(0.85, False, predicted="pho_ga"),
        _known(0.82, True),
    ]
    results = sweep_thresholds(known, [0.86, 0.30], thresholds=[0.80, 0.90, 0.95])

    selected = recommend(
        results,
        min_known_precision=0.98,
        max_ood_false_accept_rate=0.0,
        min_known_accepted=2,
    )

    assert selected is not None
    assert selected.threshold == pytest.approx(0.90)
    assert selected.known_precision == pytest.approx(1.0)
    assert selected.known_coverage == pytest.approx(0.5)
    assert selected.ood_false_accept_rate == 0.0


def test_recommend_returns_none_when_only_tiny_or_ood_unsafe_regions_pass() -> None:
    known = [_known(0.99, True), _known(0.80, False, predicted="pho_ga")]
    results = sweep_thresholds(known, [0.995], thresholds=[0.79, 0.98])

    assert recommend(
        results,
        min_known_precision=0.98,
        max_ood_false_accept_rate=0.0,
        min_known_accepted=2,
    ) is None


def test_recommend_compares_unrounded_precision_at_gate_boundary() -> None:
    known = [_known(0.9, True) for _ in range(440)]
    known.extend(_known(0.9, False, predicted="pho_ga") for _ in range(9))
    results = sweep_thresholds(known, [0.1], thresholds=[0.9])

    assert round(440 / 449, 4) == 0.98
    assert results[0].known_precision < 0.98
    assert recommend(
        results,
        min_known_precision=0.98,
        max_ood_false_accept_rate=0.02,
        min_known_accepted=449,
    ) is None


def test_confusion_summary_orders_frequent_known_errors() -> None:
    observations = [
        _known(0.8, False, truth="bun_rieu", predicted="bun_bo_hue"),
        _known(0.7, False, truth="bun_rieu", predicted="bun_bo_hue"),
        _known(0.6, False, truth="pho_bo", predicted="pho_ga"),
        _known(0.9, True),
    ]

    summary = confusion_summary(observations)

    assert summary == [
        {"truth_slug": "bun_rieu", "predicted_slug": "bun_bo_hue", "count": 2},
        {"truth_slug": "pho_bo", "predicted_slug": "pho_ga", "count": 1},
    ]


def test_build_report_is_json_serializable_and_records_gates() -> None:
    known = [_known(0.95, True), _known(0.60, False, predicted="pho_ga")]
    ood = [0.70, 0.20]
    results = sweep_thresholds(known, ood, thresholds=[0.50, 0.90])
    selected = recommend(
        results,
        min_known_precision=0.98,
        max_ood_false_accept_rate=0.0,
        min_known_accepted=1,
    )

    report = build_report(
        known,
        ood,
        results,
        selected,
        checkpoint_path="checkpoints/best_model.pth",
        known_dir="data/images/val",
        ood_dir="data/images/val_ood",
        min_known_precision=0.98,
        max_ood_false_accept_rate=0.0,
        min_known_accepted=1,
        timestamp="20260729_120000",
    )

    assert report["suite"] == "cv_solo_calibration"
    assert report["dataset"]["known_images"] == 2
    assert report["dataset"]["ood_images"] == 2
    assert report["dataset"]["ood_evaluation_available"] is True
    assert report["gates"]["min_known_precision"] == pytest.approx(0.98)
    assert report["recommended"]["threshold"] == pytest.approx(0.90)
    json.dumps(report, ensure_ascii=False)


def test_load_observations_runs_known_and_disjoint_ood_images(tmp_path, monkeypatch) -> None:
    from ml.training import train

    data_dir = tmp_path / "images"
    ood_dir = tmp_path / "ood" / "val"
    _write_image(data_dir / "val" / "known_dish" / "known.jpg")
    _write_image(ood_dir / "new_dish" / "ood.jpg")
    checkpoint_path = tmp_path / "model.pth"
    torch.save({"arch": train.ARCH, "classes": ["known_dish"]}, checkpoint_path)

    class OneClassModel(torch.nn.Module):
        def forward(self, images):
            return torch.ones((images.shape[0], 1), device=images.device)

    monkeypatch.setattr(
        train,
        "create_model",
        lambda _num_classes, _checkpoint: OneClassModel(),
    )

    known, ood, known_classes, ood_classes = _load_observations(
        checkpoint_path,
        data_dir,
        "val",
        ood_dir,
        batch_size=1,
        device_name="cpu",
    )

    assert known == [
        KnownObservation("known_dish", "known_dish", confidence=1.0, correct=True)
    ]
    assert ood == [1.0]
    assert known_classes == ["known_dish"]
    assert ood_classes == ["new_dish"]


def test_load_observations_rejects_ood_class_seen_by_checkpoint(tmp_path) -> None:
    from ml.training import train

    data_dir = tmp_path / "images"
    ood_dir = tmp_path / "ood" / "val"
    _write_image(data_dir / "val" / "known_dish" / "known.jpg")
    _write_image(ood_dir / "known_dish" / "not_really_ood.jpg")
    checkpoint_path = tmp_path / "model.pth"
    torch.save({"arch": train.ARCH, "classes": ["known_dish"]}, checkpoint_path)

    with pytest.raises(ValueError, match="OOD classes overlap"):
        _load_observations(
            checkpoint_path,
            data_dir,
            "val",
            ood_dir,
            batch_size=1,
            device_name="cpu",
        )


def test_load_observations_can_select_ood_classes_from_shared_split(
    tmp_path, monkeypatch
) -> None:
    from ml.training import train

    data_dir = tmp_path / "images"
    shared_val = data_dir / "val"
    _write_image(shared_val / "known_dish" / "known.jpg")
    _write_image(shared_val / "new_dish" / "ood.jpg")
    checkpoint_path = tmp_path / "model.pth"
    torch.save({"arch": train.ARCH, "classes": ["known_dish"]}, checkpoint_path)

    class OneClassModel(torch.nn.Module):
        def forward(self, images):
            return torch.ones((images.shape[0], 1), device=images.device)

    monkeypatch.setattr(
        train,
        "create_model",
        lambda _num_classes, _checkpoint: OneClassModel(),
    )

    known, ood, known_classes, ood_classes = _load_observations(
        checkpoint_path,
        data_dir,
        "val",
        shared_val,
        ood_classes=["new_dish"],
        batch_size=1,
        device_name="cpu",
    )

    assert len(known) == 1
    assert ood == [1.0]
    assert known_classes == ["known_dish"]
    assert ood_classes == ["new_dish"]


def test_cli_requires_explicit_ood_path_and_report_save_is_deterministic(tmp_path) -> None:
    args = parse_args(["--ood-dir", "data/images/new_classes_candidate/val"])
    report = {"suite": "cv_solo_calibration"}

    path = save_report(report, "20260729_120000", output_dir=tmp_path)

    assert args.ood_dir == Path("data/images/new_classes_candidate/val")
    assert path == tmp_path / "cv_calibration_20260729_120000.json"
    assert json.loads(path.read_text(encoding="utf-8")) == report


def test_cli_accepts_explicit_ood_class_allowlist() -> None:
    args = parse_args(
        [
            "--ood-dir",
            "data/images/val",
            "--ood-classes-file",
            "data/eval/efficientnet_ood_classes.json",
        ]
    )

    assert args.ood_classes_file == Path(
        "data/eval/efficientnet_ood_classes.json"
    )


@pytest.mark.parametrize("confidence", [-0.01, 1.01])
def test_invalid_confidence_is_rejected(confidence: float) -> None:
    with pytest.raises(ValueError, match="confidence"):
        evaluate_threshold([_known(confidence, True)], [], threshold=0.5)
