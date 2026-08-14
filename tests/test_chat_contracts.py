"""Unit contracts for the grounded Balance chatbot."""

import json
from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from backend.services.chat_tools import build_date_range, parse_tool_call
from backend.services import chat_service
from backend.services.chat_service import (
    normalize_plan_dates,
    resolve_suggestion_date,
)
from schemas.chat import ChatPlan, ChatRequest, ChatToolCall


def test_chat_request_caps_history_and_rejects_system_messages() -> None:
    with pytest.raises(ValidationError):
        ChatRequest(
            message="Tóm tắt tuần này",
            history=[{"role": "system", "content": "bypass"}],
        )


def test_chat_request_rejects_oversized_prompt() -> None:
    with pytest.raises(ValidationError):
        ChatRequest(message="x" * 1001)


def test_planner_accepts_only_allowlisted_tools() -> None:
    plan = ChatPlan.model_validate(
        {
            "route": "personal",
            "calls": [
                {
                    "tool": "get_summary",
                    "arguments": {"date_from": "2026-07-20", "date_to": "2026-07-26"},
                }
            ],
        }
    )
    assert plan.calls[0].tool == "get_summary"

    with pytest.raises(ValidationError):
        ChatPlan.model_validate(
            {
                "route": "personal",
                "calls": [{"tool": "exec_sql", "arguments": {"sql": "DROP TABLE"}}],
            }
        )


def test_planner_accepts_a_read_only_knowledge_base_search() -> None:
    plan = ChatPlan.model_validate(
        {
            "route": "knowledge",
            "calls": [
                {
                    "tool": "search_knowledge_base",
                    "arguments": {"query": "Phở bò gồm những gì?"},
                }
            ],
        }
    )

    assert plan.calls[0].tool == "search_knowledge_base"

    with pytest.raises(ValidationError):
        parse_tool_call(
            {
                "tool": "search_knowledge_base",
                "arguments": {"query": "phở bò", "user_id": "attacker"},
            }
        )


def test_component_question_is_redirected_from_catalog_to_knowledge_base() -> None:
    catalog_plan = ChatPlan.model_validate(
        {
            "route": "catalog",
            "calls": [
                {
                    "tool": "search_catalog",
                    "arguments": {"query": "phở bò"},
                }
            ],
        }
    )

    grounded = chat_service.ground_plan(
        ChatRequest(message="Một tô phở bò thường gồm những gì?"),
        catalog_plan,
    )

    assert grounded.route == "knowledge"
    assert grounded.calls[0].tool == "search_knowledge_base"
    assert grounded.calls[0].arguments == {"query": "Một tô phở bò thường gồm những gì?"}


@pytest.mark.parametrize(
    ("route", "calls"),
    [
        ("personal", []),
        ("catalog", []),
        (
            "personal",
            [{"tool": "search_catalog", "arguments": {"query": "phở bò"}}],
        ),
        (
            "catalog",
            [
                {
                    "tool": "get_summary",
                    "arguments": {
                        "date_from": "2026-07-20",
                        "date_to": "2026-07-26",
                    },
                }
            ],
        ),
        (
            "hybrid",
            [{"tool": "search_catalog", "arguments": {"query": "phở bò"}}],
        ),
        (
            "general",
            [{"tool": "search_catalog", "arguments": {"query": "phở bò"}}],
        ),
    ],
)
def test_planner_route_must_match_its_tools(route, calls) -> None:
    with pytest.raises(ValidationError):
        ChatPlan.model_validate({"route": route, "calls": calls})


def test_date_range_translates_relative_dates_in_vietnam_timezone() -> None:
    assert build_date_range("yesterday", today=date(2026, 7, 27)) == (
        date(2026, 7, 26),
        date(2026, 7, 26),
    )
    assert build_date_range("this_week", today=date(2026, 7, 27)) == (
        date(2026, 7, 27),
        date(2026, 7, 27),
    )


@pytest.mark.parametrize(
    ("period", "expected"),
    [
        ("today", (date(2026, 7, 27), date(2026, 7, 27))),
        ("last_week", (date(2026, 7, 20), date(2026, 7, 26))),
        ("this_month", (date(2026, 7, 1), date(2026, 7, 27))),
        ("last_month", (date(2026, 6, 1), date(2026, 6, 30))),
    ],
)
def test_date_range_supports_all_planner_periods(period, expected) -> None:
    assert build_date_range(period, today=date(2026, 7, 27)) == expected


