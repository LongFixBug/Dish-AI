"""Request IDs and low-cardinality Prometheus HTTP measurements."""

from __future__ import annotations

import re
import time
import uuid

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from backend.metrics import HTTP_IN_PROGRESS, HTTP_LATENCY, HTTP_REQUESTS
from backend.request_context import request_id_context

REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


class ObservabilityMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "GET")
        request_id = _request_id(scope)
        context_token = request_id_context.set(request_id)
        started = time.perf_counter()
        status_code = 500
        HTTP_IN_PROGRESS.labels(method=method).inc()

        async def send_with_request_id(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
                MutableHeaders(scope=message)["X-Request-ID"] = request_id
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            route = getattr(scope.get("route"), "path", "unmatched")
            HTTP_REQUESTS.labels(
                method=method,
                route=route,
                status=str(status_code),
            ).inc()
            HTTP_LATENCY.labels(method=method, route=route).observe(
                time.perf_counter() - started
            )
            HTTP_IN_PROGRESS.labels(method=method).dec()
            request_id_context.reset(context_token)


def _request_id(scope: Scope) -> str:
    candidate = Headers(scope=scope).get("x-request-id", "")
    if REQUEST_ID_PATTERN.fullmatch(candidate):
        return candidate
    return uuid.uuid4().hex
