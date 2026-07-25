"""Versioned model manifests and non-negotiable production quality gates."""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path


class ModelManifestError(ValueError):
    """A checkpoint or its promotion evidence cannot be trusted."""


@dataclass(frozen=True)
class QualityGateResult:
    passed: bool
    failures: dict[str, str]


QUALITY_THRESHOLDS = {
    "accuracy": 75.0,
    "macro_f1": 70.0,
    "worst_class_accuracy": 60.0,
    "ece": 0.10,
    "selective_accuracy": 85.0,
    "selective_coverage": 0.20,
}


def evaluate_quality_gate(
    metrics: dict[str, float],
    *,
    evaluation_split: str = "test",
) -> QualityGateResult:
    failures: dict[str, str] = {}
    if evaluation_split != "test":
        failures["evaluation_split"] = "independent held-out test metrics required"
    for name in ("accuracy", "macro_f1", "worst_class_accuracy"):
        value = float(metrics.get(name, 0.0))
        minimum = QUALITY_THRESHOLDS[name]
        if value < minimum:
            failures[name] = f"{value:.4f} < {minimum:.4f}"
    ece = float(metrics.get("ece", 1.0))
    if ece > QUALITY_THRESHOLDS["ece"]:
        failures["ece"] = f"{ece:.4f} > {QUALITY_THRESHOLDS['ece']:.4f}"
    for name in ("selective_accuracy", "selective_coverage"):
        value = float(metrics.get(name, 0.0))
        minimum = QUALITY_THRESHOLDS[name]
        if value < minimum:
            failures[name] = f"{value:.4f} < {minimum:.4f}"
    return QualityGateResult(passed=not failures, failures=failures)


def build_manifest(
    checkpoint_path: Path,
    *,
    model_version: str,
    arch: str,
    classes: list[str],
    metrics: dict[str, float],
    confidence_threshold: float,
    dataset_fingerprint: str,
    evaluation_split: str = "test",
) -> dict[str, object]:
    gate = evaluate_quality_gate(metrics, evaluation_split=evaluation_split)
    return {
        "schema_version": 1,
        "model_version": model_version,
        "checkpoint_sha256": sha256_file(checkpoint_path),
        "arch": arch,
        "classes": list(classes),
        "confidence_threshold": float(confidence_threshold),
        "dataset_fingerprint": dataset_fingerprint,
        "evaluation_split": evaluation_split,
        "metrics": metrics,
        "quality_gate": asdict(gate),
    }


def validate_manifest(
    manifest: dict[str, object],
    checkpoint_path: Path,
    *,
    require_passed_gate: bool = True,
) -> dict[str, object]:
    if manifest.get("schema_version") != 1:
        raise ModelManifestError("Unsupported model manifest schema")
    if manifest.get("checkpoint_sha256") != sha256_file(checkpoint_path):
        raise ModelManifestError("Checkpoint checksum does not match manifest")
    classes = manifest.get("classes")
    if not isinstance(classes, list) or not classes:
        raise ModelManifestError("Manifest classes are missing")
    threshold = manifest.get("confidence_threshold")
    if not isinstance(threshold, (int, float)) or not 0.0 < threshold <= 1.0:
        raise ModelManifestError("Manifest confidence threshold is invalid")
    gate = manifest.get("quality_gate")
    if require_passed_gate and (
        not isinstance(gate, dict) or gate.get("passed") is not True
    ):
        raise ModelManifestError("Model quality gate did not pass")
    return manifest


def load_manifest(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ModelManifestError("Cannot read model manifest") from exc
    if not isinstance(value, dict):
        raise ModelManifestError("Model manifest must be a JSON object")
    return value


def write_manifest(path: Path, manifest: dict[str, object]) -> None:
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fingerprint_dataset(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(str(path.stat().st_size).encode("ascii"))
    return digest.hexdigest()


def promote_model(
    release_checkpoint: Path,
    manifest: dict[str, object],
    serving_checkpoint: Path,
    serving_manifest: Path,
) -> None:
    """Atomically point serving files at any previously approved release."""
    validate_manifest(manifest, release_checkpoint, require_passed_gate=True)
    serving_checkpoint.parent.mkdir(parents=True, exist_ok=True)
    checkpoint_tmp = serving_checkpoint.with_suffix(
        f"{serving_checkpoint.suffix}.tmp"
    )
    manifest_tmp = serving_manifest.with_suffix(f"{serving_manifest.suffix}.tmp")
    shutil.copy2(release_checkpoint, checkpoint_tmp)
    manifest_tmp.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    checkpoint_tmp.replace(serving_checkpoint)
    manifest_tmp.replace(serving_manifest)
