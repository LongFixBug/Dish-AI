"""Approved dishes must be published to Qdrant after the database commit."""

from types import SimpleNamespace

from backend.services.vector_catalog import CatalogType
from scripts import review_dish_candidates


async def test_publish_reviewed_dish_builds_qdrant_record(monkeypatch) -> None:
    captured = []

    async def fake_upsert(record) -> None:
        captured.append(record)

    monkeypatch.setattr(review_dish_candidates, "upsert_catalog_record", fake_upsert)
    dish = SimpleNamespace(
        id="8d34fb6d-6c2f-4b8f-8998-c3b194fa53cb",
        dish_name="Phở bò",
        source="vision_reviewed",
    )

    await review_dish_candidates.publish_reviewed_dish(dish)

    assert captured[0].record_id == dish.id
    assert captured[0].name == dish.dish_name
    assert captured[0].catalog_type is CatalogType.DISH
    assert captured[0].source == dish.source
