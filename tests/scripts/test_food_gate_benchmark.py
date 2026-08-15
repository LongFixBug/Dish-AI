"""Unit contracts for Food Gate benchmark metrics and crawl plan."""


def test_summarize_predictions_reports_block_recall_false_blocks_and_latency() -> None:
    from scripts.evaluate_food_gate_benchmark import summarize_predictions

    summary = summarize_predictions(
        [
            {"expected": "food", "non_food_score": 0.10, "latency_ms": 10.0},
            {"expected": "food", "non_food_score": 0.95, "latency_ms": 20.0},
            {"expected": "non_food", "non_food_score": 0.91, "latency_ms": 30.0},
            {"expected": "non_food", "non_food_score": 0.20, "latency_ms": 40.0},
        ],
        block_threshold=0.90,
    )

    assert summary == {
        "n_total": 4,
        "n_food": 2,
        "n_non_food": 2,
        "accuracy": 0.5,
        "food_false_block_rate": 0.5,
        "non_food_block_recall": 0.5,
        "p50_latency_ms": 20.0,
        "p95_latency_ms": 40.0,
    }


def test_food_gate_query_plan_has_both_labels_and_diverse_queries() -> None:
    from scripts.fill_food_gate_benchmark import QUERY_PLAN

    assert set(QUERY_PLAN) == {"food", "non_food"}
    assert len(QUERY_PLAN["food"]) >= 8
    assert len(QUERY_PLAN["non_food"]) >= 8
    assert set(QUERY_PLAN["food"]).isdisjoint(QUERY_PLAN["non_food"])
