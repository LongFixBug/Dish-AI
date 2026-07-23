"""Pydantic schemas cho POST /analyze (ảnh → nutrition) — dish-level.

Flow mới (Jul 23, không phân tích nguyên liệu):
  ảnh → CV local (giữ cho train sau) → Vision → dishes[{dish_name, gram}]
       → lookup mỗi item trong vn_dishes (+ Qdrant fallback) + vn_ingredients
       → scale nutrition = gram_vision × per_g_db
       → món chưa có → Vision tự thêm vào vn_dishes (source=vision_auto)
"""

from typing import Literal

from pydantic import BaseModel, Field

from schemas.nutrition import NutritionTotals


class AnalyzeDish(BaseModel):
    """1 món Vision nhận diện từ ảnh (món chính hoặc món ăn kèm)."""

    dish_name: str = Field(description="Tên món tiếng Việt (có dấu)")
    grams: float = Field(
        default=0.0, ge=0, description="Khối lượng ước lượng (gram) từ Vision"
    )
    is_side: bool = Field(
        default=False,
        description="True = món ăn kèm / đồ uống (tra cả vn_ingredients nếu vn_dishes thiếu)",
    )


class AnalyzeResponse(BaseModel):
    """Response cho POST /api/v1/analyze.

    - source='cv_local': CV local conf cao + lookup trúng (chưa wire vì CV chỉ trả dish_name).
    - source='vision': Vision nhận diện + lookup vn_dishes/vn_ingredients.
    - nutrition: NutritionTotals (dish-level, không có per-ingredient list).
    - dishes: list món Vision trả (tên + gram).
    - auto_added_dishes: món mới Vision tự INSERT vào vn_dishes.
    - missing_items: item không có trong cả vn_dishes + vn_ingredients (nutrition=0).
    """

    dish_name: str | None = Field(default=None, description="Tên món chính / bữa ăn")
    source: Literal["cv_local", "vision", "cv_local_not_found_vision"]
    cv_confidence: float | None = Field(
        default=None, description="Confidence CV local (0-1), None nếu CV disabled"
    )
    nutrition: NutritionTotals | None = None
    dishes: list[AnalyzeDish] = Field(
        default_factory=list,
        description="Từng món trong ảnh (món chính + món ăn kèm) kèm gram",
    )
    vision_reasoning: str | None = Field(
        default=None, description="Chain-of-Thought reasoning từ Qwen (nếu bật)"
    )
    auto_added_dishes: list[str] = Field(
        default_factory=list,
        description="Món mới được tự động INSERT vào vn_dishes từ ảnh",
    )
    missing_items: list[str] = Field(
        default_factory=list,
        description="Item không có trong cả vn_dishes + vn_ingredients",
    )
    error: str | None = None