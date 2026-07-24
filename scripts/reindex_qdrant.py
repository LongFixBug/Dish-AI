"""Rebuild or audit the derived Qdrant catalog index.

PostgreSQL is authoritative. This command reads reviewed catalog rows, creates
their embeddings through llama.cpp, and publishes them to one Qdrant
collection. A rebuild completes only when every PostgreSQL UUID is present and
Qdrant contains no orphaned UUID.

Usage:
    uv run python scripts/reindex_qdrant.py
    uv run python scripts/reindex_qdrant.py --check
"""

import argparse
import asyncio
import math
import sys
from collections.abc import Sequence
from pathlib import Path

import httpx
from sqlalchemy import select

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.config import settings  # noqa: E402
from backend.db.models import VnDish, VnIngredient  # noqa: E402
from backend.db.postgres import async_session  # noqa: E402
from backend.services.vector_catalog import (  # noqa: E402
    VECTOR_SIZE,
    CatalogRecord,
    CatalogType,
    compute_index_drift,
    init_collection,
    list_indexed_ids,
    upsert_catalog_vectors,
)

BATCH_SIZE = 50
REQUEST_TIMEOUT_SECONDS = 60.0
INDEXED_INGREDIENT_TYPES = ("ingredient", "fruit", "product")


def build_catalog_records(
    ingredients: Sequence[VnIngredient],
    dishes: Sequence[VnDish],
) -> list[CatalogRecord]:
    """Convert authoritative ORM rows into immutable indexing records."""
    return [
        *(
            CatalogRecord(
                record_id=str(row.id),
                name=row.ingredient_name,
                catalog_type=CatalogType.INGREDIENT,
                source=row.source,
            )
            for row in ingredients
        ),
        *(
            CatalogRecord(
                record_id=str(row.id),
                name=row.dish_name,
                catalog_type=CatalogType.DISH,
                source=row.source,
            )
            for row in dishes
        ),
    ]


async def load_catalog_records() -> list[CatalogRecord]:
    """Load every searchable, reviewed catalog row from PostgreSQL."""
    async with async_session() as session:
        ingredient_result = await session.execute(
            select(VnIngredient)
            .where(VnIngredient.item_type.in_(INDEXED_INGREDIENT_TYPES))
            .order_by(VnIngredient.id)
        )
        dish_result = await session.execute(
            select(VnDish).order_by(VnDish.id)
        )
        ingredients = list(ingredient_result.scalars().all())
        dishes = list(dish_result.scalars().all())
    return build_catalog_records(ingredients, dishes)


def validate_embeddings(
    vectors: list[list[float]],
    expected_count: int,
) -> None:
    """Reject incomplete, malformed, or non-finite embedding responses."""
    if len(vectors) != expected_count:
        raise RuntimeError(
            f"Embedding server returned {len(vectors)} vectors; "
            f"expected {expected_count}."
        )
    for index, vector in enumerate(vectors):
        if len(vector) != VECTOR_SIZE:
            raise RuntimeError(
                f"Embedding {index} has {len(vector)} dimensions; "
                f"expected {VECTOR_SIZE} dimensions."
            )
        if not all(math.isfinite(value) for value in vector):
            raise RuntimeError(f"Embedding {index} contains a non-finite value.")


async def embed_batch(
    client: httpx.AsyncClient,
    records: list[CatalogRecord],
) -> list[list[float]]:
    """Embed one ordered batch through the OpenAI-compatible llama.cpp API."""
    response = await client.post(
        f"{settings.embedding_url}/v1/embeddings",
        json={
            "input": [record.name for record in records],
            "model": settings.embedding_model,
        },
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    payload = response.json()
    vectors = [item["embedding"] for item in payload["data"]]
    validate_embeddings(vectors, expected_count=len(records))
    return vectors


async def generate_all_embeddings(
    records: list[CatalogRecord],
) -> list[list[float]]:
    """Generate all vectors before replacing the currently usable index."""
    vectors: list[list[float]] = []
    total_batches = math.ceil(len(records) / BATCH_SIZE)
    async with httpx.AsyncClient() as client:
        for offset in range(0, len(records), BATCH_SIZE):
            batch = records[offset : offset + BATCH_SIZE]
            vectors.extend(await embed_batch(client, batch))
            batch_number = offset // BATCH_SIZE + 1
            print(f"Embedded batch {batch_number}/{total_batches} ({len(vectors)} rows).")
    return vectors


def _database_ids_by_type(
    records: Sequence[CatalogRecord],
) -> dict[CatalogType, set[str]]:
    ids = {catalog_type: set() for catalog_type in CatalogType}
    for record in records:
        ids[record.catalog_type].add(record.record_id)
    return ids


def assert_clean_index(
    records: Sequence[CatalogRecord],
    indexed_ids: dict[CatalogType, set[str]],
) -> None:
    """Fail when the derived index differs from PostgreSQL in either direction."""
    database_ids = _database_ids_by_type(records)
    failures: list[str] = []
    for catalog_type in CatalogType:
        drift = compute_index_drift(
            database_ids[catalog_type],
            indexed_ids.get(catalog_type, set()),
        )
        if not drift.is_clean:
            failures.append(
                f"{catalog_type.value}: missing={len(drift.missing_in_qdrant)}, "
                f"orphaned={len(drift.orphaned_in_qdrant)}"
            )
    if failures:
        raise RuntimeError("Qdrant index drift detected: " + "; ".join(failures))


async def audit_index(records: list[CatalogRecord]) -> None:
    """Verify exact UUID parity and print per-type counts."""
    indexed_ids = await list_indexed_ids()
    assert_clean_index(records, indexed_ids)
    database_ids = _database_ids_by_type(records)
    for catalog_type in CatalogType:
        print(f"{catalog_type.value}: {len(database_ids[catalog_type])} indexed rows")
    print("Qdrant audit passed: no missing or orphaned UUIDs.")


async def rebuild_index(records: list[CatalogRecord]) -> None:
    """Build all vectors, replace the collection, and publish in batches."""
    vectors = await generate_all_embeddings(records)
    await asyncio.to_thread(init_collection, True)
    for offset in range(0, len(records), BATCH_SIZE):
        await upsert_catalog_vectors(
            records[offset : offset + BATCH_SIZE],
            vectors[offset : offset + BATCH_SIZE],
        )


def build_parser() -> argparse.ArgumentParser:
    """Build the reindex command line interface."""
    parser = argparse.ArgumentParser(description="Rebuild or audit the Qdrant catalog")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Audit UUID parity without changing Qdrant.",
    )
    return parser


async def run(check_only: bool = False) -> None:
    """Execute a full rebuild or a read-only parity audit."""
    records = await load_catalog_records()
    if not records:
        raise RuntimeError("PostgreSQL catalog is empty; refusing to replace Qdrant.")
    print(f"Loaded {len(records)} authoritative PostgreSQL rows.")
    if not check_only:
        await rebuild_index(records)
    await audit_index(records)


def main() -> None:
    """Parse command line arguments and run the asynchronous workflow."""
    arguments = build_parser().parse_args()
    asyncio.run(run(check_only=arguments.check))


if __name__ == "__main__":
    main()
