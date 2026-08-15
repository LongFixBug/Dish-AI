"""Inspect the local SigLIP food-v1 dataset before training.

This command validates image bytes with Pillow and reports shortages by
train/validation/test split.  It never modifies or downloads dataset files.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from ml.training.siglip_fast_lane import IMAGE_EXTENSIONS, load_fast_lane_config  # noqa: E402

DEFAULT_CONFIG_PATH = PROJECT_ROOT / "data" / "config" / "siglip_food_v1.json"
DEFAULT_DATA_DIR = PROJECT_ROOT / "data" / "images" / "siglip_food_v1"
DEFAULT_TARGETS = {"train": 80, "val": 20, "test": 30}


def _image_inventory(folder: Path) -> tuple[int, list[str]]:
    if not folder.is_dir():
        return 0, []

    valid = 0
    invalid: list[str] = []
    for path in sorted(folder.iterdir()):
        if not path.is_file() or path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        try:
            with Image.open(path) as image:
                image.verify()
        except (OSError, ValueError):
            invalid.append(path.name)
        else:
            valid += 1
    return valid, invalid


def inventory_dataset(
    *,
    data_dir: Path = DEFAULT_DATA_DIR,
    classes: tuple[str, ...],
    targets: Mapping[str, int] = DEFAULT_TARGETS,
) -> dict[str, Any]:
    """Return only read-only validity/count information for every class."""
    expected_splits = ("train", "val", "test")
    if set(targets) != set(expected_splits) or any(value < 1 for value in targets.values()):
        raise ValueError("targets phải có train, val, test với số ảnh dương")

    splits: dict[str, dict[str, dict[str, int | list[str]]]] = {}
    for split in expected_splits:
        classes_report: dict[str, dict[str, int | list[str]]] = {}
        for slug in classes:
            valid, invalid = _image_inventory(data_dir / split / slug)
            classes_report[slug] = {
                "valid": valid,
                "missing": max(int(targets[split]) - valid, 0),
                "invalid": invalid,
            }
        splits[split] = classes_report

    entries = [entry for split in splits.values() for entry in split.values()]
    return {
        "data_dir": str(data_dir),
        "targets": dict(targets),
        "minimum_ready": all(int(entry["valid"]) > 0 and not entry["invalid"] for entry in entries),
        "target_ready": all(int(entry["missing"]) == 0 and not entry["invalid"] for entry in entries),
        "splits": splits,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument(
        "--require-target",
        action="store_true",
        help="Exit non-zero until all 80/20/30 targets have been reached.",
    )
    args = parser.parse_args()

    config = load_fast_lane_config(args.config)
    report = inventory_dataset(data_dir=args.data_dir, classes=config.classes)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.require_target and not report["target_ready"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
