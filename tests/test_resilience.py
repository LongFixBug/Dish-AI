"""Circuit breaker contracts for Vision and embedding dependencies."""

import asyncio

import httpx

import pytest

from backend.services.resilience import (
    CircuitBreaker,
    CircuitOpenError,
    ResilientHttpClient,
)


async def test_circuit_opens_after_failures_and_recovers_after_timeout() -> None:
    now = 1_000.0
    breaker = CircuitBreaker(
        failure_threshold=2,
        recovery_seconds=30,
        clock=lambda: now,
    )

    async def fail() -> None:
        raise TimeoutError("provider unavailable")

    for _ in range(2):
        with pytest.raises(TimeoutError):
            await breaker.call(fail)

    with pytest.raises(CircuitOpenError):
        await breaker.call(fail)

    now += 31

    async def succeed() -> str:
        return "ok"

    assert await breaker.call(succeed) == "ok"
    assert breaker.failure_count == 0


async def test_concurrent_first_requests_share_one_http_client() -> None:
    created = 0

    class FakeClient:
        is_closed = False

        async def post(self, url: str, **kwargs) -> httpx.Response:
            del kwargs
            await asyncio.sleep(0)
            return httpx.Response(200, request=httpx.Request("POST", url))

        async def aclose(self) -> None:
            self.is_closed = True

    def create_client() -> FakeClient:
        nonlocal created
        created += 1
        return FakeClient()

    client = ResilientHttpClient(
        service="test",
        timeout_seconds=1,
        max_concurrency=2,
        client_factory=create_client,
    )

    await asyncio.gather(
        client.post("https://example.com/one"),
        client.post("https://example.com/two"),
    )
    await client.close()

    assert created == 1
