"""FoodAI — FastAPI application entry point."""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from backend.api.chat import router as chat_router
from backend.api.analyze import router as analyze_router
from backend.api.dishes import router as dishes_router
from backend.api.feedback import router as feedback_router
from backend.config import settings

logger = logging.getLogger("foodai")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load CV model lúc startup (asyncio.to_thread vì torch.load sync).

    Load fail → log warning, app vẫn start (vision-only fallback).
    Lazy import — torch + timm + PIL không bị load nếu CV disabled,
    tiết kiệm hàng trăm MB RAM lúc startup.
    """
    try:
        from ml.inference.cv import cv_model

        await asyncio.to_thread(cv_model.load)
        logger.info("CV model loaded (%d classes)", len(cv_model.classes))
    except Exception as e:
        logger.warning("CV load failed — vision-only fallback: %s", e)
        import traceback
        traceback.print_exc()

    # ── Init Qdrant dishes collection ──────────────────────────────────
    try:
        from backend.services.qdrant_dishes import init_collection

        init_collection()
    except Exception as e:
        logger.warning("Qdrant init failed — vector search disabled: %s", e)

    yield


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI nhận diện món ăn + phân tích dinh dưỡng từ ảnh",
    lifespan=lifespan,
)


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "version": settings.app_version}


@app.get("/info")
async def info() -> dict[str, str]:
    """Thông tin ứng dụng."""
    return {
        "app": settings.app_name,
        "author": "nguyen hai long", 
        "vision_model": settings.vision_model,
        "llm_model": settings.llm_model,
    }


@app.get("/stream-demo")
async def stream_demo():
    """Demo SSE streaming."""
    async def generate():
        for i in range(10):
            yield f"data: Token {i}\n\n"
            await asyncio.sleep(0.5)

    return StreamingResponse(generate(), media_type="text/event-stream")


app.include_router(chat_router)
app.include_router(analyze_router)
app.include_router(dishes_router)
app.include_router(feedback_router)

# Static mount for processed analyze images so Streamlit can display them
app.mount("/uploads", StaticFiles(directory="data/uploads"), name="uploads")