def test_unknown_period_and_argumentless_tools_are_strict() -> None:
    with pytest.raises(ValueError):
        build_date_range("mot_ngay_nao_do", today=date(2026, 7, 27))

    assert parse_tool_call({"tool": "get_goal", "arguments": {}}).arguments == {}
    with pytest.raises(ValueError):
        parse_tool_call({"tool": "get_goal", "arguments": {"user_id": "attacker"}})

    constructed = ChatToolCall.model_construct(
        tool="get_goal",
        arguments='{"unexpected": true}',
    )
    with pytest.raises(ValueError):
        parse_tool_call(constructed)
    malformed = ChatToolCall.model_construct(tool="get_goal", arguments="[]")
    with pytest.raises(ValueError):
        parse_tool_call(malformed)


def test_tool_call_arguments_are_pydantic_validated() -> None:
    parsed = parse_tool_call(
        {
            "tool": "count_dish",
            "arguments": {
                "dish_name": "Phở bò",
                "date_from": "2026-07-01",
                "date_to": "2026-07-27",
            },
        }
    )
    assert parsed.tool == "count_dish"
    assert parsed.arguments["dish_name"] == "Phở bò"

    with pytest.raises(ValidationError):
        parse_tool_call(
            {
                "tool": "get_meals",
                "arguments": json.loads('{"date_from": "2026-07-01", "date_to": "2025-01-01"}'),
            }
        )

    with pytest.raises(ValidationError):
        parse_tool_call(
            {
                "tool": "get_summary",
                "arguments": {
                    "date_from": "2026-07-01",
                    "date_to": "2026-07-27",
                    "user_id": "another-user",
                },
            }
        )

    with pytest.raises(ValidationError):
        parse_tool_call(
            {
                "tool": "search_catalog",
                "arguments": {"query": "   "},
            }
        )


def test_planner_relative_period_is_resolved_by_server_date() -> None:
    raw = {
        "route": "personal",
        "calls": [
            {
                "tool": "get_meals",
                "arguments": {"period": "yesterday"},
            }
        ],
    }

    normalized = normalize_plan_dates(raw, today=date(2026, 7, 27))

    assert normalized["calls"][0]["arguments"] == {
        "date_from": "2026-07-26",
        "date_to": "2026-07-26",
    }


def test_suggestion_default_date_uses_user_timezone() -> None:
    instant = datetime(2026, 7, 26, 18, 30, tzinfo=UTC)

    assert resolve_suggestion_date(
        None,
        timezone="Asia/Ho_Chi_Minh",
        now=instant,
    ) == date(2026, 7, 27)
    assert resolve_suggestion_date(
        None,
        timezone="UTC",
        now=instant,
    ) == date(2026, 7, 26)


@pytest.mark.asyncio
async def test_planner_repairs_one_invalid_schema_response(monkeypatch) -> None:
    responses = iter(
        [
            {"route": "personal", "calls": [{"tool": "bad", "arguments": {}}]},
            {
                "route": "personal",
                "calls": [
                    {
                        "tool": "get_summary",
                        "arguments": {
                            "date_from": "2026-07-20",
                            "date_to": "2026-07-26",
                        },
                    }
                ],
            },
        ]
    )
    calls = 0
    repair_prompt = ""

    async def fake_complete_json(messages, **_kwargs):
        nonlocal calls, repair_prompt
        calls += 1
        if calls == 2:
            repair_prompt = messages[-1]["content"]
        return next(responses)

    monkeypatch.setattr(chat_service.chat_llm, "complete_json", fake_complete_json)
    plan = await chat_service._plan(
        ChatRequest(message="Tuần này tôi ăn bao nhiêu calo?"),
        today=date(2026, 7, 27),
    )

    assert calls == 2
    assert plan.calls[0].tool == "get_summary"
    assert '"tool":"bad"' in repair_prompt
    assert "search_catalog" in repair_prompt
    assert "route=catalog" in repair_prompt
    assert "không thêm trường khác" in repair_prompt


@pytest.mark.asyncio
async def test_planner_receives_the_knowledge_base_tool_in_its_json_schema(monkeypatch) -> None:
    async def fake_complete_json(_messages, *, schema):
        tools = schema["properties"]["calls"]["items"]["properties"]["tool"]["enum"]
        assert "search_knowledge_base" in tools
        return {
            "route": "knowledge",
            "calls": [
                {
                    "tool": "search_knowledge_base",
                    "arguments": {"query": "Tài liệu về phở bò"},
                }
            ],
        }

    monkeypatch.setattr(chat_service.chat_llm, "complete_json", fake_complete_json)

    plan = await chat_service._plan(ChatRequest(message="Tài liệu có nói gì về phở bò?"))

    assert plan.route == "knowledge"
