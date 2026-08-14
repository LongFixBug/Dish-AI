"""Image-embedding sidecar (port 8082).

Phục vụ vector ảnh L2-normalized cho dish photo matching. SigLIP2 là encoder
mặc định; DINOv2 chỉ còn là backend thử nghiệm tường minh qua
``IMAGE_EMBED_BACKEND=dinov2``. Model chỉ được load lười ở request đầu tiên;
import module này KHÔNG kéo theo torch/transformers nên test và tooling nhẹ
nhàng.

API contract:
- ``POST /v1/image-embeddings`` body ``{"images": ["<base64>", ...]}`` →
  ``{"model": str, "dim": int, "data": [{"index": int, "embedding": [...]}]}``
- ``GET /health`` → ``{"status": "ok", "model": str, "device": str, "dim": int}``
"""

from __future__ import annotations

import base64
import io
import logging
import os
import threading
from collections.abc import Callable
from dataclasses import dataclass

from fastapi import FastAPI, HTTPException
from PIL import Image
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "google/siglip2-base-patch16-224"
DEFAULT_DINOV2_MODEL = "facebook/dinov2-small"
SUPPORTED_IMAGE_EMBED_BACKENDS = ("siglip2", "dinov2")
_BACKEND_DEFAULT_DIMS = {"siglip2": 768, "dinov2": 384}


def default_model_for_backend(backend: str) -> str:
    """Return the checkpoint used by a supported image encoder backend."""
    normalized = backend.strip().lower()
    if normalized == "siglip2":
        return DEFAULT_MODEL
    if normalized == "dinov2":
        return DEFAULT_DINOV2_MODEL
    supported = ", ".join(SUPPORTED_IMAGE_EMBED_BACKENDS)
    raise ValueError(f"Unsupported IMAGE_EMBED_BACKEND {backend!r}; use {supported}")


def default_embedding_dim_for_backend(backend: str) -> int:
    """Return the expected vector width for a supported backend."""
    normalized = backend.strip().lower()
    try:
        return _BACKEND_DEFAULT_DIMS[normalized]
    except KeyError as exc:
        supported = ", ".join(SUPPORTED_IMAGE_EMBED_BACKENDS)
        raise ValueError(
            f"Unsupported IMAGE_EMBED_BACKEND {backend!r}; use {supported}"
        ) from exc


IMAGE_EMBED_BACKEND = os.environ.get("IMAGE_EMBED_BACKEND", "siglip2").strip().lower()
MODEL_NAME = os.environ.get(
    "IMAGE_EMBED_MODEL",
    default_model_for_backend(IMAGE_EMBED_BACKEND),
)
EMBED_DIM = default_embedding_dim_for_backend(IMAGE_EMBED_BACKEND)
MAX_BATCH_SIZE = 32

app = FastAPI(title="FoodAI Image Embedding Sidecar")


class ImageEmbeddingRequest(BaseModel):
    """Batch of base64-encoded images to embed."""

    images: list[str] = Field(min_length=1)


class ImageEmbeddingItem(BaseModel):
    index: int
    embedding: list[float]


class ImageEmbeddingResponse(BaseModel):
    model: str
    dim: int
    data: list[ImageEmbeddingItem]


@dataclass(frozen=True)
class EmbeddingBackend:
    """Loaded model wrapped behind a plain encode callable (dễ fake trong test)."""

    model_name: str
    device: str
    encode: Callable[[list[Image.Image]], list[list[float]]]
    dim: int = EMBED_DIM


_backend: EmbeddingBackend | None = None
_backend_lock = threading.Lock()


def resolve_image_embed_device(*, mps_available: bool) -> str:
    """Select MPS by default, with an explicit CPU escape hatch for stability."""
    requested = os.environ.get("IMAGE_EMBED_DEVICE", "auto").lower()
    if requested == "cpu":
        return "cpu"
    if requested == "mps":
        if not mps_available:
            raise RuntimeError("IMAGE_EMBED_DEVICE=mps but MPS is unavailable")
        return "mps"
    if requested != "auto":
        raise ValueError("IMAGE_EMBED_DEVICE must be auto, cpu, or mps")
    return "mps" if mps_available else "cpu"


