"""Qdrant index of reviewed reference dish images.

The image files and their labels remain the source of truth. Qdrant stores
only derived image-encoder vectors plus the minimum payload needed to vote for
a dish name at recognition time.
"""

import asyncio
from dataclasses import dataclass
from typing import Literal

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from backend.config import settings

DISH_IMAGES_COLLECTION = settings.image_embed_collection
IMAGE_VECTOR_SIZE = settings.image_embed_dim
SCROLL_PAGE_SIZE = 256
CandidateScoreMode = Literal["best", "top3_blend"]


@dataclass(frozen=True)
class DishImageHit:
    """One reviewed reference image matched by visual similarity."""

    dish_name: str
    class_slug: str
    source: str
    score: float


@dataclass(frozen=True)
class DishCandidateScore:
    """Per-dish aggregate over the matched reference images."""

    dish_name: str
    best_score: float
    votes: int
    class_slug: str | None = None


def aggregate_candidate_score(
    scores: list[float],
    *,
    mode: CandidateScoreMode,
) -> float:
    """Return one calibrated album score from a dish's nearest references.

    ``best`` is the existing production metric. ``top3_blend`` gives a small
    reward to repeated, independent-looking matches without using raw vote
    counts: classes with more indexed photos must not win simply because they
    have a larger album. The returned score stays in the cosine-score range.
    """
    if not scores:
        return 0.0
    ordered = sorted((float(score) for score in scores), reverse=True)
    best = ordered[0]
    if mode == "best":
        return best
    if mode == "top3_blend":
        mean_top3 = sum(ordered[:3]) / min(3, len(ordered))
        return round(0.75 * best + 0.25 * mean_top3, 4)
    raise ValueError(f"Unsupported dish image score mode: {mode!r}")


@dataclass(frozen=True)
class DishImageEntry:
    """One labelled reference image ready to be indexed."""

    record_id: str
    dish_name: str
    class_slug: str
    source: str


_client: QdrantClient | None = None


def _get_client() -> QdrantClient:
    """Create the synchronous Qdrant client lazily."""
    global _client
    if _client is None:
        _client = QdrantClient(url=settings.qdrant_url)
    return _client


def _collection_exists(client: QdrantClient) -> bool:
    collections = client.get_collections().collections
    return any(
        collection.name == DISH_IMAGES_COLLECTION for collection in collections
    )


def init_dish_images_collection(force: bool = False) -> None:
    """Create the image collection and its payload indexes.

    ``force`` is reserved for explicit full reindex jobs. Request-time startup
    never deletes an existing index.
    """
    client = _get_client()
    if _collection_exists(client):
        if not force:
            return
        client.delete_collection(DISH_IMAGES_COLLECTION)

    client.create_collection(
        collection_name=DISH_IMAGES_COLLECTION,
        vectors_config=qmodels.VectorParams(
            size=IMAGE_VECTOR_SIZE,
            distance=qmodels.Distance.COSINE,
        ),
    )
    payload_indexes = (
        ("class_slug", qmodels.PayloadSchemaType.KEYWORD),
        ("source", qmodels.PayloadSchemaType.KEYWORD),
        ("reviewed", qmodels.PayloadSchemaType.BOOL),
    )
    for field_name, field_schema in payload_indexes:
        client.create_payload_index(
            collection_name=DISH_IMAGES_COLLECTION,
            field_name=field_name,
            field_schema=field_schema,
        )


def _reviewed_filter() -> qmodels.Filter:
    return qmodels.Filter(must=[
        qmodels.FieldCondition(
            key="reviewed",
            match=qmodels.MatchValue(value=True),
        ),
    ])


def _hit_from_point(point) -> DishImageHit | None:
    """Map one Qdrant point to a hit, rejecting malformed payloads."""
    payload = point.payload or {}
    dish_name = payload.get("dish_name")
    class_slug = payload.get("class_slug")
    source = payload.get("source")
    if not isinstance(dish_name, str) or not dish_name:
        return None
    if not isinstance(class_slug, str) or not isinstance(source, str):
        return None
    return DishImageHit(
        dish_name=dish_name,
        class_slug=class_slug,
        source=source,
        score=round(float(point.score), 4),
    )


async def search_dish_images(
    vector: list[float],
    limit: int = 30,
) -> list[DishImageHit]:
    """Return the reviewed reference images closest to one image vector."""
    client = _get_client()
    result = await asyncio.to_thread(
        client.query_points,
        collection_name=DISH_IMAGES_COLLECTION,
        query=vector,
        query_filter=_reviewed_filter(),
        limit=limit,
        with_payload=True,
    )
    hits = (_hit_from_point(point) for point in result.points)
    return [hit for hit in hits if hit is not None]


async def top_dish_candidates(
    vector: list[float],
    point_limit: int = 30,
    dish_limit: int = 8,
    score_mode: CandidateScoreMode | None = None,
) -> list[DishCandidateScore]:
    """Group image hits by dish and rank them with the configured score mode."""
    hits = await search_dish_images(vector, limit=point_limit)
    grouped: dict[str, tuple[list[float], str | None]] = {}
    for hit in hits:
        scores, class_slug = grouped.setdefault(hit.dish_name, ([], hit.class_slug))
        scores.append(hit.score)
        if class_slug is None:
            grouped[hit.dish_name] = (scores, hit.class_slug)
    mode = score_mode or settings.image_match_score_mode
    candidates = [
        DishCandidateScore(
            dish_name=dish_name,
            best_score=aggregate_candidate_score(scores, mode=mode),
            votes=len(scores),
            class_slug=class_slug,
        )
        for dish_name, (scores, class_slug) in grouped.items()
    ]
    ranked = sorted(candidates, key=lambda item: item.best_score, reverse=True)
    return ranked[:dish_limit]


def _point(entry: DishImageEntry, vector: list[float]) -> qmodels.PointStruct:
    return qmodels.PointStruct(
        id=entry.record_id,
        vector=vector,
        payload={
            "dish_name": entry.dish_name,
            "class_slug": entry.class_slug,
            "source": entry.source,
            "reviewed": True,
        },
    )


async def upsert_dish_image_vectors(
    entries: list[DishImageEntry],
    vectors: list[list[float]],
) -> int:
    """Publish a pre-embedded batch and wait for Qdrant acknowledgement."""
    points = [
        _point(entry, vector)
        for entry, vector in zip(entries, vectors, strict=True)
    ]
    if not points:
        return 0
    client = _get_client()
    await asyncio.to_thread(
        client.upsert,
        collection_name=DISH_IMAGES_COLLECTION,
        points=points,
        wait=True,
    )
    return len(points)


def _scroll_dish_counts() -> dict[str, int]:
    client = _get_client()
    counts: dict[str, int] = {}
    offset = None
    while True:
        points, offset = client.scroll(
            collection_name=DISH_IMAGES_COLLECTION,
            limit=SCROLL_PAGE_SIZE,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        for point in points:
            payload = point.payload or {}
            dish_name = payload.get("dish_name")
            if isinstance(dish_name, str) and dish_name:
                counts[dish_name] = counts.get(dish_name, 0) + 1
        if offset is None:
            return counts


async def count_by_dish() -> dict[str, int]:
    """Count indexed reference images per dish for audits and eval reports."""
    return await asyncio.to_thread(_scroll_dish_counts)
