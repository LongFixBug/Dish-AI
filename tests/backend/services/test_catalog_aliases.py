"""Tests for explicitly reviewed dish-to-catalog aliases."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.services import catalog_aliases, dishes


def test_load_catalog_aliases_ignores_unreviewed_rows(tmp_path: Path) -> None:
    path = tmp_path / "aliases.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "aliases": [
                    {
                        "query": "Bánh chưng",
                        "canonical_name": "Bánh chưng cỡ vừa",
                        "status": "reviewed",
                    },
                    {
                        "query": "Bánh canh",
                        "canonical_name": "Bánh canh ghẹ",
                        "status": "pending",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    aliases = catalog_aliases.load_catalog_aliases(path)

    assert aliases == {"banh chung": "Bánh chưng cỡ vừa"}


def test_reviewed_alias_requires_exact_query_and_target() -> None:
    assert catalog_aliases.get_reviewed_catalog_alias("Bánh chưng") == (
        "Bánh chưng cỡ vừa"
    )
    assert catalog_aliases.is_reviewed_catalog_alias(
        "Bánh chưng", "Bánh chưng cỡ vừa"
    )
    assert not catalog_aliases.is_reviewed_catalog_alias(
        "Bánh canh", "Bánh canh ghẹ"
    )
    assert catalog_aliases.get_reviewed_catalog_alias("Mì Quảng") == "Mỳ Quảng"


@pytest.mark.asyncio
async def test_lookup_dish_resolves_reviewed_alias_before_semantic_search(monkeypatch) -> None:
    calls: list[str] = []

    async def exact(_session, name: str):
        calls.append(name)
        if name == "Bánh chưng cỡ vừa":
            return SimpleNamespace(dish_name=name)
        return None

    async def semantic_should_not_run(*_args, **_kwargs):
        raise AssertionError("reviewed alias must be resolved before Qdrant")

    monkeypatch.setattr(dishes, "_lookup_institute_exact", exact)
    monkeypatch.setattr(dishes, "_lookup_institute_by_vector", semantic_should_not_run)

    result = await dishes.lookup_dish(object(), "Bánh chưng")

    assert result.dish_name == "Bánh chưng cỡ vừa"
    assert calls == ["Bánh chưng", "Bánh chưng cỡ vừa"]
