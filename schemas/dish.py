"""Pydantic schemas cho 2-tier dish lookup + user-contributed recipes.

Tái sử dụng schemas/nutrition.py: NutritionTotals, calculate_*(),
không viết lại toán nutrition.
"""

from pydantic import BaseModel, Field

from schemas.nutrition import NutritionTotals


# ─── Ingredient autocomplete ──────────────────────────────────────────────────


class IngredientSearchResult(BaseModel):
    """1 kết quả của GET /ingredients/search."""

    id: str = Field(description="UUID nguyên liệu trong nutrition_ingredients")
    ingredient_name: str
    source: str = Field(description="usda | vnfood | sr legacy | ...")


class IngredientSearchResponse(BaseModel):
    """Response cho GET /ingredients/search."""

    query: str
    results: list[IngredientSearchResult]


# ─── Dish lookup (Tier 1) ─────────────────────────────────────────────────────


class DishLookupResponse(BaseModel):
    """Response cho GET /dishes/lookup.

    - exists=False: món chưa có → frontend chuyển sang flow đóng góp (Tier 2).
    - source='institute': dinh dưỡng tổng từ Viện Dinh Dưỡng (authoritative).
    - source='user_recipe': công thức do user đóng góp, kèm status.
    """

    exists: bool
    dish_name: str
    source: str | None = Field(
        default=None, description="institute | user_recipe | None (khi exists=False)"
    )
    status: str | None = Field(
        default=None,
        description="draft | verified — chỉ ý nghĩa với user_recipe",
    )
    dish_id: str | None = Field(
        default=None,
        description="UUID món trong dishes (chỉ khi source=user_recipe)",
    )
    nutrition: NutritionTotals | None = None


# ─── Compute + Contribute (Tier 2) ───────────────────────────────────────────


class RecipeItemInput(BaseModel):
    """1 nguyên liệu trong công thức user đóng góp."""

    ingredient_id: str = Field(description="UUID nguyên liệu (từ autocomplete)")
    amount: float = Field(gt=0, description="Số lượng, VD 100, 150, 15")
    unit: str = Field(
        default="g",
        description="Đơn vị: 'g' (mặc định) hoặc 'ml'. kg/L cũng chấp nhận.",
    )


class ComputeRequest(BaseModel):
    """Body cho POST /dishes/compute (preview, không lưu)."""

    dish_name: str
    items: list[RecipeItemInput] = Field(min_length=1)


class ContributeDishRequest(BaseModel):
    """Body cho POST /dishes (Tier 2: compute + lưu recipe mới)."""

    dish_name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    items: list[RecipeItemInput] = Field(min_length=1)
    contributor_id: str | None = Field(
        default=None,
        description="UUID do client gen (anonymous, chưa có auth)",
    )


class ContributeDishResponse(BaseModel):
    """Response cho POST /dishes."""

    success: bool = True
    dish_id: str = Field(description="UUID món mới tạo trong dishes")
    status: str = Field(description="draft")
    nutrition: NutritionTotals
    conversion_assumed: list[str] = Field(
        default_factory=list,
        description="Tên nguyên liệu dùng fallback nước (ước lượng mL→g)",
    )
    error: str | None = None


class ComputeResponse(BaseModel):
    """Response cho POST /dishes/compute."""

    success: bool = True
    nutrition: NutritionTotals
    conversion_assumed: list[str] = Field(default_factory=list)
    error: str | None = None