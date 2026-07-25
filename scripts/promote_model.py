#!/usr/bin/env python3
"""Promote or roll back to an approved model release and manifest."""

import argparse
from pathlib import Path

from ml.model_registry import load_manifest, promote_model


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("manifest", type=Path)
    parser.add_argument(
        "--serving-checkpoint",
        type=Path,
        default=Path("checkpoints/best_model.pth"),
    )
    parser.add_argument(
        "--serving-manifest",
        type=Path,
        default=Path("checkpoints/best_model.manifest.json"),
    )
    args = parser.parse_args()
    manifest = load_manifest(args.manifest)
    promote_model(
        args.checkpoint,
        manifest,
        args.serving_checkpoint,
        args.serving_manifest,
    )
    print(manifest["model_version"])


if __name__ == "__main__":
    main()
