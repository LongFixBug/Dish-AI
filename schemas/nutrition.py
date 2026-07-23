"""Schemas for nutrition analysis results — dish-level (no per-ingredient).

Thiết kế mới (Jul 23): Vision chỉ nhận diện MÓN + khối lượng + món ăn kèm,
KHÔNG phân tích từng nguyên liệu trong món. Dinh dưỡng lấy từ DB:
  - vn_dishes (mónViện DD, total Calories / typical_grams) → chia ra per-gram
  - vn_ingredients (nguyên liệu / drink Việt, đã per-gram)

Mỗi item trong ảnh (món chính hoặc món ăn kèm) = 1 NutritionPerIngredient
với gram do Vision ước lượng + per-gram từ DB. Python nhân gram × per_g
để ra dinh dưỡng thực tế (toán học, không LLM).

Flow:
    DB: bánh mì thịt = 600 cal / 1 ổ 150g → 4 cal/g
    Vision: "2 ổ bánh mì thịt, 300g"
    Python: 300 × 4 = 1200 cal (scale theo gram ảnh, KHÔNG cố định 250g)
"""

from pydantic import BaseModel, Field


class NutritionPerGram(BaseModel):
    """Dinh dưỡng trên 1 gram của 1 item (món hoặc nguyên liệu) — lưu trong DB.

    Món (vn_dishes): total_calories / typical_grams → per_g.
    Nguyên liệu (vn_ingredients): đã lưu per_g sẵn.
    """

    name: str = Field(description="Tên món/nguyên liệu")
    calories_per_g: float = Field(ge=0, description="Calo trên 1 gram (kcal/g)")
    protein_per_g: float = Field(ge=0, description="Đạm trên 1 gram (g/g)")
    fat_per_g: float = Field(ge=0, description="Chất béo trên 1 gram (g/g)")
    carbs_per_g: float = Field(ge=0, description="Carbohydrate trên 1 gram (g/g)")
    fiber_per_g: float = Field(ge=0, description="Chất xơ trên 1 gram (g/g)")
    source: str = Field(
        default="unknown",
        description="Nguồn dữ liệu: 'vnmeal', 'vnfood', 'vision_auto'...",
    )


class NutritionPerIngredient(BaseModel):
    """Dinh dưỡng thực tế của 1 item (món hoặc món ăn kèm) với gram cụ thể.

    Tính bằng Python (phép nhân): calories = grams × calories_per_g.
    Một ảnh có thể có nhiều item: món chính + các món ăn kèm.
    """

    item_name: str = Field(description="Tên món hoặc món ăn kèm")
    grams: float
    calories: float = Field(ge=0, description="Calo (kcal)")
    protein_g: float = Field(ge=0, description="Đạm (gram)")
    fat_g: float = Field(ge=0, description="Chất béo (gram)")
    carbs_g: float = Field(ge=0, description="Carbohydrate (gram)")
    fiber_g: float = Field(ge=0, description="Chất xơ (gram)")
    found_in_db: bool = Field(
        default=True,
        description=(
            "True = có trong vn_dishes/vn_ingredients. "
            "False = món mới, Vision tự thêm (nutrition ước lượng)."
        ),
    )


class NutritionTotals(BaseModel):
    """Tổng dinh dưỡng của cả bữa ăn (món chính + món ăn kèm).

    Tính bằng Python từ list items, không qua LLM.
    """

    dish_name: str = Field(description="Tên bữa ăn (VD 'Phở bò + Quẩy')")
    items: list[NutritionPerIngredient] = Field(description="Từng món/món ăn kèm")
    total_calories: float
    total_protein_g: float
    total_fat_g: float
    total_carbs_g: float
    total_fiber_g: float
    total_grams: float = Field(
        default=0.0,
        description="Tổng gram tất cả item trong ảnh (do Vision ước)",
    )
    per_100g_calories: float = Field(
        default=0.0,
        description="Calo trên 100g (để user tự nhân với khẩu phần)",
    )
    per_100g_protein_g: float = 0.0
    per_100g_fat_g: float = 0.0
    per_100g_carbs_g: float = 0.0
    per_100g_fiber_g: float = 0.0
    confidence_score: float = Field(
        ge=0.0, le=1.0, description="Tỉ lệ item tìm thấy trong DB"
    )
    missing_ingredients: list[str] = Field(
        default_factory=list,
        description="Các item không tìm thấy trong cả vn_dishes + vn_ingredients",
    )


