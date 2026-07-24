"""Unit tests cho lexical guard trước khi chấp nhận Qdrant candidate."""

from types import SimpleNamespace

from backend.services import dishes, qdrant_dishes
from backend.services.dishes import _is_semantic_candidate_compatible


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
    hits = [
        {"dish_name": "Bún chả"},
        {"dish_name": "Xôi chả"},
        {"dish_name": "Cơm gà"},
        {"dish_name": "Bánh cuốn trứng"},
        {"dish_name": "Cơm tấm sườn bì chả trứng ốp la"},
    ]

    async def fake_search(_query, limit):
        return hits[:limit]

    async def fake_exact(_session, name):
        if name == "Cơm tấm sườn bì chả trứng ốp la":
            return SimpleNamespace(dish_name=name)
        return None

    monkeypatch.setattr(qdrant_dishes, "search_dish", fake_search)
    monkeypatch.setattr(dishes, "_lookup_institute_exact", fake_exact)

    result = await dishes._lookup_institute_by_qdrant(
        object(), "Cơm bì chả trứng"
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
