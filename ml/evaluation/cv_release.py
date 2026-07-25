"""Evaluate a checkpoint on an independent test split and create a release."""

import argparse
from datetime import UTC, datetime
from pathlib import Path

import torch

from ml.model_registry import (
    build_manifest,
    evaluate_quality_gate,
    fingerprint_dataset,
    promote_model,
    write_manifest,
)
from ml.training import train
from ml.training.dataset import VietFoodDataset


def evaluate_release(
    checkpoint_path: Path,
    data_dir: Path,
    release_dir: Path,
    *,
    promote: bool,
) -> tuple[Path, Path]:
    checkpoint = train.load_checkpoint(checkpoint_path)
    classes = checkpoint.get("classes")
    if not isinstance(classes, list) or not classes:
        raise ValueError("Checkpoint has no class mapping")
    test_classes = train._class_folders(data_dir, "test")
    if test_classes != classes:
        raise ValueError(
            f"Test class folders must match checkpoint classes: {test_classes} != {classes}"
        )
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
    version = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    checkpoint["model_version"] = version
    checkpoint["cv_confidence_threshold"] = metrics["recommended_threshold"]
    checkpoint["quality_metrics"] = quality_metrics
    release_dir.mkdir(parents=True, exist_ok=True)
    release_path = release_dir / f"vietfood-{version}.pth"
    torch.save(checkpoint, release_path)
    manifest = build_manifest(
        release_path,
        model_version=version,
        arch=str(checkpoint.get("arch", train.ARCH)),
        classes=classes,
        metrics=quality_metrics,
        confidence_threshold=float(metrics["recommended_threshold"]),
        dataset_fingerprint=fingerprint_dataset(data_dir),
        evaluation_split="test",
    )
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
    args = parser.parse_args()
    release, manifest = evaluate_release(
        args.checkpoint,
        args.data_dir,
        args.release_dir,
        promote=args.promote,
    )
    print(release)
    print(manifest)


if __name__ == "__main__":
    main()
