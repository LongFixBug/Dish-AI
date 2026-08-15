"""Combined Railway sidecar for the Food Gate service slot.

Railway's trial environment already has one ML service for Food Gate.  Keep
the service slot small by exposing the optional SigLIP food-hint predictor and
the sticker segmenter from the same container.  The hint model is loaded
lazily on its first request; a cold start therefore remains fail-open to the
Vision path in the API.
"""

from __future__ import annotations

import asyncio
from io import BytesIO

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from PIL import Image

from backend.api.upload_utils import (
    read_upload_limited,
    validate_and_sanitize_image,
    validate_image_content_type,
)
from ml.inference.food_gate import create_app as create_food_gate_app
from ml.inference.siglip_food_v1 import (
    FoodHintResponse,
    SiglipFoodV1Predictor,
    SiglipFoodV1Settings,
)
from ml.serving.segment_server import app as segment_app


app: FastAPI = create_food_gate_app()
_siglip_load_lock = asyncio.Lock()


async def _get_siglip_predictor(request: Request) -> SiglipFoodV1Predictor:
    predictor = getattr(request.app.state, "siglip_predictor", None)
    if predictor is not None:
        return predictor

    async with _siglip_load_lock:
        predictor = getattr(request.app.state, "siglip_predictor", None)
        if predictor is None:
            settings = SiglipFoodV1Settings()
            predictor = await asyncio.to_thread(
                SiglipFoodV1Predictor.load,
                settings,
            )
            request.app.state.siglip_predictor = predictor
            request.app.state.siglip_semaphore = asyncio.Semaphore(
                settings.max_concurrency
            )
        return predictor


@app.get("/siglip/live")
async def siglip_live() -> dict[str, str]:
    """Liveness không nạp model, để Railway không chờ cold start."""

    return {"status": "ok"}


@app.get("/siglip/ready")
async def siglip_ready(request: Request) -> dict[str, str]:
    """Báo model đã warm hay còn cold; không làm hỏng Food Gate readiness."""

    if getattr(request.app.state, "siglip_predictor", None) is None:
        return {"status": "cold"}
    return {"status": "ready"}


@app.post("/siglip/predict", response_model=FoodHintResponse)
async def siglip_predict(
    request: Request,
    file: UploadFile = File(...),
) -> FoodHintResponse:
    """Trả candidate món cho Vision; không quyết định món hay dinh dưỡng."""

    validate_image_content_type(file)
    content = await read_upload_limited(file)
    sanitized = validate_and_sanitize_image(content, file.content_type)

    with Image.open(BytesIO(sanitized.content)) as opened_image:
        image = opened_image.convert("RGB")

    try:
        predictor = await _get_siglip_predictor(request)
    except Exception as exc:  # noqa: BLE001 - API chính sẽ fail-open về Vision
        raise HTTPException(
            status_code=503,
            detail="SigLIP food hint chưa sẵn sàng.",
        ) from exc

    semaphore = request.app.state.siglip_semaphore
    async with semaphore:
        candidates = await asyncio.to_thread(predictor.predict, image)
    return FoodHintResponse(candidates=candidates)


# Segment server giữ contract /v1/segment; mount prefix để API gọi
# http://food-gate.../segment/v1/segment trong cùng Railway service.
app.mount("/segment", segment_app)
