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


async def test_recovery_lets_exactly_one_probe_through() -> None:
    """Half-open: hết thời gian chờ chỉ MỘT request được đi thử.

    Mở toang cho tất cả sẽ khiến mọi request đang dồn lại đập vào dịch vụ vừa
    chết, và vì bộ đếm đã reset nên phải hỏng thêm đủ ngưỡng lần nữa mới ngắt.
    """
    now = 1_000.0
    breaker = CircuitBreaker(
        failure_threshold=2,
        recovery_seconds=30,
        clock=lambda: now,
    )
    started = asyncio.Event()
    release = asyncio.Event()

    async def fail() -> None:
        raise TimeoutError("provider unavailable")

    async def slow_probe() -> str:
        started.set()
        await release.wait()
        return "ok"

    for _ in range(2):
        with pytest.raises(TimeoutError):
            await breaker.call(fail)

    now += 31
    probe = asyncio.create_task(breaker.call(slow_probe))
    await started.wait()

    # Trong lúc phép thử đang chạy, mọi request khác vẫn bị chặn.
    with pytest.raises(CircuitOpenError):
        await breaker.call(slow_probe)

    release.set()
    assert await probe == "ok"


async def test_a_failed_probe_reopens_the_circuit_immediately() -> None:
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

    now += 31
    with pytest.raises(TimeoutError):
        await breaker.call(fail)

    # Phép thử hỏng → ngắt lại ngay, không chờ đủ ngưỡng lần nữa.
    with pytest.raises(CircuitOpenError):
        await breaker.call(fail)
