"""Convert a Food Gate checkpoint to a smaller floating-point dtype.

The source checkpoint is deliberately kept outside Git.  Railway's trial
runtime can load the FP16 artifact in substantially less memory while the
loader remains compatible with the original FP32 checkpoint for local use.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import torch


def convert(source: Path, destination: Path, dtype: torch.dtype = torch.float16) -> None:
    """Write ``source`` with all floating tensors converted to ``dtype``."""
    checkpoint = torch.load(source, map_location="cpu", weights_only=True)
    checkpoint["model_state_dict"] = {
        name: value.to(dtype=dtype) if torch.is_floating_point(value) else value
        for name, value in checkpoint["model_state_dict"].items()
    }
    checkpoint["artifact_dtype"] = str(dtype).removeprefix("torch.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    torch.save(checkpoint, destination)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    convert(args.source, args.destination)


if __name__ == "__main__":
    main()
