"""The active-learning report must prioritize reviewed human disagreement."""

from types import SimpleNamespace


def test_summary_separates_event_volume_from_unreviewed_label_disagreement() -> None:
    from scripts.report_active_learning import summarize_rows

    rows = [
        SimpleNamespace(
            source="local_consensus",
            final_dish_name="Phở bò",
            feedback_slug="pho_bo",
            feedback_status="pending",
        ),
        SimpleNamespace(
            source="local_consensus",
            final_dish_name="Phở bò",
            feedback_slug="bun_bo_hue",
            feedback_status="pending",
        ),
        SimpleNamespace(
            source="vision",
            final_dish_name="Cao lầu",
            feedback_slug=None,
            feedback_status=None,
        ),
    ]

    summary = summarize_rows(rows)

    assert summary["by_source"]["local_consensus"] == {
        "events": 2,
        "linked_feedback": 2,
        "label_disagreements_pending_review": 1,
    }
    assert summary["by_source"]["vision"] == {
        "events": 1,
        "linked_feedback": 0,
        "label_disagreements_pending_review": 0,
    }
    assert summary["review_queue"] == [
        {
            "source": "local_consensus",
            "predicted_dish": "Phở bò",
            "human_label_slug": "bun_bo_hue",
            "feedback_status": "pending",
        }
    ]
