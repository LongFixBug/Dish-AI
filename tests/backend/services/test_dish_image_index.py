"""Contracts for the derived Qdrant image-reference collection."""

from types import SimpleNamespace

import pytest
from qdrant_client.http import models as qmodels

from backend.services import dish_image_index
from backend.services.dish_image_index import (
    DISH_IMAGES_COLLECTION,
    IMAGE_VECTOR_SIZE,
    DishCandidateScore,
    DishImageEntry,
    DishImageHit,
)


class FakeInitClient:
    """Records collection lifecycle calls without any network access."""

    def __init__(self, existing: bool) -> None:
        self.existing = existing
        self.calls: list[str] = []
        self.vectors_config: qmodels.VectorParams | None = None

    def get_collections(self):
        collections = (
            [SimpleNamespace(name=DISH_IMAGES_COLLECTION)] if self.existing else []
        )
        return SimpleNamespace(collections=collections)

    def delete_collection(self, name):
        self.calls.append(f"delete:{name}")

    def create_collection(self, collection_name, vectors_config):
        self.calls.append(f"create:{collection_name}")
        self.vectors_config = vectors_config

    def create_payload_index(self, collection_name, field_name, field_schema):
        self.calls.append(f"index:{field_name}")


async def _passthrough_to_thread(function, /, *args, **kwargs):
    return function(*args, **kwargs)


def test_init_creates_collection_with_configured_dimension_and_payload_indexes(monkeypatch):
    client = FakeInitClient(existing=False)
    monkeypatch.setattr(dish_image_index, "_get_client", lambda: client)

    dish_image_index.init_dish_images_collection()

    assert client.calls == [
        f"create:{DISH_IMAGES_COLLECTION}",
        "index:class_slug",
        "index:source",
        "index:reviewed",
    ]
    assert client.vectors_config.size == IMAGE_VECTOR_SIZE
    assert client.vectors_config.distance == qmodels.Distance.COSINE


def test_init_is_idempotent_when_collection_exists(monkeypatch):
    client = FakeInitClient(existing=True)
    monkeypatch.setattr(dish_image_index, "_get_client", lambda: client)

    dish_image_index.init_dish_images_collection()
    dish_image_index.init_dish_images_collection(force=False)

    assert client.calls == []


def test_init_force_deletes_then_recreates_collection(monkeypatch):
    client = FakeInitClient(existing=True)
    monkeypatch.setattr(dish_image_index, "_get_client", lambda: client)

    dish_image_index.init_dish_images_collection(force=True)

    assert client.calls[:2] == [
        f"delete:{DISH_IMAGES_COLLECTION}",
        f"create:{DISH_IMAGES_COLLECTION}",
    ]


