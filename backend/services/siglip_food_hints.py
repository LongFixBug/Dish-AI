"""Fail-open client for the optional SigLIP food-hint service."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass

import httpx

from backend.config import settings

logger = logging.getLogger("foodai")


@dataclass(frozen=True)
class SiglipFoodCandidate:
    slug: str
    name: str
    score: float


@dataclass(frozen=True)
class SiglipFoodHintResult:
    model_version: str
    candidates: tuple[SiglipFoodCandidate, ...]


def _parse_food_hint_result(payload: object) -> SiglipFoodHintResult:
    if not isinstance(payload, dict):
        raise ValueError("SigLIP food hint response must be an object")

    model_version = payload.get("model_version")
    if not isinstance(model_version, str) or not model_version:
        raise ValueError("SigLIP model_version is invalid")

    raw_candidates = payload.get("candidates")
    if not isinstance(raw_candidates, list):
        raise ValueError("SigLIP candidates are invalid")

    candidates = []
    for raw_candidate in raw_candidates:
        if not isinstance(raw_candidate, dict):
            raise ValueError("SigLIP candidate is invalid")

        slug = raw_candidate.get("slug")
        name = raw_candidate.get("name")
        score = raw_candidate.get("score")

        if not isinstance(slug, str) or not slug:
            raise ValueError("SigLIP candidate slug is invalid")

        if not isinstance(name, str) or not name:
            raise ValueError("SigLIP candidate name is invalid")

        if not isinstance(score, (int, float)):
            raise ValueError("SigLIP candidate score is invalid")

        if not math.isfinite(float(score)) or not 0 <= float(score) <= 1:
            raise ValueError("SigLIP candidate score is out of range")

        candidates.append(
            SiglipFoodCandidate(
                slug=slug,
                name=name,
                score=float(score),
            )
        )

    return SiglipFoodHintResult(
        model_version=model_version,
        candidates=tuple(candidates),
    )


async def predict_siglip_food_hints(
    image_content: bytes,
    content_type: str,
) -> SiglipFoodHintResult | None:
    """Call SigLIP once; any failure must leave the Vision path unchanged."""

    if settings.siglip_food_hint_mode == "disabled" or settings.siglip_food_hint_url is None:
        return None

    try:
        async with httpx.AsyncClient(timeout=settings.siglip_food_hint_timeout_seconds) as client:
            response = await client.post(
                f"{str(settings.siglip_food_hint_url).rstrip('/')}/predict",
                files={"file": ("upload", image_content, content_type)},
            )
            response.raise_for_status()

        # result = _parse_food_hint_result(response.json())

        # return SiglipFoodHintResult(
        #     model_version=result.model_version,
        #     candidates=result.candidates[: settings.siglip_food_hint_top_k],
        # )

        result = _parse_food_hint_result(response.json())

        candidates = result.candidates[: settings.siglip_food_hint_top_k]

        if not candidates or candidates[0].score < settings.siglip_food_hint_min_score:
            return SiglipFoodHintResult(
                model_version=result.model_version,
                candidates=(),
            )

        return SiglipFoodHintResult(
            model_version=result.model_version,
            candidates=candidates,
        )

    except (httpx.HTTPError, ValueError):
        logger.warning(
            "SigLIP food hint unavailable; keep Vision path unchanged",
            exc_info=True,
        )
        return None


async def observe_siglip_food_hint_shadow(
    image_content: bytes,
    content_type: str,
) -> SiglipFoodHintResult | None:
    """Log SigLIP results without modifying the Vision request."""

    result = await predict_siglip_food_hints(image_content, content_type)
    if result is None:
        return None

    logger.info(
        "SigLIP food hint shadow model=%s candidates=%s",
        result.model_version,
        ", ".join(f"{candidate.slug}:{candidate.score:.3f}" for candidate in result.candidates),
    )
    return result
