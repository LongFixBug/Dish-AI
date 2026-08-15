from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as functional
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from PIL import Image
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from transformers import AutoImageProcessor, SiglipVisionModel

from backend.api.upload_utils import (
    read_upload_limited,
    validate_and_sanitize_image,
    validate_image_content_type,
)
from ml.inference.runtime_device import InferenceDevice, resolve_inference_device


DISPLAY_NAMES = {
    "banh_canh": "Bánh canh",
    "bun_bo_hue": "Bún bò Huế",
    "chao_long": "Cháo lòng",
    "hu_tieu": "Hủ tiếu",
    "pho_bo": "Phở bò",
}


class SiglipFoodV1Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SIGLIP_FOOD_V1_",
        extra="ignore",
    )

    encoder_dir: Path = Path("checkpoints/siglip_food_v1/encoder")
    classifier_head_path: Path = Path("checkpoints/siglip_food_v1/classifier_head.pt")

    top_k: int = Field(default=3, ge=1, le=5)
    max_concurrency: int = Field(default=1, ge=1, le=8)
    device: InferenceDevice = "auto"
    service_token: str = ""
    warm_on_startup: bool = False


class FoodCandidate(BaseModel):
    slug: str
    name: str
    score: float = Field(ge=0, le=1)


class FoodHintResponse(BaseModel):
    model_version: str = "siglip_food_v1"
    candidates: list[FoodCandidate]


class SiglipFoodV1Model(nn.Module):
    def __init__(self, encoder, num_classes: int) -> None:
        super().__init__()

        hidden_size = encoder.config.hidden_size

        self.encoder = encoder
        self.classifier = nn.Linear(hidden_size, num_classes)

    def forward(self, pixel_values):
        output = self.encoder(pixel_values=pixel_values)

        pooled = output.pooler_output

        if pooled is None:
            pooled = output.last_hidden_state[:, 0]

        embedding = functional.normalize(
            pooled,
            p=2,
            dim=-1,
        )

        return self.classifier(embedding)


@dataclass(frozen=True)
class SiglipFoodV1Predictor:
    processor: object
    model: object
    classes: tuple[str, ...]
    device: str
    top_k: int

    @classmethod
    def load(
        cls,
        settings: SiglipFoodV1Settings,
    ) -> "SiglipFoodV1Predictor":
        if not settings.encoder_dir.is_dir():
            raise FileNotFoundError(f"Không có encoder: {settings.encoder_dir}")

        if not settings.classifier_head_path.is_file():
            raise FileNotFoundError(f"Không có classifier head: {settings.classifier_head_path}")

        head_checkpoint = torch.load(
            settings.classifier_head_path,
            map_location="cpu",
            weights_only=True,
        )

        classes = tuple(head_checkpoint["classes"])

        if set(classes) != set(DISPLAY_NAMES):
            raise ValueError("Class checkpoint không khớp bộ 5 món siglip_food_v1")

        processor = AutoImageProcessor.from_pretrained(
            settings.encoder_dir,
            local_files_only=True,
        )

        encoder = SiglipVisionModel.from_pretrained(
            settings.encoder_dir,
            local_files_only=True,
        )

        model = SiglipFoodV1Model(
            encoder,
            len(classes),
        )

        model.classifier.load_state_dict(head_checkpoint["classifier_state_dict"])

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
            classes=classes,
            device=device,
            top_k=settings.top_k,
        )

    def predict(
        self,
        image: Image.Image,
    ) -> list[FoodCandidate]:
        inputs = self.processor(
            images=image,
            return_tensors="pt",
        )

        pixel_values = inputs["pixel_values"].to(self.device)

        with torch.inference_mode():
            logits = self.model(pixel_values)

        scores = torch.softmax(logits, dim=1)[0]

        ranked = sorted(
            zip(
                self.classes,
                scores.detach().cpu().tolist(),
                strict=True,
            ),
            key=lambda item: item[1],
            reverse=True,
        )

        return [
            FoodCandidate(
                slug=slug,
                name=DISPLAY_NAMES[slug],
                score=score,
            )
            for slug, score in ranked[: self.top_k]
        ]


def create_app(
    settings: SiglipFoodV1Settings | None = None,
) -> FastAPI:
    service_settings = settings or SiglipFoodV1Settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.predictor = await asyncio.to_thread(
            SiglipFoodV1Predictor.load,
            service_settings,
        )

        app.state.semaphore = asyncio.Semaphore(service_settings.max_concurrency)

        yield

    app = FastAPI(
        title="FoodAI SigLIP food-v1",
        version="1.0.0",
        lifespan=lifespan,
    )

    @app.get("/live")
    async def live() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready")
    async def ready(request: Request) -> dict[str, str]:
        if not hasattr(request.app.state, "predictor"):
            raise HTTPException(
                status_code=503,
                detail="SigLIP food-v1 chưa sẵn sàng",
            )

        return {"status": "ready"}

    @app.post("/predict", response_model=FoodHintResponse)
    async def predict(
        request: Request,
        file: UploadFile = File(...),
    ) -> FoodHintResponse:
        validate_image_content_type(file)

        content = await read_upload_limited(file)

        sanitized = validate_and_sanitize_image(
            content,
            file.content_type,
        )

        with Image.open(BytesIO(sanitized.content)) as opened_image:
            image = opened_image.convert("RGB")

        async with request.app.state.semaphore:
            candidates = await asyncio.to_thread(
                request.app.state.predictor.predict,
                image,
            )

        return FoodHintResponse(candidates=candidates)

    return app


app = create_app()
