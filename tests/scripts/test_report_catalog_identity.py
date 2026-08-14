"""Unit tests for the closed-set catalog identity readiness report."""

import json
from pathlib import Path

import pytest

from scripts.report_catalog_identity import (
    CatalogResolution,
    classify_resolution,
    load_target_classes,
    summarize_resolutions,
)


def test_load_target_classes_supports_efficientnet_allow_list(tmp_path: Path) -> None:
    classes_path = tmp_path / "classes.json"
    classes_path.write_text(
        json.dumps({"classes": ["pho_bo", "banh_xeo"]}),
        encoding="utf-8",
    )
    mapping_path = tmp_path / "names.json"
    mapping_path.write_text(
        json.dumps({"pho_bo": "Phở bò", "banh_xeo": "Bánh xèo"}),
        encoding="utf-8",
    )

    assert load_target_classes(classes_path, mapping_path) == {
        "banh_xeo": "Bánh xèo",
        "pho_bo": "Phở bò",
    }


def test_load_target_classes_rejects_missing_display_name(tmp_path: Path) -> None:
    classes_path = tmp_path / "classes.json"
    classes_path.write_text(json.dumps({"classes": ["pho_bo"]}), encoding="utf-8")
    mapping_path = tmp_path / "names.json"
    mapping_path.write_text(json.dumps({}), encoding="utf-8")

    with pytest.raises(ValueError, match="Thiếu tên hiển thị"):
        load_target_classes(classes_path, mapping_path)


def test_classify_resolution_separates_exact_variant_and_missing() -> None:
    exact = classify_resolution("Phở bò", "Phở bò", "dish-id", exact=True)
    variant = classify_resolution(
        "Phở bò", "Phở bò chín", "variant-id", exact=False
    )
    missing = classify_resolution("Mì Quảng", None, None, exact=False)

    assert exact.status == "exact"
    assert variant.status == "semantic_variant_pending_review"
    assert missing.status == "missing"
    assert variant.requires_human_review is True
    assert missing.catalog_id is None


def test_classify_resolution_marks_reviewed_alias_as_operationally_safe() -> None:
    alias = classify_resolution(
        "Bánh chưng",
        "Bánh chưng cỡ vừa",
        "dish-id",
        exact=False,
        alias_reviewed=True,
    )

    assert alias.status == "curated_alias"
    assert alias.requires_human_review is False


def test_classify_resolution_rejects_incompatible_semantic_name() -> None:
    result = classify_resolution(
        "Bánh mì kẹp thịt", "Bánh cuốn thịt", "wrong-id", exact=False
    )

    assert result.status == "semantic_incompatible"
    assert result.requires_human_review is True


def test_summarize_resolutions_only_ready_when_every_row_is_exact() -> None:
    resolutions = [
        CatalogResolution(
            slug="pho_bo",
            requested_name="Phở bò",
            status="exact",
            catalog_name="Phở bò",
            catalog_id="1",
            source="vnmeal",
            typical_grams=625.0,
            typical_grams_source="vision_reviewed",
            typical_grams_confidence=0.9,
            typical_grams_rule="test",
            requires_human_review=False,
        ),
        CatalogResolution(
            slug="mi_quang",
            requested_name="Mì Quảng",
            status="missing",
            catalog_name=None,
            catalog_id=None,
            source=None,
            typical_grams=None,
            typical_grams_source=None,
            typical_grams_confidence=None,
            typical_grams_rule=None,
            requires_human_review=True,
        ),
    ]

    summary = summarize_resolutions(resolutions)

    assert summary == {
        "total": 2,
        "exact": 1,
        "curated_alias": 0,
        "semantic_variant_pending_review": 0,
        "semantic_incompatible": 0,
        "missing": 1,
        "requires_human_review": 1,
        "ready": False,
    }
