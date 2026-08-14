"""Orchestration tests for grounded and deterministic chat responses."""

import pytest
from langchain_core.documents import Document

from backend.services import chat_service
from backend.services.chat_service import ToolContext
from schemas.chat import ChatPlan, ChatRequest, ChatSource


async def _events(iterator):
    return [event async for event in iterator]


@pytest.mark.asyncio
async def test_out_of_scope_is_deterministic_and_never_calls_answer_model(
    monkeypatch,
) -> None:
    async def plan(*_args, **_kwargs):
        return ChatPlan(route="out_of_scope", calls=[])

    async def should_not_run(*_args, **_kwargs):
        raise AssertionError("answer model must not run")
        yield

    monkeypatch.setattr(chat_service, "_plan", plan)
    monkeypatch.setattr(chat_service.chat_llm, "stream_completion", should_not_run)

    events = await _events(
        chat_service.stream_chat(
            object(),
            "user-a",
            ChatRequest(message="Tôi nên uống thuốc gì?"),
        )
    )

    assert [name for name, _ in events] == ["meta", "delta", "sources", "done"]
    assert "không thể chẩn đoán" in events[1][1]["text"]


@pytest.mark.asyncio
async def test_catalog_miss_does_not_ask_model_to_invent_an_answer(
    monkeypatch,
) -> None:
    async def plan(*_args, **_kwargs):
        return ChatPlan.model_validate(
            {
                "route": "catalog",
                "calls": [
                    {
                        "tool": "search_catalog",
                        "arguments": {"query": "món không tồn tại"},
                    }
                ],
            }
        )

    async def execute(*_args, **_kwargs):
        return ToolContext(payload={"query": "x", "records": []})

    monkeypatch.setattr(chat_service, "_plan", plan)
    monkeypatch.setattr(chat_service, "_execute_tool", execute)

    events = await _events(
        chat_service.stream_chat(
            object(),
            "user-a",
            ChatRequest(message="Món này có bao nhiêu calo?"),
        )
    )

    assert "chưa tìm thấy dữ liệu" in events[1][1]["text"]
    assert events[-1] == ("done", {})


@pytest.mark.asyncio
async def test_knowledge_base_search_returns_chunks_with_document_sources(monkeypatch) -> None:
    async def search(query: str, *, limit: int):
        assert query == "Phở bò thường gồm những gì?"
        assert limit == 3
        return [
            Document(
                page_content="Phở bò có bánh phở và nước dùng.",
                metadata={
                    "document_id": "pho-bo",
                    "title": "Phở bò",
                    "source": "foodai_demo",
                    "chunk_index": 0,
                    "score": 0.81,
                },
            )
        ]

    monkeypatch.setattr(chat_service, "search_chunks", search)

    context = await chat_service._execute_tool(
        object(),
        "user-a",
        chat_service.parse_tool_call(
            {
                "tool": "search_knowledge_base",
                "arguments": {"query": "Phở bò thường gồm những gì?"},
            }
        ),
        timezone="Asia/Ho_Chi_Minh",
    )

    assert context.payload["chunks"][0]["content"] == "Phở bò có bánh phở và nước dùng."
    assert context.sources[0].model_dump() == {
        "label": "Phở bò",
        "source": "foodai_demo",
        "score": 0.81,
    }


@pytest.mark.asyncio
async def test_knowledge_base_miss_does_not_ask_model_to_invent_an_answer(monkeypatch) -> None:
    async def plan(*_args, **_kwargs):
        return ChatPlan.model_validate(
            {
                "route": "knowledge",
                "calls": [
                    {
                        "tool": "search_knowledge_base",
                        "arguments": {"query": "Tài liệu không tồn tại"},
                    }
                ],
            }
        )

    async def execute(*_args, **_kwargs):
        return ToolContext(payload={"query": "x", "chunks": []})

    monkeypatch.setattr(chat_service, "_plan", plan)
    monkeypatch.setattr(chat_service, "_execute_tool", execute)

    events = await _events(
        chat_service.stream_chat(
            object(),
            "user-a",
            ChatRequest(message="Tài liệu này nói gì?"),
        )
    )

    assert "chưa tìm thấy tài liệu" in events[1][1]["text"]
    assert events[-1] == ("done", {})


