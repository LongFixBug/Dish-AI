"""Rate-limit contracts for public and expensive API traffic."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.config import Settings
from backend.middleware.rate_limit import RateLimitMiddleware, _request_identity
from backend.services.auth import TokenManager
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


def test_public_auth_endpoints_ignore_a_bearer_token_when_counting() -> None:
    """Đính kèm token hợp lệ không được cấp thêm hạn mức cho /login.

    /login không đọc Authorization, nên nếu middleware đếm theo token thì kẻ tấn
    công chỉ cần vài tài khoản rác là brute-force thoải mái từ một IP.
    """
    settings = Settings(_env_file=None)
    token, _ = TokenManager.from_settings(settings).create_access_token(
        user_id="00000000-0000-0000-0000-0000000000aa",
        role="user",
    )
    app = FastAPI()
    app.add_middleware(
        RateLimitMiddleware,
        store=MemoryRateLimitStore(clock=lambda: 1_000.0),
        settings=settings,
    )

    @app.post("/api/v1/auth/login")
    async def login() -> dict[str, bool]:
        return {"ok": True}

    with TestClient(app) as client:
        anonymous = [client.post("/api/v1/auth/login") for _ in range(10)]
        with_token = client.post(
            "/api/v1/auth/login",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert all(response.status_code == 200 for response in anonymous)
    assert with_token.status_code == 429


def test_forwarded_for_uses_the_rightmost_hop() -> None:
    """Proxy chỉ nối IP nó thấy vào CUỐI, các hop trái là do client tự bịa."""
    settings = Settings(_env_file=None, trust_proxy_headers=True)
    scope = {
        "type": "http",
        "client": ("10.0.0.1", 0),
        "headers": [(b"x-forwarded-for", b"1.1.1.1, 203.0.113.7")],
    }

    assert _request_identity(scope, settings) == "ip:203.0.113.7"


def test_memory_store_drops_expired_windows() -> None:
    """Key lạ (VD /api/<uuid> trả 404) không được tích tụ vĩnh viễn trong dict."""
    now = 1_000.0
    store = MemoryRateLimitStore(clock=lambda: now)
    store._windows = {
        f"stale-{index}": (now - 120, 1, now - 60)
        for index in range(MemoryRateLimitStore._SWEEP_THRESHOLD)
    }

    store._drop_expired(now)

    assert store._windows == {}