def _load_backend() -> EmbeddingBackend:
    """Load the configured image encoder lazily."""
    import torch
    from transformers import AutoImageProcessor

    device = resolve_image_embed_device(
        mps_available=torch.backends.mps.is_available(),
    )
    logger.info(
        "Loading image embedding backend %s (%s) on %s",
        IMAGE_EMBED_BACKEND,
        MODEL_NAME,
        device,
    )
    processor = AutoImageProcessor.from_pretrained(MODEL_NAME)
    if IMAGE_EMBED_BACKEND == "siglip2":
        from transformers import SiglipVisionModel

        # The full SigLIP model also loads a text tower that image retrieval
        # never uses. Loading only the vision tower keeps the Railway service
        # below its 1 GiB memory limit.
        model = SiglipVisionModel.from_pretrained(MODEL_NAME).to(device).eval()
        prefer_cls = False
    elif IMAGE_EMBED_BACKEND == "dinov2":
        from transformers import AutoModel

        model = AutoModel.from_pretrained(MODEL_NAME).to(device).eval()
        prefer_cls = True
    else:  # validated at module import, kept defensive for monkeypatches
        raise ValueError(
            f"Unsupported IMAGE_EMBED_BACKEND: {IMAGE_EMBED_BACKEND!r}"
        )

    model_config = getattr(model, "config", None)
    model_dim = int(getattr(model_config, "hidden_size", EMBED_DIM))
    if model_dim <= 0:
        raise RuntimeError(f"Image encoder returned invalid dimension: {model_dim}")

    def encode(images: list[Image.Image]) -> list[list[float]]:
        inputs = processor(images=images, return_tensors="pt").to(device)
        with torch.inference_mode():
            features = _extract_image_features(
                model,
                inputs,
                prefer_cls=prefer_cls,
            )
            normalized = torch.nn.functional.normalize(features, p=2, dim=-1)
        return normalized.cpu().tolist()

    return EmbeddingBackend(
        model_name=MODEL_NAME,
        device=device,
        encode=encode,
        dim=model_dim,
    )


def _extract_image_features(model, inputs, *, prefer_cls: bool = False):
    """Extract pooled/CLS image features across Transformers model APIs.

    transformers v5 (``Siglip2Model.get_image_features``) trả về
    ``BaseModelOutputWithPooling`` (lấy ``pooler_output``), trong khi v4 trả
    thẳng tensor. DINOv2 uses the first token in ``last_hidden_state`` as its
    image representation; ``prefer_cls`` makes that choice explicit.
    """
    import torch

    if hasattr(model, "get_image_features"):
        output = model.get_image_features(**inputs)
    elif hasattr(model, "vision_model"):
        output = model.vision_model(**inputs)
    else:
        output = model(**inputs)
    if isinstance(output, torch.Tensor):
        return output
    hidden = getattr(output, "last_hidden_state", None)
    if prefer_cls and hidden is not None:
        return hidden[:, 0]
    pooled = getattr(output, "pooler_output", None)
    if pooled is not None:
        return pooled
    if hidden is not None:
        return hidden[:, 0]
    raise RuntimeError(
        "Cannot extract pooled image features from model output "
        f"of type {type(output).__name__}"
    )


def _get_backend() -> EmbeddingBackend:
    """Trả về backend đã load; load đúng một lần kể cả khi nhiều thread cùng gọi."""
    global _backend
    if _backend is None:
        with _backend_lock:
            if _backend is None:
                _backend = _load_backend()
    return _backend


def _decode_images(encoded: list[str]) -> tuple[list[Image.Image], list[int]]:
    """Decode base64 → PIL RGB. Trả về (ảnh hợp lệ, index của ảnh hỏng)."""
    images: list[Image.Image] = []
    bad_indexes: list[int] = []
    for index, value in enumerate(encoded):
        try:
            raw = base64.b64decode(value, validate=True)
            image = Image.open(io.BytesIO(raw)).convert("RGB")
        except Exception:  # noqa: BLE001 — input không tin cậy, mọi lỗi đều là 400
            bad_indexes.append(index)
            continue
        images.append(image)
    return images, bad_indexes


@app.get("/health")
def health() -> dict:
    """Report model state without forcing an expensive load."""
    backend = _backend
    return {
        "status": "ok",
        "model": backend.model_name if backend else MODEL_NAME,
        "device": backend.device if backend else "unloaded",
        "dim": backend.dim if backend else EMBED_DIM,
        "image_embed_loaded": backend is not None,
    }


@app.get("/live")
def live() -> dict[str, str]:
    return {"status": "alive"}


@app.post("/v1/warmup")
def warmup() -> dict:
    """Load the configured image encoder before readiness checks."""
    try:
        backend = _get_backend()
    except Exception as exc:
        logger.exception("Local recognition warmup failed")
        raise HTTPException(
            status_code=503,
            detail="Local recognition models are unavailable",
        ) from exc
    return {
        "image_embed_loaded": True,
        "image_embed_model": backend.model_name,
        "dim": backend.dim,
    }


@app.post("/v1/image-embeddings")
def create_image_embeddings(request: ImageEmbeddingRequest) -> ImageEmbeddingResponse:
    """Embed một batch ảnh, giữ nguyên thứ tự input qua trường ``index``."""
    if len(request.images) > MAX_BATCH_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"Batch of {len(request.images)} exceeds limit of {MAX_BATCH_SIZE}",
        )
    images, bad_indexes = _decode_images(request.images)
    if bad_indexes:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid base64 or image data at indexes: {bad_indexes}",
        )
    try:
        backend = _get_backend()
        vectors = backend.encode(images)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Image embedding failed")
        raise HTTPException(
            status_code=503,
            detail="Image embedding model is unavailable",
        ) from exc
    return ImageEmbeddingResponse(
        model=backend.model_name,
        dim=backend.dim,
        data=[
            ImageEmbeddingItem(index=index, embedding=vector)
            for index, vector in enumerate(vectors)
        ],
    )
