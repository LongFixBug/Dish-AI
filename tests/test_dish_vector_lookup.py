"""Dish and ingredient semantic lookup must use Qdrant as the only vector store."""

from types import SimpleNamespace

from backend.db.models import VnDish, VnIngredient
from backend.services import dishes
from backend.services.vector_catalog import CatalogHit, CatalogType


def test_postgres_catalog_models_do_not_store_embeddings() -> None:
    assert "embedding" not in VnDish.__table__.c
    assert "embedding" not in VnIngredient.__table__.c


async def test_dish_lookup_resolves_qdrant_uuid_through_postgres(monkeypatch) -> None:
    candidates = [
        SimpleNamespace(id="stale-id", dish_name="Bún chả"),
        SimpleNamespace(id="dish-id", dish_name="Cơm tấm sườn bì chả"),
    ]

    class FakeSession:
        async def execute(self, _statement):
            return SimpleNamespace(
                scalars=lambda: SimpleNamespace(all=lambda: candidates)
            )

    async def fake_search(query, catalog_type, limit):
        assert query == "Cơm bì chả"
        assert catalog_type == CatalogType.DISH
        assert limit == dishes.QDRANT_CANDIDATE_LIMIT
        return [
            CatalogHit("missing-id", "Cơm gà", 0.94),
            CatalogHit("dish-id", "Cơm tấm sườn bì chả", 0.91),
        ]

    monkeypatch.setattr(dishes, "search_catalog", fake_search)

    result = await dishes._lookup_institute_by_vector(
        FakeSession(), "Cơm bì chả"
    )

    assert result.dish_name == "Cơm tấm sườn bì chả"


async def test_dish_lookup_prefers_more_specific_token_overlap(monkeypatch) -> None:
    candidates = [
        SimpleNamespace(id="short-id", dish_name="Bún bò nhừ"),
        SimpleNamespace(id="hue-id", dish_name="Bún bò giò heo (Huế)"),
    ]

    class FakeSession:
        async def execute(self, _statement):
            return SimpleNamespace(
                scalars=lambda: SimpleNamespace(all=lambda: candidates)
            )

    async def fake_search(query, catalog_type, limit):
        return [
            CatalogHit("short-id", "Bún bò nhừ", 0.90),
            CatalogHit("hue-id", "Bún bò giò heo (Huế)", 0.88),
        ]

    monkeypatch.setattr(dishes, "search_catalog", fake_search)

    result = await dishes._lookup_institute_by_vector(
        FakeSession(), "Bún bò Huế"
    )

    assert result.dish_name == "Bún bò giò heo (Huế)"


async def test_ingredient_lookup_resolves_qdrant_uuid_through_postgres(monkeypatch) -> None:
    ingredient = SimpleNamespace(id="ingredient-id", ingredient_name="Sữa bò")

    class FakeSession:
        async def execute(self, _statement):
            return SimpleNamespace(
                scalars=lambda: SimpleNamespace(all=lambda: [ingredient])
            )

    async def fake_search(query, catalog_type, limit):
        assert query == "milk"
        assert catalog_type == CatalogType.INGREDIENT
        assert limit == 5
        return [CatalogHit("ingredient-id", "Sữa bò", 0.88)]

    monkeypatch.setattr(dishes, "search_catalog", fake_search)

    result = await dishes._lookup_ingredient_vector(FakeSession(), "milk")

    assert result is ingredient
