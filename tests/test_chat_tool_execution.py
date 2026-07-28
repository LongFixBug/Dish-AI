"""Unit tests for every server-owned RAG tool branch."""

from datetime import UTC, date, datetime
from types import SimpleNamespace

import pytest

from backend.services import chat_service
from backend.services.chat_service import ToolContext
from backend.services.chat_tools import ParsedToolCall
from backend.services.vector_catalog import CatalogHit, CatalogType
from schemas.chat import ChatSource
from schemas.meal import MealSummaryResponse


class _Rows:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _Session:
    def __init__(self, *, scalar_values=(), row_batches=()):
        self._scalar_values = iter(scalar_values)
        self._row_batches = iter(row_batches)

    async def scalar(self, _statement):
        return next(self._scalar_values)

    async def scalars(self, _statement):
        return _Rows(next(self._row_batches))


def _summary(calories: float = 400) -> MealSummaryResponse:
    return MealSummaryResponse(
        date_from=date(2026, 7, 27),
        date_to=date(2026, 7, 27),
        timezone="Asia/Ho_Chi_Minh",
        meal_count=1,
        totals={
            "calories": calories,
            "protein_g": 20,
            "fat_g": 10,
            "carbs_g": 50,
            "fiber_g": 4,
        },
        by_date=[],
    )


def _meal(name: str = "Phở bò"):
    return SimpleNamespace(
        eaten_at=datetime(2026, 7, 27, 5, tzinfo=UTC),
        meal_type="lunch",
        dish_name=name,
        total_grams=450,
        calories=480,
        protein_g=28,
        fat_g=14,
        carbs_g=60,
        fiber_g=4,
    )


@pytest.mark.asyncio
async def test_goal_tool_returns_missing_or_versioned_goal() -> None:
    missing = await chat_service._execute_tool(
        _Session(scalar_values=[None]),
        "user-a",
        ParsedToolCall(tool="get_goal", arguments={}),
        timezone="Asia/Ho_Chi_Minh",
    )
    goal = SimpleNamespace(
        goal="maintain",
        result_payload={"target_calories": 2_000},
        algorithm_version="v1",
    )
    found = await chat_service._execute_tool(
        _Session(scalar_values=[goal]),
        "user-a",
        ParsedToolCall(tool="get_goal", arguments={}),
        timezone="Asia/Ho_Chi_Minh",
    )

    assert missing.payload == {"goal": None}
    assert found.payload == {
        "goal": "maintain",
        "result_payload": {"target_calories": 2_000},
        "algorithm_version": "v1",
    }


@pytest.mark.asyncio
async def test_meal_list_count_and_goal_comparison_use_python_facts(
    monkeypatch,
) -> None:
    async def list_fixture(*_args, **_kwargs):
        return [_meal(), _meal("Bún bò")]

    async def summary_fixture(*_args, **_kwargs):
        return _summary()

    monkeypatch.setattr(chat_service, "list_meals", list_fixture)
    monkeypatch.setattr(chat_service, "summarize_meals", summary_fixture)
    dates = {"date_from": "2026-07-27", "date_to": "2026-07-27"}

    listed = await chat_service._execute_tool(
        _Session(),
        "user-a",
        ParsedToolCall(tool="get_meals", arguments=dates),
        timezone="Asia/Ho_Chi_Minh",
    )
    counted = await chat_service._execute_tool(
        _Session(),
        "user-a",
        ParsedToolCall(tool="count_dish", arguments={**dates, "dish_name": "phở bò"}),
        timezone="Asia/Ho_Chi_Minh",
    )
    goal = SimpleNamespace(result_payload={"target_calories": 2_000})
    compared = await chat_service._execute_tool(
        _Session(scalar_values=[goal]),
        "user-a",
        ParsedToolCall(tool="compare_goal", arguments=dates),
        timezone="Asia/Ho_Chi_Minh",
    )

    assert [meal["dish_name"] for meal in listed.payload["meals"]] == [
        "Phở bò",
        "Bún bò",
    ]
    assert counted.payload["count"] == 1
    assert compared.payload["difference_calories"] == 1_600


@pytest.mark.asyncio
async def test_suggestion_tool_uses_budget_catalog_and_history(monkeypatch) -> None:
    async def summary_fixture(*_args, **_kwargs):
        return _summary(calories=500)

    async def list_fixture(*_args, **_kwargs):
        return [_meal("Phở bò")]

    monkeypatch.setattr(chat_service, "summarize_meals", summary_fixture)
    monkeypatch.setattr(chat_service, "list_meals", list_fixture)
    goal = SimpleNamespace(
        result_payload={
            "target_calories": 2_000,
            "protein_g": {"target": 100},
            "fat_g": {"target": 60},
            "carbohydrate_g": {"target": 250},
        }
    )
    dishes = [
        SimpleNamespace(
            dish_name="Phở bò",
            typical_grams=450,
            total_calories=480,
            total_protein_g=28,
            total_fat_g=14,
            total_carbs_g=60,
        ),
        SimpleNamespace(
            dish_name="Cơm gà",
            typical_grams=400,
            total_calories=550,
            total_protein_g=35,
            total_fat_g=16,
            total_carbs_g=70,
        ),
    ]

    context = await chat_service._execute_tool(
        _Session(scalar_values=[goal], row_batches=[dishes]),
        "user-a",
        ParsedToolCall(tool="suggest_dishes", arguments={"date": "2026-07-27"}),
        timezone="Asia/Ho_Chi_Minh",
    )

    assert context.payload["date"] == "2026-07-27"
    assert [item["dish_name"] for item in context.payload["suggestions"]] == ["Cơm gà"]


