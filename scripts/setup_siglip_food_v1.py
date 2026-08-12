"""One-command setup and 8-epoch training for the food-v1 SigLIP release.

Run from the project root:
    uv run python scripts/setup_siglip_food_v1.py
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from ml.training.siglip_fast_lane import (
    FastLaneConfig,
    load_fast_lane_config,
    resolve_device,
    train_fast_lane,
    validate_dataset_layout,
)

DEFAULT_CONFIG_PATH = PROJECT_ROOT / "data" / "config" / "siglip_food_v1.json"
DEFAULT_DATA_DIR = PROJECT_ROOT / "data" / "images" / "siglip_food_v1"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "checkpoints" / "siglip_food_v1"


def prepare_training(
    *,
    config_path: Path = DEFAULT_CONFIG_PATH,
    data_dir: Path = DEFAULT_DATA_DIR,
    device_name: str = "mps",
    epochs: int = 8,
    mps_available: bool,
    cuda_available: bool,
) -> tuple[FastLaneConfig, dict[str, Any]]:
    """Validate the release inputs before downloading/loading the model."""
    if epochs < 1:
        raise ValueError("epochs phải lớn hơn 0")
    config = replace(load_fast_lane_config(config_path), epochs=epochs)
    counts = validate_dataset_layout(data_dir, config.classes, require_test=True)
    device = resolve_device(
        device_name,
        mps_available=mps_available,
        cuda_available=cuda_available,
    )
    return config, {"device": device, "epochs": config.epochs, "counts": counts}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--device", choices=("auto", "cpu", "cuda", "mps"), default="mps")
    parser.add_argument("--epochs", type=int, default=8)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()

    import torch

    config, report = prepare_training(
        config_path=args.config,
        data_dir=args.data_dir,
        device_name=args.device,
        epochs=args.epochs,
        mps_available=torch.backends.mps.is_available(),
        cuda_available=torch.cuda.is_available(),
    )
    print(json.dumps({"setup": report}, ensure_ascii=False, indent=2))
    if args.check_only:
        return

    manifest = train_fast_lane(
        config,
        data_dir=args.data_dir,
        output_dir=args.output_dir,
        device_name=args.device,
        require_test=True,
    )
    print(json.dumps({"output_dir": str(args.output_dir), "manifest": manifest}, ensure_ascii=False))


if __name__ == "__main__":
    main()
