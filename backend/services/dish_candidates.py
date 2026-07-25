"""Stage, review, and publish dish estimates produced by Vision."""

import unicodedata
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import case, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import DishCandidate, VnDish
from schemas.nutrition import NutritionPerIngredient


class DishCandidateNotFoundError(LookupError):
    """Raised when a requested review candidate does not exist."""


class DishCandidateStateError(ValueError):
    """Raised when a reviewed candidate is submitted for review again."""


class DishCandidateDataError(ValueError):
    """Raised when a candidate lacks a usable serving estimate for approval."""


def normalize_dish_name_key(dish_name: str) -> str:
    """Normalize case and whitespace while preserving Vietnamese tones."""
    normalized = unicodedata.normalize("NFC", dish_name)
    return " ".join(normalized.strip().split()).casefold()


def _candidate_values(
    dish_name: str,
    typical_grams: float | None,
    nutrition: NutritionPerIngredient | None,
) -> dict[str, object]:
    display_name = " ".join(unicodedata.normalize("NFC", dish_name).strip().split())
    nutrient_values = {
        "total_calories": round(nutrition.calories, 1) if nutrition else 0.0,
        "total_protein_g": round(nutrition.protein_g, 1) if nutrition else 0.0,
        "total_fat_g": round(nutrition.fat_g, 1) if nutrition else 0.0,
        "total_carbs_g": round(nutrition.carbs_g, 1) if nutrition else 0.0,
        "total_fiber_g": round(nutrition.fiber_g, 1) if nutrition else 0.0,
    }
    return {
        "dish_name": display_name,
        "dish_name_key": normalize_dish_name_key(display_name),
        "typical_grams": typical_grams if typical_grams and typical_grams > 0 else None,
        **nutrient_values,
        "status": "pending",
        "observation_count": 1,
    }


def _has_positive_nutrition(record: object) -> bool:
    """Return whether a candidate or catalog row carries any nutrition value."""
    return any(
        float(getattr(record, field, 0.0) or 0.0) > 0
        for field in (
            "total_calories",
            "total_protein_g",
            "total_fat_g",
            "total_carbs_g",
            "total_fiber_g",
        )
    )


def _validate_candidate_for_approval(candidate: DishCandidate) -> None:
    """Prevent zero-filled or weightless Vision estimates entering the catalog."""
    if not candidate.typical_grams or candidate.typical_grams <= 0:
        raise DishCandidateDataError("candidate is missing a positive serving weight")
    if not candidate.total_calories or candidate.total_calories <= 0:
        raise DishCandidateDataError("candidate has no positive calorie estimate")


def _enrich_existing_catalog_row(dish: VnDish, candidate: DishCandidate) -> None:
    """Fill reviewed gaps without overwriting complete institute nutrition."""
    if not _has_positive_nutrition(dish):
        dish.typical_grams = candidate.typical_grams
        dish.total_calories = candidate.total_calories
        dish.total_protein_g = candidate.total_protein_g
        dish.total_fat_g = candidate.total_fat_g
        dish.total_carbs_g = candidate.total_carbs_g
        dish.total_fiber_g = candidate.total_fiber_g
        dish.typical_grams_source = "vision_review"
        dish.typical_grams_confidence = 0.4
        dish.typical_grams_rule = "candidate_review"
        dish.source = "vision_reviewed"
        return

    if not dish.typical_grams or dish.typical_grams <= 0:
        dish.typical_grams = candidate.typical_grams
        dish.typical_grams_source = "vision_review"
        dish.typical_grams_confidence = 0.4
        dish.typical_grams_rule = "candidate_review_weight_only"


async def stage_dish_candidate(
    session: AsyncSession,
    dish_name: str,
    typical_grams: float | None,
    *,
    nutrition: NutritionPerIngredient | None = None,
) -> DishCandidate:
    """Atomically create or refresh a Vision candidate for later review."""
    values = _candidate_values(dish_name, typical_grams, nutrition)
    statement = insert(DishCandidate).values(**values)
    excluded = statement.excluded
    pending = DishCandidate.status == "pending"
    update_columns = {
        "observation_count": DishCandidate.observation_count + 1,
        "last_seen_at": func.now(),
        **{
            column: case((pending, getattr(excluded, column)), else_=getattr(DishCandidate, column))
            for column in (
                "typical_grams",
                "total_calories",
                "total_protein_g",
                "total_fat_g",
                "total_carbs_g",
                "total_fiber_g",
            )
        },
    }
    statement = statement.on_conflict_do_update(
        index_elements=[DishCandidate.dish_name_key],
        set_=update_columns,
    ).returning(DishCandidate)
    result = await session.execute(statement)
    return result.scalar_one()


async def _lookup_candidate_by_id(
    session: AsyncSession,
    candidate_id: str,
) -> DishCandidate | None:
    result = await session.execute(
        select(DishCandidate)
        .where(DishCandidate.id == candidate_id)
        .with_for_update()
    )
    return result.scalar_one_or_none()


async def _lookup_catalog_by_name(
    session: AsyncSession,
    dish_name: str,
) -> VnDish | None:
    result = await session.execute(
        select(VnDish).where(VnDish.dish_name == dish_name).with_for_update()
    )
    return result.scalar_one_or_none()


async def approve_dish_candidate(
    session: AsyncSession,
    candidate_id: str,
) -> VnDish:
    """Publish one pending candidate as reviewed catalog data."""
    candidate = await _lookup_candidate_by_id(session, candidate_id)
    if candidate is None:
        raise DishCandidateNotFoundError(candidate_id)
    if candidate.status != "pending":
        raise DishCandidateStateError(candidate.status)
    _validate_candidate_for_approval(candidate)

    dish = await _lookup_catalog_by_name(session, candidate.dish_name)
    if dish is None:
        dish = VnDish(
            id=str(uuid4()),
            dish_name=candidate.dish_name,
            typical_grams=candidate.typical_grams,
            total_calories=candidate.total_calories,
            total_protein_g=candidate.total_protein_g,
            total_fat_g=candidate.total_fat_g,
            total_carbs_g=candidate.total_carbs_g,
            total_fiber_g=candidate.total_fiber_g,
            typical_grams_source="vision_review",
            typical_grams_confidence=0.4,
            typical_grams_rule="candidate_review",
            source="vision_reviewed",
        )
        session.add(dish)
    else:
        _enrich_existing_catalog_row(dish, candidate)

    candidate.status = "approved"
    candidate.approved_dish_id = dish.id
    candidate.reviewed_at = datetime.now(timezone.utc)
    await session.flush()
    return dish


async def reject_dish_candidate(
    session: AsyncSession,
    candidate_id: str,
) -> DishCandidate:
    """Reject one pending candidate without publishing catalog data."""
    candidate = await _lookup_candidate_by_id(session, candidate_id)
    if candidate is None:
        raise DishCandidateNotFoundError(candidate_id)
    if candidate.status != "pending":
        raise DishCandidateStateError(candidate.status)

    candidate.status = "rejected"
    candidate.reviewed_at = datetime.now(timezone.utc)
    await session.flush()
    return candidate


async def list_pending_candidates(
    session: AsyncSession,
    limit: int = 50,
) -> list[DishCandidate]:
    """Return frequently observed pending candidates first."""
    result = await session.execute(
        select(DishCandidate)
        .where(DishCandidate.status == "pending")
        .order_by(
            DishCandidate.observation_count.desc(),
            DishCandidate.created_at.asc(),
        )
        .limit(limit)
    )
    return list(result.scalars())
