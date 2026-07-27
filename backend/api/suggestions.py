"""Endpoint gợi ý món theo khoảng dinh dưỡng còn lại trong ngày."""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.dependencies import CurrentUser, require_user
from backend.db.models import UserNutritionGoal, VnDish
from backend.db.postgres import get_session
from backend.services.suggestions import (
    DishOption,
    rank_dishes,
    remaining_budget,
)
from schemas.suggestion import (
    RemainingNutrition,
    SuggestedDish,
    SuggestionRequest,
    SuggestionResponse,
)

logger = logging.getLogger("foodai")

router = APIRouter(prefix="/api/v1", tags=["suggestions"])

# Chỉ lấy món đủ dữ liệu để so khớp; món thiếu số liệu đưa vào chỉ làm nhiễu.
CANDIDATE_LIMIT = 400


async def _catalog_options(session: AsyncSession) -> list[DishOption]:
    """Đọc các món đã duyệt có đủ khối lượng và dinh dưỡng."""
    result = await session.execute(
        select(VnDish)
        .where(
            (VnDish.typical_grams > 0)
            & (VnDish.total_calories > 0)
        )
        .order_by(VnDish.dish_name)
        .limit(CANDIDATE_LIMIT)
    )
    return [
        DishOption(
            dish_name=row.dish_name,
            grams=float(row.typical_grams),
            calories=float(row.total_calories),
            protein_g=float(row.total_protein_g or 0),
            fat_g=float(row.total_fat_g or 0),
            carbs_g=float(row.total_carbs_g or 0),
        )
        for row in result.scalars().all()
    ]


# Mục tiêu mặc định khi người dùng chưa thiết lập: đủ để gợi ý vẫn chạy được
# thay vì trả 404, nhưng cố ý ở mức trung tính chứ không đoán theo cơ thể ai.
DEFAULT_TARGET = {
    "calories": 2000.0,
    "protein_g": 100.0,
    "fat_g": 60.0,
    "carbs_g": 250.0,
}


async def _target_macros(session: AsyncSession, user_id: str) -> dict[str, float]:
    """Mục tiêu dinh dưỡng đã lưu, hoặc mức trung tính khi chưa có."""
    record = await session.scalar(
        select(UserNutritionGoal).where(UserNutritionGoal.user_id == user_id)
    )
    payload = getattr(record, "result_payload", None)
    if not isinstance(payload, dict):
        return dict(DEFAULT_TARGET)
    try:
        return {
            "calories": float(payload["target_calories"]),
            "protein_g": float(payload["protein_g"]["target"]),
            "fat_g": float(payload["fat_g"]["target"]),
            "carbs_g": float(payload["carbohydrate_g"]["target"]),
        }
    except (KeyError, TypeError, ValueError):
        # Bản ghi cũ hoặc khác định dạng: gợi ý vẫn phải chạy được.
        logger.warning("Mục tiêu dinh dưỡng sai định dạng, dùng mức mặc định")
        return dict(DEFAULT_TARGET)


@router.post("/suggestions", response_model=SuggestionResponse)
async def suggest_dishes(
    request: SuggestionRequest,
    session: AsyncSession = Depends(get_session),
    current_user: CurrentUser = Depends(require_user),
) -> SuggestionResponse:
    """Gợi ý vài món lấp vừa phần dinh dưỡng còn thiếu của hôm nay."""
    goal = await _target_macros(session, current_user.id)
    budget = remaining_budget(
        target_calories=goal["calories"],
        target_protein_g=goal["protein_g"],
        target_fat_g=goal["fat_g"],
        target_carbs_g=goal["carbs_g"],
        consumed_calories=request.consumed_calories,
        consumed_protein_g=request.consumed_protein_g,
        consumed_fat_g=request.consumed_fat_g,
        consumed_carbs_g=request.consumed_carbs_g,
    )
    ranked = rank_dishes(
        await _catalog_options(session),
        budget,
        preferences=request.preferences,
        allergies=request.allergies,
        exclude_names=request.exclude_dish_names,
        limit=request.limit,
    )
    return SuggestionResponse(
        remaining=RemainingNutrition(
            calories=round(budget.calories, 1),
            protein_g=round(budget.protein_g, 1),
            fat_g=round(budget.fat_g, 1),
            carbs_g=round(budget.carbs_g, 1),
        ),
        suggestions=[
            SuggestedDish(
                dish_name=item.dish.dish_name,
                grams=round(item.dish.grams, 1),
                calories=round(item.dish.calories, 1),
                protein_g=round(item.dish.protein_g, 1),
                fat_g=round(item.dish.fat_g, 1),
                carbs_g=round(item.dish.carbs_g, 1),
                reason=item.reason,
                score=round(item.score, 4),
            )
            for item in ranked
        ],
        allergy_filter_is_partial=bool(request.allergies),
    )
