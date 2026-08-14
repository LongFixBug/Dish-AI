"""ASGI rate limiting for all API routes with stricter expensive-path quotas."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from backend.api.dependencies import token_manager
from backend.config import Settings
from backend.services.auth import AccessTokenError
from backend.services.rate_limit import RateLimitDecision, RateLimitStore

logger = logging.getLogger("foodai.rate_limit")


@dataclass(frozen=True)
class RateLimitPolicy:
    limit: int
    window_seconds: int


POLICIES = {
    ("POST", "/api/v1/auth/register"): RateLimitPolicy(10, 60),
    ("POST", "/api/v1/auth/login"): RateLimitPolicy(10, 60),
    ("POST", "/api/v1/auth/google"): RateLimitPolicy(10, 60),
    ("POST", "/api/v1/auth/refresh"): RateLimitPolicy(30, 60),
    ("POST", "/api/v1/analyze/vision-only"): RateLimitPolicy(3, 60),
    ("POST", "/api/v1/analyze"): RateLimitPolicy(10, 60),
    ("POST", "/api/v1/rag/chat"): RateLimitPolicy(10, 60),
    ("POST", "/api/v1/chat/stream"): RateLimitPolicy(10, 60),
    ("POST", "/api/v1/feedback/training-data"): RateLimitPolicy(20, 3600),
    ("GET", "/ready"): RateLimitPolicy(30, 60),
}
DEFAULT_POLICY = RateLimitPolicy(120, 60)

# Endpoint không yêu cầu đăng nhập: luôn đếm theo IP.
# Nếu đếm theo token, kẻ tấn công chỉ cần đính kèm một token rác bất kỳ
# là có ngay một hạn mức mới cho mỗi lần thử mật khẩu.
PUBLIC_PATHS = frozenset({
    "/api/v1/auth/register",
    "/api/v1/auth/login",
    "/api/v1/auth/google",
    "/api/v1/auth/refresh",
})

# Đường dẫn ngoài /api/ vẫn cần đếm vì chúng chạm tới Postgres/Redis/S3/Qdrant.
METERED_PATHS = frozenset({"/ready"})


def _is_metered(path: str) -> bool:
    return path.startswith("/api/") or path in METERED_PATHS


class RateLimitMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        *,
        store: RateLimitStore,
        settings: Settings,
    ) -> None:
        self.app = app
        self.store = store
        self.settings = settings

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        path = scope.get("path", "")
        if scope["type"] != "http" or not _is_metered(path):
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "GET")
        policy = POLICIES.get((method, path), DEFAULT_POLICY)
        identity = _request_identity(
            scope,
            self.settings,
            allow_token_identity=path not in PUBLIC_PATHS,
        )
        key = f"{method}:{path}:{identity}"
        try:
            decision = await self.store.hit(
                key,
                limit=policy.limit,
                window_seconds=policy.window_seconds,
            )
        except Exception:
            logger.exception("Rate-limit backend failed")
            if self.settings.is_production:
                response = JSONResponse(
                    {"detail": "Dịch vụ đang bận, vui lòng thử lại sau."},
                    status_code=503,
                )
                await response(scope, receive, send)
                return
            await self.app(scope, receive, send)
            return

        if not decision.allowed:
            response = JSONResponse(
                {"detail": "Bạn thao tác quá nhanh. Vui lòng thử lại sau."},
                status_code=429,
                headers=_rate_headers(decision, include_retry_after=True),
            )
            await response(scope, receive, send)
            return

        async def send_with_rate_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in _rate_headers(decision).items():
                    headers[name] = value
            await send(message)

        await self.app(scope, receive, send_with_rate_headers)


def _request_identity(
    scope: Scope,
    settings: Settings,
    *,
    allow_token_identity: bool = True,
) -> str:
    headers = Headers(scope=scope)
    authorization = headers.get("authorization", "")
    if allow_token_identity and authorization.lower().startswith("bearer "):
        try:
            claims = token_manager.decode_access_token(authorization[7:])
            return f"user:{claims.user_id}"
        except AccessTokenError:
            pass

    client_host = scope.get("client", ("unknown", 0))[0]
    if settings.trust_proxy_headers:
        forwarded = headers.get("x-forwarded-for")
        if forwarded:
            # Lấy hop PHẢI NHẤT: proxy chỉ nối thêm IP nó thấy vào cuối,
            # nên các hop bên trái là do client tự bịa ra được.
            client_host = forwarded.rsplit(",", 1)[-1].strip()
    return f"ip:{client_host}"


def _rate_headers(
    decision: RateLimitDecision,
    *,
    include_retry_after: bool = False,
) -> dict[str, str]:
    headers = {
        "X-RateLimit-Limit": str(decision.limit),
        "X-RateLimit-Remaining": str(decision.remaining),
    }
    if include_retry_after:
        headers["Retry-After"] = str(decision.retry_after)
    return headers
