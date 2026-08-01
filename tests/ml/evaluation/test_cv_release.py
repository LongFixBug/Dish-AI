"""Release evaluation must support an approved subset of dataset classes."""

import json
from pathlib import Path

import pytest

from ml.evaluation.cv_release import (
    load_calibrated_threshold,
    validate_test_class_folders,
)
from ml.model_registry import sha256_file


def test_release_accepts_extra_unreviewed_test_class_folders() -> None:
    validate_test_class_folders(
        checkpoint_classes=["com_tam", "pho_bo"],
        available_classes=["com_tam", "noisy_web_class", "pho_bo"],
    )


def test_release_rejects_missing_checkpoint_test_class_folder() -> None:
    with pytest.raises(ValueError, match="missing checkpoint classes"):
        validate_test_class_folders(
            checkpoint_classes=["com_tam", "pho_bo"],
            available_classes=["com_tam", "noisy_web_class"],
        )


def test_release_loads_passing_calibration_threshold_bound_to_checkpoint(
    tmp_path: Path,
) -> None:
    checkpoint = tmp_path / "model.pth"
    checkpoint.write_bytes(b"approved-model")
    report = tmp_path / "calibration.json"
    report.write_text(
        json.dumps(
            {
                "suite": "cv_solo_calibration",
                "checkpoint_sha256": sha256_file(checkpoint),
                "gates": {
                    "min_known_precision": 0.98,
                    "max_ood_false_accept_rate": 0.02,
                    "min_known_accepted": 30,
                },
                "recommended": {
                    "threshold": 0.996,
                    "known_precision": 0.994,
                    "ood_false_accept_rate": 0.0175,
                    "known_accepted": 838,
                },
            }
        ),
        encoding="utf-8",
    )

    assert load_calibrated_threshold(report, checkpoint) == 0.996


def test_release_rejects_calibration_report_for_other_checkpoint(tmp_path: Path) -> None:
    checkpoint = tmp_path / "model.pth"
    checkpoint.write_bytes(b"approved-model")
    report = tmp_path / "calibration.json"
    report.write_text(
        json.dumps(
            {
                "suite": "cv_solo_calibration",
                "checkpoint_sha256": "0" * 64,
                "gates": {
                    "min_known_precision": 0.98,
                    "max_ood_false_accept_rate": 0.02,
                    "min_known_accepted": 30,
                },
                "recommended": {
                    "threshold": 0.996,
                    "known_precision": 0.994,
                    "ood_false_accept_rate": 0.0175,
                    "known_accepted": 838,
                },
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="checksum"):
        load_calibrated_threshold(report, checkpoint)
