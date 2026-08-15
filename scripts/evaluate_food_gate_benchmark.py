"""Measure Food Gate on an independently crawled, reviewable benchmark."""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path
from typing import Any

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ml.inference.food_gate import FoodGatePredictor, FoodGateSettings  # noqa: E402
from ml.training.siglip_fast_lane import IMAGE_EXTENSIONS  # noqa: E402

DEFAULT_ROOT = PROJECT_ROOT / "data" / "images" / "food_gate_real_eval"
DEFAULT_OUTPUT = PROJECT_ROOT / "checkpoints" / "food_gate" / "evaluation" / "benchmark.json"


def _percentile(values: list[float], quantile: float) -> float:
    if not values:
        return 0.0
    rank = max(0, math.ceil(len(values) * quantile) - 1)
    return round(sorted(values)[rank], 2)


def summarize_predictions(
    rows: list[dict[str, float | str]], *, block_threshold: float
) -> dict[str, float | int]:
    """Compute safety-oriented metrics from labeled Food Gate predictions."""
    if not 0 <= block_threshold <= 1:
        raise ValueError("block_threshold must be between 0 and 1")
    food = [row for row in rows if row["expected"] == "food"]
    non_food = [row for row in rows if row["expected"] == "non_food"]
    if len(food) + len(non_food) != len(rows) or not food or not non_food:
        raise ValueError("Benchmark phải có cả food và non_food")

    def is_blocked(row: dict[str, float | str]) -> bool:
        return float(row["non_food_score"]) >= block_threshold

    correct = sum(not is_blocked(row) for row in food) + sum(is_blocked(row) for row in non_food)
    latencies = [float(row["latency_ms"]) for row in rows]
    return {
        "n_total": len(rows),
        "n_food": len(food),
        "n_non_food": len(non_food),
        "accuracy": round(correct / len(rows), 4),
        "food_false_block_rate": round(sum(is_blocked(row) for row in food) / len(food), 4),
        "non_food_block_recall": round(sum(is_blocked(row) for row in non_food) / len(non_food), 4),
        "p50_latency_ms": _percentile(latencies, 0.50),
        "p95_latency_ms": _percentile(latencies, 0.95),
    }


def _paths(root: Path, label: str) -> list[Path]:
    folder = root / label
    return sorted(
        path for path in folder.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    ) if folder.is_dir() else []


def run_benchmark(*, root: Path, min_per_label: int, settings: FoodGateSettings) -> dict[str, Any]:
    food_paths = _paths(root, "food")
    non_food_paths = _paths(root, "non_food")
    if len(food_paths) < min_per_label or len(non_food_paths) < min_per_label:
        raise ValueError(
            f"Cần ít nhất {min_per_label} ảnh mỗi nhãn; hiện food={len(food_paths)}, non_food={len(non_food_paths)}"
        )

    predictor = FoodGatePredictor.load(settings)
    rows: list[dict[str, float | str]] = []
    for expected, paths in (("food", food_paths), ("non_food", non_food_paths)):
        for path in paths:
            with Image.open(path) as opened:
                image = opened.convert("RGB")
            started = time.perf_counter()
            prediction = predictor.predict(image)
            rows.append({
                "image": str(path.relative_to(root)),
                "expected": expected,
                "food_score": prediction.food_score,
                "non_food_score": prediction.non_food_score,
                "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            })
    return {
        "schema_version": 1,
        "root": str(root),
        "block_threshold": settings.block_threshold,
        "summary": summarize_predictions(rows, block_threshold=settings.block_threshold),
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--min-per-label", type=int, default=100)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.min_per_label < 1:
        raise ValueError("--min-per-label must be positive")
    report = run_benchmark(
        root=args.root,
        min_per_label=args.min_per_label,
        settings=FoodGateSettings(),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(f"Report: {args.output}")


if __name__ == "__main__":
    main()
