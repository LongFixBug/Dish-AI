"""Fail-open client for the optional Food Gate shadow service."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Literal

import httpx

from backend.config import settings

logger = logging.getLogger("foodai")


@dataclass(frozen=True)
class FoodGateShadowResult:
    action: Literal["block", "vision"]
    food_score: float
    non_food_score: float
    block_threshold: float


def _parse_shadow_result(payload: object) -> FoodGateShadowResult:
    if not isinstance(payload, dict):
        raise ValueError("Food Gate response must be an object")

    action = payload.get("action")
    if action not in {"block", "vision"}:
        raise ValueError("Food Gate action is invalid")

    scores = {
        name: payload.get(name) for name in ("food_score", "non_food_score", "block_threshold")
    }
    if any(not isinstance(value, (int, float)) for value in scores.values()):
        raise ValueError("Food Gate scores are invalid")
    if any(
        not math.isfinite(float(value)) or not 0 <= float(value) <= 1
        for value in scores.values()
    ):
        raise ValueError("Food Gate scores are out of range")

    return FoodGateShadowResult(
        action=action,
        food_score=float(scores["food_score"]),
        non_food_score=float(scores["non_food_score"]),
        block_threshold=float(scores["block_threshold"]),
    )


async def predict_food_gate(
    image_content: bytes,
    content_type: str,
) -> FoodGateShadowResult | None:
    """Call Food Gate once; any failure must fall back to Vision."""

    if settings.food_gate_mode == "disabled" or settings.food_gate_url is None:
        return None

    headers = {}
    if settings.food_gate_service_token:
        headers["X-Food-Gate-Token"] = settings.food_gate_service_token

    try:
        async with httpx.AsyncClient(timeout=settings.food_gate_timeout_seconds) as client:
            response = await client.post(
                f"{str(settings.food_gate_url).rstrip('/')}/predict",
                files={"file": ("upload", image_content, content_type)},
                headers=headers,
            )
            response.raise_for_status()
        return _parse_shadow_result(response.json())
    except (httpx.HTTPError, ValueError):
        logger.warning(
            "Food Gate unavailable; keep Vision path",
            exc_info=True,
        )
        return None


async def observe_food_gate_shadow(
    image_content: bytes,
    content_type: str,
) -> FoodGateShadowResult | None:
    """Log Food Gate output without changing the Vision decision."""

    result = await predict_food_gate(image_content, content_type)
    if result is None:
        return None

    logger.info(
        "Food Gate shadow action=%s food_score=%.3f non_food_score=%.3f threshold=%.3f",
        result.action,
        result.food_score,
        result.non_food_score,
        result.block_threshold,
    )
    return result
