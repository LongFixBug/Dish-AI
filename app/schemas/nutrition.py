"""Schemas for nutrition analysis results."""

from pydantic import BaseModel, Field


class Ingredient(BaseModel):
    """Một thành phần trong món ăn."""

    name: str = Field(description="Tên thành phần, ví dụ: 'thịt bò', 'bún', 'rau thơm'")
    estimated_grams: float = Field(ge=0, description="Khối lượng ước tính (gram)")


class NutritionPerIngredient(BaseModel):
    """Dinh dưỡng của một thành phần."""

    ingredient_name: str
    grams: float
    calories: float = Field(ge=0, description="Calo (kcal)")
    protein_g: float = Field(ge=0, description="Đạm (gram)")
    fat_g: float = Field(ge=0, description="Chất béo (gram)")
    carbs_g: float = Field(ge=0, description="Carbohydrate (gram)")
    fiber_g: float = Field(ge=0, description="Chất xơ (gram)")


class NutritionTotals(BaseModel):
    """Tổng dinh dưỡng của cả món ăn."""

    dish_name: str = Field(description="Tên món ăn đã nhận diện")
    ingredients: list[NutritionPerIngredient]
    total_calories: float
    total_protein_g: float
    total_fat_g: float
    total_carbs_g: float
    total_fiber_g: float
    confidence_score: float = Field(ge=0.0, le=1.0, description="Điểm tự tin của kết quả")


class NutritionResponse(BaseModel):
    """API response wrapper."""

    success: bool = True
    data: NutritionTotals | None = None
    error: str | None = None
