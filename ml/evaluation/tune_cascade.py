"""Offline tuner cho ngưỡng cascade nhận diện bằng ảnh (Phase 2).

Với mỗi ảnh trong ``--images-dir`` (layout ``<class_slug>/*.jpg``), embed qua
sidecar SigLIP (``backend.services.image_embeddings``) rồi lấy top dish
candidates từ Qdrant (``backend.services.dish_image_index``). Sau đó sweep
cặp ngưỡng (t1 = best_score, t2 = margin top1−top2):

- coverage  = % ảnh có top1.best_score ≥ t1 và margin ≥ t2
- precision = % ảnh trong tập covered mà top1 trùng ground truth

Phần sweep là pure function trên tuple (truth, top1_name, top1_score, margin)
đã tính sẵn — unit test không cần Qdrant/sidecar.

Cần hạ tầng khi chạy thật: sidecar embedding (8082) + Qdrant có dish_images.

Usage:
    python -m ml.evaluation.tune_cascade --images-dir data/images/val
"""

import argparse
import asyncio
import json
import sys
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

# Cho phép chạy thẳng ``python ml/evaluation/tune_cascade.py`` (không qua -m):
# thêm repo root vào sys.path như scripts/index_dish_images.py vẫn làm.
_REPO_ROOT = str(Path(__file__).resolve().parents[2])
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from ml.evaluation.recognition_eval import (  # noqa: E402
    PROJECT_ROOT,
    REPORTS_DIR,
    ClassTruth,
    collect_images,
    load_ground_truth,
    normalize_name,
)

DEFAULT_IMAGES_DIR = PROJECT_ROOT / "data" / "images" / "val"
DEFAULT_MIN_PRECISION = 0.95
DEFAULT_BATCH_SIZE = 8

#: Lưới sweep dựng từ số nguyên /100 để tránh trôi số float.
T1_VALUES: tuple[float, ...] = tuple(i / 100 for i in range(50, 100))
T2_VALUES: tuple[float, ...] = tuple(i / 100 for i in range(0, 16))


# ─── Pure sweep logic ────────────────────────────────────────────────────────


@dataclass(frozen=True)
class CascadeObservation:
    """Quan sát 1 ảnh: top1 là gì, điểm bao nhiêu, cách top2 bao xa."""

    truth_slug: str
    top1_name: str | None
    top1_score: float
    margin: float
    correct: bool


@dataclass(frozen=True)
class ThresholdResult:
    """Kết quả 1 cặp ngưỡng. precision=None khi không ảnh nào được cover."""

    t1: float
    t2: float
    covered: int
    total: int
    coverage: float
    precision: float | None


def build_observation(
    truth: ClassTruth, candidates: Sequence
) -> CascadeObservation:
    """DishCandidateScore list (sorted desc) → observation cho sweep.

    Không có top2 thì margin = top1_score (luôn vượt mọi t2 hợp lệ) —
    một candidate duy nhất nghĩa là không có đối thủ cạnh tranh.
    """
    if not candidates:
        return CascadeObservation(
            truth_slug=truth.slug, top1_name=None,
            top1_score=0.0, margin=0.0, correct=False,
        )
    top1 = candidates[0]
    top2_score = float(candidates[1].best_score) if len(candidates) > 1 else 0.0
    top1_score = float(top1.best_score)
    return CascadeObservation(
        truth_slug=truth.slug,
        top1_name=top1.dish_name,
        top1_score=top1_score,
        margin=top1_score - top2_score,
        correct=normalize_name(top1.dish_name) in truth.acceptable,
    )


def evaluate_pair(
    observations: Sequence[CascadeObservation], t1: float, t2: float
) -> ThresholdResult:
    """Tính coverage + precision cho 1 cặp ngưỡng."""
    covered = [
        o
        for o in observations
        if o.top1_name is not None and o.top1_score >= t1 and o.margin >= t2
    ]
    total = len(observations)
    correct = sum(o.correct for o in covered)
    return ThresholdResult(
        t1=t1,
        t2=t2,
        covered=len(covered),
        total=total,
        coverage=round(len(covered) / total, 4) if total else 0.0,
        precision=round(correct / len(covered), 4) if covered else None,
    )


def sweep_thresholds(
    observations: Sequence[CascadeObservation],
    t1_values: Sequence[float] = T1_VALUES,
    t2_values: Sequence[float] = T2_VALUES,
) -> tuple[ThresholdResult, ...]:
    """Quét toàn bộ lưới (t1, t2)."""
    return tuple(
        evaluate_pair(observations, t1, t2)
        for t1 in t1_values
        for t2 in t2_values
    )


def pareto_frontier(
    results: Sequence[ThresholdResult],
) -> tuple[ThresholdResult, ...]:
    """Giữ các cặp không bị cặp khác vượt cả coverage lẫn precision.

    Nhiều cặp trùng (coverage, precision) → giữ cặp bảo thủ nhất
    (t1, t2 cao nhất) cho mỗi điểm.
    """
    scored = [r for r in results if r.precision is not None]
    best_per_point: dict[tuple[float, float], ThresholdResult] = {}
    for r in scored:
        key = (r.coverage, r.precision)
        current = best_per_point.get(key)
        if current is None or (r.t1, r.t2) > (current.t1, current.t2):
            best_per_point[key] = r
    points = list(best_per_point.values())
    frontier = [
        r
        for r in points
        if not any(
            o.coverage >= r.coverage
            and o.precision >= r.precision
            and (o.coverage > r.coverage or o.precision > r.precision)
            for o in points
        )
    ]
    return tuple(sorted(frontier, key=lambda r: r.coverage, reverse=True))


