"""Fixed-window rate-limit stores for local and distributed deployments."""

from __future__ import annotations

import asyncio
import math
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from redis.asyncio import Redis


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    limit: int
    remaining: int
    retry_after: int


class RateLimitStore(Protocol):
    async def hit(
        self,
        key: str,
        *,
        limit: int,
        window_seconds: int,
    ) -> RateLimitDecision: ...

    async def close(self) -> None: ...


class MemoryRateLimitStore:
    """Process-local limiter for development and deterministic tests."""

    #: Chỉ quét dọn khi dict đã đủ lớn, tránh tốn O(n) ở mỗi request.
    _SWEEP_THRESHOLD = 1024

    def __init__(self, *, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        # key -> (window_start, count, expires_at)
        self._windows: dict[str, tuple[float, int, float]] = {}
        self._lock = asyncio.Lock()

    async def hit(
        self,
        key: str,
        *,
        limit: int,
        window_seconds: int,
    ) -> RateLimitDecision:
        now = self._clock()
        async with self._lock:
            self._drop_expired(now)
            window_start, count, _ = self._windows.get(key, (now, 0, 0.0))
            if now - window_start >= window_seconds:
                window_start, count = now, 0
            count += 1
            self._windows[key] = (window_start, count, window_start + window_seconds)

        retry_after = max(1, math.ceil(window_seconds - (now - window_start)))
        return RateLimitDecision(
            allowed=count <= limit,
            limit=limit,
            remaining=max(0, limit - count),
            retry_after=retry_after,
        )

    def _drop_expired(self, now: float) -> None:
        """Xoá cửa sổ đã hết hạn để dict không phình vô hạn theo số key lạ."""
        if len(self._windows) < self._SWEEP_THRESHOLD:
            return
        self._windows = {
            key: window
            for key, window in self._windows.items()
            if window[2] > now
        }

    async def close(self) -> None:
        return None


class RedisRateLimitStore:
    """Atomic fixed-window counter shared by every API replica."""

    _HIT_SCRIPT = """
    local current = redis.call('INCR', KEYS[1])
    if current == 1 then
      redis.call('EXPIRE', KEYS[1], ARGV[1])
    end
    local ttl = redis.call('TTL', KEYS[1])
    return {current, ttl}
    """

    def __init__(self, url: str) -> None:
        self._client = Redis.from_url(
            url,
            decode_responses=True,
            socket_connect_timeout=1,
            socket_timeout=1,
            retry_on_timeout=False,
        )

    async def hit(
        self,
        key: str,
        *,
        limit: int,
        window_seconds: int,
    ) -> RateLimitDecision:
        result = await self._client.eval(
            self._HIT_SCRIPT,
            1,
            f"foodai:rate:{key}",
            window_seconds,
        )
        count, ttl = int(result[0]), max(1, int(result[1]))
        return RateLimitDecision(
            allowed=count <= limit,
            limit=limit,
            remaining=max(0, limit - count),
            retry_after=ttl,
        )

    async def close(self) -> None:
        await self._client.aclose()
