"""Dishes endpoint — lookup món ăn trong vn_dishes.

Phiên bản Jul 23: chỉ giữ GET /dishes/lookup.
Đã bỏ POST /dishes (contribute), /dishes/compute, /ingredients/*
(mô hình mới không có user-recipe + không quản lý nguyên liệu thủ công).
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.postgres import get_session
from backend.services.dishes import _has_weight, _vn_dish_to_per_gram, lookup_dish
from schemas.nutrition import NutritionPerIngredient, NutritionTotals, calculate_totals

router = APIRouter(prefix="/api/v1", tags=["dishes"])


@router.get("/dishes/lookup")
async def get_dish_lookup(
    name: str = Query(..., min_length=1, description="Tên món, VD 'phở bò'"),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Tìm món trong vn_dishes (+ Qdrant fallback). Trả nutrition cấp món.

    Không còn user-recipe — chỉ vn_dishes.
    """
    vn = await lookup_dish(session, name)
    if vn is None:
        return {
            "exists": False,
            "dish_name": name,
            "source": None,
            "status": None,
            "dish_id": None,
            "nutrition": None,
        }

    per_gram = _vn_dish_to_per_gram(vn)

    if _has_weight(vn):
        # Có trọng lượng → nutrition cho 1 khẩu phần typical_grams.
        item = NutritionPerIngredient(
            item_name=vn.dish_name,
            grams=vn.typical_grams,
            calories=round(per_gram.calories_per_g * vn.typical_grams, 1),
            protein_g=round(per_gram.protein_per_g * vn.typical_grams, 1),
            fat_g=round(per_gram.fat_per_g * vn.typical_grams, 1),
            carbs_g=round(per_gram.carbs_per_g * vn.typical_grams, 1),
            fiber_g=round(per_gram.fiber_per_g * vn.typical_grams, 1),
            found_in_db=True,
        )
    else:
        # Không biết trọng lượng → raw per-serving, sentinel grams=1.
        item = NutritionPerIngredient(
            item_name=vn.dish_name,
            grams=1.0,
            calories=round(per_gram.calories_per_g, 1),
            protein_g=round(per_gram.protein_per_g, 1),
            fat_g=round(per_gram.fat_per_g, 1),
            carbs_g=round(per_gram.carbs_per_g, 1),
            fiber_g=round(per_gram.fiber_per_g, 1),
            found_in_db=True,
        )

    totals = calculate_totals(vn.dish_name, [item])
    return {
        "exists": True,
        "dish_name": vn.dish_name,
        "source": "vnmeal",
        "status": "verified",
        "dish_id": str(vn.id),
        "nutrition": totals,
    }