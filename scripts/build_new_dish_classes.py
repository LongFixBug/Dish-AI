"""Add reviewed candidates for new EfficientNet classes without split leakage.

Each requested dish is first collected under ``data/images/new_classes_candidate``
with four disjoint splits. A class is added to the live train/val/test/reference
folders only after it reaches every target. This prevents a half-created class
from breaking the shared class contract used by ``ml.training.train``.

Usage:
    uv run python scripts/build_new_dish_classes.py --apply
    uv run python scripts/build_new_dish_classes.py --classes bo_ne,pha_lau --apply
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
import tempfile
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

import imagehash

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.build_reference_album import (  # noqa: E402
    PHASH_DISTANCE,
    collect_blocked_hashes,
    crawl_bing,
)
from scripts.build_test_split import (  # noqa: E402
    IMAGE_EXTENSIONS,
    hash_directory_images,
    open_verified_image,
    save_survivors,
)
from scripts.download_datasets import is_min_size  # noqa: E402

IMAGE_ROOT = PROJECT_ROOT / "data" / "images"
CANDIDATE_ROOT = IMAGE_ROOT / "new_classes_candidate"
CLASS_NAMES_PATH = PROJECT_ROOT / "data" / "eval" / "class_names.json"
GOLDEN_DIR = IMAGE_ROOT / "golden"

# Class names are intentionally specific enough to be visually distinguishable.
NEW_DISHES = {
    "banh_trang_tron": "Bánh tráng trộn",
    "pha_lau": "Phá lấu",
    "xien_que_chien": "Xiên que chiên",
    "goi_kho_bo": "Gỏi khô bò",
    "sup_cua": "Súp cua",
    "xoi_man": "Xôi mặn",
    "com_ga_xoi_mo": "Cơm gà xối mỡ",
    "bo_ne": "Bò né",
    "chao_suon": "Cháo sườn",
    "rau_muong_xao_toi": "Rau muống xào tỏi",
    "khoai_lang_nuong": "Khoai lang nướng",
    "uc_ga_ap_chao": "Ức gà áp chảo",
    "salad_uc_ga": "Salad ức gà",
    "tra_sua_tran_chau": "Trà sữa trân châu",
    "ca_phe_sua_da": "Cà phê sữa đá",
    "nuoc_mia": "Nước mía",
    "che_khuc_bach": "Chè khúc bạch",
}

SPLIT_TARGETS = {
    # Initial web-crawled cohort. These are deliberately smaller than the
    # curated Hugging Face classes, because val/test/reference must be truly
    # disjoint rather than copies of train. Class-weighted fine-tuning and
    # review-backed feedback will grow them over time.
    "train": 80,
    "val": 20,
    "test": 30,
    "references": 30,
}
DEFAULT_CRAWL_LIMIT = 300
SLEEP_BETWEEN_CLASSES_SECONDS = 2.0

# Alternate names widen image-source coverage without merging visually different
# dishes into one EfficientNet label.
SEARCH_ALIASES = {
    "Trà sữa trân châu": ("bubble tea trân châu", "boba milk tea"),
}

logger = logging.getLogger("build_new_dish_classes")
CrawlFunction = Callable[[str, Path, int], None]


@dataclass(frozen=True)
class ClassResult:
    """Coverage and rejection information for one candidate class."""

    counts: dict[str, int]
    rejected_duplicates: int
    errors: tuple[str, ...]
    targets: Mapping[str, int]

    @property
    def complete(self) -> bool:
        return all(self.counts.get(split, 0) >= total for split, total in self.targets.items())


@dataclass(frozen=True)
class FastSelection:
    """Accepted paths and rejections from an integer pHash comparison."""

    accepted: list[Path]
    rejected_duplicate: int


def _image_count(directory: Path) -> int:
    if not directory.is_dir():
        return 0
    return sum(
        1
        for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )


def _split_dir(root: Path, split: str, slug: str) -> Path:
    return root / split / slug


def class_queries(dish_name: str) -> list[str]:
    """Diversify Bing results instead of repeating one generic food query."""
    queries = [
        f'"{dish_name}" Sài Gòn',
        f'"{dish_name}" món ăn đường phố',
        f'"{dish_name}" quán ăn',
        f'"{dish_name}" food review',
        f'"{dish_name}" món ăn Việt Nam',
        f'"{dish_name}" nhà hàng Việt Nam',
    ]
    queries.extend(
        f'"{alias}" food' for alias in SEARCH_ALIASES.get(dish_name, ())
    )
    return list(dict.fromkeys(queries))


def _hash_as_int(value: imagehash.ImageHash) -> int:
    return int(str(value), 16)


def select_survivors_fast(
    staging: Path,
    blocked_hashes: list[imagehash.ImageHash],
    *,
    limit: int,
    max_distance: int = PHASH_DISTANCE,
) -> FastSelection:
    """Select valid, globally distinct images using integer Hamming distance.

    ``ImageHash.__sub__`` calls NumPy for every pair. With 20k+ already-known
    images that made one class take minutes. Python integer ``bit_count`` keeps
    the identical 64-bit pHash rule while making the comparison inexpensive.
    """
    blocked = [_hash_as_int(item) for item in blocked_hashes]
    accepted: list[Path] = []
    rejected_duplicate = 0
    paths = sorted(
        path
        for path in staging.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )
    for path in paths:
        if len(accepted) >= limit:
            break
        image = open_verified_image(path)
        if image is None or not is_min_size(image):
            continue
        candidate = _hash_as_int(imagehash.phash(image))
        if any((candidate ^ known).bit_count() <= max_distance for known in blocked):
            rejected_duplicate += 1
            continue
        blocked.append(candidate)
        accepted.append(path)
    return FastSelection(accepted=accepted, rejected_duplicate=rejected_duplicate)


def _save_and_register(
    paths: list[Path], class_dir: Path, slug: str, blocked: list[imagehash.ImageHash]
) -> int:
    """Save JPEG survivors and immediately block them for all later splits."""
    added = save_survivors(paths, class_dir, slug)
    for path in paths:
        from PIL import Image

        with Image.open(path) as image:
            blocked.append(imagehash.phash(image))
    return added


def _build_split(
    split: str,
    slug: str,
    dish_name: str,
    candidate_root: Path,
    blocked: list[imagehash.ImageHash],
    *,
    target: int,
    crawl_limit: int,
    crawl: CrawlFunction,
) -> tuple[int, int, tuple[str, ...]]:
    """Fill one split; every accepted image is blocked for future splits."""
    class_dir = _split_dir(candidate_root, split, slug)
    class_dir.mkdir(parents=True, exist_ok=True)
    blocked.extend(hash_directory_images(class_dir))
    count = _image_count(class_dir)
    rejected_duplicates = 0
    errors: list[str] = []

    for query_index, query in enumerate(class_queries(dish_name)):
        if count >= target:
            break
        remaining = target - count
        limit = min(crawl_limit, max(60, remaining * 2))
        with tempfile.TemporaryDirectory(
            prefix=f"new_class_{slug}_{split}_{query_index}_"
        ) as temporary:
            try:
                crawl(query, Path(temporary), limit)
            except Exception as exc:  # noqa: BLE001 - one query must not end a class
                errors.append(f"{split}/{query}: {type(exc).__name__}: {exc}")
                logger.warning("Crawl failed for %s (%s): %s", split, query, exc)
                continue
            selection = select_survivors_fast(
                Path(temporary),
                blocked,
                limit=remaining,
                max_distance=PHASH_DISTANCE,
            )
            rejected_duplicates += selection.rejected_duplicate
            count += _save_and_register(selection.accepted, class_dir, slug, blocked)
    return count, rejected_duplicates, tuple(errors)


def build_class(
    slug: str,
    dish_name: str,
    candidate_root: Path,
    blocked_hashes: list[imagehash.ImageHash],
    *,
    split_targets: Mapping[str, int] = SPLIT_TARGETS,
    crawl_limit: int = DEFAULT_CRAWL_LIMIT,
    crawl: CrawlFunction = crawl_bing,
) -> ClassResult:
    """Create disjoint train/val/test/reference candidates for one new class."""
    counts: dict[str, int] = {}
    rejected_duplicates = 0
    errors: list[str] = []
    for split, target in split_targets.items():
        count, rejected, split_errors = _build_split(
            split,
            slug,
            dish_name,
            candidate_root,
            blocked_hashes,
            target=target,
            crawl_limit=crawl_limit,
            crawl=crawl,
        )
        counts[split] = count
        rejected_duplicates += rejected
        errors.extend(split_errors)
    return ClassResult(
        counts=counts,
        rejected_duplicates=rejected_duplicates,
        errors=tuple(errors),
        targets=split_targets,
    )


def apply_class(
    slug: str,
    candidate_root: Path,
    image_root: Path,
    split_targets: Mapping[str, int] = SPLIT_TARGETS,
) -> None:
    """Move a complete new class into live splits without overwriting files."""
    counts = {
        split: _image_count(_split_dir(candidate_root, split, slug))
        for split in split_targets
    }
    missing = {
        split: count
        for split, count in counts.items()
        if count < split_targets[split]
    }
    if missing:
        raise ValueError(f"Class {slug} chưa đủ ảnh: {missing}")
    destinations = {split: _split_dir(image_root, split, slug) for split in split_targets}
    existing = [str(path) for path in destinations.values() if path.exists()]
    if existing:
        raise FileExistsError(f"Từ chối ghi đè class {slug}: {', '.join(existing)}")
    for split, destination in destinations.items():
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(_split_dir(candidate_root, split, slug)), str(destination))


def is_class_applied(
    slug: str,
    image_root: Path,
    split_targets: Mapping[str, int] = SPLIT_TARGETS,
) -> bool:
    """Return true only when the live dataset has every complete split."""
    return all(
        _image_count(_split_dir(image_root, split, slug)) >= target
        for split, target in split_targets.items()
    )


def applied_dishes(
    dishes: Mapping[str, str],
    image_root: Path,
    split_targets: Mapping[str, int] = SPLIT_TARGETS,
) -> dict[str, str]:
    """Return selected classes that already have every live split.

    A resumed crawl skips classes moved by an earlier run.  Their canonical
    display names still need to be merged into the shared class manifest.
    """
    return {
        slug: dish_name
        for slug, dish_name in dishes.items()
        if is_class_applied(slug, image_root, split_targets)
    }


def merge_class_names(path: Path, additions: Mapping[str, str]) -> None:
    """Merge only successfully applied classes, preserving canonical old labels."""
    current: dict[str, str] = {}
    if path.is_file():
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError(f"{path} phải là JSON object")
        current = {str(key): str(value) for key, value in raw.items()}
    merged = dict(sorted({**additions, **current}.items()))
    path.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def _selected_dishes(raw: str | None) -> dict[str, str]:
    if not raw:
        return NEW_DISHES
    requested = {part.strip() for part in raw.split(",") if part.strip()}
    unknown = sorted(requested - set(NEW_DISHES))
    if unknown:
        raise ValueError(f"Class không hỗ trợ: {', '.join(unknown)}")
    return {slug: NEW_DISHES[slug] for slug in sorted(requested)}


def _blocked_roots(candidate_root: Path) -> tuple[Path, ...]:
    return (
        IMAGE_ROOT / "train",
        IMAGE_ROOT / "val",
        IMAGE_ROOT / "test",
        IMAGE_ROOT / "references",
        GOLDEN_DIR,
        candidate_root,
    )


def run(
    *,
    candidate_root: Path,
    classes: str | None,
    crawl_limit: int,
    apply: bool,
) -> int:
    """Build classes serially and apply only complete ones when requested."""
    if crawl_limit < 1:
        raise ValueError("--crawl-limit phải >= 1")
    dishes = _selected_dishes(classes)
    blocked = collect_blocked_hashes(_blocked_roots(candidate_root))
    print(f"🔎 Đã nạp {len(blocked)} pHash để chống leakage.")
    applied: dict[str, str] = {}
    incomplete: dict[str, dict[str, int]] = {}

    for index, (slug, dish_name) in enumerate(dishes.items(), start=1):
        print(f"[{index}/{len(dishes)}] {dish_name}")
        if is_class_applied(slug, IMAGE_ROOT):
            print("   ℹ️ Đã có đủ bốn split, bỏ qua")
            continue
        result = build_class(
            slug,
            dish_name,
            candidate_root,
            blocked,
            crawl_limit=crawl_limit,
        )
        print(f"   {result.counts} | loại trùng {result.rejected_duplicates}")
        if result.complete:
            if apply:
                apply_class(slug, candidate_root, IMAGE_ROOT)
                applied[slug] = dish_name
                print("   ✅ Đã nhập vào dataset live")
        else:
            incomplete[slug] = result.counts
            print("   ⚠️ Chưa đủ, giữ trong staging để chạy lại")
        if index < len(dishes):
            time.sleep(SLEEP_BETWEEN_CLASSES_SECONDS)

    if apply:
        merge_class_names(CLASS_NAMES_PATH, applied_dishes(dishes, IMAGE_ROOT))
    if incomplete:
        print(f"\n⚠️ Class chưa đủ: {incomplete}")
    print(f"✅ Đã nhập {len(applied)} class; còn staging {len(incomplete)} class.")
    return 0 if not incomplete else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Crawl lớp món mới cho train/val/test/references không trùng nhau"
    )
    parser.add_argument("--classes", default=None)
    parser.add_argument("--candidate-root", type=Path, default=CANDIDATE_ROOT)
    parser.add_argument("--crawl-limit", type=int, default=DEFAULT_CRAWL_LIMIT)
    parser.add_argument("--apply", action="store_true")
    return parser


def main() -> None:
    logging.basicConfig(level=logging.WARNING)
    args = build_parser().parse_args()
    try:
        exit_code = run(
            candidate_root=args.candidate_root,
            classes=args.classes,
            crawl_limit=args.crawl_limit,
            apply=args.apply,
        )
    except (FileNotFoundError, FileExistsError, ValueError) as exc:
        print(f"❌ {exc}")
        exit_code = 1
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
