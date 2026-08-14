"""Durable, privacy-preserving observation of the recognition decision path."""

from __future__ import annotations

import logging
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import RecognitionEvent

logger = logging.getLogger("foodai.recognition_events")


class RecognitionResponse(Protocol):
    source: str
    dish_name: str | None
    model_version: str | None


def _bounded(value: float | None) -> float | None:
    if value is None:
        return None
    return min(1.0, max(0.0, float(value)))


async def record_recognition_event(
    session: AsyncSession,
    *,
    user_id: str,
    response: RecognitionResponse,
    cv_dish_name: str | None,
    cv_confidence: float | None,
    album_dish_name: str | None,
    album_score: float | None,
    album_margin: float | None,
    cv_top1_name: str | None = None,
    cv_top2_name: str | None = None,
    cv_top2_confidence: float | None = None,
    fusion_reason: str | None = None,
) -> str | None:
    """Persist only decision metadata; telemetry failure never breaks analysis."""
    event = RecognitionEvent(
        submitted_by=user_id,
        source=str(response.source),
        final_dish_name=response.dish_name,
        cv_dish_name=cv_dish_name,
        cv_top1_name=cv_top1_name,
        cv_confidence=_bounded(cv_confidence),
        cv_top2_name=cv_top2_name,
        cv_top2_confidence=_bounded(cv_top2_confidence),
        album_dish_name=album_dish_name,
        album_score=_bounded(album_score),
        album_margin=_bounded(album_margin),
        fusion_reason=fusion_reason,
        model_version=response.model_version,
    )
    try:
        session.add(event)
        await session.commit()
        return str(event.id)
    except Exception:  # telemetry is explicitly best-effort
        await session.rollback()
        logger.exception("Failed to persist recognition event")
        return None
