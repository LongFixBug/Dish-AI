"""Unit tests for lexical guards before accepting Qdrant dish candidates."""

from types import SimpleNamespace

from backend.services import dishes
from backend.services.dishes import _is_semantic_candidate_compatible
from backend.services.vector_catalog import CatalogHit, CatalogType


def test_rejects_candidate_with_different_main_dish_family() -> None:
    assert not _is_semantic_candidate_compatible(
        "Cơm sườn bì chả", "Bún chả"
    )


def test_accepts_close_variant_with_shared_menu_tokens() -> None:
    assert _is_semantic_candidate_compatible(
        "Bánh mì kẹp thịt", "Bánh mì thịt"
    )


def test_rejects_same_family_with_only_generic_token_shared() -> None:
    assert not _is_semantic_candidate_compatible("Phở bò", "Phở gà")


async def test_lookup_scans_past_incompatible_top_results(monkeypatch) -> None:
    candidates = [SimpleNamespace(
        id="target-id",
        dish_name="Cơm tấm sườn bì chả trứng ốp la",
    )]

    class FakeSession:
        async def execute(self, _statement):
            return SimpleNamespace(
                scalars=lambda: SimpleNamespace(all=lambda: candidates)
            )

    async def fake_search(_query, catalog_type, limit):
        assert catalog_type == CatalogType.DISH
        assert limit == dishes.QDRANT_CANDIDATE_LIMIT
        return [
            CatalogHit("1", "Bún chả", 0.97),
            CatalogHit("2", "Xôi chả", 0.96),
            CatalogHit("3", "Cơm gà", 0.95),
            CatalogHit("4", "Bánh cuốn trứng", 0.94),
            CatalogHit(
                "target-id",
                "Cơm tấm sườn bì chả trứng ốp la",
                0.91,
            ),
        ]

    monkeypatch.setattr(dishes, "search_catalog", fake_search)

    result = await dishes._lookup_institute_by_vector(
        FakeSession(), "Cơm bì chả trứng"
    )

    assert result is not None
    assert result.dish_name == "Cơm tấm sườn bì chả trứng ốp la"


async def test_side_ingredient_lookup_never_uses_substring_match(monkeypatch) -> None:
    async def fake_exact(_session, name):
        assert name == "Bì"
        return None

    async def substring_lookup_must_not_run(_session, _name):
        raise AssertionError("Tên ngắn 'Bì' không được match '%bi%' vào 'Rong biển'")

    monkeypatch.setattr(dishes, "_lookup_ingredient_exact", fake_exact, raising=False)
    monkeypatch.setattr(dishes, "_lookup_ingredient_ilike", substring_lookup_must_not_run)

    assert await dishes.lookup_ingredient_text(object(), "Bì") is None
