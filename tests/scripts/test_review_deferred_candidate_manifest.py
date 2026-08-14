"""Contracts for the second-pass visual review of noisy candidates."""


def _base_manifest() -> dict:
    return {
        "schema_version": 1,
        "demo_only": True,
        "review_method": "codex_visual_review",
        "reviewed_at": "2026-08-06",
        "review_status": "reviewed",
        "provenance_status": "unverified_demo",
        "approved_paths": [
            "pho_bo/approved.jpg",
            "banh_can/approved.jpg",
        ],
        "reviewed_paths": [
            "pho_bo/approved.jpg",
            "banh_can/approved.jpg",
        ],
        "deferred_paths": [
            "pho_bo/clear.jpg",
            "banh_can/noisy.jpg",
        ],
        "summary": {},
        "visual_review_notes": {},
        "provenance_records": [],
    }


def test_second_pass_promotes_only_explicitly_clear_paths() -> None:
    from scripts.review_deferred_candidate_manifest import build_reviewed_manifest

    result = build_reviewed_manifest(
        _base_manifest(),
        promoted_paths={"pho_bo/clear.jpg"},
        reviewed_at="2026-08-06",
    )

    assert result["approved_paths"] == [
        "banh_can/approved.jpg",
        "pho_bo/approved.jpg",
        "pho_bo/clear.jpg",
    ]
    assert result["deferred_paths"] == ["banh_can/noisy.jpg"]
    assert result["reviewed_deferred_paths"] == [
        "banh_can/noisy.jpg",
        "pho_bo/clear.jpg",
    ]
    assert result["summary"]["approved_images"] == 3
    assert result["summary"]["deferred_images"] == 1


def test_second_pass_rejects_path_not_in_original_deferred_queue() -> None:
    import pytest

    from scripts.review_deferred_candidate_manifest import build_reviewed_manifest

    with pytest.raises(ValueError, match="deferred queue"):
        build_reviewed_manifest(
            _base_manifest(),
            promoted_paths={"pho_bo/missing.jpg"},
            reviewed_at="2026-08-06",
        )
