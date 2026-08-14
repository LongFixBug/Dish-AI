"""Legacy offline evaluation for the retired EfficientNet + album policy.

The online API resolves labels to PostgreSQL UUIDs before calling
``decide_local_fusion``.  An offline labelled dataset can use stable class slugs
as the same canonical identity, which lets us measure the consensus auto-local
branch without calling Vision, PostgreSQL, or an HTTP API.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from backend.config import settings  # noqa: E402
from backend.services.recognition_cascade import (  # noqa: E402
    LocalEvidence,
    decide_local_fusion,
    is_catalog_identity_safe,
)  # noqa: E402
from ml.evaluation.recognition_eval import (  # noqa: E402
    PROJECT_ROOT,
    REPORTS_DIR,
    ClassTruth,
    collect_images,
    load_ground_truth,
    normalize_name,
)  # noqa: E402

AUTO_ACTIONS: tuple[str, ...] = ("local_consensus",)
Action = Literal["local_consensus", "vision"]
DEFAULT_IMAGES_DIR = PROJECT_ROOT / "data" / "images" / "golden"
DEFAULT_CHECKPOINT = PROJECT_ROOT / "checkpoints" / "best_model.pth"
_DEFAULT_CV_SOLO = object()
DEFAULT_FUSION_CV_MIN_THRESHOLD = 0.90


def fusion_cv_thresholds(
    minimum: float,
    maximum: float,
) -> tuple[float, ...]:
    """Build an inclusive millesimal sweep without excluding raw-CV evidence.

    Unlike the serving setting, this is evaluation-only. A result below the
    current threshold is never activated until the resulting report passes the
    same consensus precision gate as every other candidate.
    """
    if not 0.0 <= minimum <= maximum <= 1.0:
        raise ValueError("Fusion CV thresholds must be within [0, 1]")
    lower = int(round(minimum * 1000))
    upper = int(round(maximum * 1000))
    return tuple(index / 1000 for index in range(lower, upper + 1))


@dataclass(frozen=True)
class FusionObservation:
    """One labelled image with the raw evidence from both local recognizers."""

    truth_slug: str
    cv_slug: str | None
    cv_confidence: float
    album_slug: str | None
    album_score: float
    album_margin: float
    # Runtime identities are PostgreSQL UUIDs (or ``None`` when the API would
    # reject a broad/unsafe catalog refinement).  The slug fallback preserves
    # synthetic unit tests while live collection always fills these fields.
    truth_canonical_id: str | None = None
    cv_canonical_id: str | None = None
    album_canonical_id: str | None = None


@dataclass(frozen=True)
class FusionResult:
    """One production-equivalent fusion decision plus its labelled outcome."""

    truth_slug: str
    action: Action
    predicted_slug: str | None
    correct: bool | None


@dataclass(frozen=True)
class FusionThresholdResult:
    """One candidate operating point and the evidence for enabling it."""

    cv_threshold: float
    album_threshold: float
    album_margin: float
    actions: dict[str, dict]
    auto_coverage: float
    gate: dict[str, object]


def build_dish_slug_index(
    truths: Mapping[str, ClassTruth],
) -> dict[str, str]:
    """Map album display names to eval slugs, preferring exact labels to aliases."""
    index = {
        normalize_name(truth.display_name): slug
        for slug, truth in truths.items()
    }
    for slug, truth in truths.items():
        for name in truth.acceptable:
            index.setdefault(name, slug)
    return index


def slug_from_cv_prediction(
    predicted_name: str | None,
    checkpoint_classes: Sequence[str],
) -> str | None:
    """Resolve CV's title-cased name back to its checkpoint class slug."""
    if not predicted_name:
        return None
    normalized = normalize_name(predicted_name)
    for slug in checkpoint_classes:
        if normalize_name(slug.replace("_", " ")) == normalized:
            return slug
    return None


async def resolve_runtime_catalog_identity(
    session: object,
    dish_name: str | None,
    cache: dict[str, str | None],
    *,
    lookup,
) -> str | None:
    """Mirror the API's safe catalog-identity gate for one local label.

    An offline alias is useful for measuring classifier accuracy, but it is
    not enough for an automatic nutrition answer.  The serving API resolves
    the name through PostgreSQL/Qdrant then rejects unsafe family changes
    (for example generic ``Phở`` becoming ``Phở bò``).  Fusion evaluation must
    make exactly the same distinction or its local coverage is overstated.
    """
    if not dish_name:
        return None
    key = normalize_name(dish_name)
    if not key:
        return None
    if key in cache:
        return cache[key]
    row = await lookup(session, dish_name)
    if row is None or not is_catalog_identity_safe(dish_name, row.dish_name):
        cache[key] = None
        return None
    identity = str(getattr(row, "id", "") or row.dish_name.casefold())
    cache[key] = identity
    return identity


