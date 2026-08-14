"""Offline fusion evaluation must enforce evidence per local decision branch."""

from pathlib import Path

from ml.evaluation.fusion_eval import (
    FusionObservation,
    build_report,
    build_dish_slug_index,
    evaluate_rollout_gate,
    decide_observation,
    recommend_thresholds,
    resolve_runtime_catalog_identity,
    slug_from_cv_prediction,
    summarize_actions,
    sweep_thresholds,
    fusion_cv_thresholds,
)
from ml.evaluation.recognition_eval import ClassTruth, normalize_name


def _observation(
    *,
    truth: str = "pho_bo",
    cv_slug: str | None = "pho_bo",
    cv_confidence: float = 0.996,
    album_slug: str | None = "pho_bo",
    album_score: float = 0.80,
    album_margin: float = 0.05,
) -> FusionObservation:
    return FusionObservation(
        truth_slug=truth,
        cv_slug=cv_slug,
        cv_confidence=cv_confidence,
        album_slug=album_slug,
        album_score=album_score,
        album_margin=album_margin,
    )


def test_matching_strong_sources_are_counted_as_correct_consensus() -> None:
    result = decide_observation(
        _observation(),
        cv_threshold=0.996,
        album_threshold=0.73,
        album_margin=0.04,
    )

    assert result.action == "local_consensus"
    assert result.correct is True


def test_fusion_tuner_can_measure_thresholds_below_serving_gate() -> None:
    values = fusion_cv_thresholds(0.90, 0.902)

    assert values == (0.9, 0.901, 0.902)


def test_fusion_report_records_album_score_mode() -> None:
    report = build_report(
        [_observation()],
        [decide_observation(_observation(), 0.996, 0.73, 0.04)],
        images_dir=Path("data/images/golden"),
        checkpoint_path=Path("checkpoints/best_model.pth"),
        cv_threshold=0.996,
        album_threshold=0.73,
        album_margin=0.04,
        album_score_mode="top3_blend",
        cv_model_serving_threshold=0.996,
        cv_solo_threshold=None,
        album_solo_enabled=False,
        min_precision=0.98,
        min_accepted=1,
        required_actions=("local_consensus",),
        timestamp="20260806_150000",
    )

    assert report["thresholds"]["album_score_mode"] == "top3_blend"


def test_strong_disagreement_defers_to_vision_instead_of_auto_answering() -> None:
    result = decide_observation(
        _observation(album_slug="bun_bo_hue"),
        cv_threshold=0.996,
        album_threshold=0.73,
        album_margin=0.04,
    )

    assert result.action == "vision"
    assert result.correct is None


def test_alias_only_album_label_is_not_treated_as_catalog_evidence() -> None:
    """Offline aliases must not bypass production's PostgreSQL refinement gate."""
    result = decide_observation(
        FusionObservation(
            truth_slug="pho_bo",
            cv_slug="pho_bo",
            cv_confidence=0.999,
            album_slug="pho_bo",
            album_score=0.90,
            album_margin=0.10,
            truth_canonical_id="dish-pho-bo",
            cv_canonical_id="dish-pho-bo",
            # The runtime does not allow generic "Phở" to claim "Phở bò".
            album_canonical_id=None,
        ),
        cv_threshold=0.998,
        album_threshold=0.73,
        album_margin=0.05,
        cv_solo_threshold=None,
    )

    assert result.action == "vision"


async def test_runtime_catalog_identity_requires_same_refinement_as_api() -> None:
    class Row:
        id = "dish-pho-bo"
        dish_name = "Phở bò"

    async def lookup(_session, _name):
        return Row()

    cache: dict[str, str | None] = {}

    resolved = await resolve_runtime_catalog_identity(
        object(), "Phở bò", cache, lookup=lookup
    )
    generic = await resolve_runtime_catalog_identity(
        object(), "Phở", cache, lookup=lookup
    )

    assert resolved == "dish-pho-bo"
    assert generic is None


def test_disabled_cv_solo_uses_strong_cv_only_to_guard_album_or_consensus() -> None:
    result = decide_observation(
        _observation(album_slug=None, album_score=0.0, album_margin=0.0),
        cv_threshold=0.996,
        album_threshold=0.73,
        album_margin=0.04,
        cv_solo_threshold=None,
    )

    assert result.action == "vision"


