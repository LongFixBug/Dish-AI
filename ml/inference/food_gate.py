"""Standalone Food Gate service for deciding whether an image merits Vision."""

from __future__ import annotations

import asyncio
import math
import secrets
from collections.abc import Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Literal

import torch
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from PIL import Image
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from transformers import AutoConfig, AutoImageProcessor, AutoModelForImageClassification

from backend.api.upload_utils import (
    read_upload_limited,
    validate_and_sanitize_image,
    validate_image_content_type,
)
from ml.inference.runtime_device import InferenceDevice, resolve_inference_device


class FoodGateSettings(BaseSettings):
    """Configuration owned by the Food Gate container, not the main API."""

    model_config = SettingsConfigDict(env_prefix="FOOD_GATE_", extra="ignore")

    checkpoint_path: Path = Path("checkpoints/food_gate/siglip2_food_gate_best.pt")
    block_threshold: float = Field(default=0.90, ge=0, le=1)
    max_concurrency: int = Field(default=1, ge=1, le=16)
    service_token: str = ""
    device: InferenceDevice = "auto"

    def decide(self, *, non_food_score: float) -> Literal["block", "vision"]:
        if not math.isfinite(non_food_score) or not 0 <= non_food_score <= 1:
            raise ValueError("non_food_score must be between 0 and 1")
        return "block" if non_food_score >= self.block_threshold else "vision"


@dataclass(frozen=True)
class FoodGatePrediction:
    food_score: float
    non_food_score: float


class FoodGateResponse(BaseModel):
    action: Literal["block", "vision"]
    food_score: float = Field(ge=0, le=1)
    non_food_score: float = Field(ge=0, le=1)
    block_threshold: float = Field(ge=0, le=1)


class FoodGatePredictor:
    """Loads the fine-tuned SigLIP2 classifier once and predicts sanitized images."""

    def __init__(
        self,
        *,
        processor,
        model,
        label2id: dict[str, int],
        device: str,
        dtype: torch.dtype,
    ) -> None:
        self._processor = processor
        self._model = model
        self._label2id = label2id
        self._device = device
        self._dtype = dtype

    @staticmethod
    def _checkpoint_dtype(state_dict: dict[str, torch.Tensor]) -> torch.dtype:
        """Return the floating-point dtype used by the stored model weights.

        Production sidecars use the same loader for the original FP32 artifact
        and the smaller FP16 artifact.  Looking at the artifact instead of an
        environment flag keeps the deployment immutable and prevents a dtype
        mismatch between the model and its state dict.
        """
        for value in state_dict.values():
            if torch.is_floating_point(value):
                return value.dtype
        return torch.float32

    @classmethod
    def load(cls, settings: FoodGateSettings) -> FoodGatePredictor:
        if not settings.checkpoint_path.is_file():
            raise FileNotFoundError(
                f"Food Gate checkpoint không tồn tại: {settings.checkpoint_path}"
            )

        checkpoint = torch.load(
            settings.checkpoint_path,
            map_location="cpu",
            weights_only=True,
        )
        checkpoint_name = checkpoint["checkpoint"]
        label2id = checkpoint["label2id"]
        id2label = checkpoint["id2label"]

        # The fine-tuned checkpoint already contains the complete vision model
        # and classifier. Only the small config/processor files are baked into
        # the image; never download the original base weights at service start.
        processor = AutoImageProcessor.from_pretrained(
            checkpoint_name,
            local_files_only=True,
        )
        config = AutoConfig.from_pretrained(checkpoint_name, local_files_only=True)
        config.num_labels = 2
        config.id2label = id2label
        config.label2id = label2id
        dtype = cls._checkpoint_dtype(checkpoint["model_state_dict"])
        previous_dtype = torch.get_default_dtype()
        torch.set_default_dtype(dtype)
        try:
            model = AutoModelForImageClassification.from_config(config)
        finally:
            torch.set_default_dtype(previous_dtype)
        model.load_state_dict(checkpoint["model_state_dict"])
        device = resolve_inference_device(
            requested=settings.device,
            cuda_available=torch.cuda.is_available(),
            mps_available=torch.backends.mps.is_available(),
        )
        model = model.to(device)
        model.eval()
        return cls(
            processor=processor,
            model=model,
            label2id=label2id,
            device=device,
            dtype=dtype,
        )

    def predict(self, image: Image.Image) -> FoodGatePrediction:
        inputs = self._processor(images=image, return_tensors="pt")
        inputs = {
            name: (
                value.to(device=self._device, dtype=self._dtype)
                if torch.is_floating_point(value)
                else value.to(self._device)
            )
            for name, value in inputs.items()
        }
        with torch.inference_mode():
            outputs = self._model(**inputs)
        scores = torch.softmax(outputs.logits, dim=1)[0]
        return FoodGatePrediction(
            food_score=scores[self._label2id["food"]].item(),
            non_food_score=scores[self._label2id["non_food"]].item(),
        )


PredictorFactory = Callable[[FoodGateSettings], FoodGatePredictor]


def create_app(
    *,
    settings: FoodGateSettings | None = None,
    predictor_factory: PredictorFactory = FoodGatePredictor.load,
) -> FastAPI:
    """Build the isolated HTTP service without loading a model at import time."""

    service_settings = settings or FoodGateSettings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.predictor = await asyncio.to_thread(predictor_factory, service_settings)
        app.state.prediction_semaphore = asyncio.Semaphore(service_settings.max_concurrency)
        yield

    app = FastAPI(title="FoodAI Food Gate", version="1.0.0", lifespan=lifespan)

    @app.get("/live")
    async def live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready")
    async def ready(request: Request) -> dict[str, str]:
        if not hasattr(request.app.state, "predictor"):
            raise HTTPException(status_code=503, detail="Food Gate chưa sẵn sàng.")
        return {"status": "ready"}

    @app.post("/predict", response_model=FoodGateResponse)
    async def predict(request: Request, file: UploadFile = File(...)) -> FoodGateResponse:
        if service_settings.service_token:
            supplied_token = request.headers.get("X-Food-Gate-Token", "")
            if not secrets.compare_digest(supplied_token, service_settings.service_token):
                raise HTTPException(status_code=403, detail="Không được phép gọi Food Gate.")

        validate_image_content_type(file)
        content = await read_upload_limited(file)
        sanitized = validate_and_sanitize_image(content, file.content_type)

        with Image.open(BytesIO(sanitized.content)) as opened_image:
            image = opened_image.convert("RGB")

        async with request.app.state.prediction_semaphore:
            prediction = await asyncio.to_thread(request.app.state.predictor.predict, image)

        action = service_settings.decide(non_food_score=prediction.non_food_score)
        return FoodGateResponse(
            action=action,
            food_score=prediction.food_score,
            non_food_score=prediction.non_food_score,
            block_threshold=service_settings.block_threshold,
        )

    return app


app = create_app()
