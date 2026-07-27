"""Unit tests cho phần pure của ml.evaluation.tune_cascade.

Sweep chạy trên observation tổng hợp — không cần Qdrant hay sidecar.
"""

import json
from types import SimpleNamespace

import pytest

from ml.evaluation.recognition_eval import ClassTruth, normalize_name
from ml.evaluation.tune_cascade import (
    T1_VALUES,
    T2_VALUES,
    CascadeObservation,
    ThresholdResult,
    build_observation,
    build_report,
    evaluate_pair,
    pareto_frontier,
    recommend,
    sweep_thresholds,
)


def _truth(slug: str, display: str, aliases: tuple[str, ...] = ()) -> ClassTruth:
    return ClassTruth(
        slug=slug,
        display_name=display,
        acceptable=frozenset(
            normalize_name(n) for n in (display, *aliases)
        ),
    )


def _candidate(name: str, score: float) -> SimpleNamespace:
    """Giả DishCandidateScore (chỉ cần .dish_name và .best_score)."""
    return SimpleNamespace(dish_name=name, best_score=score, votes=1)


def _obs(
    score: float, margin: float, correct: bool, name: str = "Phở bò"
) -> CascadeObservation:
    return CascadeObservation(
        truth_slug="pho_bo", top1_name=name,
        top1_score=score, margin=margin, correct=correct,
    )


# ─── build_observation ───────────────────────────────────────────────────────


def test_build_observation_computes_margin_and_accent_insensitive_match():
    truth = _truth("pho_bo", "Phở bò")
    candidates = [_candidate("Phở bò", 0.95), _candidate("Bún chả", 0.80)]

    obs = build_observation(truth, candidates)

    assert obs.top1_name == "Phở bò"
    assert obs.top1_score == pytest.approx(0.95)
    assert obs.margin == pytest.approx(0.15)
    assert obs.correct is True


def test_build_observation_alias_match_counts_as_correct():
    truth = _truth("pho_bo", "Phở bò", ("Phở bò tái",))
    obs = build_observation(truth, [_candidate("pho bo tai", 0.9)])
    assert obs.correct is True


def test_build_observation_single_candidate_margin_equals_score():
    truth = _truth("pho_bo", "Phở bò")
    obs = build_observation(truth, [_candidate("Phở bò", 0.9)])
    assert obs.margin == pytest.approx(0.9)


def test_build_observation_no_candidates_is_never_covered():
    truth = _truth("pho_bo", "Phở bò")
    obs = build_observation(truth, [])

    assert obs.top1_name is None
    result = evaluate_pair([obs], 0.5, 0.0)
    assert result.covered == 0
    assert result.precision is None


# ─── evaluate_pair + sweep ───────────────────────────────────────────────────


def test_evaluate_pair_computes_coverage_and_precision():
    observations = [
        _obs(0.98, 0.10, True),
        _obs(0.97, 0.10, True),
        _obs(0.60, 0.05, False, name="Bún chả"),
        _obs(0.55, 0.02, False, name="Bún chả"),
    ]

    loose = evaluate_pair(observations, 0.5, 0.0)
    assert loose.covered == 4
    assert loose.coverage == pytest.approx(1.0)
    assert loose.precision == pytest.approx(0.5)

    strict = evaluate_pair(observations, 0.9, 0.06)
    assert strict.covered == 2
    assert strict.coverage == pytest.approx(0.5)
    assert strict.precision == pytest.approx(1.0)


def test_evaluate_pair_margin_filters_low_margin_hits():
    observations = [_obs(0.9, 0.01, True), _obs(0.9, 0.12, True)]
    result = evaluate_pair(observations, 0.5, 0.05)
    assert result.covered == 1


def test_sweep_thresholds_covers_full_grid():
    results = sweep_thresholds([_obs(0.9, 0.1, True)])
    assert len(results) == len(T1_VALUES) * len(T2_VALUES)
    assert len(T1_VALUES) == 50  # 0.50 → 0.99 bước 0.01
    assert len(T2_VALUES) == 16  # 0.00 → 0.15 bước 0.01


