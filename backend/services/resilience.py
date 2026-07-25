"""Reusable circuit breaker and resilient pooled HTTP client."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Protocol, TypeVar

import httpx

from backend.metrics import EXTERNAL_LATENCY, EXTERNAL_REQUESTS

T = TypeVar("T")


class AsyncHttpClient(Protocol):
    is_closed: bool

    async def post(self, url: str, **kwargs) -> httpx.Response: ...

    async def aclose(self) -> None: ...


class CircuitOpenError(RuntimeError):
    """The downstream dependency is temporarily isolated."""


class CircuitBreaker:
    def __init__(
        self,
        *,
        failure_threshold: int,
        recovery_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._failure_threshold = failure_threshold
        self._recovery_seconds = recovery_seconds
        self._clock = clock
        self._failure_count = 0
        self._opened_at: float | None = None
        self._lock = asyncio.Lock()

    @property
    def failure_count(self) -> int:
        return self._failure_count

    async def call(self, operation: Callable[[], Awaitable[T]]) -> T:
        async with self._lock:
            if self._opened_at is not None:
                if self._clock() - self._opened_at < self._recovery_seconds:
                    raise CircuitOpenError("Downstream circuit is open")
                self._opened_at = None
                self._failure_count = 0
        try:
            result = await operation()
        except Exception:
            async with self._lock:
                self._failure_count += 1
                if self._failure_count >= self._failure_threshold:
                    self._opened_at = self._clock()
            raise
        async with self._lock:
            self._failure_count = 0
            self._opened_at = None
        return result


class ResilientHttpClient:
    RETRYABLE = (
        httpx.ConnectError,
        httpx.ConnectTimeout,
        httpx.ReadTimeout,
        httpx.RemoteProtocolError,
        httpx.HTTPStatusError,
    )

    def __init__(
        self,
        *,
        service: str,
        timeout_seconds: float,
        max_concurrency: int,
        max_attempts: int = 2,
        client_factory: Callable[[], AsyncHttpClient] | None = None,
    ) -> None:
        self._service = service
        self._timeout = httpx.Timeout(timeout_seconds)
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._max_attempts = max_attempts
        self._client_factory = client_factory or (
            lambda: httpx.AsyncClient(timeout=self._timeout)
        )
        self._breaker = CircuitBreaker(
            failure_threshold=5,
            recovery_seconds=30,
        )
        self._client: AsyncHttpClient | None = None
        self._client_lock: asyncio.Lock | None = None

    async def _get_client(self) -> AsyncHttpClient:
        client = self._client
        if client is not None and not client.is_closed:
            return client
        lock = self._client_lock
        if lock is None:
            lock = asyncio.Lock()
            self._client_lock = lock
        async with lock:
            client = self._client
            if client is None or client.is_closed:
                client = self._client_factory()
                self._client = client
            return client

    async def post(self, url: str, **kwargs) -> httpx.Response:
        last_error: Exception | None = None
        for attempt in range(self._max_attempts):
            started = time.perf_counter()
            try:
                async def operation() -> httpx.Response:
                    async with self._semaphore:
                        client = await self._get_client()
                        response = await client.post(url, **kwargs)
                        if response.status_code >= 500:
                            response.raise_for_status()
                        return response

                response = await self._breaker.call(operation)
                EXTERNAL_REQUESTS.labels(
                    service=self._service,
                    outcome=str(response.status_code),
                ).inc()
                return response
            except self.RETRYABLE as exc:
                last_error = exc
                EXTERNAL_REQUESTS.labels(
                    service=self._service,
                    outcome="retryable_error",
                ).inc()
                if attempt + 1 >= self._max_attempts:
                    raise
                await asyncio.sleep(0.2 * (2**attempt))
            except CircuitOpenError:
                EXTERNAL_REQUESTS.labels(
                    service=self._service,
                    outcome="circuit_open",
                ).inc()
                raise
            finally:
                EXTERNAL_LATENCY.labels(service=self._service).observe(
                    time.perf_counter() - started
                )
        assert last_error is not None
        raise last_error

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
        self._client_lock = None
