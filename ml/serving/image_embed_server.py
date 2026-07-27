"""SigLIP 2 image-embedding sidecar (port 8082).

Phục vụ vector ảnh 768 chiều (L2-normalized) cho dish photo matching. Model
chỉ được load lười ở request đầu tiên; import module này KHÔNG kéo theo
torch/transformers nên test và tooling nhẹ nhàng.

API contract:
- ``POST /v1/image-embeddings`` body ``{"images": ["<base64>", ...]}`` →
  ``{"model": str, "dim": 768, "data": [{"index": int, "embedding": [...]}]}``
- ``GET /health`` → ``{"status": "ok", "model": str, "device": str, "dim": 768}``
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
MODEL_NAME = os.environ.get("IMAGE_EMBED_MODEL", DEFAULT_MODEL)
EMBED_DIM = 768
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


_backend: EmbeddingBackend | None = None
_backend_lock = threading.Lock()


def _load_backend() -> EmbeddingBackend:
    """Load SigLIP 2 lazily. torch/transformers chỉ import ở đây, không ở module."""
    import torch
    from transformers import AutoImageProcessor, AutoModel

    device = "mps" if torch.backends.mps.is_available() else "cpu"
    logger.info("Loading image embedding model %s on %s", MODEL_NAME, device)
    processor = AutoImageProcessor.from_pretrained(MODEL_NAME)
    model = AutoModel.from_pretrained(MODEL_NAME).to(device).eval()

    def encode(images: list[Image.Image]) -> list[list[float]]:
        inputs = processor(images=images, return_tensors="pt").to(device)
        with torch.inference_mode():
            features = _extract_image_features(model, inputs)
            normalized = torch.nn.functional.normalize(features, p=2, dim=-1)
        return normalized.cpu().tolist()

    return EmbeddingBackend(model_name=MODEL_NAME, device=device, encode=encode)


def _extract_image_features(model, inputs):
    """Lấy pooled image features, chống đỡ khác biệt API giữa các bản transformers.

    transformers v5 (``Siglip2Model.get_image_features``) trả về
    ``BaseModelOutputWithPooling`` (lấy ``pooler_output``), trong khi v4 trả
    thẳng tensor. Checkpoint chỉ có vision tower thì không có
    ``get_image_features`` → gọi ``vision_model`` trực tiếp.
    """
    import torch

    if hasattr(model, "get_image_features"):
        output = model.get_image_features(**inputs)
    else:
        output = model.vision_model(**inputs)
    if isinstance(output, torch.Tensor):
        return output
    pooled = getattr(output, "pooler_output", None)
    if pooled is not None:
        return pooled
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
    """Health không ép load model: chưa load thì báo device ``unloaded``."""
    backend = _backend
    return {
        "status": "ok",
        "model": backend.model_name if backend else MODEL_NAME,
        "device": backend.device if backend else "unloaded",
        "dim": EMBED_DIM,
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
        dim=EMBED_DIM,
        data=[
            ImageEmbeddingItem(index=index, embedding=vector)
            for index, vector in enumerate(vectors)
        ],
    )
