"""Crawl a separate, raw Food Gate benchmark; all downloaded labels need review."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

import imagehash

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.build_new_dish_classes import select_survivors_fast  # noqa: E402
from scripts.build_reference_album import collect_blocked_hashes  # noqa: E402
from scripts.build_test_split import IMAGE_EXTENSIONS, save_survivors  # noqa: E402
from scripts.fill_siglip_food_v1 import crawl_bing_html  # noqa: E402

DEFAULT_ROOT = PROJECT_ROOT / "data" / "images" / "food_gate_real_eval"
QUERY_PLAN = {
    "food": (
        '"phở bò" food',
        '"cơm tấm" food',
        '"bánh mì" food',
        '"bún bò Huế" food',
        '"món ăn Việt Nam"',
        '"vietnamese rice meal" food',
        '"vietnamese noodle soup" food',
        '"vietnamese street food"',
    ),
    "non_food": (
        "green leaves plant photo",
        "waterfall landscape photo",
        "city street car photo",
        "domestic dog portrait photo",
        "person portrait photo",
        "laptop desk photo",
        "beach landscape photo",
        "building architecture photo",
    ),
}
CrawlFunction = Callable[[str, Path, int], None]


def _count(folder: Path) -> int:
    return sum(
        path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
        for path in folder.iterdir()
    ) if folder.is_dir() else 0


def fill_label(
    *, root: Path, label: str, target: int, blocked: list[imagehash.ImageHash], crawl: CrawlFunction
) -> int:
    folder = root / label
    folder.mkdir(parents=True, exist_ok=True)
    blocked.extend(collect_blocked_hashes((folder,)))
    for query in QUERY_PLAN[label]:
        remaining = target - _count(folder)
        if remaining <= 0:
            break
        with tempfile.TemporaryDirectory(prefix=f"food_gate_{label}_") as temporary:
            crawl(query, Path(temporary), max(60, remaining * 2))
            selection = select_survivors_fast(Path(temporary), blocked, limit=remaining)
            save_survivors(selection.accepted, folder, label)
            blocked.extend(collect_blocked_hashes((folder,)))
    return _count(folder)


def run(*, root: Path = DEFAULT_ROOT, target_per_label: int = 100, crawl: CrawlFunction = crawl_bing_html) -> dict[str, int]:
    if target_per_label < 1:
        raise ValueError("target_per_label must be positive")
    root.mkdir(parents=True, exist_ok=True)
    blocked = collect_blocked_hashes((root / "food", root / "non_food"))
    counts = {
        label: fill_label(root=root, label=label, target=target_per_label, blocked=blocked, crawl=crawl)
        for label in ("food", "non_food")
    }
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "purpose": "Food Gate benchmark raw crawl; manual label review required before CV claims.",
                "source": "Bing image search",
                "generated_at": datetime.now(UTC).isoformat(),
                "target_per_label": target_per_label,
                "queries": QUERY_PLAN,
                "counts": counts,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--target-per-label", type=int, default=100)
    args = parser.parse_args()
    print(json.dumps(run(root=args.root, target_per_label=args.target_per_label), ensure_ascii=False))


if __name__ == "__main__":
    main()
