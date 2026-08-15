"""Create the deployable SigLIP food-hint artifact after a successful train.

The archive intentionally contains inference files only. It is written under
``checkpoints/`` by default, which remains local and is never committed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tarfile
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CHECKPOINT_DIR = PROJECT_ROOT / "checkpoints" / "siglip_food_v1"
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "data" / "config" / "siglip_food_v1.json"


@dataclass(frozen=True)
class ArtifactReport:
    path: Path
    sha256: str
    bytes: int


def _read_expected_classes(config_path: Path) -> tuple[str, ...]:
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    classes = payload.get("classes")
    if not isinstance(classes, list) or not all(isinstance(item, str) for item in classes):
        raise ValueError("Config SigLIP phải có danh sách classes hợp lệ")
    # ``load_fast_lane_config`` uses alphabetical order to give class indices a
    # reproducible identity. Package with that same canonical contract.
    normalized = tuple(sorted(item.strip() for item in classes if item.strip()))
    if len(normalized) != len(classes) or len(set(normalized)) != len(normalized):
        raise ValueError("Config SigLIP chứa class rỗng hoặc trùng")
    return normalized


def _validate_checkpoint(checkpoint_dir: Path, expected_classes: tuple[str, ...]) -> None:
    manifest_path = checkpoint_dir / "manifest.json"
    head_path = checkpoint_dir / "classifier_head.pt"
    encoder_dir = checkpoint_dir / "encoder"
    required = (manifest_path, head_path, encoder_dir)
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FileNotFoundError("Thiếu artifact SigLIP: " + ", ".join(missing))

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if tuple(manifest.get("classes", ())) != expected_classes:
        raise ValueError("Classes trong manifest không khớp config")
    if manifest.get("test_evaluated") is not True:
        raise ValueError("Chưa có kết quả test held-out; không được package model")
    if not any(path.is_file() for path in encoder_dir.rglob("*")):
        raise FileNotFoundError("Encoder artifact đang rỗng")


def package_artifact(
    *,
    checkpoint_dir: Path,
    destination: Path,
    expected_classes: tuple[str, ...],
) -> ArtifactReport:
    """Archive exactly the files the inference service needs and hash them."""
    _validate_checkpoint(checkpoint_dir, expected_classes)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".part")
    encoder_dir = checkpoint_dir / "encoder"

    with tarfile.open(temporary, "w:gz") as archive:
        for source in sorted(path for path in encoder_dir.rglob("*") if path.is_file()):
            archive.add(source, arcname=str(source.relative_to(checkpoint_dir)))
        for name in ("classifier_head.pt", "manifest.json"):
            archive.add(checkpoint_dir / name, arcname=name)

    os.replace(temporary, destination)
    with destination.open("rb") as artifact:
        sha256 = hashlib.file_digest(artifact, "sha256").hexdigest()
    return ArtifactReport(path=destination, sha256=sha256, bytes=destination.stat().st_size)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint-dir", type=Path, default=DEFAULT_CHECKPOINT_DIR)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    destination = args.output or args.checkpoint_dir / "siglip_food_v1.tar.gz"
    report = package_artifact(
        checkpoint_dir=args.checkpoint_dir,
        destination=destination,
        expected_classes=_read_expected_classes(args.config),
    )
    print(
        json.dumps(
            {"artifact": str(report.path), "sha256": report.sha256, "bytes": report.bytes},
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
