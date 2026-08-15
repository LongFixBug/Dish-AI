"""Choose an inference device consistently across FoodAI model sidecars."""

from __future__ import annotations

from typing import Literal


InferenceDevice = Literal["auto", "cuda", "mps", "cpu"]


def resolve_inference_device(
    *,
    requested: InferenceDevice,
    cuda_available: bool,
    mps_available: bool,
) -> Literal["cuda", "mps", "cpu"]:
    """Prefer CUDA for production, then Apple MPS, then CPU."""

    if requested == "auto":
        if cuda_available:
            return "cuda"
        if mps_available:
            return "mps"
        return "cpu"

    if requested == "cuda":
        if not cuda_available:
            raise ValueError("CUDA không sẵn sàng")
        return "cuda"

    if requested == "mps":
        if not mps_available:
            raise ValueError("MPS không sẵn sàng")
        return "mps"

    return "cpu"
