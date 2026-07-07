"""FoodAI — FastAPI application entry point."""

from fastapi import FastAPI

from app.config import settings

import asyncio
from fastapi.responses import StreamingResponse
from app.api.chat import router as chat_router



app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI nhận diện món ăn + phân tích dinh dưỡng từ ảnh",
)


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "version": settings.app_version}

@app.get("/info")
async def health() -> dict[str, str]:
    """Mo ta ngan gon"""
    return {
    "app": settings.app_name,
    "author": "nguyen hai long",
    "model": settings.gemini_model
    }


@app.get("/stream-demo")
async def stream_demo():
    async def generate():
        for i in range(10):
            yield f"data: Token {i}\n\n"
            await asyncio.sleep(0.5)

    return StreamingResponse(generate(),
                            media_type="text/event-stream")
        

app.include_router(chat_router)