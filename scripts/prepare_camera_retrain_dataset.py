"""Prepare an isolated CV experiment dataset from reviewed camera feedback.

The command is intentionally a preparation step, not a training command.  It
refuses to copy anything until the camera manifest proves that the consent,
review, total-count and hard-class gates all pass.  The baseline dataset is
copied into a new experiment directory and the reviewed camera train/val
images are merged into it without touching ``data/images`` or the serving
checkpoint.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

DEFAULT_BASE_DIR = PROJECT_ROOT / "data/images"
DEFAULT_CAMERA_DIR = PROJECT_ROOT / "data/images/feedback_camera_reviewed"
DEFAULT_MANIFEST = PROJECT_ROOT / "data/eval/camera_feedback_dataset_manifest.json"

IMAGE_SUFFIXES = frozenset({".jpg", ".jpeg", ".png", ".webp"})
SPLITS = ("train", "val")


def require_ready_manifest(manifest: dict[str, object]) -> dict[str, object]:
    """Reject a camera dataset unless every exporter gate is satisfied."""
    if manifest.get("ready") is not True:
        reasons = manifest.get("blocking_reasons") or ["unknown"]
        reason_text = ", ".join(str(reason) for reason in reasons)
        raise ValueError(f"camera dataset chưa đạt gate: {reason_text}")

    camera_images = manifest.get("camera_images")
    minimum_total = manifest.get("minimum_total")
    classes_below = manifest.get("classes_below_minimum")
    if not isinstance(camera_images, int) or not isinstance(minimum_total, int):
        raise ValueError("camera dataset manifest thiếu số lượng ảnh hợp lệ")
    if camera_images < minimum_total:
        raise ValueError("camera dataset chưa đạt gate: camera_images_below_minimum")
    if not isinstance(classes_below, list) or classes_below:
        raise ValueError("camera dataset chưa đạt gate: hard_classes_below_minimum")
    return manifest


def _image_files(root: Path) -> list[Path]:
    """List direct image files in one class folder deterministically."""
    return sorted(
        path
        for path in root.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_SUFFIXES
    )


def _next_destination(directory: Path, source: Path, source_name: str) -> Path:
    """Choose a non-overwriting destination for a possible filename collision."""
    destination = directory / source.name
    if not destination.exists():
        return destination
    stem, suffix = source.stem, source.suffix
    destination = directory / f"{source_name}_{stem}{suffix}"
    index = 2
    while destination.exists():
        destination = directory / f"{source_name}_{stem}_{index}{suffix}"
        index += 1
    return destination


def _copy_split(source_root: Path, output_root: Path, source_name: str) -> int:
    """Merge train/val folders from one source into the experiment directory."""
    copied = 0
    for split in SPLITS:
        split_root = source_root / split
        if not split_root.is_dir():
            raise FileNotFoundError(f"Không tìm thấy split {split_root}")
        for class_dir in sorted(path for path in split_root.iterdir() if path.is_dir()):
            destination_dir = output_root / split / class_dir.name
            destination_dir.mkdir(parents=True, exist_ok=True)
            for source in _image_files(class_dir):
                destination = _next_destination(destination_dir, source, source_name)
                shutil.copy2(source, destination)
                copied += 1
    return copied


def prepare_dataset(
    base_data_dir: Path,
    camera_data_dir: Path,
    output_dir: Path,
) -> int:
    """Copy baseline plus reviewed camera train/val into a fresh experiment."""
    base = base_data_dir.resolve()
    camera = camera_data_dir.resolve()
    output = output_dir.resolve()
    if output in {base, camera}:
        raise ValueError("output_dir phải là thư mục experiment riêng")
    if output.exists() and any(output.iterdir()):
        raise ValueError(f"output_dir phải rỗng hoặc chưa tồn tại: {output}")
    if not base.is_dir() or not camera.is_dir():
        raise FileNotFoundError("Thiếu thư mục baseline hoặc camera dataset")

    output.mkdir(parents=True, exist_ok=True)
    copied = _copy_split(base, output, "baseline")
    copied += _copy_split(camera, output, "camera")
    return copied


def _load_manifest(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Không đọc được camera manifest: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError("camera manifest phải là JSON object")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare an isolated retrain dataset after camera gates pass"
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--base-dir", type=Path, default=DEFAULT_BASE_DIR)
    parser.add_argument("--camera-dir", type=Path, default=DEFAULT_CAMERA_DIR)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    manifest = require_ready_manifest(_load_manifest(args.manifest))
    copied = prepare_dataset(args.base_dir, args.camera_dir, args.output_dir)
    report = {
        "suite": "camera_retrain_dataset",
        "source_manifest": str(args.manifest),
        "base_data_dir": str(args.base_dir),
        "camera_data_dir": str(args.camera_dir),
        "output_dir": str(args.output_dir),
        "camera_images": manifest["camera_images"],
        "copied_files": copied,
        "splits": list(SPLITS),
        "ready_for_training": True,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
