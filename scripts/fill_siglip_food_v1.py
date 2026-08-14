"""Crawl directly into the isolated SigLIP food-v1 train/val/test splits.

The script never touches the shared ``data/images/{train,val,test}`` dataset.
It keeps all downloaded images pHash-distinct across the three SigLIP splits,
so the existing held-out test images remain held out.

Usage:
    uv run python scripts/fill_siglip_food_v1.py --classes hu_tieu,bun_bo_hue,chao_long
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

import imagehash

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.build_new_dish_classes import ClassResult, build_class
from scripts.build_reference_album import collect_blocked_hashes
from scripts.expand_dish_classes import _query_terms, parse_bing_image_tasks

DEFAULT_ROOT = PROJECT_ROOT / "data" / "images" / "siglip_food_v1"
DEFAULT_TARGETS = {"train": 60, "val": 15, "test": 130}
DISHES = {
    "banh_canh": "Bánh canh",
    "hu_tieu": "Hủ tiếu",
    "bun_bo_hue": "Bún bò Huế",
    "pho_bo": "Phở bò",
    "chao_long": "Cháo lòng",
}
CrawlFunction = Callable[[str, Path, int], None]


def crawl_bing_html(query: str, destination: Path, limit: int) -> None:
    """Download one Bing result page without the unstable legacy crawler."""
    search_url = "https://www.bing.com/images/search?" + urlencode(
        {"q": query, "first": 1, "count": min(limit, 35), "form": "HDRSC2"}
    )
    request = Request(search_url, headers={"User-Agent": "FoodAI/0.1 dataset review"})
    with urlopen(request, timeout=20) as response:  # noqa: S310 - fixed Bing endpoint
        tasks = parse_bing_image_tasks(
            response.read(), required_terms=_query_terms(query)
        )

    destination.mkdir(parents=True, exist_ok=True)
    downloaded = 0
    for task in tasks:
        if downloaded >= limit:
            break
        urls = [task.get("file_url"), task.get("fallback_url")]
        for image_url in urls:
            if not image_url:
                continue
            try:
                encoded_image_url = quote(image_url, safe=":/?&=%#;,+")
                image_request = Request(
                    encoded_image_url,
                    headers={"User-Agent": "FoodAI/0.1 dataset review"},
                )
                with urlopen(image_request, timeout=10) as response:  # noqa: S310 - Bing result
                    data = response.read()
                if len(data) < 1024:
                    continue
                (destination / f"bing_{downloaded:04d}.jpg").write_bytes(data)
                downloaded += 1
                break
            except OSError:
                continue


def _selected_dishes(raw: str | None) -> dict[str, str]:
    if not raw:
        return dict(DISHES)
    slugs = {value.strip() for value in raw.split(",") if value.strip()}
    unknown = sorted(slugs - DISHES.keys())
    if unknown:
        raise ValueError(f"Class không hỗ trợ: {', '.join(unknown)}")
    return {slug: DISHES[slug] for slug in sorted(slugs)}


def run(
    *,
    root: Path = DEFAULT_ROOT,
    dishes: Mapping[str, str] = DISHES,
    targets: Mapping[str, int] = DEFAULT_TARGETS,
    crawl_limit: int = 100,
    crawl: CrawlFunction = crawl_bing_html,
) -> dict[str, ClassResult]:
    """Fill only missing images directly in this versioned dataset."""
    required_splits = ("train", "val", "test")
    if set(targets) != set(required_splits) or any(
        not isinstance(value, int) or value < 1 for value in targets.values()
    ):
        raise ValueError("targets phải có train, val, test với số ảnh dương")
    if crawl_limit < 1:
        raise ValueError("crawl_limit phải lớn hơn 0")

    root.mkdir(parents=True, exist_ok=True)
    blocked: list[imagehash.ImageHash] = collect_blocked_hashes(
        root / split for split in required_splits
    )
    results: dict[str, ClassResult] = {}
    for slug, dish_name in dishes.items():
        results[slug] = build_class(
            slug,
            dish_name,
            root,
            blocked,
            split_targets=targets,
            crawl_limit=crawl_limit,
            crawl=crawl,
        )
    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Crawl trực tiếp vào data/images/siglip_food_v1"
    )
    parser.add_argument("--classes", default=None)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--train-target", type=int, default=DEFAULT_TARGETS["train"])
    parser.add_argument("--val-target", type=int, default=DEFAULT_TARGETS["val"])
    parser.add_argument("--test-target", type=int, default=DEFAULT_TARGETS["test"])
    parser.add_argument("--crawl-limit", type=int, default=100)
    args = parser.parse_args()

    results = run(
        root=args.root,
        dishes=_selected_dishes(args.classes),
        targets={
            "train": args.train_target,
            "val": args.val_target,
            "test": args.test_target,
        },
        crawl_limit=args.crawl_limit,
    )
    print(
        json.dumps(
            {
                slug: {
                    "counts": result.counts,
                    "duplicates": result.rejected_duplicates,
                    "errors": result.errors,
                }
                for slug, result in results.items()
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
