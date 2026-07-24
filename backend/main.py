"""FoodAI — FastAPI application entry point."""

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles

from backend.api.chat import router as chat_router
from backend.api.analyze import UPLOAD_DIR, router as analyze_router
from backend.api.dishes import router as dishes_router
from backend.api.feedback import router as feedback_router
from backend.config import settings

logger = logging.getLogger("foodai")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize optional local inference and semantic-search dependencies.

    Both initializers run outside the event loop. Their failure is non-fatal:
    Vision analysis and exact PostgreSQL lookup remain available respectively.
    """
    try:
        from ml.inference.cv import cv_model

        await asyncio.to_thread(cv_model.load)
        logger.info("CV model loaded (%d classes)", len(cv_model.classes))
    except Exception:
        logger.exception("CV load failed; continuing with Vision-only analysis")

    try:
        from backend.services.vector_catalog import init_collection

        await asyncio.to_thread(init_collection)
    except Exception:
        logger.exception("Qdrant init failed; exact catalog lookup remains available")

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

# Serve generated previews from the same absolute directory used by the API.
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")