def recommend(
    results: Sequence[ThresholdResult], min_precision: float
) -> ThresholdResult | None:
    """Cặp coverage cao nhất trong các cặp đạt precision ≥ min_precision.

    Hòa coverage → precision cao hơn → ngưỡng bảo thủ hơn (t1, t2 lớn hơn).
    """
    eligible = [
        r
        for r in results
        if r.precision is not None and r.precision >= min_precision
    ]
    if not eligible:
        return None
    return max(eligible, key=lambda r: (r.coverage, r.precision, r.t1, r.t2))


# ─── Data collection (cần sidecar + Qdrant) ──────────────────────────────────


async def collect_observations(
    images_dir: Path,
    truths: dict[str, ClassTruth],
    *,
    limit_per_class: int = 0,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> list[CascadeObservation]:
    """Embed từng batch ảnh rồi truy vấn Qdrant lấy candidates.

    Import function-level: module vẫn import (và unit-test phần pure) được
    khi backend chưa cài đủ dependency của sidecar.
    """
    from backend.services.dish_image_index import top_dish_candidates
    from backend.services.image_embeddings import embed_images

    pairs = collect_images(images_dir, limit_per_class)
    known = [(slug, path) for slug, path in pairs if slug in truths]
    skipped = len(pairs) - len(known)
    if skipped:
        print(f"⚠️  Bỏ qua {skipped} ảnh thuộc class không có trong class_names.json")

    observations: list[CascadeObservation] = []
    for start in range(0, len(known), batch_size):
        batch = known[start : start + batch_size]
        images = [
            await asyncio.to_thread(path.read_bytes) for _slug, path in batch
        ]
        try:
            vectors = await embed_images(images)
        except Exception as exc:
            raise RuntimeError(
                f"Embed batch ảnh thất bại (bắt đầu từ {batch[0][1]}): {exc}"
            ) from exc
        for (slug, _path), vector in zip(batch, vectors, strict=True):
            candidates = await top_dish_candidates(vector)
            observations.append(build_observation(truths[slug], candidates))
    return observations


# ─── Report ──────────────────────────────────────────────────────────────────


def build_report(
    observations: Sequence[CascadeObservation],
    frontier: Sequence[ThresholdResult],
    recommended: ThresholdResult | None,
    *,
    images_dir: str,
    min_precision: float,
    timestamp: str,
) -> dict:
    """Gom kết quả tuning thành dict JSON-serializable."""
    return {
        "timestamp": timestamp,
        "suite": "cascade_tuning",
        "images_dir": images_dir,
        "min_precision": min_precision,
        "n_images": len(observations),
        "n_no_candidates": sum(1 for o in observations if o.top1_name is None),
        "frontier": [asdict(r) for r in frontier],
        "recommended": asdict(recommended) if recommended else None,
    }


def render_table(frontier: Sequence[ThresholdResult]) -> str:
    """Bảng Pareto frontier in console."""
    lines = ["  t1     t2     coverage  precision", "  " + "-" * 34]
    for r in frontier:
        lines.append(
            f"  {r.t1:.2f}   {r.t2:.2f}   {r.coverage:>8.4f}  {r.precision:>9.4f}"
        )
    return "\n".join(lines)


def save_report(report: dict, timestamp: str) -> Path:
    """Lưu report JSON vào ml/evaluation/reports/."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    json_path = REPORTS_DIR / f"cascade_tuning_{timestamp}.json"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return json_path


# ─── CLI ─────────────────────────────────────────────────────────────────────


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Tune cascade thresholds")
    parser.add_argument("--images-dir", type=Path, default=DEFAULT_IMAGES_DIR)
    parser.add_argument("--min-precision", type=float, default=DEFAULT_MIN_PRECISION)
    parser.add_argument("--limit-per-class", type=int, default=0)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    return parser.parse_args(argv)


async def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    truths = load_ground_truth()
    print(f"🔍 Cascade tuning — embed ảnh từ {args.images_dir}")
    try:
        observations = await collect_observations(
            args.images_dir,
            truths,
            limit_per_class=args.limit_per_class,
            batch_size=max(1, args.batch_size),
        )
    finally:
        # Best-effort: đóng client sidecar nếu module đã import được.
        try:
            from backend.services.image_embeddings import (
                close_image_embedding_client,
            )

            await close_image_embedding_client()
        except Exception:  # noqa: BLE001 — không che lỗi thật phía trên
            pass
    if not observations:
        raise SystemExit(f"Không có ảnh hợp lệ trong {args.images_dir}")

    results = sweep_thresholds(observations)
    frontier = pareto_frontier(results)
    recommended = recommend(results, args.min_precision)

    print(f"\n📊 Pareto frontier ({len(observations)} ảnh):")
    print(render_table(frontier))
    if recommended:
        print(
            f"\n✅ Đề xuất: t1={recommended.t1:.2f}, t2={recommended.t2:.2f}"
            f" → coverage={recommended.coverage:.4f},"
            f" precision={recommended.precision:.4f}"
        )
    else:
        print(f"\n⚠️  Không cặp ngưỡng nào đạt precision ≥ {args.min_precision}")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report = build_report(
        observations, frontier, recommended,
        images_dir=str(args.images_dir),
        min_precision=args.min_precision,
        timestamp=timestamp,
    )
    json_path = save_report(report, timestamp)
    print(f"\n💾 Report saved: {json_path}")


if __name__ == "__main__":
    asyncio.run(main())
