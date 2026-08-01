"""Calibrate the EfficientNet solo threshold on known and OOD images.

The threshold sweep is deliberately pure: model inference first produces known
observations plus OOD confidences, then the same evidence can be reviewed or
re-scored without loading Torch again.

Usage::

    DEBUG=false uv run python -m ml.evaluation.cv_calibration \
        --checkpoint checkpoints/best_model.pth \
        --data-dir data/images \
        --ood-dir data/images/new_classes_candidate/val
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from ml.model_registry import sha256_file

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPORTS_DIR = Path(__file__).resolve().parent / "reports"
DEFAULT_CHECKPOINT = PROJECT_ROOT / "checkpoints" / "best_model.pth"
DEFAULT_DATA_DIR = PROJECT_ROOT / "data" / "images"
DEFAULT_THRESHOLDS: tuple[float, ...] = tuple(index / 1000 for index in range(500, 1001))
DEFAULT_MIN_KNOWN_PRECISION = 0.98
DEFAULT_MAX_OOD_FALSE_ACCEPT_RATE = 0.02
DEFAULT_MIN_KNOWN_ACCEPTED = 30
DEFAULT_BATCH_SIZE = 32


@dataclass(frozen=True)
class KnownObservation:
    """One labeled, in-distribution validation prediction."""

    truth_slug: str
    predicted_slug: str
    confidence: float
    correct: bool


@dataclass(frozen=True)
class ThresholdResult:
    """Known selective metrics and OOD false accepts at one threshold."""

    threshold: float
    known_accepted: int
    known_total: int
    known_correct: int
    known_precision: float | None
    known_coverage: float
    ood_accepted: int
    ood_total: int
    ood_false_accept_rate: float | None


def _validate_probability(value: float, name: str) -> None:
    if not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be between 0 and 1: {value}")


def evaluate_threshold(
    known: Sequence[KnownObservation],
    ood_confidences: Sequence[float],
    threshold: float,
) -> ThresholdResult:
    """Measure the CV-only decision gate at one confidence threshold."""
    _validate_probability(threshold, "threshold")
    for observation in known:
        _validate_probability(observation.confidence, "confidence")
    for confidence in ood_confidences:
        _validate_probability(confidence, "OOD confidence")

    accepted_known = [item for item in known if item.confidence >= threshold]
    known_correct = sum(item.correct for item in accepted_known)
    accepted_ood = sum(confidence >= threshold for confidence in ood_confidences)
    return ThresholdResult(
        threshold=threshold,
        known_accepted=len(accepted_known),
        known_total=len(known),
        known_correct=known_correct,
        known_precision=(
            known_correct / len(accepted_known) if accepted_known else None
        ),
        known_coverage=len(accepted_known) / len(known) if known else 0.0,
        ood_accepted=accepted_ood,
        ood_total=len(ood_confidences),
        ood_false_accept_rate=(
            accepted_ood / len(ood_confidences) if ood_confidences else None
        ),
    )


def sweep_thresholds(
    known: Sequence[KnownObservation],
    ood_confidences: Sequence[float],
    thresholds: Sequence[float] = DEFAULT_THRESHOLDS,
) -> tuple[ThresholdResult, ...]:
    """Evaluate every requested CV confidence threshold."""
    return tuple(
        evaluate_threshold(known, ood_confidences, threshold)
        for threshold in thresholds
    )


def recommend(
    results: Sequence[ThresholdResult],
    *,
    min_known_precision: float = DEFAULT_MIN_KNOWN_PRECISION,
    max_ood_false_accept_rate: float = DEFAULT_MAX_OOD_FALSE_ACCEPT_RATE,
    min_known_accepted: int = DEFAULT_MIN_KNOWN_ACCEPTED,
) -> ThresholdResult | None:
    """Choose maximum known coverage among operating points passing both gates."""
    _validate_probability(min_known_precision, "min_known_precision")
    _validate_probability(max_ood_false_accept_rate, "max_ood_false_accept_rate")
    if min_known_accepted < 1:
        raise ValueError("min_known_accepted must be at least 1")

    eligible = [
        result
        for result in results
        if result.known_precision is not None
        and result.known_precision >= min_known_precision
        and result.ood_false_accept_rate is not None
        and result.ood_false_accept_rate <= max_ood_false_accept_rate
        and result.known_accepted >= min_known_accepted
    ]
    if not eligible:
        return None
    return max(
        eligible,
        key=lambda result: (
            result.known_coverage,
            -result.ood_false_accept_rate,
            result.known_precision,
            result.threshold,
        ),
    )


def confusion_summary(
    observations: Sequence[KnownObservation],
    *,
    min_confidence: float = 0.0,
) -> list[dict[str, str | int]]:
    """Count wrong known-class pairs, most frequent first."""
    _validate_probability(min_confidence, "min_confidence")
    counts = Counter(
        (item.truth_slug, item.predicted_slug)
        for item in observations
        if not item.correct and item.confidence >= min_confidence
    )
    return [
        {"truth_slug": truth, "predicted_slug": predicted, "count": count}
        for (truth, predicted), count in sorted(
            counts.items(), key=lambda item: (-item[1], item[0])
        )
    ]


def _serialize_result(result: ThresholdResult) -> dict:
    """Round presentation values without changing the values used by gates."""
    payload = asdict(result)
    for key in (
        "threshold",
        "known_precision",
        "known_coverage",
        "ood_false_accept_rate",
    ):
        value = payload[key]
        if value is not None:
            payload[key] = round(value, 4)
    return payload


def build_report(
    known: Sequence[KnownObservation],
    ood_confidences: Sequence[float],
    results: Sequence[ThresholdResult],
    selected: ThresholdResult | None,
    *,
    checkpoint_path: str,
    known_dir: str,
    ood_dir: str,
    min_known_precision: float,
    max_ood_false_accept_rate: float,
    min_known_accepted: int,
    timestamp: str,
) -> dict:
    """Build a reviewable, JSON-serializable calibration report."""
    recommended_threshold = selected.threshold if selected else 1.0
    return {
        "timestamp": timestamp,
        "suite": "cv_solo_calibration",
        "checkpoint_path": checkpoint_path,
        "dataset": {
            "known_dir": known_dir,
            "ood_dir": ood_dir,
            "known_images": len(known),
            "ood_images": len(ood_confidences),
            "ood_evaluation_available": bool(ood_confidences),
            "known_accuracy": (
                round(sum(item.correct for item in known) / len(known), 4)
                if known
                else 0.0
            ),
        },
        "gates": {
            "min_known_precision": min_known_precision,
            "max_ood_false_accept_rate": max_ood_false_accept_rate,
            "min_known_accepted": min_known_accepted,
        },
        "known_confusions": confusion_summary(known),
        "accepted_confusions": confusion_summary(
            known, min_confidence=recommended_threshold
        ),
        "threshold_results": [_serialize_result(result) for result in results],
        "recommended": _serialize_result(selected) if selected else None,
    }


def _predict_known(model, loader, device, classes, torch) -> list[KnownObservation]:
    observations: list[KnownObservation] = []
    with torch.no_grad():
        for images, labels in loader:
            probabilities = torch.softmax(model(images.to(device)), dim=1)
            confidences, predicted = probabilities.max(dim=1)
            for truth_index, predicted_index, confidence in zip(
                labels.tolist(), predicted.tolist(), confidences.tolist(), strict=True
            ):
                observations.append(
                    KnownObservation(
                        truth_slug=classes[truth_index],
                        predicted_slug=classes[predicted_index],
                        confidence=float(confidence),
                        correct=truth_index == predicted_index,
                    )
                )
    return observations


def _predict_ood_confidences(model, loader, device, torch) -> list[float]:
    values: list[float] = []
    with torch.no_grad():
        for images, _labels in loader:
            probabilities = torch.softmax(model(images.to(device)), dim=1)
            confidences = probabilities.max(dim=1).values
            values.extend(float(value) for value in confidences.tolist())
    return values


def _load_observations(
    checkpoint_path: Path,
    data_dir: Path,
    known_split: str,
    ood_dir: Path,
    *,
    batch_size: int,
    device_name: str | None,
    ood_classes: list[str] | None = None,
) -> tuple[list[KnownObservation], list[float], list[str], list[str]]:
    """Run the checkpoint over known validation and unseen-class images."""
    import torch
    from torch.utils.data import DataLoader

    from ml.training import train
    from ml.training.dataset import VietFoodDataset

    if not checkpoint_path.is_file():
        raise FileNotFoundError(f"Checkpoint not found: {checkpoint_path}")
    if not ood_dir.is_dir():
        raise FileNotFoundError(f"OOD directory not found: {ood_dir}")

    device = torch.device(device_name) if device_name else train.DEVICE
    checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=True)
    classes = checkpoint.get("classes")
    if not isinstance(classes, list) or not classes:
        raise ValueError("Checkpoint has no class mapping")
    if checkpoint.get("arch", train.ARCH) != train.ARCH:
        raise ValueError(f"Checkpoint architecture must be {train.ARCH}")

    known_dataset = VietFoodDataset(data_dir, classes=classes, split=known_split)
    empty_classes = [
        name
        for name, count in zip(classes, known_dataset.class_counts(), strict=True)
        if count == 0
    ]
    if empty_classes:
        raise ValueError(f"Known validation classes without images: {empty_classes}")

    ood_dataset = VietFoodDataset(
        ood_dir.parent,
        classes=sorted(ood_classes) if ood_classes is not None else None,
        split=ood_dir.name,
    )
    overlap = sorted(set(classes) & set(ood_dataset.classes))
    if overlap:
        raise ValueError(f"OOD classes overlap checkpoint classes: {overlap}")

    model = train.create_model(len(classes), checkpoint).to(device)
    model.eval()
    known_loader = DataLoader(
        known_dataset, batch_size=batch_size, shuffle=False, num_workers=0
    )
    ood_loader = DataLoader(
        ood_dataset, batch_size=batch_size, shuffle=False, num_workers=0
    )
    known = _predict_known(model, known_loader, device, classes, torch)
    ood_confidences = _predict_ood_confidences(model, ood_loader, device, torch)
    return known, ood_confidences, list(classes), list(ood_dataset.classes)


def save_report(report: dict, timestamp: str, output_dir: Path = REPORTS_DIR) -> Path:
    """Write one immutable JSON report for PO review."""
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"cv_calibration_{timestamp}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Calibrate EfficientNet CV solo threshold")
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--known-split", default="val")
    parser.add_argument("--ood-dir", type=Path, required=True)
    parser.add_argument(
        "--ood-classes-file",
        type=Path,
        help="Optional versioned allowlist of OOD classes inside --ood-dir.",
    )
    parser.add_argument("--min-known-precision", type=float, default=0.98)
    parser.add_argument("--max-ood-far", type=float, default=0.02)
    parser.add_argument("--min-known-accepted", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--device", choices=("cpu", "mps", "cuda"))
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    ood_classes = None
    if args.ood_classes_file is not None:
        from ml.training.train import load_class_allowlist

        ood_classes = load_class_allowlist(args.ood_classes_file)
    known, ood, known_classes, ood_classes = _load_observations(
        args.checkpoint,
        args.data_dir,
        args.known_split,
        args.ood_dir,
        batch_size=max(1, args.batch_size),
        device_name=args.device,
        ood_classes=ood_classes,
    )
    results = sweep_thresholds(known, ood)
    selected = recommend(
        results,
        min_known_precision=args.min_known_precision,
        max_ood_false_accept_rate=args.max_ood_far,
        min_known_accepted=args.min_known_accepted,
    )
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report = build_report(
        known,
        ood,
        results,
        selected,
        checkpoint_path=str(args.checkpoint),
        known_dir=str(args.data_dir / args.known_split),
        ood_dir=str(args.ood_dir),
        min_known_precision=args.min_known_precision,
        max_ood_false_accept_rate=args.max_ood_far,
        min_known_accepted=args.min_known_accepted,
        timestamp=timestamp,
    )
    report["checkpoint_sha256"] = sha256_file(args.checkpoint)
    report["dataset"]["known_classes"] = known_classes
    report["dataset"]["ood_classes"] = ood_classes
    path = save_report(report, timestamp)

    if selected:
        print(
            f"Recommended threshold={selected.threshold:.3f}: "
            f"known precision={selected.known_precision:.4f}, "
            f"coverage={selected.known_coverage:.4f}, "
            f"OOD FAR={selected.ood_false_accept_rate:.4f}"
        )
    else:
        print("No threshold passed all CV solo gates; keep Vision fallback enabled.")
    print(f"Report saved: {path}")


if __name__ == "__main__":
    main()
