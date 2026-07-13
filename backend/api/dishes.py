"""Dishes endpoints — 2-tier lookup + user-contributed recipes.

4 endpoint theo plan:
  GET  /dishes/lookup              — Tier 1
  GET  /ingredients/search         — autocomplete nguyên liệu
  POST /dishes/compute             — preview nutrition (không lưu)
  POST /dishes                     — Tier 2 đóng góp món mới
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.postgres import get_session
from backend.services.dishes import (
    compute_nutrition,
    contribute_dish,
    lookup_dish,
)
from backend.services.ingredients import search_ingredients
from schemas.dish import (
    ComputeRequest,
    ComputeResponse,
    ContributeDishRequest,
    ContributeDishResponse,
    DishLookupResponse,
    IngredientSearchResult,
    IngredientSearchResponse,
)

router = APIRouter(prefix="/api/v1", tags=["dishes"])


# ─── Tier 1: Lookup ──────────────────────────────────────────────────────────


@router.get("/dishes/lookup", response_model=DishLookupResponse)
async def get_dish_lookup(
    name: str = Query(..., min_length=1, description="Tên món, VD 'cơm sườn'"),
    session: AsyncSession = Depends(get_session),
) -> DishLookupResponse:
    """Tìm món trong DB (institute trước, fallback user-recipe).

    exists=False → frontend đi flow đóng góp (POST /dishes).
    """
    result = await lookup_dish(session, name)
    return DishLookupResponse(**result)


# ─── Autocomplete nguyên liệu ─────────────────────────────────────────────────


@router.get("/ingredients/search", response_model=IngredientSearchResponse)
async def search_ingredients_endpoint(
    q: str = Query(..., min_length=1, description="1-2 chữ user gõ"),
    limit: int = Query(8, ge=1, le=20),
    session: AsyncSession = Depends(get_session),
) -> IngredientSearchResponse:
    """Tìm nguyên liệu cho autocomplete: ILIKE trước, vector fallback."""
    hits = await search_ingredients(session, q, limit)
    return IngredientSearchResponse(
        query=q,
        results=[
            IngredientSearchResult(
                id=ing.id,
                ingredient_name=ing.ingredient_name,
                source=ing.source,
            )
            for ing in hits
        ],
    )


# ─── Tier 2: Compute (preview) ───────────────────────────────────────────────


@router.post("/dishes/compute", response_model=ComputeResponse)
async def compute_dish(
    body: ComputeRequest,
    session: AsyncSession = Depends(get_session),
) -> ComputeResponse:
    """Preview nutrition từ list (ingredient_id, amount, unit) — không lưu."""
    totals, assumed = await compute_nutrition(session, body.dish_name, body.items)
    return ComputeResponse(success=True, nutrition=totals, conversion_assumed=assumed)


# ─── Tier 2: Contribute (lưu recipe mới) ────────────────────────────────────


@router.post("/dishes", response_model=ContributeDishResponse)
async def contribute_dish_endpoint(
    body: ContributeDishRequest,
    session: AsyncSession = Depends(get_session),
) -> ContributeDishResponse:
    """Món chưa có → user đóng góp công thức + tính nutrition + lưu (status=draft)."""
    try:
        dish_id, totals, assumed = await contribute_dish(
            session,
            dish_name=body.dish_name,
            description=body.description,
            items=body.items,
            contributor_id=body.contributor_id,
        )
    except ValueError as e:
        # Trùng tên món
        raise HTTPException(status_code=409, detail=str(e)) from e

    return ContributeDishResponse(
        success=True,
        dish_id=dish_id,
        status="draft",
        nutrition=totals,
        conversion_assumed=assumed,
    )