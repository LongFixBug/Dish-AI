"""Expand existing dish classes with staged, leakage-safe web-crawled images.

The 46-class dataset already contains all class folders, but the 17 classes
that were kept open-set have much smaller splits.  This command fills only the
shortfall toward the release targets, validates every image, rejects global
pHash duplicates, and moves a class into the live dataset only when all four
splits are complete.

Usage::

    .venv/bin/python scripts/expand_dish_classes.py --apply
    .venv/bin/python scripts/expand_dish_classes.py --classes ha_cao,pho_ga --apply
"""

from __future__ import annotations

import argparse
import html
import json
import logging
import re
import shutil
import sys
import tempfile
import time
import unicodedata
from collections.abc import Callable, Mapping
from pathlib import Path
from threading import Lock

import imagehash

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.build_new_dish_classes import (  # noqa: E402
    class_queries,
    select_survivors_fast,
)
from scripts.build_reference_album import collect_blocked_hashes  # noqa: E402
from scripts.build_test_split import (  # noqa: E402
    IMAGE_EXTENSIONS,
    hash_directory_images,
    save_survivors,
)
from scripts.download_datasets import next_image_path  # noqa: E402

IMAGE_ROOT = PROJECT_ROOT / "data" / "images"
CLASS_NAMES_PATH = PROJECT_ROOT / "data" / "eval" / "class_names.json"
OOD_CLASSES_PATH = PROJECT_ROOT / "data" / "eval" / "efficientnet_ood_classes.json"
CANDIDATE_ROOT = IMAGE_ROOT / "expanded_classes_candidate"

# Targets are deliberately comparable to the current 29-class Tier A data.
EXPANSION_TARGETS: dict[str, int] = {
    "train": 300,
    "val": 60,
    "test": 100,
    "references": 40,
}
# The 29-class Hugging Face seed is already complete enough for Tier A. This
# expansion intentionally follows the legacy Bing crawl recipe for the 17
# smaller/open-set classes and never streams another Hugging Face split.
CRAWL_SOURCE = "bing_legacy_query_pipeline"
DEFAULT_CRAWL_LIMIT = 300
SLEEP_BETWEEN_CLASSES_SECONDS = 2.0
CRAWL_STATE_FILENAME = ".bing_crawl_state.json"

QUERY_ALIASES: dict[str, tuple[str, ...]] = {
    "Bánh tráng trộn": ('"vietnamese rice paper salad"',),
    "Bò né": ('"vietnamese sizzling beef"',),
    "Cháo sườn": ('"vietnamese pork rib congee"',),
    "Chè khúc bạch": ('"vietnamese almond jelly dessert"',),
    "Cơm gà xối mỡ": ('"vietnamese crispy chicken rice"',),
    "Há cảo": ("há cảo hấp", "har gow vietnamese"),
    "Khoai lang nướng": ('"vietnamese grilled sweet potato"',),
    "Nem nướng": ("nem nướng nha trang", "vietnamese grilled pork sausage"),
    "Nước mía": ('"vietnamese sugarcane juice"',),
    "Phá lấu": ('"vietnamese pha lau"',),
    "Phở gà": ("phở gà hà nội", "vietnamese chicken pho"),
    "Súp cua": ('"vietnamese crab soup"',),
    "Cà phê sữa đá": ("vietnamese iced coffee",),
    "Trà sữa trân châu": ("vietnamese bubble tea", "boba milk tea"),
    "Ức gà áp chảo": ('"vietnamese pan seared chicken breast"',),
    "Xiên que chiên": ("vietnamese fried skewers",),
    "Xôi mặn": ('"vietnamese savory sticky rice"',),
}

logger = logging.getLogger("expand_dish_classes")
CrawlFunction = Callable[[str, Path, int], None]
_CRAWL_SEEN_URLS: set[str] = set()
_CRAWL_SEEN_URLS_LOCK = Lock()
_CRAWL_QUERY_OFFSETS: dict[str, int] = {}


def _normalize_search_text(value: str) -> str:
    """Normalize Vietnamese/English metadata for conservative term matching."""
    value = value.replace("đ", "d").replace("Đ", "D")
    return (
        unicodedata.normalize("NFD", value)
        .encode("ascii", "ignore")
        .decode("ascii")
        .lower()
    )


def _query_terms(query: str) -> tuple[str, ...]:
    """Return the dish phrase terms used to reject unrelated Bing results."""
    quoted = re.search(r'"([^"]+)"', query)
    phrase = quoted.group(1) if quoted else query
    return tuple(
        term for term in _normalize_search_text(phrase).split() if term
    )


