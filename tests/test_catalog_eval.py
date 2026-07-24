"""Deterministic portfolio metrics must remain reproducible without an LLM judge."""

from ml.evaluation.catalog_eval import aggregate_results, render_markdown


def test_aggregate_results_reports_accuracy_and_coverage() -> None:
    summary = aggregate_results([
        {"query": "phở", "matched": True, "expected": True},
        {"query": "bún", "matched": False, "expected": True},
        {"query": "unknown", "matched": False, "expected": False},
    ])

    assert summary == {
        "total": 3,
        "expected_matches": 2,
        "correct_matches": 1,
        "accuracy": 0.667,
        "coverage": 0.5,
    }


def test_render_markdown_includes_reproducible_metrics() -> None:
    report = {
        "generated_at": "2026-07-24T00:00:00+00:00",
        "suite": "catalog_lookup",
        "summary": {
            "total": 2,
            "expected_matches": 1,
            "correct_matches": 1,
            "accuracy": 1.0,
            "coverage": 1.0,
        },
        "results": [],
    }

    markdown = render_markdown(report)

    assert "Accuracy: **100.0%**" in markdown
    assert "Coverage: **100.0%**" in markdown
