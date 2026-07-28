"""Contracts for personalized nutrition-goal estimates.

The values in this module are estimates for healthy adults. They are not a
clinical prescription and intentionally carry source/provenance metadata.
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

Sex = Literal["male", "female", "other"]
ActivityLevel = Literal["sedentary", "light", "moderate", "very_active"]
Goal = Literal["lose", "maintain", "gain"]
PregnancyStatus = Literal["none", "pregnant", "breastfeeding"]
SafetyStatus = Literal["normal", "review_required"]
NutritionGroup = Literal["auto", "normal", "underweight", "overweight_obesity"]


class NutritionGoalRequest(BaseModel):
    """Input required to estimate an adult's daily nutrition targets."""

    age: int = Field(ge=18, le=120)
    sex: Sex
    height_cm: float = Field(ge=120, le=230)
    weight_kg: float = Field(ge=30, le=300)
    activity_level: ActivityLevel
    goal: Goal
    target_weight_kg: float = Field(ge=30, le=300)
    target_days: int = Field(ge=1, le=730)
    pregnancy_status: PregnancyStatus = "none"
    nutrition_group: NutritionGroup = "auto"
    medical_conditions: list[str] = Field(default_factory=list, max_length=10)

    @field_validator("medical_conditions")
    @classmethod
    def normalize_medical_conditions(cls, values: list[str]) -> list[str]:
        normalized = [" ".join(value.split()) for value in values]
        return [value[:100] for value in normalized if value]


class MacroTarget(BaseModel):
    """A gram range plus the value used to rank suggested dishes."""

    min: float = Field(ge=0)
    target: float = Field(ge=0)
    max: float = Field(ge=0)


class NutritionProfile(BaseModel):
    """The normalized profile shown above the daily recommendation table."""

    age: int = Field(ge=18)
    sex: Sex
    height_cm: float = Field(gt=0)
    weight_kg: float = Field(gt=0)
    bmi: float = Field(ge=0)
    bmi_category: Literal["underweight", "normal", "overweight", "obesity"]
    nutrition_group: Literal["normal", "underweight", "overweight_obesity"]


class DailyNutritionTarget(BaseModel):
    """One display-ready row in the daily nutrition recommendation table."""

    code: str
    name_vi: str
    name_en: str | None = None
    category: Literal[
        "energy",
        "water",
        "macronutrient",
        "limit",
        "micronutrient",
        "amino_acid",
    ]
    unit: str
    minimum: float | None = Field(default=None, ge=0)
    maximum: float | None = Field(default=None, ge=0)
    comparator: Literal["=", "range", "<", "<=", ">", ">="] = "range"
    display_value: str
    variant: str | None = None
    source: str


class NutritionReference(BaseModel):
    """Evidence/provenance attached to every calculated response."""

    standard: str
    standard_source_url: str
    macro_source_url: str
    goal_model_source_url: str
    goal_model_method: str
    standard_usage: str
    algorithm_version: str
    scope: str
    reference_source_endpoint: str | None = None
    reference_age_group: str | None = None


class NutritionGoalResponse(BaseModel):
    """Calculated daily targets for a healthy adult."""

    maintenance_calories: int = Field(ge=0)
    target_calories: int = Field(ge=0)
    goal_delta_calories: int
    profile: NutritionProfile | None = None
    daily_targets: list[DailyNutritionTarget] = Field(default_factory=list)
    protein_g: MacroTarget
    carbohydrate_g: MacroTarget
    fat_g: MacroTarget
    safety_status: SafetyStatus
    warnings: list[str] = Field(default_factory=list)
    reference: NutritionReference


class PersistedNutritionGoalResponse(BaseModel):
    """Stored goal response scoped to the authenticated owner."""

    user_id: str
    goal: NutritionGoalResponse
    created_at: datetime
    updated_at: datetime