def decide_observation(
    observation: FusionObservation,
    cv_threshold: float,
    album_threshold: float,
    album_margin: float,
    cv_solo_threshold: float | None | object = _DEFAULT_CV_SOLO,
    album_solo_enabled: bool = True,
) -> FusionResult:
    """Apply the production consensus-only decision matrix offline."""
    cv_canonical_id = observation.cv_canonical_id or observation.cv_slug
    album_canonical_id = observation.album_canonical_id or observation.album_slug
    truth_canonical_id = observation.truth_canonical_id or observation.truth_slug
    cv_strong = bool(
        observation.cv_slug and observation.cv_confidence >= cv_threshold
    )
    solo_threshold = (
        cv_threshold if cv_solo_threshold is _DEFAULT_CV_SOLO else cv_solo_threshold
    )
    album_strong = bool(
        observation.album_slug
        and observation.album_score >= album_threshold
        and observation.album_margin >= album_margin
    )
    decision = decide_local_fusion(
        LocalEvidence(
            dish_name=observation.cv_slug,
            canonical_id=cv_canonical_id if cv_strong else None,
            confidence=observation.cv_confidence,
            strong=cv_strong,
            solo_strong=bool(
                cv_strong
                and isinstance(solo_threshold, (int, float))
                and observation.cv_confidence >= solo_threshold
            ),
        ),
        LocalEvidence(
            dish_name=observation.album_slug,
            canonical_id=album_canonical_id if album_strong else None,
            confidence=observation.album_score,
            strong=album_strong,
            solo_strong=album_strong and album_solo_enabled,
        ),
    )
    action: Action = decision.action
    predicted = decision.canonical_id
    return FusionResult(
        truth_slug=observation.truth_slug,
        action=action,
        predicted_slug=predicted,
        correct=(predicted == truth_canonical_id) if predicted else None,
    )


def summarize_actions(results: Sequence[FusionResult]) -> dict[str, dict]:
    """Report accepted/correct/precision independently for each decision action."""
    summary: dict[str, dict] = {
        action: {"accepted": 0, "correct": 0, "precision": None}
        for action in AUTO_ACTIONS
    }
    summary["vision"] = {"deferred": 0}
    for result in results:
        if result.action == "vision":
            summary["vision"]["deferred"] += 1
            continue
        row = summary[result.action]
        row["accepted"] += 1
        row["correct"] += int(result.correct is True)
    for action in AUTO_ACTIONS:
        row = summary[action]
        if row["accepted"]:
            row["precision"] = round(row["correct"] / row["accepted"], 4)
    return summary


def evaluate_rollout_gate(
    summary: Mapping[str, Mapping[str, object]],
    *,
    min_precision: float = 0.98,
    min_accepted: int = 30,
    required_actions: Sequence[str] = AUTO_ACTIONS,
) -> dict[str, object]:
    """Require sufficient precision and labelled evidence for every auto branch."""
    failures: dict[str, str] = {}
    for action in required_actions:
        row = summary.get(action, {})
        accepted = int(row.get("accepted", 0))
        precision = row.get("precision")
        if accepted < min_accepted:
            failures[action] = f"accepted {accepted} < {min_accepted}"
        elif not isinstance(precision, (int, float)) or precision < min_precision:
            value = float(precision or 0.0)
            failures[action] = f"precision {value:.4f} < {min_precision:.4f}"
    return {"passed": not failures, "failures": failures}