@pytest.mark.asyncio
async def test_component_question_cannot_stream_an_ungrounded_catalog_answer(monkeypatch) -> None:
    plan_value = ChatPlan.model_validate(
        {
            "route": "catalog",
            "calls": [{"tool": "search_catalog", "arguments": {"query": "phở bò"}}],
        }
    )
    executed_tools = []

    async def plan(*_args, **_kwargs):
        return plan_value

    async def execute(_session, _user_id, call, **_kwargs):
        executed_tools.append(call.tool)
        return ToolContext(
            payload={
                "query": "phở bò",
                "chunks": [
                    {
                        "document_id": "pho-bo",
                        "title": "Phở bò",
                        "source": "foodai_demo",
                        "chunk_index": 0,
                        "content": "Phở bò có bánh phở và nước dùng.",
                    }
                ],
            }
        )

    async def stream(*_args, **_kwargs):
        yield "Phở bò có bánh phở và nước dùng."

    monkeypatch.setattr(chat_service, "_plan", plan)
    monkeypatch.setattr(chat_service, "_execute_tool", execute)
    monkeypatch.setattr(chat_service.chat_llm, "stream_completion", stream)

    events = await _events(
        chat_service.stream_chat(
            object(),
            "user-a",
            ChatRequest(message="Phở bò thường gồm những gì?"),
        )
    )

    assert executed_tools == ["search_knowledge_base"]
    assert events[0][1]["route"] == "knowledge"


@pytest.mark.asyncio
async def test_grounded_stream_deduplicates_sources(monkeypatch) -> None:
    plan_value = ChatPlan.model_validate(
        {
            "route": "hybrid",
            "calls": [
                {"tool": "get_goal", "arguments": {}},
                {
                    "tool": "search_catalog",
                    "arguments": {"query": "phở bò"},
                },
            ],
        }
    )
    source = ChatSource(label="Phở bò", source="vnmeal")

    async def plan(*_args, **_kwargs):
        return plan_value

    async def execute(*_args, **_kwargs):
        return ToolContext(payload={"fact": 480}, sources=(source,))

    async def stream(*_args, **_kwargs):
        yield "Khoảng "
        yield "480 kcal."

    monkeypatch.setattr(chat_service, "_plan", plan)
    monkeypatch.setattr(chat_service, "_execute_tool", execute)
    monkeypatch.setattr(chat_service.chat_llm, "stream_completion", stream)

    events = await _events(
        chat_service.stream_chat(
            object(),
            "user-a",
            ChatRequest(message="So với mục tiêu, phở bò thế nào?"),
        )
    )

    assert events[0][1]["sources"] == [{"label": "Phở bò", "source": "vnmeal", "score": None}]
    assert [payload["text"] for name, payload in events if name == "delta"] == [
        "Khoảng ",
        "480 kcal.",
    ]


@pytest.mark.asyncio
async def test_empty_general_answer_and_internal_error_are_safe(monkeypatch) -> None:
    async def general_plan(*_args, **_kwargs):
        return ChatPlan(route="general", calls=[])

    async def empty_stream(*_args, **_kwargs):
        if False:
            yield ""

    monkeypatch.setattr(chat_service, "_plan", general_plan)
    monkeypatch.setattr(chat_service.chat_llm, "stream_completion", empty_stream)
    empty_events = await _events(
        chat_service.stream_chat(
            object(),
            "user-a",
            ChatRequest(message="Xin chào"),
        )
    )
    assert "chưa có đủ dữ liệu" in empty_events[1][1]["text"]

    async def broken_plan(*_args, **_kwargs):
        raise RuntimeError("database password must stay private")

    monkeypatch.setattr(chat_service, "_plan", broken_plan)
    error_events = await _events(
        chat_service.stream_chat(
            object(),
            "user-a",
            ChatRequest(message="Xin chào"),
        )
    )
    assert error_events == [
        (
            "error",
            {"message": "Balance chưa truy xuất được dữ liệu. Bạn thử lại sau nhé."},
        ),
        ("done", {}),
    ]
