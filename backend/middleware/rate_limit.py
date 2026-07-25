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
    ("POST", "/api/v1/auth/refresh"): RateLimitPolicy(30, 60),
    ("POST", "/api/v1/analyze/vision-only"): RateLimitPolicy(3, 60),
    ("POST", "/api/v1/analyze"): RateLimitPolicy(10, 60),
    ("POST", "/api/v1/feedback/training-data"): RateLimitPolicy(20, 3600),
}
DEFAULT_POLICY = RateLimitPolicy(120, 60)


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
        if scope["type"] != "http" or not path.startswith("/api/"):
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "GET")
        policy = POLICIES.get((method, path), DEFAULT_POLICY)
        identity = _request_identity(scope, self.settings)
        key = f"{method}:{path}:{identity}"
        try:
            decision = await self.store.hit(
                key,
                limit=policy.limit,
                window_seconds=policy.window_seconds,
            )
        except Exception:
            logger.exception("Rate-limit backend failed")
            if self.settings.environment.lower() == "production":
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


def _request_identity(scope: Scope, settings: Settings) -> str:
    headers = Headers(scope=scope)
    authorization = headers.get("authorization", "")
    if authorization.lower().startswith("bearer "):
        try:
            claims = token_manager.decode_access_token(authorization[7:])
            return f"user:{claims.user_id}"
        except AccessTokenError:
            pass

    client_host = scope.get("client", ("unknown", 0))[0]
    if settings.trust_proxy_headers:
        forwarded = headers.get("x-forwarded-for")
        if forwarded:
            client_host = forwarded.split(",", 1)[0].strip()
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
