"""Evaluate a checkpoint on an independent test split and create a release."""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import torch

from ml.model_registry import (
    build_manifest,
    evaluate_quality_gate,
    fingerprint_dataset,
    promote_model,
    sha256_file,
    write_manifest,
)
from ml.training import train
from ml.training.dataset import VietFoodDataset


def validate_test_class_folders(
    checkpoint_classes: list[str],
    available_classes: list[str],
) -> None:
    """Require every trained class while allowing unrelated OOD folders."""
    missing = sorted(set(checkpoint_classes) - set(available_classes))
    if missing:
        raise ValueError(
            f"Test split is missing checkpoint classes: {missing}"
        )


def load_calibrated_threshold(report_path: Path, checkpoint_path: Path) -> float:
    """Accept only a passing calibration report bound to this exact checkpoint."""
    try:
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read calibration report: {report_path}") from exc
    if not isinstance(report, dict) or report.get("suite") != "cv_solo_calibration":
        raise ValueError("Calibration report has an unsupported suite")
    if report.get("checkpoint_sha256") != sha256_file(checkpoint_path):
        raise ValueError("Calibration report checkpoint checksum does not match")
    gates = report.get("gates")
    selected = report.get("recommended")
    if not isinstance(gates, dict) or not isinstance(selected, dict):
        raise ValueError("Calibration report has no passing recommendation")
    try:
        threshold = float(selected["threshold"])
        known_precision = float(selected["known_precision"])
        ood_far = float(selected["ood_false_accept_rate"])
        known_accepted = int(selected["known_accepted"])
        min_precision = float(gates["min_known_precision"])
        max_ood_far = float(gates["max_ood_false_accept_rate"])
        min_accepted = int(gates["min_known_accepted"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("Calibration report recommendation is malformed") from exc
    if not 0.5 <= threshold <= 1.0:
        raise ValueError("Calibration threshold must be between 0.5 and 1.0")
    if (
        known_precision < min_precision
        or ood_far > max_ood_far
        or known_accepted < min_accepted
    ):
        raise ValueError("Calibration recommendation does not pass its gates")
    return threshold


def evaluate_release(
    checkpoint_path: Path,
    data_dir: Path,
    release_dir: Path,
    *,
    promote: bool,
    calibration_report: Path | None = None,
) -> tuple[Path, Path]:
    if promote and calibration_report is None:
        raise ValueError("Promotion requires a passing calibration report")
    checkpoint = train.load_checkpoint(checkpoint_path)
    classes = checkpoint.get("classes")
    if not isinstance(classes, list) or not classes:
        raise ValueError("Checkpoint has no class mapping")
    # create_model load weights với strict=False: kiến trúc lệch thì không key
    # nào khớp và ta sẽ đi đánh giá một mạng khởi tạo ngẫu nhiên, rồi ghi
    # manifest với metric của mạng đó. Chặn ngay từ đầu.
    checkpoint_arch = checkpoint.get("arch", train.ARCH)
    if checkpoint_arch != train.ARCH:
        raise ValueError(
            f"Checkpoint arch {checkpoint_arch!r} does not match {train.ARCH!r}"
        )
    test_classes = train._class_folders(data_dir, "test")
    validate_test_class_folders(classes, test_classes)
    dataset = VietFoodDataset(data_dir, classes=classes, split="test")
    if any(count == 0 for count in dataset.class_counts()):
        raise ValueError("Every test class must contain at least one image")
    loader = torch.utils.data.DataLoader(
        dataset,
        batch_size=train.BATCH_SIZE,
        shuffle=False,
        num_workers=train.NUM_WORKERS,
    )
    model = train.create_model(len(classes), checkpoint).to(train.DEVICE)
    criterion = torch.nn.CrossEntropyLoss()
    _, accuracy, per_class, metrics = train.evaluate(
        model,
        loader,
        criterion,
        classes=classes,
    )
    worst = min(per_class.values()) if per_class else 0.0
    quality_metrics = {
        "accuracy": round(accuracy, 2),
        "macro_f1": float(metrics["macro_f1"]),
        "worst_class_accuracy": round(worst, 2),
        "ece": float(metrics["ece"]),
        "selective_accuracy": float(metrics["selective_accuracy"]),
        "selective_coverage": float(metrics["selective_coverage"]),
    }
    serving_threshold = (
        load_calibrated_threshold(calibration_report, checkpoint_path)
        if calibration_report is not None
        else float(metrics["recommended_threshold"])
    )
    version = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    checkpoint["model_version"] = version
    checkpoint["cv_confidence_threshold"] = serving_threshold
    checkpoint["quality_metrics"] = quality_metrics
    release_dir.mkdir(parents=True, exist_ok=True)
    release_path = release_dir / f"vietfood-{version}.pth"
    torch.save(checkpoint, release_path)
    manifest = build_manifest(
        release_path,
        model_version=version,
        arch=train.ARCH,
        classes=classes,
        metrics=quality_metrics,
        confidence_threshold=serving_threshold,
        dataset_fingerprint=fingerprint_dataset(data_dir),
        evaluation_split="test",
    )
    if calibration_report is not None:
        manifest["calibration_report"] = str(calibration_report)
    manifest_path = release_path.with_suffix(".manifest.json")
    write_manifest(manifest_path, manifest)
    gate = evaluate_quality_gate(quality_metrics, evaluation_split="test")
    if promote:
        if not gate.passed:
            raise ValueError(f"Model quality gate failed: {gate.failures}")
        promote_model(
            release_path,
            manifest,
            train.BEST_CHECKPOINT_PATH,
            train.BEST_MANIFEST_PATH,
        )
    return release_path, manifest_path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("--data-dir", type=Path, default=Path("data/images"))
    parser.add_argument("--release-dir", type=Path, default=Path("checkpoints/releases"))
    parser.add_argument("--promote", action="store_true")
    parser.add_argument("--calibration-report", type=Path)
    args = parser.parse_args()
    release, manifest = evaluate_release(
        args.checkpoint,
        args.data_dir,
        args.release_dir,
        promote=args.promote,
        calibration_report=args.calibration_report,
    )
    print(release)
    print(manifest)


if __name__ == "__main__":
    main()
