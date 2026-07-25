"""Model manifests make promotion and rollback verifiable."""

from pathlib import Path

import pytest

from ml.model_registry import (
    ModelManifestError,
    build_manifest,
    evaluate_quality_gate,
    validate_manifest,
    promote_model,
)


GOOD_METRICS = {
    "accuracy": 82.0,
    "macro_f1": 79.0,
    "worst_class_accuracy": 68.0,
    "ece": 0.06,
    "selective_accuracy": 90.0,
    "selective_coverage": 0.45,
}


def test_quality_gate_rejects_current_portfolio_level_metrics() -> None:
    result = evaluate_quality_gate(
        {
            "accuracy": 61.21,
            "macro_f1": 58.0,
            "worst_class_accuracy": 42.11,
            "ece": 0.18,
            "selective_accuracy": 78.0,
            "selective_coverage": 0.2,
        }
    )

    assert result.passed is False
    assert "accuracy" in result.failures
    assert "worst_class_accuracy" in result.failures


def test_manifest_hash_detects_checkpoint_tampering(tmp_path: Path) -> None:
    checkpoint = tmp_path / "model.pth"
    checkpoint.write_bytes(b"approved-model")
    manifest = build_manifest(
        checkpoint,
        model_version="2026-07-25-e18",
        arch="efficientnet_b0",
        classes=["pho_bo", "com_tam"],
        metrics=GOOD_METRICS,
        confidence_threshold=0.88,
        dataset_fingerprint="dataset-sha256",
    )

    validated = validate_manifest(manifest, checkpoint)
    assert validated["quality_gate"]["passed"] is True

    checkpoint.write_bytes(b"tampered-model")
    with pytest.raises(ModelManifestError, match="checksum"):
        validate_manifest(manifest, checkpoint)


def test_promote_model_atomically_updates_serving_files(tmp_path: Path) -> None:
    release = tmp_path / "release.pth"
    release.write_bytes(b"release-model")
    manifest = build_manifest(
        release,
        model_version="release-v2",
        arch="efficientnet_b0",
        classes=["pho_bo", "com_tam"],
        metrics=GOOD_METRICS,
        confidence_threshold=0.9,
        dataset_fingerprint="dataset-sha256",
    )
    serving = tmp_path / "best_model.pth"
    serving_manifest = tmp_path / "best_model.manifest.json"

    promote_model(release, manifest, serving, serving_manifest)

    assert serving.read_bytes() == b"release-model"
    assert validate_manifest(manifest, serving)["model_version"] == "release-v2"
    assert serving_manifest.exists()
