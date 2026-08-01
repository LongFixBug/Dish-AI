"""Crawl a reference album that is disjoint from every evaluation split.

The crawler writes to ``data/images/references_candidate`` first. Images are
decoded with Pillow, must have a minimum side of 100 px, and are rejected when
their perceptual hash is within distance 6 of anything in train/val/test,
golden, the old references album, or the candidate album itself.

The existing album is never overwritten in place. ``--promote`` is accepted
only after every train class has ``--per-class`` valid images; the previous
album is moved to ``data/images/reference_backups/<timestamp>``.

Usage:
    uv run python scripts/build_reference_album.py --per-class 40
    uv run python scripts/build_reference_album.py --per-class 40 --promote
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
import tempfile
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import imagehash

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.build_test_split import (  # noqa: E402
    IMAGE_EXTENSIONS,
    hash_directory_images,
    save_survivors,
    select_survivors,
)

IMAGE_ROOT = PROJECT_ROOT / "data" / "images"
TRAIN_DIR = IMAGE_ROOT / "train"
VAL_DIR = IMAGE_ROOT / "val"
TEST_DIR = IMAGE_ROOT / "test"
GOLDEN_DIR = IMAGE_ROOT / "golden"
REFERENCES_DIR = IMAGE_ROOT / "references"
CANDIDATE_DIR = IMAGE_ROOT / "references_candidate"
BACKUP_ROOT = IMAGE_ROOT / "reference_backups"
CLASS_NAMES_PATH = PROJECT_ROOT / "data" / "eval" / "class_names.json"

DEFAULT_PER_CLASS = 40
DEFAULT_CRAWL_LIMIT = 80
PHASH_DISTANCE = 6
SLEEP_BETWEEN_CLASSES_SECONDS = 2.0

logger = logging.getLogger("build_reference_album")
CrawlFunction = Callable[[str, Path, int], None]


@dataclass(frozen=True)
class ClassBuildResult:
    """Final count and rejection totals for one dish class."""

    saved: int
    rejected_invalid: int
    rejected_small: int
    rejected_duplicate: int
    errors: tuple[str, ...]


@dataclass(frozen=True)
class AlbumAudit:
    """Coverage check performed before an album can be promoted."""

    counts: dict[str, int]
    required_per_class: int

    @property
    def complete(self) -> bool:
        return bool(self.counts) and all(
            count >= self.required_per_class for count in self.counts.values()
        )


def load_target_dishes(train_dir: Path, mapping_path: Path) -> dict[str, str]:
    """Use train folders as the canonical closed-set class contract."""
    if not train_dir.is_dir():
        raise FileNotFoundError(f"Không tìm thấy train directory: {train_dir}")
    mapping: dict[str, str] = {}
    if mapping_path.is_file():
        value = json.loads(mapping_path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError(f"{mapping_path} phải là JSON object")
        mapping = {str(key): str(name) for key, name in value.items()}
    slugs = sorted(path.name for path in train_dir.iterdir() if path.is_dir())
    if not slugs:
        raise ValueError(f"Không có class folder trong {train_dir}")
    return {
        slug: mapping.get(slug, slug.replace("_", " ").capitalize())
        for slug in slugs
    }


def collect_blocked_hashes(roots: Iterable[Path]) -> list[imagehash.ImageHash]:
    """Build one global registry so duplicates cannot cross class labels."""
    hashes: list[imagehash.ImageHash] = []
    for root in roots:
        hashes.extend(hash_directory_images(root))
    return hashes


def build_queries(dish_name: str) -> list[str]:
    """Return multiple Vietnamese search contexts for source diversity."""
    return [
        f'"{dish_name}" món ăn Việt Nam',
        f'"{dish_name}" nhà hàng Việt Nam',
        f'"{dish_name}" đặc sản Việt Nam',
    ]


def crawl_bing(query: str, destination: Path, limit: int) -> None:
    """Download one query lazily so unit tests stay network-free."""
    from icrawler.builtin import BingImageCrawler

    destination.mkdir(parents=True, exist_ok=True)
    crawler = BingImageCrawler(
        storage={"root_dir": str(destination)},
        downloader_threads=4,
    )
    crawler.crawl(keyword=query, max_num=limit)


def _image_count(directory: Path) -> int:
    if not directory.is_dir():
        return 0
    return sum(
        1
        for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )


def build_class(
    slug: str,
    dish_name: str,
    output_root: Path,
    blocked_hashes: list[imagehash.ImageHash],
    *,
    per_class: int,
    crawl_limit: int,
    crawl: CrawlFunction = crawl_bing,
) -> ClassBuildResult:
    """Crawl one class and save only globally unique, valid survivors."""
    class_dir = output_root / slug
    class_dir.mkdir(parents=True, exist_ok=True)
    existing_hashes = hash_directory_images(class_dir)
    blocked_hashes.extend(existing_hashes)
    saved = _image_count(class_dir)
    rejected_invalid = rejected_small = rejected_duplicate = 0
    errors: list[str] = []

    for query_index, query in enumerate(build_queries(dish_name)):
        if saved >= per_class:
            break
        with tempfile.TemporaryDirectory(
            prefix=f"reference_{slug}_{query_index}_"
        ) as temporary:
            staging = Path(temporary)
            try:
                crawl(query, staging, crawl_limit)
            except Exception as exc:  # noqa: BLE001 - try the next query
                errors.append(f"{query}: {type(exc).__name__}: {exc}")
                logger.warning("Crawl failed for %s: %s", query, exc)
                continue
            result = select_survivors(
                staging,
                blocked_hashes,
                per_class=per_class - saved,
                max_distance=PHASH_DISTANCE,
            )
            rejected_invalid += result.rejected_invalid
            rejected_small += result.rejected_small
            rejected_duplicate += result.rejected_duplicate
            added = save_survivors(result.accepted, class_dir, slug)
            saved += added
            for path in result.accepted:
                from PIL import Image

                with Image.open(path) as image:
                    blocked_hashes.append(imagehash.phash(image))

    return ClassBuildResult(
        saved=saved,
        rejected_invalid=rejected_invalid,
        rejected_small=rejected_small,
        rejected_duplicate=rejected_duplicate,
        errors=tuple(errors),
    )


def audit_candidate(
    root: Path, classes: Iterable[str], *, per_class: int
) -> AlbumAudit:
    """Count every expected class; absent folders count as zero."""
    counts = {slug: _image_count(root / slug) for slug in sorted(classes)}
    return AlbumAudit(counts=counts, required_per_class=per_class)


def promote_candidate(
    candidate: Path,
    target: Path,
    backup_root: Path,
    timestamp: str,
) -> Path:
    """Swap albums through a recoverable backup, never delete the old one."""
    if not candidate.is_dir():
        raise FileNotFoundError(f"Candidate album không tồn tại: {candidate}")
    backup = backup_root / f"references_{timestamp}"
    if backup.exists():
        raise FileExistsError(f"Backup đã tồn tại: {backup}")
    backup_root.mkdir(parents=True, exist_ok=True)
    if target.exists():
        shutil.move(str(target), str(backup))
    shutil.move(str(candidate), str(target))
    return backup


def _selected_dishes(
    dishes: dict[str, str], requested: str | None
) -> dict[str, str]:
    if not requested:
        return dishes
    selected = {part.strip() for part in requested.split(",") if part.strip()}
    unknown = sorted(selected - set(dishes))
    if unknown:
        raise ValueError(f"Class không có trong train: {', '.join(unknown)}")
    return {slug: dishes[slug] for slug in sorted(selected)}


def run(
    *,
    per_class: int,
    crawl_limit: int,
    candidate_dir: Path,
    requested_classes: str | None,
    promote: bool,
) -> int:
    """Build/resume the candidate album and optionally promote it."""
    if per_class < 1 or crawl_limit < 1:
        raise ValueError("--per-class và --crawl-limit phải >= 1")
    all_dishes = load_target_dishes(TRAIN_DIR, CLASS_NAMES_PATH)
    dishes = _selected_dishes(all_dishes, requested_classes)
    blocked_roots = (
        TRAIN_DIR,
        VAL_DIR,
        TEST_DIR,
        GOLDEN_DIR,
        REFERENCES_DIR,
        candidate_dir,
    )
    print("🔎 Đang tính pHash của train/val/test/golden/references...")
    blocked = collect_blocked_hashes(blocked_roots)
    print(f"   Đã chặn {len(blocked)} ảnh nguồn/candidate.")

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
        print(
            f"   giữ {result.saved}/{per_class} | loại hỏng "
            f"{result.rejected_invalid}, nhỏ {result.rejected_small}, "
            f"trùng {result.rejected_duplicate}"
        )
        if result.errors:
            print(f"   ⚠️ {len(result.errors)} truy vấn crawl lỗi")
        if index < len(dishes):
            time.sleep(SLEEP_BETWEEN_CLASSES_SECONDS)

    audit = audit_candidate(candidate_dir, all_dishes, per_class=per_class)
    underfilled = {
        slug: count for slug, count in audit.counts.items() if count < per_class
    }
    print(f"\n📊 Candidate: {sum(audit.counts.values())} ảnh/{len(audit.counts)} lớp")
    if underfilled:
        print(f"⚠️ Chưa đủ: {underfilled}")
    if not promote:
        print(f"ℹ️ Chưa thay album cũ. Candidate nằm tại {candidate_dir}")
        return 0 if audit.complete else 1
    if requested_classes:
        raise ValueError("Không được --promote khi chỉ crawl một phần --classes")
    if not audit.complete:
        raise ValueError("Candidate chưa đủ mọi class; từ chối thay references")
    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup = promote_candidate(candidate_dir, REFERENCES_DIR, BACKUP_ROOT, timestamp)
    print(f"✅ Đã thay references; album cũ được giữ tại {backup}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Crawl album references mới, chống leakage xuyên mọi split"
    )
    parser.add_argument("--per-class", type=int, default=DEFAULT_PER_CLASS)
    parser.add_argument("--crawl-limit", type=int, default=DEFAULT_CRAWL_LIMIT)
    parser.add_argument("--candidate-dir", type=Path, default=CANDIDATE_DIR)
    parser.add_argument("--classes", default=None)
    parser.add_argument("--promote", action="store_true")
    return parser


def main() -> None:
    logging.basicConfig(level=logging.WARNING)
    args = build_parser().parse_args()
    try:
        exit_code = run(
            per_class=args.per_class,
            crawl_limit=args.crawl_limit,
            candidate_dir=args.candidate_dir,
            requested_classes=args.classes,
            promote=args.promote,
        )
    except (FileNotFoundError, FileExistsError, ValueError) as exc:
        print(f"❌ {exc}")
        exit_code = 1
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
