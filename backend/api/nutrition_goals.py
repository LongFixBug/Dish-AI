"""Preview endpoint for personalized nutrition targets."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import CurrentUser, require_user
from backend.db.models import UserNutritionGoal
from backend.db.postgres import get_session
from backend.services.nutrition_goals import calculate_nutrition_goal
from schemas.nutrition_goals import (
    NutritionGoalRequest,
    NutritionGoalResponse,
    PersistedNutritionGoalResponse,
)

router = APIRouter(prefix="/api/v1/nutrition-goals", tags=["nutrition-goals"])


@router.post(
    "/preview",
    response_model=NutritionGoalResponse,
    status_code=status.HTTP_200_OK,
)
async def preview_nutrition_goal(
    payload: NutritionGoalRequest,
    _current_user: Annotated[CurrentUser, Depends(require_user)],
) -> NutritionGoalResponse:
    """Return a non-persisted, source-labelled nutrition target estimate."""
    try:
        return calculate_nutrition_goal(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post(
    "",
    response_model=PersistedNutritionGoalResponse,
    status_code=status.HTTP_200_OK,
)
async def save_nutrition_goal(
    payload: NutritionGoalRequest,
    current_user: Annotated[CurrentUser, Depends(require_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PersistedNutritionGoalResponse:
    """Create or replace the authenticated user's current goal."""
    try:
        result = calculate_nutrition_goal(payload)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    now = datetime.now(UTC)
    record = await session.scalar(
        select(UserNutritionGoal).where(UserNutritionGoal.user_id == current_user.id)
    )
    if record is None:
        record = UserNutritionGoal(user_id=current_user.id)
        session.add(record)

    record.goal = payload.goal
    record.current_weight_kg = payload.weight_kg
    record.target_weight_kg = payload.target_weight_kg
    record.target_days = payload.target_days
    record.algorithm_version = result.reference.algorithm_version
    record.input_payload = payload.model_dump(mode="json")
    record.result_payload = result.model_dump(mode="json")
    record.updated_at = now
    await session.commit()
    await session.refresh(record)
    return _to_persisted_response(record)


@router.get(
    "/current",
    response_model=PersistedNutritionGoalResponse,
)
async def get_current_nutrition_goal(
    current_user: Annotated[CurrentUser, Depends(require_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> PersistedNutritionGoalResponse:
    """Return only the current user's persisted goal."""
    record = await session.scalar(
        select(UserNutritionGoal).where(UserNutritionGoal.user_id == current_user.id)
    )
    if record is None:
        raise HTTPException(status_code=404, detail="Bạn chưa thiết lập mục tiêu dinh dưỡng.")
    return _to_persisted_response(record)


def _to_persisted_response(record: UserNutritionGoal) -> PersistedNutritionGoalResponse:
    return PersistedNutritionGoalResponse(
        user_id=str(record.user_id),
        goal=NutritionGoalResponse.model_validate(record.result_payload),
        created_at=record.created_at,
        updated_at=record.updated_at,
    )
