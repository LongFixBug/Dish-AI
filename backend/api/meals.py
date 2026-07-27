"""Authenticated meal journal and local-first sync endpoints."""

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse, Response
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import CurrentUser, require_user
from backend.db.postgres import get_session
from backend.services.meals import (
    delete_meal,
    get_meal_for_user,
    list_meals,
    patch_meal,
    summarize_meals,
    upsert_meal,
)
from schemas.meal import (
    MealCreate,
    MealListResponse,
    MealPatch,
    MealResponse,
    MealSummaryResponse,
    MealType,
    validate_timezone,
)

router = APIRouter(prefix="/api/v1/meals", tags=["meals"])


def _timezone(value: str) -> str:
    try:
        return validate_timezone(value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _response(meal: object) -> dict[str, object]:
    return MealResponse.model_validate(meal).model_dump(mode="json")


@router.post("", response_model=MealResponse)
async def create_or_update_meal(
    payload: MealCreate,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_user),
) -> JSONResponse:
    meal, created = await upsert_meal(session, current_user.id, payload)
    return JSONResponse(
        status_code=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        content=_response(meal),
    )


@router.get("", response_model=MealListResponse)
async def get_meals(
    date_from: date = Query(alias="from"),
    date_to: date = Query(alias="to"),
    timezone: str = "Asia/Ho_Chi_Minh",
    meal_type: MealType | None = None,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_user),
) -> MealListResponse:
    if date_to < date_from:
        raise HTTPException(status_code=422, detail="Khoảng ngày không hợp lệ.")
    timezone = _timezone(timezone)
    meals = await list_meals(
        session,
        current_user.id,
        date_from=date_from,
        date_to=date_to,
        timezone=timezone,
        meal_type=meal_type,
    )
    return MealListResponse(items=[MealResponse.model_validate(meal) for meal in meals])


@router.get("/summary", response_model=MealSummaryResponse)
async def get_meal_summary(
    date_from: date = Query(alias="from"),
    date_to: date = Query(alias="to"),
    timezone: str = "Asia/Ho_Chi_Minh",
    meal_type: MealType | None = None,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_user),
) -> MealSummaryResponse:
    if date_to < date_from:
        raise HTTPException(status_code=422, detail="Khoảng ngày không hợp lệ.")
    timezone = _timezone(timezone)
    return await summarize_meals(
        session,
        current_user.id,
        date_from=date_from,
        date_to=date_to,
        timezone=timezone,
        meal_type=meal_type,
    )


@router.patch("/{meal_id}", response_model=MealResponse)
async def update_meal(
    meal_id: str,
    payload: MealPatch,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_user),
) -> MealResponse:
    meal = await get_meal_for_user(session, current_user.id, meal_id)
    if meal is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy bữa ăn.")
    return MealResponse.model_validate(await patch_meal(session, meal, payload))


@router.delete("/{meal_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_meal(
    meal_id: str,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_user),
) -> Response:
    meal = await get_meal_for_user(session, current_user.id, meal_id)
    if meal is None:
        raise HTTPException(status_code=404, detail="Không tìm thấy bữa ăn.")
    await delete_meal(session, meal)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