def parse_bing_image_tasks(
    content: bytes,
    required_terms: tuple[str, ...] = (),
) -> list[dict[str, str]]:
    """Extract relevant original and Bing-thumbnail URLs from one result page."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(content.decode("utf-8", "ignore"), "lxml")
    normalized_terms = tuple(
        term
        for raw_term in required_terms
        for term in _normalize_search_text(raw_term).split()
        if term
    )
    tasks: list[dict[str, str]] = []
    seen_originals: set[str] = set()
    for image_div in soup.find_all("div", class_="imgpt"):
        anchor = image_div.find("a")
        if anchor is None or not anchor.get("m"):
            continue
        try:
            metadata = json.loads(html.unescape(anchor["m"]))
        except (TypeError, json.JSONDecodeError):
            continue
        metadata_text = " ".join(
            str(metadata.get(key, "")) for key in ("t", "desc", "purl")
        )
        normalized_metadata = _normalize_search_text(metadata_text)
        if normalized_terms and not all(
            term in normalized_metadata for term in normalized_terms
        ):
            continue
        original = metadata.get("murl")
        thumbnail = metadata.get("turl")
        if not isinstance(original, str) or not original:
            continue
        if original in seen_originals:
            continue
        seen_originals.add(original)
        task = {"file_url": original}
        if isinstance(thumbnail, str) and thumbnail and thumbnail != original:
            task["fallback_url"] = thumbnail
        tasks.append(task)
    return tasks


def deduplicate_bing_tasks(
    tasks: list[dict[str, str]],
    seen_urls: set[str],
) -> list[dict[str, str]]:
    """Keep only image URLs not attempted by an earlier query in this run."""
    unique: list[dict[str, str]] = []
    for task in tasks:
        url = task.get("file_url")
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        unique.append(task)
    return unique


def next_query_offset(
    query: str,
    page_size: int,
    offsets: dict[str, int],
) -> int:
    """Advance a query to the next Bing page between train/val/test crawls."""
    offset = offsets.get(query, 0)
    offsets[query] = offset + max(1, page_size)
    return offset


def load_query_offsets(path: Path) -> dict[str, int]:
    """Load persisted Bing offsets; malformed state safely starts at zero."""
    if not path.is_file():
        return {}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(value, dict):
        return {}
    return {
        str(query): offset
        for query, offset in value.items()
        if isinstance(query, str) and type(offset) is int and offset >= 0
    }


def save_query_offsets(path: Path, offsets: Mapping[str, int]) -> None:
    """Persist offsets atomically so interrupted crawls can resume later."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(
        json.dumps(dict(sorted(offsets.items())), ensure_ascii=False, indent=2)
        + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def crawl_bing_fast(query: str, destination: Path, limit: int) -> None:
    """Crawl Bing with bounded network retries for bulk dataset expansion.

    ``icrawler.builtin.BingImageCrawler.crawl`` does not expose the parser and
    downloader timeouts, so call the base crawler explicitly.  The default
    icrawler retry policy can spend several minutes on dead image hosts; one
    short attempt gives the next query a chance to provide a usable image.
    """
    from icrawler import Crawler
    from icrawler.builtin import BingImageCrawler
    from icrawler.downloader import ImageDownloader
    from icrawler.parser import Parser

    class BingFallbackParser(Parser):
        def parse(self, response, **kwargs):
            tasks = parse_bing_image_tasks(
                response.content,
                required_terms=kwargs.get("required_terms", ()),
            )
            with _CRAWL_SEEN_URLS_LOCK:
                tasks = deduplicate_bing_tasks(tasks, _CRAWL_SEEN_URLS)
            yield from tasks

    class BingFallbackDownloader(ImageDownloader):
        def download(self, task, default_ext, timeout=5, max_retry=1, **kwargs):
            original_url = task.get("file_url")
            fallback_url = task.get("fallback_url")
            super().download(
                task,
                default_ext,
                timeout,
                max_retry=max_retry,
                **kwargs,
            )
            if task.get("success") or not fallback_url:
                return
            task["file_url"] = fallback_url
            try:
                super().download(
                    task,
                    default_ext,
                    timeout,
                    max_retry=max_retry,
                    **kwargs,
                )
            finally:
                if original_url:
                    task["file_url"] = original_url

    destination.mkdir(parents=True, exist_ok=True)
    with _CRAWL_SEEN_URLS_LOCK:
        offset = next_query_offset(query, limit, _CRAWL_QUERY_OFFSETS)
    crawler = BingImageCrawler(
        parser_cls=BingFallbackParser,
        downloader_cls=BingFallbackDownloader,
        storage={"root_dir": str(destination)},
        parser_threads=3,
        downloader_threads=16,
        log_level=logging.ERROR,
    )
    Crawler.crawl(
        crawler,
        feeder_kwargs={"keyword": query, "offset": offset, "max_num": limit},
        parser_kwargs={
            "req_timeout": 2,
            "max_retry": 1,
            "required_terms": _query_terms(query),
        },
        downloader_kwargs={
            "max_num": limit,
            "req_timeout": 2,
            "max_retry": 1,
            "max_idle_time": 12,
        },
    )


