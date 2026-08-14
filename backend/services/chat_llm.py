"""Small OpenAI-compatible llama.cpp client for planner JSON and SSE output."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from backend.config import settings
from backend.services.resilience import CircuitBreaker, CircuitOpenError

CHAT_COMPLETIONS_URL = f"{settings.llm_url.rstrip('/')}/v1/chat/completions"
CHAT_HEALTH_URL = f"{settings.llm_url.rstrip('/')}/health"
_client: httpx.AsyncClient | None = None
_client_lock = asyncio.Lock()
_semaphore = asyncio.Semaphore(settings.llm_max_concurrency)
_breaker = CircuitBreaker(failure_threshold=5, recovery_seconds=30)


class ChatModelError(RuntimeError):
    """Downstream model is unavailable or returned an invalid response."""


def _auth_headers() -> dict[str, str]:
    """Authenticate only when the configured model is a cloud endpoint."""
    if not settings.llm_api_key:
        return {}
    return {"Authorization": f"Bearer {settings.llm_api_key}"}


async def check_chat_health() -> None:
    """Raise unless the configured llama.cpp server is ready."""
    response = await (await _get_client()).get(CHAT_HEALTH_URL, headers=_auth_headers())
    response.raise_for_status()


async def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is not None and not _client.is_closed:
        return _client
    async with _client_lock:
        if _client is None or _client.is_closed:
            _client = httpx.AsyncClient(
                timeout=httpx.Timeout(settings.chat_request_timeout_seconds),
            )
        return _client


async def complete_json(
    messages: list[dict[str, str]],
    *,
    schema: dict[str, Any],
) -> dict[str, Any]:
    payload = {
        "model": settings.llm_model,
        "messages": messages,
        "temperature": 0,
        "max_tokens": 512,
        "stream": False,
        "response_format": {
            "type": "json_schema",
            "json_schema": {
                "name": "balance_chat_plan",
                "strict": True,
                "schema": schema,
            },
        },
    }
    try:
        async with _semaphore:

            async def operation() -> httpx.Response:
                response = await (await _get_client()).post(
                    CHAT_COMPLETIONS_URL,
                    json=payload,
                    headers=_auth_headers(),
                )
                response.raise_for_status()
                return response

            response = await _breaker.call(operation)
        body = response.json()
        content = body["choices"][0]["message"]["content"]
        parsed = json.loads(content)
    except (
        CircuitOpenError,
        httpx.HTTPError,
        KeyError,
        IndexError,
        TypeError,
        json.JSONDecodeError,
    ) as exc:
        raise ChatModelError("Không đọc được kế hoạch từ model.") from exc
    if not isinstance(parsed, dict):
        raise ChatModelError("Model trả về kế hoạch không hợp lệ.")
    return parsed


async def stream_completion(
    messages: list[dict[str, str]],
) -> AsyncIterator[str]:
    payload = {
        "model": settings.llm_model,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 700,
        "stream": True,
    }
    stream_context = None
    try:
        async with _semaphore:
            client = await _get_client()
            stream_context = client.stream(
                "POST",
                CHAT_COMPLETIONS_URL,
                json=payload,
                headers=_auth_headers(),
            )

            async def open_stream() -> httpx.Response:
                response = await stream_context.__aenter__()
                try:
                    response.raise_for_status()
                except Exception:
                    await stream_context.__aexit__(None, None, None)
                    raise
                return response

            response = await _breaker.call(open_stream)
            try:
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    raw = line[5:].strip()
                    if raw == "[DONE]":
                        return
                    try:
                        chunk = json.loads(raw)
                        delta = chunk["choices"][0].get("delta", {})
                        content = delta.get("content")
                    except (json.JSONDecodeError, KeyError, IndexError, TypeError):
                        continue
                    if isinstance(content, str) and content:
                        yield content
            finally:
                await stream_context.__aexit__(None, None, None)
    except (CircuitOpenError, httpx.HTTPError) as exc:
        raise ChatModelError("Model chat hiện không sẵn sàng.") from exc


async def close_chat_client() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
