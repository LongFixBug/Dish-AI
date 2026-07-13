"""Pydantic schemas cho POST /analyze (ảnh → nutrition).

Flow 2-tier (Giai đoạn A):
  ảnh → CV local (conf≥0.6) → lookup_dish → nutrition        (source=cv_local)
  ảnh → CV (conf<0.6 hoặc lookup miss) → vision fallback     (source=cv_local_not_found_vision | vision)
       → ingredients → map name→id → compute_nutrition → nutrition
"""

from typing import Literal

from pydantic import BaseModel, Field

from schemas.nutrition import NutritionTotals


class AnalyzeIngredient(BaseModel):
    """1 nguyên liệu do vision (Qwen3.7) nhận diện từ ảnh."""

    name: str = Field(description="Tên nguyên liệu tiếng Việt (có dấu)")
    grams: float = Field(description="Khối lượng ước lượng (gram)")


class AnalyzeResponse(BaseModel):
    """Response cho POST /api/v1/analyze.

    - source='cv_local': CV local conf≥0.6 + lookup_dish trúng (institute/user_recipe).
    - source='cv_local_not_found_vision': CV conf≥0.6 nhưng lookup miss → fallback vision.
    - source='vision': CV conf<0.6 hoặc CV disabled → vision trực tiếp.
    - nutrition: NutritionTotals từ lookup (cv_local) hoặc compute (vision path).
    - ingredients: chỉ vision path (CV không detect nguyên liệu).
    - missing_ingredients: nguyên liệu vision trả nhưng không map được sang DB.
    """

    dish_name: str | None = Field(default=None, description="Tên món nhận diện")
    source: Literal["cv_local", "vision", "cv_local_not_found_vision"]
    cv_confidence: float | None = Field(
        default=None, description="Confidence CV local (0-1), None nếu CV disabled"
    )
    nutrition: NutritionTotals | None = None
    ingredients: list[AnalyzeIngredient] | None = Field(
        default=None, description="Chỉ vision path — list nguyên liệu từ ảnh"
    )
    missing_ingredients: list[str] = Field(
        default_factory=list,
        description="Nguyên liệu vision trả nhưng không tìm thấy trong DB",
    )
    error: str | None = None
