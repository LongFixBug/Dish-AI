"""Read-only dish lookup endpoint backed by ``vn_dishes``."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.postgres import get_session
from backend.services.dishes import _has_weight, _vn_dish_to_per_gram, lookup_dish
from schemas.nutrition import (
    NutritionPerIngredient,
    calculate_item_nutrition,
    calculate_totals,
)

router = APIRouter(prefix="/api/v1", tags=["dishes"])


@router.get("/dishes/lookup")
async def get_dish_lookup(
    name: str = Query(..., min_length=1, description="Tên món, VD 'phở bò'"),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Return dish-level nutrition from the local catalog and semantic fallback."""
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

    if _has_weight(vn):
        item = calculate_item_nutrition(
            vn.dish_name,
            vn.typical_grams,
            _vn_dish_to_per_gram(vn),
        )
    else:
        item = NutritionPerIngredient(
            item_name=vn.dish_name,
            grams=0.0,
            calories=round(vn.total_calories, 1),
            protein_g=round(vn.total_protein_g, 1),
            fat_g=round(vn.total_fat_g, 1),
            carbs_g=round(vn.total_carbs_g, 1),
            fiber_g=round(vn.total_fiber_g, 1),
            found_in_db=True,
            nutrition_basis="source_serving",
        )

    totals = calculate_totals(vn.dish_name, [item])
    return {
        "exists": True,
        "dish_name": vn.dish_name,
        "source": vn.source,
        "status": {
            "vnmeal": "verified",
            "vision_reviewed": "reviewed",
        }.get(vn.source, "estimated"),
        "dish_id": str(vn.id),
        "nutrition": totals,
    }
