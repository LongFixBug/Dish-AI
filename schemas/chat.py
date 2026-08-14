"""Validated request/response contracts for the Balance chatbot."""

from datetime import date, datetime
from typing import Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ChatRole = Literal["user", "assistant"]
ChatRoute = Literal["personal", "catalog", "knowledge", "hybrid", "general", "out_of_scope"]
ChatToolName = Literal[
    "get_meals",
    "get_summary",
    "count_dish",
    "get_goal",
    "compare_goal",
    "suggest_dishes",
    "search_catalog",
    "search_knowledge_base",
]


class _StrictModel(BaseModel):
    """Reject fields that the model/client was never allowed to provide."""

    model_config = ConfigDict(extra="forbid")


class ChatMessage(_StrictModel):
    role: ChatRole
    content: str = Field(min_length=1, max_length=2_000)


class ChatRequest(_StrictModel):
    message: str = Field(min_length=1, max_length=1_000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=12)
    timezone: str = "Asia/Ho_Chi_Minh"

    @field_validator("message")
    @classmethod
    def trim_message(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("message không được để trống.")
        return value

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("timezone không hợp lệ.") from exc
        return value

    @model_validator(mode="after")
    def cap_history_bytes(self) -> "ChatRequest":
        if sum(len(item.content) for item in self.history) > 8_000:
            raise ValueError("history vượt quá giới hạn.")
        return self


class ChatToolCall(_StrictModel):
    tool: ChatToolName
    arguments: dict[str, Any] = Field(default_factory=dict)


class ChatPlan(_StrictModel):
    route: ChatRoute
    calls: list[ChatToolCall] = Field(default_factory=list, max_length=3)

    @model_validator(mode="after")
    def route_matches_tools(self) -> "ChatPlan":
        tools = {call.tool for call in self.calls}
        retrieval_tools = {"search_catalog", "search_knowledge_base"}
        personal_tools = tools - retrieval_tools
        uses_catalog = "search_catalog" in tools
        uses_knowledge = "search_knowledge_base" in tools
        if self.route == "personal" and (not personal_tools or uses_catalog):
            raise ValueError("Route personal chỉ được gọi tool dữ liệu cá nhân.")
        if self.route == "catalog" and tools != {"search_catalog"}:
            raise ValueError("Route catalog phải gọi search_catalog.")
        if self.route == "knowledge" and tools != {"search_knowledge_base"}:
            raise ValueError("Route knowledge phải gọi search_knowledge_base.")
        if self.route == "hybrid" and (not personal_tools or not (uses_catalog or uses_knowledge)):
            raise ValueError("Route hybrid cần tool cá nhân và ít nhất một tool truy xuất.")
        if self.route in {"general", "out_of_scope"} and self.calls:
            raise ValueError(f"Route {self.route} không được gọi tool.")
        return self


class ChatSource(_StrictModel):
    label: str
    source: str
    score: float | None = None


class ChatMeta(BaseModel):
    route: ChatRoute
    sources: list[ChatSource] = Field(default_factory=list)


class DateRangeArgs(_StrictModel):
    date_from: date
    date_to: date

    @model_validator(mode="after")
    def valid_order(self) -> "DateRangeArgs":
        if self.date_to < self.date_from:
            raise ValueError("date_to phải từ date_from trở đi.")
        if (self.date_to - self.date_from).days > 366:
            raise ValueError("Khoảng truy vấn tối đa 366 ngày.")
        return self


class MealsToolArgs(DateRangeArgs):
    meal_type: Literal["breakfast", "lunch", "dinner", "snack"] | None = None


class CountDishToolArgs(DateRangeArgs):
    dish_name: str = Field(min_length=1, max_length=300)

    @field_validator("dish_name")
    @classmethod
    def trim_dish_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("dish_name không được để trống.")
        return value


class SearchCatalogToolArgs(_StrictModel):
    query: str = Field(min_length=1, max_length=300)

    @field_validator("query")
    @classmethod
    def trim_query(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("query không được để trống.")
        return value


class SearchKnowledgeBaseToolArgs(SearchCatalogToolArgs):
    """A read-only semantic lookup over the approved RAG document corpus."""


class SuggestDishesToolArgs(_StrictModel):
    date: datetime | date | None = None