def test_disabled_album_solo_defers_a_single_album_match_to_vision() -> None:
    result = decide_observation(
        _observation(
            cv_slug=None,
            cv_confidence=0.0,
            album_score=0.90,
            album_margin=0.10,
        ),
        cv_threshold=0.999,
        album_threshold=0.74,
        album_margin=0.04,
        cv_solo_threshold=None,
        album_solo_enabled=False,
    )

    assert result.action == "vision"


def test_summary_separates_auto_precision_from_vision_deferrals() -> None:
    results = [
        decide_observation(
            _observation(), 0.996, 0.73, 0.04
        ),
        decide_observation(
            _observation(
                cv_slug=None,
                cv_confidence=0.2,
                album_slug="bun_bo_hue",
            ),
            0.996,
            0.73,
            0.04,
        ),
        decide_observation(
            _observation(
                album_slug="bun_bo_hue",
            ),
            0.996,
            0.73,
            0.04,
        ),
    ]

    summary = summarize_actions(results)

    assert summary["local_consensus"] == {
        "accepted": 1,
        "correct": 1,
        "precision": 1.0,
    }
    assert summary["vision"]["deferred"] == 2


def test_rollout_gate_requires_minimum_evidence_for_consensus() -> None:
    summary = {
        "local_consensus": {"accepted": 30, "correct": 30, "precision": 1.0},
        "vision": {"deferred": 10},
    }

    gate = evaluate_rollout_gate(
        summary,
        min_precision=0.98,
        min_accepted=30,
    )

    assert gate == {"passed": True, "failures": {}}


def test_rollout_gate_has_no_solo_branches() -> None:
    summary = {
        "local_consensus": {"accepted": 30, "correct": 30, "precision": 1.0},
        "vision": {"deferred": 10},
    }

    gate = evaluate_rollout_gate(
        summary,
        min_precision=0.98,
        min_accepted=30,
        required_actions=("local_consensus",),
    )

    assert gate == {"passed": True, "failures": {}}


def test_dish_name_mapping_prefers_exact_golden_label_over_alias() -> None:
    truths = {
        "banh_mi": ClassTruth(
            slug="banh_mi",
            display_name="Bánh mì",
            acceptable=frozenset({normalize_name("Bánh mì")}),
        ),
        "banh_mi_kep_thit": ClassTruth(
            slug="banh_mi_kep_thit",
            display_name="Bánh mì kẹp thịt",
            acceptable=frozenset(
                {normalize_name("Bánh mì"), normalize_name("Bánh mì kẹp thịt")}
            ),
        ),
    }

    index = build_dish_slug_index(truths)

    assert index[normalize_name("Bánh mì")] == "banh_mi"
    assert index[normalize_name("Bánh mì kẹp thịt")] == "banh_mi_kep_thit"


def test_cv_prediction_name_resolves_against_checkpoint_slugs() -> None:
    assert slug_from_cv_prediction(
        "Banh Mi Kep Thit", ["banh_mi_kep_thit", "pho_bo"]
    ) == "banh_mi_kep_thit"


def test_fusion_tuner_raises_thresholds_to_remove_bad_solo_evidence() -> None:
    observations = [
        _observation(cv_confidence=0.999, album_score=0.90),
        _observation(
            cv_confidence=0.999,
            album_slug=None,
            album_score=0.0,
            album_margin=0.0,
        ),
        _observation(
            cv_confidence=0.996,
            album_slug=None,
            album_score=0.0,
            album_margin=0.0,
            truth="bun_bo_hue",
        ),
        _observation(
            cv_slug=None,
            cv_confidence=0.1,
            album_score=0.90,
        ),
        _observation(
            cv_slug=None,
            cv_confidence=0.1,
            album_score=0.73,
            truth="bun_bo_hue",
        ),
    ]

    results = sweep_thresholds(
        observations,
        cv_thresholds=[0.996, 0.998],
        album_thresholds=[0.73, 0.80],
        album_margins=[0.04],
        min_precision=0.98,
        min_accepted=1,
    )
    recommended = recommend_thresholds(results)

    assert recommended is not None
    assert recommended.cv_threshold == 0.998
    assert recommended.album_threshold == 0.80
    assert recommended.gate["passed"] is True
