"""Deterministic catalog-quality rules must be safe before touching live data."""

import unicodedata

from backend.services.catalog_audit import audit_catalog_records, render_markdown_report
from backend.services.catalog_quality import (
    build_cleanup_plan,
    canonical_name_key,
    deduplicate_catalog_rows,
)


def _ingredient(**overrides: object) -> dict[str, object]:
    record: dict[str, object] = {
        "id": "ingredient-1",
        "ingredient_name": "Thịt ngan",
        "source": "vnfood",
        "calories_per_g": 4.0,
        "protein_per_g": 0.24,
        "fat_per_g": 0.34,
        "carbs_per_g": 0.0,
        "fiber_per_g": 0.0,
    }
    record.update(overrides)
    return record


def _dish(**overrides: object) -> dict[str, object]:
    record: dict[str, object] = {
        "id": "dish-1",
        "dish_name": "Phở trâu",
        "source": "vnmeal",
        "total_calories": 500.0,
        "total_protein_g": 35.0,
        "total_fat_g": 12.0,
        "total_carbs_g": 63.0,
        "total_fiber_g": 2.0,
        "typical_grams": 600.0,
        "typical_grams_source": "nutrition_heuristic_v1",
        "typical_grams_confidence": 0.5,
        "typical_grams_rule": "noodle_soup",
    }
    record.update(overrides)
    return record


def test_canonical_key_deduplicates_case_without_collapsing_vietnamese_tones() -> None:
    assert canonical_name_key("  Phở   Trâu ") == canonical_name_key("phở trâu")
    assert canonical_name_key(unicodedata.normalize("NFD", "Bún ốc nguội")) == (
        canonical_name_key("Bún ốc nguội")
    )
    assert canonical_name_key("Mực xào dưa") != canonical_name_key("Mực xào dứa")


def test_audit_reports_negative_nutrients_and_physical_serving_errors() -> None:
    report = audit_catalog_records(
        ingredients=[_ingredient(carbs_per_g=-0.0003)],
        dishes=[
            _dish(
                dish_name="Vịt om sấu",
                typical_grams=250.0,
                total_calories=2814.0,
                total_protein_g=200.0,
                total_fat_g=150.0,
                total_carbs_g=100.0,
            )
        ],
        candidates=[],
    )

    codes = {issue["code"] for issue in report["issues"]}
    assert "negative_nutrient" in codes
    assert "implausible_energy_density" in codes
    assert "implausible_macro_mass" in codes
    assert report["summary"]["errors"] == 3


def test_audit_separates_case_duplicates_from_accent_collisions() -> None:
    report = audit_catalog_records(
        ingredients=[],
        dishes=[
            _dish(id="dish-1", dish_name="Phở trâu"),
            _dish(id="dish-2", dish_name="Phở Trâu"),
            _dish(id="dish-3", dish_name="Mực xào dưa"),
            _dish(id="dish-4", dish_name="Mực xào dứa"),
        ],
        candidates=[],
    )

    issues_by_code = {
        code: [issue for issue in report["issues"] if issue["code"] == code]
        for code in {issue["code"] for issue in report["issues"]}
    }
    assert len(issues_by_code["case_duplicate"]) == 1
    assert issues_by_code["case_duplicate"][0]["severity"] == "error"
    assert len(issues_by_code["accent_insensitive_collision"]) == 1
    assert issues_by_code["accent_insensitive_collision"][0]["severity"] == "warning"


def test_cleanup_plan_is_conservative_and_recoverable() -> None:
    plan = build_cleanup_plan(
        ingredients=[
            _ingredient(id="tiny-negative", carbs_per_g=-0.0003),
            _ingredient(id="large-negative", carbs_per_g=-0.2),
        ],
        dishes=[
            _dish(
                id="bad-serving",
                typical_grams=100.0,
                total_calories=1200.0,
                total_protein_g=90.0,
                total_fat_g=80.0,
                total_carbs_g=70.0,
            )
        ],
        candidates=[],
    )

    actions = {(action["action"], action["record_id"]): action for action in plan}
    clamp = actions[("clamp_tiny_negative", "tiny-negative")]
    quarantine = actions[("quarantine_serving_weight", "bad-serving")]
    assert clamp["changes"] == {"carbs_per_g": 0.0}
    assert ("clamp_tiny_negative", "large-negative") not in actions
    assert quarantine["changes"]["typical_grams"] is None
    assert quarantine["before"]["typical_grams"] == 100.0


def test_cleanup_plan_keeps_best_case_duplicate_and_archives_the_other() -> None:
    plan = build_cleanup_plan(
        ingredients=[],
        dishes=[
            _dish(
                id="inconsistent",
                dish_name="Nem lụi",
                total_calories=500.0,
                total_protein_g=10.0,
                total_fat_g=5.0,
                total_carbs_g=10.0,
            ),
            _dish(
                id="consistent",
                dish_name="Nem Lụi",
                total_calories=165.0,
                total_protein_g=20.0,
                total_fat_g=5.0,
                total_carbs_g=10.0,
            ),
        ],
        candidates=[],
    )

    deletion = next(action for action in plan if action["action"] == "archive_duplicate")
    assert deletion["record_id"] == "inconsistent"
    assert deletion["survivor_id"] == "consistent"
    assert deletion["before"]["dish_name"] == "Nem lụi"


def test_source_deduplication_keeps_tones_and_selects_the_best_record() -> None:
    rows = [
        _dish(
            id="inconsistent",
            dish_name="Nem lụi",
            total_calories=500.0,
            total_protein_g=10.0,
            total_fat_g=5.0,
            total_carbs_g=10.0,
        ),
        _dish(
            id="consistent",
            dish_name="Nem Lụi",
            total_calories=165.0,
            total_protein_g=20.0,
            total_fat_g=5.0,
            total_carbs_g=10.0,
        ),
        _dish(id="pickle", dish_name="Mực xào dưa"),
        _dish(id="pineapple", dish_name="Mực xào dứa"),
    ]

    deduplicated = deduplicate_catalog_rows(rows, entity_type="dish")

    assert {row["id"] for row in deduplicated} == {
        "consistent",
        "pickle",
        "pineapple",
    }


def test_cleanup_plan_rejects_legacy_empty_pending_candidates() -> None:
    plan = build_cleanup_plan(
        ingredients=[],
        dishes=[],
        candidates=[
            {
                "id": "candidate-1",
                "dish_name": "Nước chấm",
                "status": "pending",
                "typical_grams": 50.0,
                "total_calories": 0.0,
            }
        ],
    )

    action = next(action for action in plan if action["action"] == "reject_invalid_candidate")
    assert action["record_id"] == "candidate-1"
    assert action["changes"] == {"status": "rejected"}


def test_markdown_report_contains_summary_and_actionable_issue() -> None:
    report = audit_catalog_records(
        ingredients=[_ingredient(carbs_per_g=-0.0003)],
        dishes=[],
        candidates=[],
    )

    markdown = render_markdown_report(report)

    assert "# FoodAI Catalog Quality Audit" in markdown
    assert "Errors: **1**" in markdown
    assert "negative_nutrient" in markdown


def test_audit_names_an_unresolved_nutrition_conflict() -> None:
    report = audit_catalog_records(
        ingredients=[],
        dishes=[_dish(
            typical_grams=None,
            typical_grams_source="nutrition_conflict",
            typical_grams_rule="energy_macro_mismatch",
        )],
        candidates=[],
    )

    issue = next(issue for issue in report["issues"] if "conflict" in issue["code"])
    assert issue["code"] == "unresolved_nutrition_conflict"
    assert issue["severity"] == "warning"