# ─── recommend ───────────────────────────────────────────────────────────────


def test_recommend_honors_min_precision():
    observations = [
        _obs(0.98, 0.10, True),
        _obs(0.97, 0.10, True),
        _obs(0.60, 0.05, False, name="Bún chả"),
        _obs(0.55, 0.02, False, name="Bún chả"),
    ]
    results = sweep_thresholds(observations)

    recommended = recommend(results, min_precision=0.95)

    # Cặp phủ cả 4 ảnh chỉ đạt precision 0.5 → phải lùi về tập 2 ảnh đúng,
    # và trong các cặp hòa nhau chọn ngưỡng bảo thủ nhất.
    assert recommended is not None
    assert recommended.coverage == pytest.approx(0.5)
    assert recommended.precision == pytest.approx(1.0)
    assert recommended.t1 == pytest.approx(0.97)
    assert recommended.t2 == pytest.approx(0.10)


def test_recommend_returns_none_when_nothing_meets_min_precision():
    observations = [_obs(0.9, 0.1, False, name="Bún chả")]
    results = sweep_thresholds(observations)
    assert recommend(results, min_precision=0.95) is None


def test_recommend_ignores_pairs_with_no_coverage():
    obs_none = CascadeObservation(
        truth_slug="pho_bo", top1_name=None,
        top1_score=0.0, margin=0.0, correct=False,
    )
    results = sweep_thresholds([obs_none])
    assert recommend(results, min_precision=0.0) is None


# ─── pareto_frontier ─────────────────────────────────────────────────────────


def _threshold_result(
    t1: float, t2: float, coverage: float, precision: float | None
) -> ThresholdResult:
    return ThresholdResult(
        t1=t1, t2=t2, covered=int(coverage * 10), total=10,
        coverage=coverage, precision=precision,
    )


def test_pareto_frontier_drops_dominated_points():
    r1 = _threshold_result(0.6, 0.00, 0.9, 0.8)
    r2 = _threshold_result(0.8, 0.05, 0.8, 0.9)
    dominated = _threshold_result(0.7, 0.02, 0.8, 0.8)
    uncovered = _threshold_result(0.99, 0.15, 0.0, None)

    frontier = pareto_frontier([r1, r2, dominated, uncovered])

    assert list(frontier) == [r1, r2]  # sort coverage giảm dần


def test_pareto_frontier_dedupes_ties_keeping_most_conservative():
    loose = _threshold_result(0.60, 0.00, 0.8, 0.9)
    conservative = _threshold_result(0.75, 0.05, 0.8, 0.9)

    frontier = pareto_frontier([loose, conservative])

    assert frontier == (conservative,)


# ─── report ──────────────────────────────────────────────────────────────────


def test_build_report_shape_is_json_serializable():
    observations = [
        _obs(0.9, 0.1, True),
        CascadeObservation(
            truth_slug="pho_ga", top1_name=None,
            top1_score=0.0, margin=0.0, correct=False,
        ),
    ]
    results = sweep_thresholds(observations)
    frontier = pareto_frontier(results)
    recommended = recommend(results, min_precision=0.95)

    report = build_report(
        observations, frontier, recommended,
        images_dir="data/images/val", min_precision=0.95,
        timestamp="20260726_120000",
    )

    assert set(report) == {
        "timestamp", "suite", "images_dir", "min_precision",
        "n_images", "n_no_candidates", "frontier", "recommended",
    }
    assert report["suite"] == "cascade_tuning"
    assert report["n_images"] == 2
    assert report["n_no_candidates"] == 1
    assert report["recommended"]["precision"] == pytest.approx(1.0)
    json.dumps(report, ensure_ascii=False)  # không được nổ


def test_build_report_handles_missing_recommendation():
    report = build_report(
        [], (), None,
        images_dir="x", min_precision=0.95, timestamp="ts",
    )
    assert report["recommended"] is None
    assert report["n_images"] == 0
