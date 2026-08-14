from types import SimpleNamespace


def test_summarize_rows_groups_fallback_reasons_and_cv_confusions() -> None:
    from scripts.report_recognition_telemetry import summarize_rows

    rows = [
        SimpleNamespace(
            source="vision",
            final_dish_name="Phở bò",
            cv_top1_name="Bún bò Huế",
            cv_top2_name="Phở bò",
            cv_top2_confidence=0.21,
            fusion_reason="cv_below_serving_threshold",
        ),
        SimpleNamespace(
            source="vision",
            final_dish_name="Hủ tiếu",
            cv_top1_name="Phở bò",
            cv_top2_name="Hủ tiếu",
            cv_top2_confidence=0.18,
            fusion_reason="album_low_margin",
        ),
        SimpleNamespace(
            source="local_consensus",
            final_dish_name="Cơm tấm",
            cv_top1_name="Cơm tấm",
            cv_top2_name="Bún thịt nướng",
            cv_top2_confidence=0.01,
            fusion_reason="same_uuid",
        ),
    ]

    summary = summarize_rows(rows)

    assert summary["events"] == 3
    assert summary["by_source"] == {
        "local_consensus": 1,
        "vision": 2,
    }
    assert summary["by_fusion_reason"] == {
        "album_low_margin": 1,
        "cv_below_serving_threshold": 1,
        "same_uuid": 1,
    }
    assert summary["cv_confusions"] == [
        {"top1": "Bún bò Huế", "top2": "Phở bò", "count": 1},
        {"top1": "Cơm tấm", "top2": "Bún thịt nướng", "count": 1},
        {"top1": "Phở bò", "top2": "Hủ tiếu", "count": 1},
    ]


def test_summarize_rows_ignores_missing_telemetry_without_crashing() -> None:
    from scripts.report_recognition_telemetry import summarize_rows

    summary = summarize_rows(
        [
            SimpleNamespace(
                source="vision",
                final_dish_name="Phở bò",
                cv_top1_name=None,
                cv_top2_name=None,
                cv_top2_confidence=None,
                fusion_reason=None,
            )
        ]
    )

    assert summary["events"] == 1
    assert summary["by_fusion_reason"] == {"unknown": 1}
    assert summary["cv_confusions"] == []
