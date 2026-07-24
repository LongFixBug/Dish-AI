"""Contracts for rebuilding the derived Qdrant catalog from PostgreSQL."""

from types import SimpleNamespace

import pytest

from backend.services.vector_catalog import CatalogType
from scripts import reindex_qdrant


def test_build_catalog_records_preserves_postgres_uuids_and_types() -> None:
    ingredients = [
        SimpleNamespace(
            id="ingredient-id",
            ingredient_name="Thịt bò",
            source="vnfood",
        )
    ]
    dishes = [
        SimpleNamespace(id="dish-id", dish_name="Phở bò", source="vnmeal")
    ]

    records = reindex_qdrant.build_catalog_records(ingredients, dishes)

    assert [(record.record_id, record.catalog_type) for record in records] == [
        ("ingredient-id", CatalogType.INGREDIENT),
        ("dish-id", CatalogType.DISH),
    ]


def test_assert_clean_index_rejects_missing_or_orphaned_points() -> None:
    records = [
        reindex_qdrant.CatalogRecord(
            record_id="dish-id",
            name="Phở bò",
            catalog_type=CatalogType.DISH,
            source="vnmeal",
        )
    ]
    indexed = {
        CatalogType.DISH: {"orphan-id"},
        CatalogType.INGREDIENT: set(),
    }

    with pytest.raises(RuntimeError, match="dish: missing=1, orphaned=1"):
        reindex_qdrant.assert_clean_index(records, indexed)


def test_validate_embeddings_rejects_wrong_vector_size() -> None:
    with pytest.raises(RuntimeError, match="expected 1024 dimensions"):
        reindex_qdrant.validate_embeddings([[0.1, 0.2]], expected_count=1)
