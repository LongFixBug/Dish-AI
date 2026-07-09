"""Schemas for nutrition analysis results.

Thiết kế: DB lưu dinh dưỡng trên 1 gram. Khi có gram thực tế từ Vision model,
Python làm phép nhân (không để LLM tính). LLM chỉ dùng để viết lời giải thích.

Flow:
    DB: thịt_bò = 2.5 cal/g, 0.26g protein/g, 0.15g fat/g, ...
    Vision: "thịt bò ~100g"
    Python: 100 × 2.5 = 250 cal (toán học, không thể sai)
    LLM: "Tô phở của bạn có 450 calo, trong đó thịt bò đóng góp 250 calo..."
"""

from pydantic import BaseModel, Field


class Ingredient(BaseModel):
    """Một thành phần trong món ăn (đầu ra từ Vision model)."""

    name: str = Field(description="Tên thành phần, ví dụ: 'thịt bò', 'bún', 'rau thơm'")
    estimated_grams: float = Field(ge=0, description="Khối lượng ước tính (gram)")


class NutritionPerGram(BaseModel):
    """Dinh dưỡng trên 1 gram của 1 ingredient (lưu trong DB).

    Đây là dữ liệu gốc từ USDA / Vietnam Food Composition Table.
    Mọi giá trị đều tính trên 1 gram để dễ nhân với gram thực tế.
    """

    ingredient_name: str
    calories_per_g: float = Field(ge=0, description="Calo trên 1 gram (kcal/g)")
    protein_per_g: float = Field(ge=0, description="Đạm trên 1 gram (g/g)")
    fat_per_g: float = Field(ge=0, description="Chất béo trên 1 gram (g/g)")
    carbs_per_g: float = Field(ge=0, description="Carbohydrate trên 1 gram (g/g)")
    fiber_per_g: float = Field(ge=0, description="Chất xơ trên 1 gram (g/g)")
    source: str = Field(
        default="unknown",
        description="Nguồn dữ liệu: 'usda', 'vfood', 'manual'",
    )


class NutritionPerIngredient(BaseModel):
    """Dinh dưỡng thực tế của 1 thành phần với gram cụ thể.

    Được tính bằng Python (phép nhân), không qua LLM:
        calories = estimated_grams × calories_per_g
        protein_g = estimated_grams × protein_per_g
        ...
    """

    ingredient_name: str
    grams: float
    calories: float = Field(ge=0, description="Calo (kcal)")
    protein_g: float = Field(ge=0, description="Đạm (gram)")
    fat_g: float = Field(ge=0, description="Chất béo (gram)")
    carbs_g: float = Field(ge=0, description="Carbohydrate (gram)")
    fiber_g: float = Field(ge=0, description="Chất xơ (gram)")
    found_in_db: bool = Field(
        default=True,
        description="Có tìm thấy trong database không? False = dữ liệu ước lượng",
    )


class NutritionTotals(BaseModel):
    """Tổng dinh dưỡng của cả món ăn (tính bằng Python, không qua LLM)."""

    dish_name: str = Field(description="Tên món ăn đã nhận diện")
    ingredients: list[NutritionPerIngredient]
    total_calories: float
    total_protein_g: float
    total_fat_g: float
    total_carbs_g: float
    total_fiber_g: float
    confidence_score: float = Field(
        ge=0.0, le=1.0, description="Điểm tự tin dựa trên tỉ lệ ingredient tìm thấy trong DB"
    )
    missing_ingredients: list[str] = Field(
        default_factory=list,
        description="Các ingredient không tìm thấy trong DB",
    )


class NutritionResponse(BaseModel):
    """API response wrapper."""

    success: bool = True
    data: NutritionTotals | None = None
    error: str | None = None


# ─── Hàm tính toán (Python math, không LLM) ──────────────────────────

def calculate_ingredient_nutrition(
    ingredient: Ingredient,
    per_gram: NutritionPerGram,
) -> NutritionPerIngredient:
    """Tính dinh dưỡng thực tế = gram × per_gram.

    Đây là phép nhân thuần túy, không liên quan đến AI/LLM.
    Đảm bảo kết quả chính xác 100% về mặt toán học.
    """
    g = ingredient.estimated_grams
    return NutritionPerIngredient(
        ingredient_name=ingredient.name,
        grams=g,
        calories=round(g * per_gram.calories_per_g, 1),
        protein_g=round(g * per_gram.protein_per_g, 1),
        fat_g=round(g * per_gram.fat_per_g, 1),
        carbs_g=round(g * per_gram.carbs_per_g, 1),
        fiber_g=round(g * per_gram.fiber_per_g, 1),
        found_in_db=True,
    )


def calculate_totals(
    dish_name: str,
    ingredients: list[NutritionPerIngredient],
    missing: list[str] | None = None,
) -> NutritionTotals:
    """Tính tổng dinh dưỡng = cộng dồn từ tất cả ingredients.

    Cũng là phép cộng thuần túy, không AI.
    """
    total_cal = sum(ing.calories for ing in ingredients)
    total_protein = sum(ing.protein_g for ing in ingredients)
    total_fat = sum(ing.fat_g for ing in ingredients)
    total_carbs = sum(ing.carbs_g for ing in ingredients)
    total_fiber = sum(ing.fiber_g for ing in ingredients)

    missing = missing or []
    found_count = sum(1 for ing in ingredients if ing.found_in_db)
    total_count = len(ingredients) + len(missing)
    confidence = found_count / max(total_count, 1)

    return NutritionTotals(
        dish_name=dish_name,
        ingredients=ingredients,
        total_calories=round(total_cal, 1),
        total_protein_g=round(total_protein, 1),
        total_fat_g=round(total_fat, 1),
        total_carbs_g=round(total_carbs, 1),
        total_fiber_g=round(total_fiber, 1),
        confidence_score=round(confidence, 2),
        missing_ingredients=missing,
    )
