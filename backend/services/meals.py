"""Database-backed meal journal operations used by mobile sync and chat tools."""

from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import MealLog
from schemas.meal import MealCreate, MealPatch, MealSummaryResponse

NUTRIENT_FIELDS = ("calories", "protein_g", "fat_g", "carbs_g", "fiber_g")


def _utc_bounds(date_from: date, date_to: date, timezone: str) -> tuple[datetime, datetime]:
    zone = ZoneInfo(timezone)
    start = datetime.combine(date_from, time.min, tzinfo=zone)
    end = datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=zone)
    return start.astimezone(UTC), end.astimezone(UTC)


def _as_float(value: float | None) -> float:
    return round(float(value or 0), 2)


def _apply_create(meal: MealLog, payload: MealCreate, user_id: str) -> None:
    values = payload.model_dump()
    meal.user_id = user_id
    for field, value in values.items():
        setattr(meal, field, value)


async def upsert_meal(
    session: AsyncSession,
    user_id: str,
    payload: MealCreate,
) -> tuple[MealLog, bool]:
    """Create or overwrite one client entry; return (row, was_created)."""
    meal = await session.scalar(
        select(MealLog).where(
            MealLog.user_id == user_id,
            MealLog.client_entry_id == payload.client_entry_id,
        )
    )
    created = meal is None
    if meal is None:
        meal = MealLog()
        session.add(meal)
    _apply_create(meal, payload, user_id)
    await session.commit()
    await session.refresh(meal)
    return meal, created


async def list_meals(
    session: AsyncSession,
    user_id: str,
    *,
    date_from: date,
    date_to: date,
    timezone: str,
    meal_type: str | None = None,
) -> list[MealLog]:
    start, end = _utc_bounds(date_from, date_to, timezone)
    statement = (
        select(MealLog)
        .where(
            MealLog.user_id == user_id,
            MealLog.eaten_at >= start,
            MealLog.eaten_at < end,
        )
        .order_by(MealLog.eaten_at.desc(), MealLog.created_at.desc())
    )
    if meal_type is not None:
        statement = statement.where(MealLog.meal_type == meal_type)
    return list((await session.scalars(statement)).all())


async def get_meal_for_user(
    session: AsyncSession,
    user_id: str,
    meal_id: str,
) -> MealLog | None:
    return await session.scalar(
        select(MealLog).where(MealLog.id == meal_id, MealLog.user_id == user_id)
    )


async def patch_meal(
    session: AsyncSession,
    meal: MealLog,
    payload: MealPatch,
) -> MealLog:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(meal, field, value)
    await session.commit()
    await session.refresh(meal)
    return meal


async def delete_meal(session: AsyncSession, meal: MealLog) -> None:
    await session.delete(meal)
    await session.commit()


async def summarize_meals(
    session: AsyncSession,
    user_id: str,
    *,
    date_from: date,
    date_to: date,
    timezone: str,
    meal_type: str | None = None,
) -> MealSummaryResponse:
    meals = await list_meals(
        session,
        user_id,
        date_from=date_from,
        date_to=date_to,
        timezone=timezone,
        meal_type=meal_type,
    )
    totals = {field: round(sum(_as_float(getattr(meal, field)) for meal in meals), 2)
              for field in NUTRIENT_FIELDS}
    zone = ZoneInfo(timezone)
    by_date: dict[date, dict[str, float | int]] = {}
    for meal in meals:
        local_date = meal.eaten_at.astimezone(zone).date()
        day = by_date.setdefault(
            local_date,
            {"date": local_date.isoformat(), "meal_count": 0, **{field: 0.0 for field in NUTRIENT_FIELDS}},
        )
        day["meal_count"] = int(day["meal_count"]) + 1
        for field in NUTRIENT_FIELDS:
            day[field] = round(float(day[field]) + _as_float(getattr(meal, field)), 2)
    return MealSummaryResponse(
        date_from=date_from,
        date_to=date_to,
        timezone=timezone,
        meal_count=len(meals),
        totals=totals,
        by_date=[by_date[key] for key in sorted(by_date)],
    )


def count_dish(meals: Iterable[MealLog], dish_name: str) -> int:
    """Count a dish case-insensitively without fuzzy matching user history."""
    needle = " ".join(dish_name.casefold().split())
    return sum(
        " ".join(meal.dish_name.casefold().split()) == needle
        for meal in meals
    )
