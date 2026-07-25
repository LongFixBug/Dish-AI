"""Contracts for the shared Qdrant dish and ingredient index."""

from types import SimpleNamespace

from backend.services import vector_catalog
from backend.services.vector_catalog import (
    CatalogRecord,
    CatalogType,
    compute_index_drift,
)


async def test_search_filters_qdrant_by_catalog_type_and_offloads_client(monkeypatch) -> None:
    captured: dict[str, object] = {}
    offloaded: list[str] = []

    class FakeClient:
        def query_points(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(points=[
                SimpleNamespace(
                    id="dish-id",
                    payload={"name": "Phở bò", "catalog_type": "dish"},
                    score=0.91,
                )
            ])

    async def fake_embed(_query):
        return [0.0] * vector_catalog.VECTOR_SIZE

    async def fake_to_thread(function, /, *args, **kwargs):
        offloaded.append(function.__name__)
        return function(*args, **kwargs)

    monkeypatch.setattr(vector_catalog, "_get_client", lambda: FakeClient())
    monkeypatch.setattr(vector_catalog, "embed_query", fake_embed)
    monkeypatch.setattr(vector_catalog.asyncio, "to_thread", fake_to_thread)

    hits = await vector_catalog.search_catalog("pho bo", CatalogType.DISH, limit=7)

    assert hits[0].record_id == "dish-id"
    assert hits[0].name == "Phở bò"
    assert captured["limit"] == 7
    condition = captured["query_filter"].must[0]
    assert condition.key == "catalog_type"
    assert condition.match.value == "dish"
    assert offloaded == ["query_points"]


async def test_upsert_uses_postgres_uuid_and_reviewed_payload(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeClient:
        def upsert(self, **kwargs):
            captured.update(kwargs)

    async def fake_embed(_name):
        return [0.1] * vector_catalog.VECTOR_SIZE

    async def fake_to_thread(function, /, *args, **kwargs):
        return function(*args, **kwargs)

    monkeypatch.setattr(vector_catalog, "_get_client", lambda: FakeClient())
    monkeypatch.setattr(vector_catalog, "embed_query", fake_embed)
    monkeypatch.setattr(vector_catalog.asyncio, "to_thread", fake_to_thread)

    record = CatalogRecord(
        record_id="8d34fb6d-6c2f-4b8f-8998-c3b194fa53cb",
        name="Phở bò",
        catalog_type=CatalogType.DISH,
        source="vnmeal",
    )
    await vector_catalog.upsert_catalog_record(record)

    point = captured["points"][0]
    assert str(point.id) == record.record_id
    assert point.payload == {
        "name": "Phở bò",
        "catalog_type": "dish",
        "source": "vnmeal",
        "reviewed": True,
    }


def test_compute_index_drift_reports_missing_and_orphan_ids() -> None:
    drift = compute_index_drift(
        database_ids={"shared", "missing"},
        qdrant_ids={"shared", "orphan"},
    )

    assert drift.missing_in_qdrant == {"missing"}
    assert drift.orphaned_in_qdrant == {"orphan"}
    assert drift.is_clean is False


async def test_delete_catalog_records_waits_for_qdrant_acknowledgement(monkeypatch) -> None:
    captured: dict[str, object] = {}

    class FakeClient:
        def delete(self, **kwargs):
            captured.update(kwargs)

    async def fake_to_thread(function, /, *args, **kwargs):
        return function(*args, **kwargs)

    monkeypatch.setattr(vector_catalog, "_get_client", lambda: FakeClient())
    monkeypatch.setattr(vector_catalog.asyncio, "to_thread", fake_to_thread)

    deleted = await vector_catalog.delete_catalog_records(["dish-id", "ingredient-id"])

    assert deleted == 2
    assert captured["wait"] is True
    assert captured["points_selector"].points == ["dish-id", "ingredient-id"]
