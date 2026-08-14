"""Crawl public image-search candidates for the requested product classes.

The crawler writes only to ``data/images/references_candidate``.  It reuses the
existing validation and pHash de-duplication pipeline, so downloaded images are
still candidate data and require human label/provenance review before indexing.

Usage:
    uv run python scripts/crawl_candidate_reference_classes.py
    uv run python scripts/crawl_candidate_reference_classes.py --per-class 50
    uv run python scripts/crawl_candidate_reference_classes.py --classes pizza,sua_milo
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Iterable
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.build_reference_album import (  # noqa: E402
    CANDIDATE_DIR,
    GOLDEN_DIR,
    REFERENCES_DIR,
    TEST_DIR,
    TRAIN_DIR,
    VAL_DIR,
    build_class,
    collect_blocked_hashes,
)

CLASS_NAMES_PATH = PROJECT_ROOT / "data" / "eval" / "class_names.json"

REQUESTED_CLASS_SLUGS = (
    "banh_kem",
    "banh_mi_khong",
    "chocolate",
    "coca_cola",
    "com_trang",
    "ga_ran",
    "hamburger",
    "khoai_luoc",
    "pizza",
    "sau_rieng",
    "sua_milo",
    "tra_sua",
    "tra_trai_cay",
    "trung_chien",
    "trung_luoc",
    "uc_ga",
    "xoi_man",
    "xuc_xich_nuong",
)

DEFAULT_PER_CLASS = 50
DEFAULT_CRAWL_LIMIT = 80
DEFAULT_SLEEP_SECONDS = 2.0


def load_target_dishes(
    mapping_path: Path, slugs: Iterable[str]
) -> dict[str, str]:
    """Resolve selected slugs to the canonical display names."""
    value = json.loads(mapping_path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{mapping_path} phải là JSON object")
    selected = tuple(sorted(set(slugs)))
    missing = [slug for slug in selected if slug not in value]
    if missing:
        raise ValueError(f"Thiếu tên hiển thị cho class: {', '.join(missing)}")
    return {slug: str(value[slug]) for slug in selected}


def select_classes(raw: str | None) -> tuple[str, ...]:
    """Return all requested classes or a validated comma-separated subset."""
    if not raw:
        return tuple(sorted(REQUESTED_CLASS_SLUGS))
    requested = {part.strip() for part in raw.split(",") if part.strip()}
    unknown = sorted(requested - set(REQUESTED_CLASS_SLUGS))
    if unknown:
        raise ValueError(f"Class không hỗ trợ: {', '.join(unknown)}")
    return tuple(sorted(requested))


def _blocked_roots(candidate_dir: Path) -> tuple[Path, ...]:
    return (
        TRAIN_DIR,
        VAL_DIR,
        TEST_DIR,
        GOLDEN_DIR,
        REFERENCES_DIR,
        candidate_dir,
    )


def run(
    *,
    per_class: int = DEFAULT_PER_CLASS,
    crawl_limit: int = DEFAULT_CRAWL_LIMIT,
    sleep_seconds: float = DEFAULT_SLEEP_SECONDS,
    candidate_dir: Path = CANDIDATE_DIR,
    requested_classes: str | None = None,
) -> dict[str, int]:
    """Crawl and de-duplicate the selected classes into the candidate album."""
    if per_class < 1 or crawl_limit < 1 or sleep_seconds < 0:
        raise ValueError("per-class/crawl-limit phải >= 1 và sleep phải >= 0")
    selected = select_classes(requested_classes)
    dishes = load_target_dishes(CLASS_NAMES_PATH, selected)
    candidate_dir.mkdir(parents=True, exist_ok=True)
    blocked = collect_blocked_hashes(_blocked_roots(candidate_dir))
    counts: dict[str, int] = {}

    for index, (slug, dish_name) in enumerate(dishes.items(), start=1):
        print(f"[{index}/{len(dishes)}] {dish_name} → {slug}")
        result = build_class(
            slug,
            dish_name,
            candidate_dir,
            blocked,
            per_class=per_class,
            crawl_limit=crawl_limit,
        )
        counts[slug] = result.saved
        print(
            f"  giữ {result.saved}/{per_class} | loại hỏng "
            f"{result.rejected_invalid}, nhỏ {result.rejected_small}, "
            f"trùng {result.rejected_duplicate}"
        )
        if result.errors:
            print(f"  ⚠️ {len(result.errors)} truy vấn crawl lỗi")
        if index < len(dishes) and sleep_seconds:
            time.sleep(sleep_seconds)

    print(f"\nCandidate đã nhận {sum(counts.values())} ảnh/{len(counts)} lớp")
    print(f"Thư mục: {candidate_dir}")
    return counts


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Crawl ảnh public vào reference candidate, không đụng runtime"
    )
    parser.add_argument("--per-class", type=int, default=DEFAULT_PER_CLASS)
    parser.add_argument("--crawl-limit", type=int, default=DEFAULT_CRAWL_LIMIT)
    parser.add_argument("--sleep", type=float, default=DEFAULT_SLEEP_SECONDS)
    parser.add_argument("--classes", default=None)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        run(
            per_class=args.per_class,
            crawl_limit=args.crawl_limit,
            sleep_seconds=args.sleep,
            requested_classes=args.classes,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"❌ {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