def sweep_thresholds(
    observations: Sequence[FusionObservation],
    *,
    cv_thresholds: Sequence[float],
    album_thresholds: Sequence[float],
    album_margins: Sequence[float],
    min_precision: float,
    min_accepted: int,
    cv_solo_threshold: float | None | object = _DEFAULT_CV_SOLO,
    album_solo_enabled: bool = True,
    required_actions: Sequence[str] = AUTO_ACTIONS,
) -> tuple[FusionThresholdResult, ...]:
    """Evaluate every fusion threshold triple against the same sealed evidence."""
    results: list[FusionThresholdResult] = []
    for cv_threshold in cv_thresholds:
        for album_threshold in album_thresholds:
            for album_margin in album_margins:
                decisions = [
                    decide_observation(
                        item,
                        cv_threshold,
                        album_threshold,
                        album_margin,
                        cv_solo_threshold=cv_solo_threshold,
                        album_solo_enabled=album_solo_enabled,
                    )
                    for item in observations
                ]
                actions = summarize_actions(decisions)
                gate = evaluate_rollout_gate(
                    actions,
                    min_precision=min_precision,
                    min_accepted=min_accepted,
                    required_actions=required_actions,
                )
                auto_coverage = (
                    sum(actions[action]["accepted"] for action in AUTO_ACTIONS)
                    / len(observations)
                    if observations
                    else 0.0
                )
                results.append(
                    FusionThresholdResult(
                        cv_threshold=cv_threshold,
                        album_threshold=album_threshold,
                        album_margin=album_margin,
                        actions=actions,
                        auto_coverage=round(auto_coverage, 4),
                        gate=gate,
                    )
                )
    return tuple(results)


def recommend_thresholds(
    results: Sequence[FusionThresholdResult],
) -> FusionThresholdResult | None:
    """Prefer the highest safe local coverage, then the more conservative tie."""
    passing = [item for item in results if item.gate.get("passed") is True]
    if not passing:
        return None
    return max(
        passing,
        key=lambda item: (
            item.auto_coverage,
            item.cv_threshold,
            item.album_threshold,
            item.album_margin,
        ),
    )


def _threshold_payload(result: FusionThresholdResult) -> dict[str, object]:
    return {
        "cv_threshold": result.cv_threshold,
        "album_threshold": result.album_threshold,
        "album_margin": result.album_margin,
        "auto_coverage": result.auto_coverage,
        "actions": result.actions,
        "gate": result.gate,
    }


def _album_evidence(
    candidates: Sequence,
    dish_slug_index: Mapping[str, str],
) -> tuple[str | None, str | None, float, float]:
    """Convert album candidates to a canonical slug, score, and score margin."""
    if not candidates:
        return None, None, 0.0, 0.0
    top1 = candidates[0]
    score = float(top1.best_score)
    runner_up = float(candidates[1].best_score) if len(candidates) > 1 else 0.0
    slug = dish_slug_index.get(normalize_name(top1.dish_name))
    return slug, top1.dish_name, score, score - runner_up


async def collect_live_observations(
    images_dir: Path,
    checkpoint_path: Path,
    *,
    device: str | None,
    limit_per_class: int,
    batch_size: int,
    album_score_mode: Literal["best", "top3_blend"],
) -> tuple[list[FusionObservation], float]:
    """Collect serving-equivalent local evidence without calling Vision.

    The image model/Qdrant retrieval is live, and names are resolved through
    the same PostgreSQL + guarded semantic lookup used by ``/analyze``.
    """
    from backend.db.postgres import async_session
    from backend.services.dishes import lookup_dish
    from backend.services.dish_image_index import top_dish_candidates
    from backend.services.image_embeddings import embed_images
    from ml.inference.cv import CVModel

    manifest_path = checkpoint_path.with_suffix(".manifest.json")
    model = CVModel(
        checkpoint_path=checkpoint_path,
        device=device,
        manifest_path=manifest_path,
        require_manifest=manifest_path.exists(),
    )
    model.load()
    if not model.is_loaded:
        raise RuntimeError(f"CV checkpoint is unavailable: {checkpoint_path}")

    truths = load_ground_truth()
    dish_slug_index = build_dish_slug_index(truths)
    pairs = [
        (slug, path)
        for slug, path in collect_images(images_dir, limit_per_class)
        if slug in truths
    ]
    observations: list[FusionObservation] = []
    identity_cache: dict[str, str | None] = {}
    async with async_session() as session:
        for start in range(0, len(pairs), batch_size):
            batch = pairs[start : start + batch_size]
            images = [await asyncio.to_thread(path.read_bytes) for _slug, path in batch]
            vectors = await embed_images(images)
            for (truth_slug, path), vector in zip(batch, vectors, strict=True):
                candidates = await top_dish_candidates(
                    vector,
                    score_mode=album_score_mode,
                )
                album_slug, album_name, album_score, album_margin = _album_evidence(
                    candidates, dish_slug_index
                )
                prediction = await asyncio.to_thread(model.predict, path)
                top_predictions = prediction.get("all_predictions", [])
                top_name = (
                    top_predictions[0].get("class_name")
                    if isinstance(top_predictions, list) and top_predictions
                    and isinstance(top_predictions[0], dict)
                    else None
                )
                truth = truths[truth_slug]
                truth_identity = await resolve_runtime_catalog_identity(
                    session,
                    truth.display_name,
                    identity_cache,
                    lookup=lookup_dish,
                )
                cv_identity = await resolve_runtime_catalog_identity(
                    session,
                    top_name,
                    identity_cache,
                    lookup=lookup_dish,
                )
                album_identity = await resolve_runtime_catalog_identity(
                    session,
                    album_name,
                    identity_cache,
                    lookup=lookup_dish,
                )
                observations.append(
                    FusionObservation(
                        truth_slug=truth_slug,
                        cv_slug=slug_from_cv_prediction(top_name, model.classes),
                        cv_confidence=float(prediction.get("confidence", 0.0)),
                        album_slug=album_slug,
                        album_score=album_score,
                        album_margin=album_margin,
                        truth_canonical_id=truth_identity,
                        cv_canonical_id=cv_identity,
                        album_canonical_id=album_identity,
                    )
                )
    return observations, model.serving_threshold


