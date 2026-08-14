"""Offline contracts for the new reference-candidate crawler."""

import json

import pytest


def test_select_classes_returns_all_requested_product_classes() -> None:
    from scripts.crawl_candidate_reference_classes import (
        REQUESTED_CLASS_SLUGS,
        select_classes,
    )

    selected = select_classes(None)

    assert tuple(selected) == tuple(sorted(REQUESTED_CLASS_SLUGS))
    assert "sua_milo" in selected
    assert "trung_chien" in selected


def test_default_candidate_target_is_large_enough_for_reference_album() -> None:
    from scripts.crawl_candidate_reference_classes import DEFAULT_PER_CLASS

    assert DEFAULT_PER_CLASS == 50


def test_select_classes_rejects_unknown_slug() -> None:
    from scripts.crawl_candidate_reference_classes import select_classes

    with pytest.raises(ValueError, match="Class không hỗ trợ: unknown"):
        select_classes("unknown")


def test_load_target_dishes_reads_display_names(tmp_path) -> None:
    from scripts.crawl_candidate_reference_classes import load_target_dishes

    mapping = tmp_path / "class_names.json"
    mapping.write_text(
        json.dumps({"sua_milo": "Sữa Milo", "pizza": "Pizza"}),
        encoding="utf-8",
    )

    assert load_target_dishes(mapping, ("sua_milo", "pizza")) == {
        "pizza": "Pizza",
        "sua_milo": "Sữa Milo",
    }
