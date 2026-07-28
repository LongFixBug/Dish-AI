"""FoodAI — FastAPI application entry point."""

import asyncio
import logging
import secrets
from contextlib import asynccontextmanager

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse, Response, StreamingResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from backend.api.chat import router as chat_router
from backend.api.auth import router as auth_router
from backend.api.analyze import router as analyze_router
from backend.api.dishes import router as dishes_router
from backend.api.feedback import router as feedback_router
from backend.api.meals import router as meals_router
from backend.api.nutrition_goals import router as nutrition_goals_router
from backend.api.suggestions import router as suggestions_router
from backend.config import settings
from backend.db.postgres import engine
from backend.middleware.rate_limit import RateLimitMiddleware
from backend.middleware.observability import ObservabilityMiddleware
from backend.logging_config import configure_logging
from backend.services.rate_limit import MemoryRateLimitStore, RedisRateLimitStore
from backend.services.readiness import check_readiness

logger = logging.getLogger("foodai")

configure_logging(settings.log_level)

rate_limit_store = (
    RedisRateLimitStore(settings.redis_url)
    if settings.rate_limit_backend == "redis"
    else MemoryRateLimitStore()
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize optional local inference and semantic-search dependencies.

    Both initializers run outside the event loop. Their failure is non-fatal:
    Vision analysis and exact PostgreSQL lookup remain available respectively.
    """
    if settings.cv_enabled:
        try:
            from ml.inference.cv import cv_model

            await asyncio.to_thread(cv_model.load)
            logger.info("CV model loaded (%d classes)", len(cv_model.classes))
        except Exception:
            logger.exception("CV load failed")

    try:
        from backend.services.vector_catalog import init_collection

        await asyncio.to_thread(init_collection)
    except Exception:
        logger.exception("Qdrant init failed; exact catalog lookup remains available")

    try:
        yield
    finally:
        from backend.services.embeddings import close_embedding_client
        from backend.services.chat_llm import close_chat_client
        from ml.inference.vision import close_vision_client

        await close_embedding_client()
        await close_chat_client()
        await close_vision_client()
        await rate_limit_store.close()
        await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="AI nhận diện món ăn + phân tích dinh dưỡng từ ảnh",
    lifespan=lifespan,
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None if settings.is_production else "/redoc",
    openapi_url=None if settings.is_production else "/openapi.json",
)
app.add_middleware(
    RateLimitMiddleware,
    store=rate_limit_store,
    settings=settings,
)
app.add_middleware(ObservabilityMiddleware)


@app.get("/health")
async def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok", "version": settings.app_version}


@app.get("/live")
async def live() -> dict[str, str]:
    """Process liveness; external dependency failures do not affect it."""
    return {"status": "alive", "version": settings.app_version}


@app.get("/ready")
async def ready() -> JSONResponse:
    """Return 503 until every explicitly required capability is ready."""
    report = await check_readiness()
    status_code = 200 if report["status"] == "ready" else 503
    return JSONResponse(report, status_code=status_code)


@app.get("/metrics", include_in_schema=False)
async def metrics(
    authorization: str | None = Header(default=None),
) -> Response:
    if not settings.metrics_enabled:
        raise HTTPException(status_code=404, detail="Not found")
    if settings.metrics_token:
        expected = f"Bearer {settings.metrics_token}"
        # So sánh trên bytes: compare_digest ném TypeError với chuỗi có ký tự non-ASCII.
        if authorization is None or not secrets.compare_digest(
            authorization.encode("utf-8", "ignore"),
            expected.encode("utf-8"),
        ):
            raise HTTPException(status_code=401, detail="Unauthorized")
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


if not settings.is_production and settings.enable_dev_routes:
    @app.get("/info")
    async def info() -> dict[str, str]:
        """Development-only application information."""
        return {
            "app": settings.app_name,
            "author": "nguyen hai long",
            "vision_model": settings.vision_model,
            "llm_model": settings.llm_model,
        }

    @app.get("/stream-demo")
    async def stream_demo():
        """Development-only SSE streaming demo."""
        async def generate():
            for i in range(10):
                yield f"data: Token {i}\n\n"
                await asyncio.sleep(0.5)

        return StreamingResponse(generate(), media_type="text/event-stream")


app.include_router(chat_router)
app.include_router(auth_router)
app.include_router(analyze_router)
app.include_router(dishes_router)
app.include_router(feedback_router)
app.include_router(meals_router)
app.include_router(nutrition_goals_router)
app.include_router(suggestions_router)
