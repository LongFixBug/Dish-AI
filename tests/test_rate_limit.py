"""Rate-limit contracts for public and expensive API traffic."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.config import Settings
from backend.middleware.rate_limit import RateLimitMiddleware
from backend.services.rate_limit import MemoryRateLimitStore


async def test_memory_rate_limit_blocks_after_quota_and_resets_window() -> None:
    now = 1_000.0
    store = MemoryRateLimitStore(clock=lambda: now)

    first = await store.hit("analyze:user-1", limit=2, window_seconds=60)
    second = await store.hit("analyze:user-1", limit=2, window_seconds=60)
    blocked = await store.hit("analyze:user-1", limit=2, window_seconds=60)

    assert first.allowed is True
    assert first.remaining == 1
    assert second.allowed is True
    assert second.remaining == 0
    assert blocked.allowed is False
    assert blocked.retry_after == 60

    now += 61
    reset = await store.hit("analyze:user-1", limit=2, window_seconds=60)
    assert reset.allowed is True
    assert reset.remaining == 1


async def test_rate_limit_keys_are_isolated_per_identity() -> None:
    store = MemoryRateLimitStore(clock=lambda: 1_000.0)

    await store.hit("vision:user-1", limit=1, window_seconds=60)
    other_user = await store.hit("vision:user-2", limit=1, window_seconds=60)

    assert other_user.allowed is True


def test_api_middleware_returns_429_with_retry_headers() -> None:
    app = FastAPI()
    app.add_middleware(
        RateLimitMiddleware,
        store=MemoryRateLimitStore(clock=lambda: 1_000.0),
        settings=Settings(_env_file=None),
    )

    @app.post("/api/v1/analyze")
    async def expensive_endpoint() -> dict[str, bool]:
        return {"ok": True}

    with TestClient(app) as client:
        responses = [client.post("/api/v1/analyze") for _ in range(11)]

    assert all(response.status_code == 200 for response in responses[:10])
    assert "retry-after" not in responses[0].headers
    assert responses[-1].status_code == 429
    assert responses[-1].headers["retry-after"] == "60"
    assert responses[-1].headers["x-ratelimit-remaining"] == "0"