def image_count(directory: Path) -> int:
    """Count direct, supported image files in one split/class folder."""
    if not directory.is_dir():
        return 0
    return sum(
        1
        for path in directory.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )


def missing_counts(
    image_root: Path,
    slug: str,
    targets: Mapping[str, int] = EXPANSION_TARGETS,
) -> dict[str, int]:
    """Return only the shortfall for a live class, never a negative value."""
    return {
        split: max(0, target - image_count(image_root / split / slug))
        for split, target in targets.items()
    }


def _staged_counts(
    candidate_root: Path,
    slug: str,
    targets: Mapping[str, int],
) -> dict[str, int]:
    return {
        split: image_count(candidate_root / split / slug)
        for split in targets
    }


def _queries(dish_name: str) -> list[str]:
    """Add unambiguous Vietnamese/English contexts to the base queries."""
    aliases = QUERY_ALIASES.get(dish_name, ())
    return list(dict.fromkeys([*class_queries(dish_name), *aliases]))


def _build_split(
    *,
    split: str,
    slug: str,
    dish_name: str,
    candidate_root: Path,
    remaining: int,
    blocked: list[imagehash.ImageHash],
    crawl_limit: int,
    crawl: CrawlFunction,
) -> tuple[int, int, tuple[str, ...]]:
    """Crawl one split into staging and register accepted hashes globally."""
    if remaining <= 0:
        return 0, 0, ()

    stage_dir = candidate_root / split / slug
    stage_dir.mkdir(parents=True, exist_ok=True)
    saved = image_count(stage_dir)
    rejected_duplicates = 0
    errors: list[str] = []

    for query_index, query in enumerate(_queries(dish_name)):
        if saved >= remaining:
            break
        needed = remaining - saved
        limit = min(crawl_limit, max(60, needed * 2))
        with tempfile.TemporaryDirectory(
            prefix=f"expand_{slug}_{split}_{query_index}_"
        ) as temporary:
            try:
                crawl(query, Path(temporary), limit)
            except Exception as exc:  # noqa: BLE001 - continue to next query
                errors.append(f"{split}/{query}: {type(exc).__name__}: {exc}")
                logger.warning("Crawl failed for %s (%s): %s", slug, query, exc)
                continue
            selection = select_survivors_fast(
                Path(temporary),
                blocked,
                limit=needed,
            )
            rejected_duplicates += selection.rejected_duplicate
            save_survivors(selection.accepted, stage_dir, slug)
            saved = image_count(stage_dir)
            # Stage images must also be blocked from every later split/class.
            blocked.extend(hash_directory_images(stage_dir))

    return saved, rejected_duplicates, tuple(errors)


def build_missing_class(
    slug: str,
    dish_name: str,
    image_root: Path,
    candidate_root: Path,
    blocked: list[imagehash.ImageHash],
    *,
    targets: Mapping[str, int] = EXPANSION_TARGETS,
    crawl_limit: int = DEFAULT_CRAWL_LIMIT,
    crawl: CrawlFunction = crawl_bing_fast,
) -> tuple[dict[str, int], int, tuple[str, ...]]:
    """Fill a class's live shortfall while keeping downloads in staging."""
    live_missing = missing_counts(image_root, slug, targets)
    staged = _staged_counts(candidate_root, slug, targets)
    rejected_duplicates = 0
    errors: list[str] = []

    for split, target in targets.items():
        current_live = image_count(image_root / split / slug)
        remaining = max(0, target - current_live - staged[split])
        saved, rejected, split_errors = _build_split(
            split=split,
            slug=slug,
            dish_name=dish_name,
            candidate_root=candidate_root,
            remaining=remaining,
            blocked=blocked,
            crawl_limit=crawl_limit,
            crawl=crawl,
        )
        rejected_duplicates += rejected
        errors.extend(split_errors)
        if saved and split in live_missing:
            logger.info("Staged %s/%s: %s new images", split, slug, saved)

    counts = {
        split: image_count(image_root / split / slug)
        + image_count(candidate_root / split / slug)
        for split in targets
    }
    return counts, rejected_duplicates, tuple(errors)


