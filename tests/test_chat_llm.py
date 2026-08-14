"""Offline contracts for the OpenAI-compatible llama.cpp chat client."""

import json

import httpx
import pytest

from backend.services import chat_llm
from backend.services.resilience import CircuitBreaker


def _use_transport(monkeypatch, handler) -> None:
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(chat_llm, "_client", client)
    monkeypatch.setattr(
        chat_llm,
        "_breaker",
        CircuitBreaker(failure_threshold=5, recovery_seconds=30),
    )


@pytest.mark.asyncio
async def test_health_and_json_completion_use_llama_contract(monkeypatch) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path == "/health":
            return httpx.Response(200, json={"status": "ok"})
        payload = json.loads(request.content)
        assert payload["stream"] is False
        assert payload["response_format"]["type"] == "json_schema"
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": '{"route":"general","calls":[]}',
                        }
                    }
                ]
            },
        )

    _use_transport(monkeypatch, handler)

    await chat_llm.check_chat_health()
    result = await chat_llm.complete_json(
        [{"role": "user", "content": "Xin chào"}],
        schema={"type": "object"},
    )

    assert result == {"route": "general", "calls": []}
    assert [request.url.path for request in requests] == [
        "/health",
        "/v1/chat/completions",
    ]
    await chat_llm.close_chat_client()
    assert chat_llm._client is None


@pytest.mark.asyncio
async def test_cloud_chat_completion_sends_bearer_token(monkeypatch) -> None:
    captured: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": '{"route":"general","calls":[]}'}},
                ]
            },
        )

    monkeypatch.setattr(chat_llm.settings, "llm_api_key", "cloud-test-key")
    _use_transport(monkeypatch, handler)

    result = await chat_llm.complete_json([], schema={"type": "object"})

    assert result == {"route": "general", "calls": []}
    assert captured[0].headers["authorization"] == "Bearer cloud-test-key"
    await chat_llm.close_chat_client()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(503, text="loading"),
        httpx.Response(
            200,
            json={"choices": [{"message": {"content": "not-json"}}]},
        ),
        httpx.Response(
            200,
            json={"choices": [{"message": {"content": "[]"}}]},
        ),
    ],
)
async def test_json_completion_converts_bad_downstream_responses(
    monkeypatch,
    response,
) -> None:
    _use_transport(monkeypatch, lambda _request: response)

    with pytest.raises(chat_llm.ChatModelError):
        await chat_llm.complete_json([], schema={"type": "object"})

    await chat_llm.close_chat_client()


@pytest.mark.asyncio
async def test_stream_completion_skips_bad_chunks_and_yields_text(monkeypatch) -> None:
    body = "\n".join(
        [
            ": keepalive",
            "data: not-json",
            'data: {"choices":[{"delta":{}}]}',
            'data: {"choices":[{"delta":{"content":"Xin "}}]}',
            'data: {"choices":[{"delta":{"content":"chào"}}]}',
            "data: [DONE]",
            "",
        ]
    )
    _use_transport(
        monkeypatch,
        lambda _request: httpx.Response(200, text=body),
    )

    chunks = [
        chunk
        async for chunk in chat_llm.stream_completion([{"role": "user", "content": "Xin chào"}])
    ]

    assert chunks == ["Xin ", "chào"]
    await chat_llm.close_chat_client()


@pytest.mark.asyncio
async def test_stream_completion_wraps_http_failure(monkeypatch) -> None:
    _use_transport(
        monkeypatch,
        lambda _request: httpx.Response(503, text="loading"),
    )

    with pytest.raises(chat_llm.ChatModelError):
        _ = [chunk async for chunk in chat_llm.stream_completion([])]

    await chat_llm.close_chat_client()
