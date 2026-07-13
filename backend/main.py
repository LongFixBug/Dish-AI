"""FoodAI — FastAPI application entry point."""

import asyncio

from fastapi import FastAPI
from fastapi.responses import StreamingResponse

from backend.api.chat import router as chat_router
from backend.api.analyze import router as analyze_router
from backend.api.dishes import router as dishes_router
from backend.config import settings

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
