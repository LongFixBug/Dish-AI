"""SigLIP food-hint routes shared by the CPU and GPU ML sidecars."""

from __future__ import annotations

import asyncio
import secrets
from contextlib import asynccontextmanager
from io import BytesIO

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from PIL import Image

from backend.api.upload_utils import (
    read_upload_limited,
    validate_and_sanitize_image,
    validate_image_content_type,
)
from ml.inference.siglip_food_v1 import (
    FoodHintResponse,
    SiglipFoodV1Predictor,
    SiglipFoodV1Settings,
)


def attach_siglip_food_hint_routes(app: FastAPI) -> None:
    """Attach optional, token-protected SigLIP candidate-hint routes."""

    load_lock = asyncio.Lock()

    async def load_predictor(sidecar_app: FastAPI) -> SiglipFoodV1Predictor:
        predictor = getattr(sidecar_app.state, "siglip_predictor", None)
        if predictor is not None:
            return predictor

        async with load_lock:
            predictor = getattr(sidecar_app.state, "siglip_predictor", None)
            if predictor is None:
                settings = SiglipFoodV1Settings()
                predictor = await asyncio.to_thread(SiglipFoodV1Predictor.load, settings)
                sidecar_app.state.siglip_predictor = predictor
                sidecar_app.state.siglip_semaphore = asyncio.Semaphore(
                    settings.max_concurrency
                )
            return predictor

    async def get_predictor(request: Request) -> SiglipFoodV1Predictor:
        return await load_predictor(request.app)

    food_gate_lifespan = app.router.lifespan_context

    @asynccontextmanager
    async def sidecar_lifespan(sidecar_app: FastAPI):
        async with food_gate_lifespan(sidecar_app):
            siglip_settings = SiglipFoodV1Settings()
            if siglip_settings.warm_on_startup:
                await load_predictor(sidecar_app)
            yield

    app.router.lifespan_context = sidecar_lifespan

    @app.get("/siglip/live")
    async def siglip_live() -> dict[str, str]:
        """Liveness does not load the model."""

        return {"status": "ok"}

    @app.get("/siglip/ready")
    async def siglip_ready(request: Request) -> dict[str, str]:
        """Report whether the model was loaded without loading it."""

        if getattr(request.app.state, "siglip_predictor", None) is None:
            return {"status": "cold"}
        return {"status": "ready"}

    @app.post("/siglip/predict", response_model=FoodHintResponse)
    async def siglip_predict(
        request: Request,
        file: UploadFile = File(...),
    ) -> FoodHintResponse:
        """Return candidates for Vision; never decide nutrition identity."""

        siglip_settings = SiglipFoodV1Settings()
        if siglip_settings.service_token:
            supplied_token = request.headers.get("X-Food-Gate-Token", "")
            if not secrets.compare_digest(supplied_token, siglip_settings.service_token):
                raise HTTPException(
                    status_code=403,
                    detail="Không được phép gọi SigLIP Food Hint.",
                )

        validate_image_content_type(file)
        content = await read_upload_limited(file)
        sanitized = validate_and_sanitize_image(content, file.content_type)

        with Image.open(BytesIO(sanitized.content)) as opened_image:
            image = opened_image.convert("RGB")

        try:
            predictor = await get_predictor(request)
        except Exception as exc:  # noqa: BLE001 - API chính will fail open to Vision
            raise HTTPException(
                status_code=503,
                detail="SigLIP food hint chưa sẵn sàng.",
            ) from exc

        semaphore = request.app.state.siglip_semaphore
        async with semaphore:
            candidates = await asyncio.to_thread(predictor.predict, image)
        return FoodHintResponse(candidates=candidates)
