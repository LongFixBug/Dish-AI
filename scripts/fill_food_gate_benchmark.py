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
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

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
IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp"})
PHASH_DISTANCE = 4


def _verified_hash(path: Path) -> imagehash.ImageHash | None:
    try:
        with Image.open(path) as image:
            image.verify()
        with Image.open(path) as image:
            return imagehash.phash(image.convert("RGB"))
    except (OSError, ValueError):
        return None


def collect_blocked_hashes(folders: tuple[Path, ...]) -> list[imagehash.ImageHash]:
    """Read only valid local images to prevent duplicate benchmark samples."""

    hashes: list[imagehash.ImageHash] = []
    for folder in folders:
        if not folder.is_dir():
            continue
        for path in folder.iterdir():
            if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
                image_hash = _verified_hash(path)
                if image_hash is not None:
                    hashes.append(image_hash)
    return hashes


def select_survivors_fast(
    staging: Path,
    blocked_hashes: list[imagehash.ImageHash],
    *,
    limit: int,
) -> list[Path]:
    """Keep valid images whose perceptual hash differs from known samples."""

    known = [int(str(item), 16) for item in blocked_hashes]
    accepted: list[Path] = []
    for path in sorted(staging.rglob("*")):
        if len(accepted) >= limit:
            break
        if not path.is_file() or path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        image_hash = _verified_hash(path)
        if image_hash is None:
            continue
        value = int(str(image_hash), 16)
        if any((value ^ existing).bit_count() <= PHASH_DISTANCE for existing in known):
            continue
        accepted.append(path)
        known.append(value)
    return accepted


def save_survivors(paths: list[Path], destination: Path, label: str) -> None:
    for offset, path in enumerate(paths, start=_count(destination)):
        suffix = path.suffix.lower() if path.suffix.lower() in IMAGE_EXTENSIONS else ".jpg"
        target = destination / f"{label}_{offset:04d}{suffix}"
        target.write_bytes(path.read_bytes())


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
            save_survivors(selection, folder, label)
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
