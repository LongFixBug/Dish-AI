"""Production readiness checks for required FoodAI dependencies."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable

from redis.asyncio import Redis
from sqlalchemy import text

from backend.config import settings
from backend.db.postgres import async_session
from backend.services.object_storage import create_object_storage
from backend.services.vector_catalog import check_qdrant_health

object_storage = create_object_storage(settings)
CHECK_TIMEOUT_SECONDS = 3.0
CACHE_SECONDS = 5.0

_cached: tuple[float, dict[str, object]] | None = None
_cache_lock = asyncio.Lock()


async def check_readiness() -> dict[str, object]:
    """Kết quả readiness có cache vài giây.

    ``/ready`` là endpoint công khai; nếu mỗi lần gọi đều mở session Postgres,
    client Redis mới và gọi S3/Qdrant thì chỉ cần một vòng lặp curl là cạn
    connection pool. Giữ lock trong lúc dò để nhiều request đồng thời chỉ tốn
    một lượt kiểm tra.
    """
    global _cached
    async with _cache_lock:
        if _cached is not None and time.monotonic() - _cached[0] < CACHE_SECONDS:
            return _cached[1]
        report = await _probe_components()
        _cached = (time.monotonic(), report)
        return report


async def _probe_components() -> dict[str, object]:
    checks: dict[str, Callable[[], Awaitable[None]]] = {
        "postgres": _check_postgres,
        "object_storage": object_storage.healthcheck,
    }
    if settings.qdrant_required:
        checks["qdrant"] = _check_qdrant
    if settings.rate_limit_backend == "redis":
        checks["redis"] = _check_redis
    if settings.vision_enabled:
        checks["vision"] = _check_vision_config
    if settings.cv_enabled:
        checks["cv_model"] = _check_cv_model
    if settings.chat_enabled:
        checks["llm"] = _check_chat_llm

    names = list(checks)
    results = await asyncio.gather(
        *(_run_check(checks[name]) for name in names),
    )
    components = dict(zip(names, results, strict=True))
    ready = all(component["ready"] for component in components.values())
    return {
        "status": "ready" if ready else "not_ready",
        "components": components,
    }


async def _run_check(check: Callable[[], Awaitable[None]]) -> dict[str, object]:
    try:
        await asyncio.wait_for(check(), timeout=CHECK_TIMEOUT_SECONDS)
    except Exception as exc:
        return {"ready": False, "detail": type(exc).__name__}
    return {"ready": True, "detail": "ok"}


async def _check_postgres() -> None:
    async with async_session() as session:
        await session.execute(text("SELECT 1"))


async def _check_qdrant() -> None:
    await asyncio.to_thread(check_qdrant_health)


async def _check_redis() -> None:
    client = Redis.from_url(
        settings.redis_url,
        socket_connect_timeout=1,
        socket_timeout=1,
        retry_on_timeout=False,
    )
    try:
        await client.ping()
    finally:
        await client.aclose()


async def _check_vision_config() -> None:
    if not settings.vision_api_key:
        raise RuntimeError("Vision API key is missing")


async def _check_cv_model() -> None:
    from ml.inference.cv import cv_model

    if not cv_model.is_loaded:
        raise RuntimeError("CV model is not loaded")


async def _check_chat_llm() -> None:
    from backend.services.chat_llm import check_chat_health

    await check_chat_health()
