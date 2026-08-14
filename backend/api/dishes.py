"""Read-only food lookup endpoint backed by all nutrition catalogs."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import CurrentUser, require_user
from backend.db.postgres import get_session
from backend.services.dishes import _has_weight, _vn_dish_to_per_gram
from backend.services.food_catalog import (
    choose_food_match,
    lookup_food_matches,
    match_to_per_gram,
)
from schemas.nutrition import (
    NutritionPerIngredient,
    calculate_item_nutrition,
    calculate_totals,
)

router = APIRouter(prefix="/api/v1", tags=["dishes"])


@router.get("/dishes/lookup")
async def get_dish_lookup(
    current_user: Annotated[CurrentUser, Depends(require_user)],
    name: str = Query(..., min_length=1, description="Tên món, VD 'phở bò'"),
    session: AsyncSession = Depends(get_session),
) -> dict:
    """Return nutrition from vn_dishes, vn_ingredients or crawled NRIHCM data.

    Cần đăng nhập: mỗi lần tra hụt sẽ gọi embedding server + Qdrant, không nên
    để người lạ bơm tải vào stack inference nội bộ.
    """
    matches = await lookup_food_matches(session, name)
    selected = choose_food_match(matches)
    if selected is None:
        status_value = "ambiguous" if matches else None
        return {
            "exists": False,
            "dish_name": name,
            "source": None,
            "status": status_value,
            "dish_id": None,
            "nutrition": None,
            "matches": [match.as_dict() for match in matches],
        }

    if selected.catalog_type == "vn_dish":
        vn = selected.row
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
    else:
        # Search endpoint uses 100g so ingredients and raw NRIHCM rows have a
        # common, explicit basis. The text analysis endpoint accepts custom g.
        item = calculate_item_nutrition(
            selected.canonical_name,
            100.0,
            match_to_per_gram(selected),
        )

    totals = calculate_totals(selected.canonical_name, [item])
    status_value = (
        {
            "vnmeal": "verified",
            "vision_reviewed": "reviewed",
        }.get(selected.source, "estimated")
        if selected.catalog_type == "vn_dish"
        else ("raw" if selected.catalog_type == "nrihcm_food" else "reviewed")
    )
    return {
        "exists": True,
        "dish_name": selected.canonical_name,
        "source": selected.source,
        "status": status_value,
        "dish_id": selected.record_id,
        "record_id": selected.record_id,
        "catalog_type": selected.catalog_type,
        "nutrition": totals,
        "matches": [match.as_dict() for match in matches],
    }