@pytest.mark.asyncio
async def test_catalog_context_prefers_postgres_exact_rows(monkeypatch) -> None:
    async def should_not_search(*_args, **_kwargs):
        raise AssertionError("Qdrant must not run after an exact PostgreSQL hit")

    monkeypatch.setattr(chat_service, "search_catalog", should_not_search)
    dish = SimpleNamespace(
        id="dish-id",
        dish_name="Phở bò",
        source="vnmeal",
        typical_grams=450,
        total_calories=480,
        total_protein_g=28,
        total_fat_g=14,
        total_carbs_g=60,
        total_fiber_g=4,
    )
    ingredient = SimpleNamespace(
        id="ingredient-id",
        ingredient_name="Thịt bò",
        source="vnfood",
        calories_per_g=2,
        protein_per_g=0.25,
        fat_per_g=0.1,
        carbs_per_g=0,
        fiber_per_g=0,
    )

    context = await chat_service._catalog_context(
        _Session(row_batches=[[dish], [ingredient]]),
        "phở bò",
    )

    assert [record["type"] for record in context.payload["records"]] == [
        "dish",
        "ingredient",
    ]
    dish_record, ingredient_record = context.payload["records"]
    assert dish_record["nutrition_basis"] == "per_serving"
    assert dish_record["serving_grams"] == 450
    assert dish_record["calories_kcal_per_serving"] == 480
    assert ingredient_record["nutrition_basis"] == "per_100g"
    assert ingredient_record["calories_kcal_per_100g"] == 200
    assert "calories_per_g" not in ingredient_record
    assert [source.source for source in context.sources] == ["vnmeal", "vnfood"]


@pytest.mark.asyncio
async def test_catalog_context_matches_vietnamese_accents_before_qdrant(monkeypatch) -> None:
    async def should_not_search(*_args, **_kwargs):
        raise AssertionError("accent-insensitive PostgreSQL match must win")

    monkeypatch.setattr(chat_service, "search_catalog", should_not_search)
    dish = SimpleNamespace(
        id="pho-id",
        dish_name="Phở gà",
        source="vnmeal",
        typical_grams=450,
        total_calories=455,
        total_protein_g=25,
        total_fat_g=12,
        total_carbs_g=55,
        total_fiber_g=3,
    )
    context = await chat_service._catalog_context(
        _Session(row_batches=[[dish], []]),
        "pho",
    )

    assert context.payload["records"][0]["name"] == "Phở gà"
    assert context.sources[0].source == "vnmeal"


@pytest.mark.asyncio
async def test_catalog_vector_hits_are_resolved_back_to_postgres(
    monkeypatch,
) -> None:
    dish = SimpleNamespace(
        id="dish-id",
        dish_name="Phở bò",
        source="vnmeal",
        typical_grams=450,
        total_calories=480,
        total_protein_g=28,
        total_fat_g=14,
        total_carbs_g=60,
        total_fiber_g=4,
    )

    async def search(_query, catalog_type, limit):
        assert limit == 5
        if catalog_type is CatalogType.DISH:
            return [CatalogHit(record_id="dish-id", name="Phở bò", score=0.9)]
        return []

    monkeypatch.setattr(chat_service, "search_catalog", search)
    context = await chat_service._catalog_context(
        _Session(row_batches=[[], [dish], []]),
        "món nước bò",
    )

    assert context.payload["records"][0]["name"] == "Phở bò"
    assert context.sources[0].score == 0.9


@pytest.mark.asyncio
async def test_search_dispatch_and_unknown_tool_are_explicit(monkeypatch) -> None:
    expected = ToolContext(
        payload={"records": []},
        sources=(ChatSource(label="Catalog", source="vnmeal"),),
    )

    async def catalog(*_args, **_kwargs):
        return expected

    async def no_meals(*_args, **_kwargs):
        return []

    async def summary(*_args, **_kwargs):
        return _summary()

    monkeypatch.setattr(chat_service, "_catalog_context", catalog)
    monkeypatch.setattr(chat_service, "list_meals", no_meals)
    monkeypatch.setattr(chat_service, "summarize_meals", summary)

    result = await chat_service._execute_tool(
        _Session(),
        "user-a",
        ParsedToolCall(tool="search_catalog", arguments={"query": "phở"}),
        timezone="Asia/Ho_Chi_Minh",
    )
    assert result is expected

    with pytest.raises(ValueError, match="không được triển khai"):
        await chat_service._execute_tool(
            _Session(),
            "user-a",
            ParsedToolCall(
                tool="unknown",
                arguments={
                    "date_from": "2026-07-27",
                    "date_to": "2026-07-27",
                },
            ),
            timezone="Asia/Ho_Chi_Minh",
        )