def _disagreement_counts(
    observations: Sequence[FusionObservation],
    *,
    cv_threshold: float,
    album_threshold: float,
    album_margin: float,
) -> list[dict[str, object]]:
    """Summarize strong local conflicts that correctly fall through to Vision."""
    counts: dict[tuple[str, str], int] = {}
    for item in observations:
        cv_strong = item.cv_slug and item.cv_confidence >= cv_threshold
        album_strong = (
            item.album_slug
            and item.album_score >= album_threshold
            and item.album_margin >= album_margin
        )
        if cv_strong and album_strong and item.cv_slug != item.album_slug:
            key = (item.cv_slug, item.album_slug)
            counts[key] = counts.get(key, 0) + 1
    return [
        {"cv_slug": cv_slug, "album_slug": album_slug, "count": count}
        for (cv_slug, album_slug), count in sorted(
            counts.items(), key=lambda item: (-item[1], item[0])
        )
    ]


def build_report(
    observations: Sequence[FusionObservation],
    results: Sequence[FusionResult],
    *,
    images_dir: Path,
    checkpoint_path: Path,
    cv_threshold: float,
    album_threshold: float,
    album_margin: float,
    album_score_mode: Literal["best", "top3_blend"],
    cv_model_serving_threshold: float,
    cv_solo_threshold: float | None,
    album_solo_enabled: bool,
    min_precision: float,
    min_accepted: int,
    required_actions: Sequence[str],
    timestamp: str,
) -> dict[str, object]:
    """Serialize one reviewable fusion evaluation artifact."""
    actions = summarize_actions(results)
    return {
        "timestamp": timestamp,
        "suite": "local_fusion_shadow_eval",
        "canonicalization": "runtime_postgres_qdrant_refinement",
        "images_dir": str(images_dir),
        "checkpoint_path": str(checkpoint_path),
        "n_images": len(observations),
        "thresholds": {
            "cv": cv_threshold,
            "cv_model_serving": cv_model_serving_threshold,
            "cv_solo": cv_solo_threshold,
            "album_solo_enabled": album_solo_enabled,
            "album_score": album_threshold,
            "album_margin": album_margin,
            "album_score_mode": album_score_mode,
        },
        "actions": actions,
        "auto_coverage": round(
            sum(actions[action]["accepted"] for action in AUTO_ACTIONS)
            / len(observations),
            4,
        ) if observations else 0.0,
        "strong_disagreements": _disagreement_counts(
            observations,
            cv_threshold=cv_threshold,
            album_threshold=album_threshold,
            album_margin=album_margin,
        ),
        "rollout_gate": evaluate_rollout_gate(
            actions,
            min_precision=min_precision,
            min_accepted=min_accepted,
            required_actions=required_actions,
        ),
    }