async def test_search_maps_payload_and_skips_malformed_points(monkeypatch):
    captured: dict[str, object] = {}

    class FakeClient:
        def query_points(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(points=[
                SimpleNamespace(
                    id="a",
                    payload={
                        "dish_name": "Phở bò",
                        "class_slug": "pho_bo",
                        "source": "seed",
                        "reviewed": True,
                    },
                    score=0.9512,
                ),
                SimpleNamespace(id="b", payload=None, score=0.9),
                SimpleNamespace(
                    id="c",
                    payload={"class_slug": "com_tam", "source": "seed"},
                    score=0.9,
                ),
                SimpleNamespace(
                    id="d",
                    payload={"dish_name": "", "class_slug": "x", "source": "seed"},
                    score=0.9,
                ),
                SimpleNamespace(
                    id="e",
                    payload={"dish_name": "Cơm tấm", "class_slug": 7, "source": "seed"},
                    score=0.9,
                ),
            ])

    monkeypatch.setattr(dish_image_index, "_get_client", lambda: FakeClient())
    monkeypatch.setattr(
        dish_image_index.asyncio, "to_thread", _passthrough_to_thread,
    )

    hits = await dish_image_index.search_dish_images(
        [0.0] * IMAGE_VECTOR_SIZE, limit=13,
    )

    assert hits == [
        DishImageHit(dish_name="Phở bò", class_slug="pho_bo", source="seed", score=0.9512)
    ]
    assert captured["collection_name"] == DISH_IMAGES_COLLECTION
    assert captured["limit"] == 13
    condition = captured["query_filter"].must[0]
    assert condition.key == "reviewed"
    assert condition.match.value is True


async def test_top_dish_candidates_groups_votes_sorts_and_truncates(monkeypatch):
    captured: dict[str, object] = {}

    async def fake_search(vector, limit):
        captured["limit"] = limit
        return [
            DishImageHit("Phở bò", "pho_bo", "seed", 0.95),
            DishImageHit("Cơm tấm", "com_tam", "seed", 0.97),
            DishImageHit("Phở bò", "pho_bo", "feedback", 0.90),
            DishImageHit("Bánh xèo", "banh_xeo", "seed", 0.80),
        ]

    monkeypatch.setattr(dish_image_index, "search_dish_images", fake_search)

    candidates = await dish_image_index.top_dish_candidates(
        [0.0] * IMAGE_VECTOR_SIZE, point_limit=12, dish_limit=2,
    )

    assert captured["limit"] == 12
    assert candidates == [
        DishCandidateScore(
            dish_name="Cơm tấm",
            best_score=0.97,
            votes=1,
            class_slug="com_tam",
        ),
        DishCandidateScore(
            dish_name="Phở bò",
            best_score=0.95,
            votes=2,
            class_slug="pho_bo",
        ),
    ]


async def test_top3_blend_prefers_consistent_hits_over_a_lucky_single_hit(monkeypatch):
    async def fake_search(_vector, *, limit):
        return [
            DishImageHit("Bánh căn", "banh_can", "seed", 0.96),
            DishImageHit("Bánh căn", "banh_can", "seed", 0.60),
            DishImageHit("Bánh căn", "banh_can", "feedback", 0.58),
            DishImageHit("Bánh khọt", "banh_khot", "seed", 0.93),
            DishImageHit("Bánh khọt", "banh_khot", "feedback", 0.92),
            DishImageHit("Bánh khọt", "banh_khot", "licensed", 0.91),
        ]

    monkeypatch.setattr(dish_image_index, "search_dish_images", fake_search)

    candidates = await dish_image_index.top_dish_candidates(
        [0.0] * IMAGE_VECTOR_SIZE,
        score_mode="top3_blend",
    )

    assert [candidate.dish_name for candidate in candidates] == [
        "Bánh khọt",
        "Bánh căn",
    ]
    assert candidates[0].votes == 3


async def test_upsert_publishes_reviewed_payload_and_waits(monkeypatch):
    captured: dict[str, object] = {}

    class FakeClient:
        def upsert(self, **kwargs):
            captured.update(kwargs)

    monkeypatch.setattr(dish_image_index, "_get_client", lambda: FakeClient())
    monkeypatch.setattr(
        dish_image_index.asyncio, "to_thread", _passthrough_to_thread,
    )
    entry = DishImageEntry(
        record_id="6ba7b811-9dad-11d1-80b4-00c04fd430c8",
        dish_name="Phở bò",
        class_slug="pho_bo",
        source="seed",
    )

    count = await dish_image_index.upsert_dish_image_vectors(
        [entry], [[0.1] * IMAGE_VECTOR_SIZE],
    )

    assert count == 1
    assert captured["wait"] is True
    point = captured["points"][0]
    assert str(point.id) == entry.record_id
    assert point.payload == {
        "dish_name": "Phở bò",
        "class_slug": "pho_bo",
        "source": "seed",
        "reviewed": True,
    }


async def test_upsert_rejects_mismatched_batch_lengths():
    entry = DishImageEntry(
        record_id="6ba7b811-9dad-11d1-80b4-00c04fd430c8",
        dish_name="Phở bò",
        class_slug="pho_bo",
        source="seed",
    )

    with pytest.raises(ValueError):
        await dish_image_index.upsert_dish_image_vectors([entry], [])


async def test_upsert_empty_batch_returns_zero_without_client(monkeypatch):
    def fail_client():
        raise AssertionError("Qdrant must not be touched for an empty batch")

    monkeypatch.setattr(dish_image_index, "_get_client", fail_client)

    assert await dish_image_index.upsert_dish_image_vectors([], []) == 0


async def test_count_by_dish_scrolls_every_page_payload_only(monkeypatch):
    def _point(dish_name):
        return SimpleNamespace(payload={"dish_name": dish_name})

    class FakeClient:
        def __init__(self) -> None:
            self.offsets: list[object] = []
            self.with_vectors: list[bool] = []

        def scroll(self, collection_name, limit, offset, with_payload, with_vectors):
            self.offsets.append(offset)
            self.with_vectors.append(with_vectors)
            if offset is None:
                return (
                    [_point("Phở bò"), _point("Phở bò"), SimpleNamespace(payload=None)],
                    "page-2",
                )
            return ([_point("Cơm tấm")], None)

    client = FakeClient()
    monkeypatch.setattr(dish_image_index, "_get_client", lambda: client)

    counts = await dish_image_index.count_by_dish()

    assert counts == {"Phở bò": 2, "Cơm tấm": 1}
    assert client.offsets == [None, "page-2"]
    assert client.with_vectors == [False, False]
