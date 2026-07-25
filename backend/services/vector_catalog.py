"""Qdrant index for reviewed dishes and ingredients.

PostgreSQL remains the source of truth. Qdrant stores only derived vectors and
the minimum payload required to find the corresponding PostgreSQL UUID.
"""

import asyncio
from dataclasses import dataclass
from enum import Enum

from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from backend.config import settings
from backend.services.embeddings import embed_query

COLLECTION_NAME = "food_catalog"
VECTOR_SIZE = 1024
SIMILARITY_THRESHOLD = 0.75


class CatalogType(str, Enum):
    """Payload discriminator for the shared vector collection."""

    DISH = "dish"
    INGREDIENT = "ingredient"


@dataclass(frozen=True)
class CatalogRecord:
    """Reviewed PostgreSQL record ready to be indexed."""

    record_id: str
    name: str
    catalog_type: CatalogType
    source: str


@dataclass(frozen=True)
class CatalogHit:
    """Minimal semantic candidate returned by Qdrant."""

    record_id: str
    name: str
    score: float


@dataclass(frozen=True)
class IndexDrift:
    """Difference between source-of-truth UUIDs and derived Qdrant UUIDs."""

    missing_in_qdrant: set[str]
    orphaned_in_qdrant: set[str]

    @property
    def is_clean(self) -> bool:
        return not self.missing_in_qdrant and not self.orphaned_in_qdrant


_client: QdrantClient | None = None


def _get_client() -> QdrantClient:
    """Create the synchronous Qdrant client lazily."""
    global _client
    if _client is None:
        _client = QdrantClient(url=settings.qdrant_url)
    return _client


def _collection_exists(client: QdrantClient) -> bool:
    collections = client.get_collections().collections
    return any(collection.name == COLLECTION_NAME for collection in collections)


def init_collection(force: bool = False) -> None:
    """Create the shared collection and its payload indexes.

    ``force`` is reserved for explicit full reindex jobs. Request-time startup
    never deletes an existing index.
    """
    client = _get_client()
    if _collection_exists(client):
        if not force:
            return
        client.delete_collection(COLLECTION_NAME)

    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=qmodels.VectorParams(
            size=VECTOR_SIZE,
            distance=qmodels.Distance.COSINE,
        ),
    )
    client.create_payload_index(
        collection_name=COLLECTION_NAME,
        field_name="catalog_type",
        field_schema=qmodels.PayloadSchemaType.KEYWORD,
    )
    client.create_payload_index(
        collection_name=COLLECTION_NAME,
        field_name="reviewed",
        field_schema=qmodels.PayloadSchemaType.BOOL,
    )


def _catalog_filter(catalog_type: CatalogType) -> qmodels.Filter:
    return qmodels.Filter(must=[
        qmodels.FieldCondition(
            key="catalog_type",
            match=qmodels.MatchValue(value=catalog_type.value),
        ),
        qmodels.FieldCondition(
            key="reviewed",
            match=qmodels.MatchValue(value=True),
        ),
    ])


async def search_catalog(
    query: str,
    catalog_type: CatalogType,
    limit: int = 5,
) -> list[CatalogHit]:
    """Embed a query and return reviewed candidates of one catalog type."""
    vector = await embed_query(query)
    client = _get_client()
    result = await asyncio.to_thread(
        client.query_points,
        collection_name=COLLECTION_NAME,
        query=vector,
        query_filter=_catalog_filter(catalog_type),
        score_threshold=SIMILARITY_THRESHOLD,
        limit=limit,
        with_payload=True,
    )
    hits: list[CatalogHit] = []
    for point in result.points:
        payload = point.payload or {}
        name = payload.get("name")
        if not isinstance(name, str) or not name:
            continue
        hits.append(CatalogHit(
            record_id=str(point.id),
            name=name,
            score=round(float(point.score), 4),
        ))
    return hits


def _point(record: CatalogRecord, vector: list[float]) -> qmodels.PointStruct:
    return qmodels.PointStruct(
        id=record.record_id,
        vector=vector,
        payload={
            "name": record.name,
            "catalog_type": record.catalog_type.value,
            "source": record.source,
            "reviewed": True,
        },
    )


async def upsert_catalog_record(record: CatalogRecord) -> None:
    """Generate and publish one vector after its PostgreSQL commit succeeds."""
    vector = await embed_query(record.name)
    await upsert_catalog_vectors([record], [vector])


async def upsert_catalog_vectors(
    records: list[CatalogRecord],
    vectors: list[list[float]],
) -> int:
    """Publish a pre-embedded batch and wait for Qdrant acknowledgement."""
    points = [
        _point(record, vector)
        for record, vector in zip(records, vectors, strict=True)
    ]
    if not points:
        return 0
    client = _get_client()
    await asyncio.to_thread(
        client.upsert,
        collection_name=COLLECTION_NAME,
        points=points,
        wait=True,
    )
    return len(points)


async def delete_catalog_records(record_ids: list[str]) -> int:
    """Delete derived vectors after the authoritative DB rows are committed."""
    unique_ids = list(dict.fromkeys(record_ids))
    if not unique_ids:
        return 0
    client = _get_client()
    await asyncio.to_thread(
        client.delete,
        collection_name=COLLECTION_NAME,
        points_selector=qmodels.PointIdsList(points=unique_ids),
        wait=True,
    )
    return len(unique_ids)


def compute_index_drift(
    database_ids: set[str],
    qdrant_ids: set[str],
) -> IndexDrift:
    """Compare authoritative and derived identifiers without mutating either."""
    return IndexDrift(
        missing_in_qdrant=database_ids - qdrant_ids,
        orphaned_in_qdrant=qdrant_ids - database_ids,
    )


def _scroll_all_records() -> dict[CatalogType, set[str]]:
    client = _get_client()
    indexed = {catalog_type: set() for catalog_type in CatalogType}
    offset = None
    while True:
        points, offset = client.scroll(
            collection_name=COLLECTION_NAME,
            limit=256,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        for point in points:
            payload = point.payload or {}
            try:
                catalog_type = CatalogType(payload.get("catalog_type"))
            except (TypeError, ValueError):
                continue
            indexed[catalog_type].add(str(point.id))
        if offset is None:
            return indexed


async def list_indexed_ids() -> dict[CatalogType, set[str]]:
    """Read every indexed UUID for consistency audits."""
    return await asyncio.to_thread(_scroll_all_records)