class NutritionResponse(BaseModel):
    """API response wrapper."""

    success: bool = True
    data: NutritionTotals | None = None
    error: str | None = None


# ─── Hàm tính toán (Python math, không LLM) ──────────────────────────


def calculate_item_nutrition(
    item_name: str,
    grams: float,
    per_gram: NutritionPerGram,
) -> NutritionPerIngredient:
    """Tính dinh dưỡng thực tế của 1 item = gram × per_gram.

    Phép nhân thuần túy, không liên quan AI/LLM → chính xác 100% toán học.
    """
    g = max(0.0, grams)
    return NutritionPerIngredient(
        item_name=item_name,
        grams=g,
        calories=round(g * per_gram.calories_per_g, 1),
        protein_g=round(g * per_gram.protein_per_g, 1),
        fat_g=round(g * per_gram.fat_per_g, 1),
        carbs_g=round(g * per_gram.carbs_per_g, 1),
        fiber_g=round(g * per_gram.fiber_per_g, 1),
        found_in_db=True,
    )


def calculate_item_nutrition_unknown(
    item_name: str,
    grams: float,
    *,
    per_gram: NutritionPerGram | None = None,
) -> NutritionPerIngredient:
    """Item KHÔNG có trong DB (món mới) → nutrition = 0 hoặc theo ước lượng Vision.

    Truyền per_gram=None → toàn 0 (chưa biết dinh dưỡng).
    Truyền per_gram (Vision ước) → nhân bình thường (found_in_db=False).
    """
    g = max(0.0, grams)
    if per_gram is None:
        per_gram = NutritionPerGram(
            name=item_name,
            calories_per_g=0.0, protein_per_g=0.0, fat_per_g=0.0,
            carbs_per_g=0.0, fiber_per_g=0.0, source="vision_auto",
        )
    return NutritionPerIngredient(
        item_name=item_name,
        grams=g,
        calories=round(g * per_gram.calories_per_g, 1),
        protein_g=round(g * per_gram.protein_per_g, 1),
        fat_g=round(g * per_gram.fat_per_g, 1),
        carbs_g=round(g * per_gram.carbs_per_g, 1),
        fiber_g=round(g * per_gram.fiber_per_g, 1),
        found_in_db=False,
    )


def calculate_totals(
    dish_name: str,
    items: list[NutritionPerIngredient],
    missing: list[str] | None = None,
) -> NutritionTotals:
    """Tổng dinh dưỡng = cộng dồn items + per-100g. Toán học thuần túy."""
    total_cal = sum(it.calories for it in items)
    total_protein = sum(it.protein_g for it in items)
    total_fat = sum(it.fat_g for it in items)
    total_carbs = sum(it.carbs_g for it in items)
    total_fiber = sum(it.fiber_g for it in items)
    total_grams = sum(it.grams for it in items)

    if total_grams > 0:
        scale = 100.0 / total_grams
        per_100g_cal = round(total_cal * scale, 1)
        per_100g_protein = round(total_protein * scale, 1)
        per_100g_fat = round(total_fat * scale, 1)
        per_100g_carbs = round(total_carbs * scale, 1)
        per_100g_fiber = round(total_fiber * scale, 1)
    else:
        per_100g_cal = per_100g_protein = per_100g_fat = per_100g_carbs = per_100g_fiber = 0.0

    missing = missing or []
    in_db = sum(1 for it in items if it.found_in_db)
    total_count = len(items) + len(missing)
    confidence = in_db / max(total_count, 1)

    return NutritionTotals(
        dish_name=dish_name,
        items=items,
        total_calories=round(total_cal, 1),
        total_protein_g=round(total_protein, 1),
        total_fat_g=round(total_fat, 1),
        total_carbs_g=round(total_carbs, 1),
        total_fiber_g=round(total_fiber, 1),
        total_grams=round(total_grams, 1),
        per_100g_calories=per_100g_cal,
        per_100g_protein_g=per_100g_protein,
        per_100g_fat_g=per_100g_fat,
        per_100g_carbs_g=per_100g_carbs,
        per_100g_fiber_g=per_100g_fiber,
        confidence_score=round(confidence, 2),
        missing_ingredients=missing,
    )