def merge_staged_class(
    candidate_root: Path,
    image_root: Path,
    slug: str,
    targets: Mapping[str, int] = EXPANSION_TARGETS,
) -> dict[str, int]:
    """Append a complete staged class without overwriting existing files."""
    staged_counts = _staged_counts(candidate_root, slug, targets)
    missing = {
        split: target
        - image_count(image_root / split / slug)
        - staged_counts[split]
        for split, target in targets.items()
        if image_count(image_root / split / slug) + staged_counts[split] < target
    }
    if missing:
        raise ValueError(f"Class {slug} chưa đủ ảnh để merge: {missing}")

    merged: dict[str, int] = {}
    for split in targets:
        source_dir = candidate_root / split / slug
        destination_dir = image_root / split / slug
        destination_dir.mkdir(parents=True, exist_ok=True)
        for source in sorted(source_dir.glob("*")) if source_dir.is_dir() else ():
            if not source.is_file() or source.suffix.lower() not in IMAGE_EXTENSIONS:
                continue
            destination = next_image_path(destination_dir, slug, 0)
            shutil.move(str(source), str(destination))
        if source_dir.is_dir() and not any(source_dir.iterdir()):
            source_dir.rmdir()
        merged[split] = image_count(destination_dir)
    return merged


def _load_dishes(classes: str | None) -> dict[str, str]:
    value = json.loads(CLASS_NAMES_PATH.read_text(encoding="utf-8"))
    names = {str(slug): str(name) for slug, name in value.items()}
    if classes:
        requested = {part.strip() for part in classes.split(",") if part.strip()}
    else:
        ood = json.loads(OOD_CLASSES_PATH.read_text(encoding="utf-8"))
        requested = set(ood.get("classes", []))
    unknown = sorted(requested - set(names))
    if unknown:
        raise ValueError(f"Không có tên chuẩn cho class: {', '.join(unknown)}")
    return {slug: names[slug] for slug in sorted(requested)}


def _blocked_roots(candidate_root: Path) -> tuple[Path, ...]:
    return (
        IMAGE_ROOT / "train",
        IMAGE_ROOT / "val",
        IMAGE_ROOT / "test",
        IMAGE_ROOT / "references",
        IMAGE_ROOT / "golden",
        candidate_root,
    )


def run(
    *,
    classes: str | None,
    candidate_root: Path,
    crawl_limit: int,
    apply: bool,
) -> int:
    """Expand selected classes and optionally merge only complete classes."""
    if crawl_limit < 1:
        raise ValueError("--crawl-limit phải >= 1")
    candidate_root.mkdir(parents=True, exist_ok=True)
    state_path = candidate_root / CRAWL_STATE_FILENAME
    with _CRAWL_SEEN_URLS_LOCK:
        _CRAWL_SEEN_URLS.clear()
        _CRAWL_QUERY_OFFSETS.clear()
        _CRAWL_QUERY_OFFSETS.update(load_query_offsets(state_path))
    dishes = _load_dishes(classes)
    blocked = collect_blocked_hashes(_blocked_roots(candidate_root))
    print(f"🔎 Đã nạp {len(blocked)} pHash để chống leakage toàn cục.")

    incomplete: dict[str, dict[str, int]] = {}
    merged = 0
    for index, (slug, dish_name) in enumerate(dishes.items(), start=1):
        print(f"[{index}/{len(dishes)}] {dish_name} ({slug})")
        counts, rejected, errors = build_missing_class(
            slug,
            dish_name,
            IMAGE_ROOT,
            candidate_root,
            blocked,
            crawl_limit=crawl_limit,
        )
        print(f"   counts={counts} | loại duplicate={rejected}")
        if errors:
            print(f"   ⚠️ crawl lỗi: {len(errors)}")
        if all(counts[split] >= target for split, target in EXPANSION_TARGETS.items()):
            if apply:
                result = merge_staged_class(candidate_root, IMAGE_ROOT, slug)
                merged += 1
                print(f"   ✅ merged: {result}")
        else:
            incomplete[slug] = counts
            print("   ⚠️ chưa đủ, giữ trong staging")
        with _CRAWL_SEEN_URLS_LOCK:
            save_query_offsets(state_path, _CRAWL_QUERY_OFFSETS)
        if index < len(dishes):
            time.sleep(SLEEP_BETWEEN_CLASSES_SECONDS)

    if incomplete:
        print(f"\n⚠️ Class chưa đủ: {incomplete}")
    print(f"✅ Đã merge {merged} class; staging: {candidate_root}")
    return 0 if not incomplete else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Crawl bổ sung 46 lớp món, chống leakage và không ghi đè"
    )
    parser.add_argument("--classes", default=None, help="slug phân tách bằng dấu phẩy")
    parser.add_argument("--candidate-root", type=Path, default=CANDIDATE_ROOT)
    parser.add_argument("--crawl-limit", type=int, default=DEFAULT_CRAWL_LIMIT)
    parser.add_argument("--apply", action="store_true")
    return parser


def main() -> None:
    logging.basicConfig(level=logging.WARNING)
    args = build_parser().parse_args()
    raise SystemExit(run(
        classes=args.classes,
        candidate_root=args.candidate_root,
        crawl_limit=args.crawl_limit,
        apply=args.apply,
    ))


if __name__ == "__main__":
    main()
