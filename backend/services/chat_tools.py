"""Allowlisted chatbot tools with strict, user-independent argument validation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from pydantic import BaseModel

from schemas.chat import (
    ChatToolCall,
    CountDishToolArgs,
    DateRangeArgs,
    MealsToolArgs,
    SearchCatalogToolArgs,
    SuggestDishesToolArgs,
)


@dataclass(frozen=True)
class ParsedToolCall:
    tool: str
    arguments: dict[str, Any]


_TOOL_ARGUMENTS: dict[str, type[BaseModel]] = {
    "get_meals": MealsToolArgs,
    "get_summary": DateRangeArgs,
    "count_dish": CountDishToolArgs,
    "compare_goal": DateRangeArgs,
    "search_catalog": SearchCatalogToolArgs,
    "suggest_dishes": SuggestDishesToolArgs,
}


def parse_tool_call(raw: ChatToolCall | dict[str, Any]) -> ParsedToolCall:
    call = raw if isinstance(raw, ChatToolCall) else ChatToolCall.model_validate(raw)
    arguments = call.arguments
    if isinstance(arguments, str):
        arguments = json.loads(arguments)
    if not isinstance(arguments, dict):
        raise ValueError("Tool arguments phải là object JSON.")
    schema = _TOOL_ARGUMENTS.get(call.tool)
    if schema is None:
        if arguments:
            raise ValueError(f"Tool {call.tool} không nhận arguments.")
        return ParsedToolCall(tool=call.tool, arguments={})
    parsed = schema.model_validate(arguments)
    return ParsedToolCall(tool=call.tool, arguments=parsed.model_dump(mode="json"))


def build_date_range(
    period: str,
    *,
    today: date,
) -> tuple[date, date]:
    """Translate the planner's stable period tokens to concrete local dates."""
    normalized = period.strip().casefold().replace("-", "_").replace(" ", "_")
    if normalized in {"yesterday", "hom_qua"}:
        target = today - timedelta(days=1)
        return target, target
    if normalized in {"today", "hom_nay"}:
        return today, today
    if normalized in {"this_week", "tuan_nay"}:
        start = today - timedelta(days=today.weekday())
        return start, today
    if normalized in {"last_week", "tuan_truoc"}:
        end = today - timedelta(days=today.weekday() + 1)
        return end - timedelta(days=6), end
    if normalized in {"this_month", "thang_nay"}:
        return today.replace(day=1), today
    if normalized in {"last_month", "thang_truoc"}:
        first_this_month = today.replace(day=1)
        last_previous = first_this_month - timedelta(days=1)
        return last_previous.replace(day=1), last_previous
    raise ValueError(f"Không hiểu khoảng thời gian: {period}")