def save_report(report: Mapping[str, object], timestamp: str) -> Path:
    """Write immutable fusion evidence for PO review."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORTS_DIR / f"fusion_shadow_{timestamp}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate local CV + album fusion")
    parser.add_argument("--images-dir", type=Path, default=DEFAULT_IMAGES_DIR)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--device", choices=("cpu", "mps", "cuda"))
    parser.add_argument("--limit-per-class", type=int, default=0)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--album-threshold", type=float, default=settings.image_match_threshold)
    parser.add_argument("--album-margin", type=float, default=settings.image_match_margin)
    parser.add_argument(
        "--album-score-mode",
        choices=("best", "top3_blend"),
        default=settings.image_match_score_mode,
        help="Album aggregation to measure; this does not change serving config.",
    )
    parser.add_argument(
        "--cv-fusion-threshold",
        type=float,
        default=settings.local_fusion_cv_threshold,
        help="CV confidence required to join fusion consensus/disagreement.",
    )
    parser.add_argument(
        "--cv-fusion-min-threshold",
        type=float,
        default=DEFAULT_FUSION_CV_MIN_THRESHOLD,
        help=(
            "Lowest raw CV top-1 confidence considered during --tune; "
            "evaluation only, never a direct serving switch."
        ),
    )
    parser.add_argument(
        "--cv-solo-threshold",
        type=float,
        default=settings.cv_solo_confidence_threshold,
        help="Deprecated compatibility option; CV-only answers remain disabled.",
    )
    parser.add_argument("--min-precision", type=float, default=0.98)
    parser.add_argument("--min-accepted", type=int, default=30)
    parser.add_argument(
        "--tune",
        action="store_true",
        help="Sweep stricter CV/album thresholds and write the best passing point.",
    )
    return parser.parse_args(argv)


async def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    observations, cv_model_serving_threshold = await collect_live_observations(
        args.images_dir,
        args.checkpoint,
        device=args.device,
        limit_per_class=max(0, args.limit_per_class),
        batch_size=max(1, args.batch_size),
        album_score_mode=args.album_score_mode,
    )
    cv_threshold = args.cv_fusion_threshold or cv_model_serving_threshold
    results = [
        decide_observation(
            item,
            cv_threshold,
            args.album_threshold,
            args.album_margin,
            cv_solo_threshold=args.cv_solo_threshold,
            album_solo_enabled=settings.local_fusion_album_solo_enabled,
        )
        for item in observations
    ]
    required_actions = ["local_consensus"]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report = build_report(
        observations,
        results,
        images_dir=args.images_dir,
        checkpoint_path=args.checkpoint,
        cv_threshold=cv_threshold,
        album_threshold=args.album_threshold,
        album_margin=args.album_margin,
        album_score_mode=args.album_score_mode,
        cv_model_serving_threshold=cv_model_serving_threshold,
        cv_solo_threshold=args.cv_solo_threshold,
        album_solo_enabled=settings.local_fusion_album_solo_enabled,
        min_precision=args.min_precision,
        min_accepted=args.min_accepted,
        required_actions=required_actions,
        timestamp=timestamp,
    )
    if args.tune:
        cv_values = fusion_cv_thresholds(
            min(args.cv_fusion_min_threshold, cv_threshold),
            0.999,
        )
        album_values = tuple(index / 100 for index in range(73, 91))
        margin_values = tuple(index / 100 for index in range(4, 11))
        candidates = sweep_thresholds(
            observations,
            cv_thresholds=cv_values,
            album_thresholds=album_values,
            album_margins=margin_values,
            min_precision=args.min_precision,
            min_accepted=args.min_accepted,
            cv_solo_threshold=args.cv_solo_threshold,
            album_solo_enabled=settings.local_fusion_album_solo_enabled,
            required_actions=required_actions,
        )
        recommended = recommend_thresholds(candidates)
        passing = [item for item in candidates if item.gate.get("passed") is True]
        best_effort = max(
            candidates,
            key=lambda item: (
                -len(item.gate.get("failures", {})),
                item.auto_coverage,
                item.cv_threshold,
                item.album_threshold,
                item.album_margin,
            ),
        )
        report["tuning"] = {
            "candidates": len(candidates),
            "passing_candidates": len(passing),
            "recommended": (
                _threshold_payload(recommended) if recommended is not None else None
            ),
            "best_effort": _threshold_payload(best_effort),
        }
    path = save_report(report, timestamp)
    print(json.dumps(report["actions"], ensure_ascii=False, indent=2))
    print(f"Rollout gate: {report['rollout_gate']}")
    if args.tune:
        print(f"Tuning: {report['tuning']}")
    print(f"Report saved: {path}")


if __name__ == "__main__":
    asyncio.run(main())
