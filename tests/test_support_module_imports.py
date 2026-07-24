"""Support scripts must stay importable after catalog refactors."""

import importlib

import pytest


@pytest.mark.parametrize(
    "module_name",
    [
        "scripts.seed_nutrition",
        "scripts.reindex_qdrant",
        "scripts.seed_conversion_rates",
        "scripts.create_tables",
        "scripts.recreate_vn_dishes",
        "scripts.review_dish_candidates",
        "scripts.rebuild_dish_servings",
        "ml.evaluation.dataset",
        "ml.evaluation.rag_eval",
    ],
)
def test_support_module_imports(module_name: str) -> None:
    importlib.import_module(module_name)
