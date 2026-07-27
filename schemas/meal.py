"""Pydantic contracts for the user meal journal and sync API."""

from datetime import date, datetime
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator

MealType = Literal["breakfast", "lunch", "dinner", "snack"]
MealSource = Literal["analyze", "suggestion", "manual"]


def _aware_datetime(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("eaten_at phải có timezone.")
    return value


class MealCreate(BaseModel):
    client_entry_id: str = Field(min_length=1, max_length=200)
    eaten_at: datetime
    meal_type: MealType
    dish_name: str = Field(min_length=1, max_length=300)
    total_grams: float = Field(default=0, ge=0, le=100_000)
    calories: float = Field(default=0, ge=0, le=20_000)
    protein_g: float = Field(default=0, ge=0, le=2_000)
    fat_g: float = Field(default=0, ge=0, le=2_000)
    carbs_g: float = Field(default=0, ge=0, le=3_000)
    fiber_g: float = Field(default=0, ge=0, le=2_000)
    source: MealSource = "manual"
    analyze_source: str | None = Field(default=None, max_length=50)
    note: str | None = Field(default=None, max_length=500)

    _validate_eaten_at = field_validator("eaten_at")(_aware_datetime)


class MealPatch(BaseModel):
    eaten_at: datetime | None = None
    meal_type: MealType | None = None
    dish_name: str | None = Field(default=None, min_length=1, max_length=300)
    total_grams: float | None = Field(default=None, ge=0, le=100_000)
    calories: float | None = Field(default=None, ge=0, le=20_000)
    protein_g: float | None = Field(default=None, ge=0, le=2_000)
    fat_g: float | None = Field(default=None, ge=0, le=2_000)
    carbs_g: float | None = Field(default=None, ge=0, le=3_000)
    fiber_g: float | None = Field(default=None, ge=0, le=2_000)
    source: MealSource | None = None
    analyze_source: str | None = Field(default=None, max_length=50)
    note: str | None = Field(default=None, max_length=500)

    @field_validator("eaten_at")
    @classmethod
    def validate_eaten_at(cls, value: datetime | None) -> datetime | None:
        return None if value is None else _aware_datetime(value)


class MealResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    client_entry_id: str
    eaten_at: datetime
    meal_type: MealType
    dish_name: str
    total_grams: float
    calories: float
    protein_g: float
    fat_g: float
    carbs_g: float
    fiber_g: float
    source: MealSource
    analyze_source: str | None
    note: str | None
    created_at: datetime
    updated_at: datetime


class MealListResponse(BaseModel):
    items: list[MealResponse]


class MealSummaryResponse(BaseModel):
    date_from: date
    date_to: date
    timezone: str
    meal_count: int
    totals: dict[str, float]
    by_date: list[dict[str, object]]


def validate_timezone(value: str) -> str:
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError("timezone không hợp lệ.") from exc
    return value
