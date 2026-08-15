"""Đắp đầy data/images/test/ (đang RỖNG) cho 8 lớp CV local.

Giống download_food_images.py: BingImageCrawler với keyword tiếng Việt có
dấu + suffix địa danh để lọc ảnh sai, sleep 5s giữa món tránh rate limit.
Khác biệt quan trọng: ảnh tải về thư mục staging TẠM, validate bằng Pillow
(verify + cạnh nhỏ nhất >= 100px), rồi dedup imagehash.phash (hamming <= 6
→ loại) so với TOÀN BỘ ảnh đã có trong data/images/train/<class>/,
data/images/val/<class>/ và cây data/images/references/ — để chống leakage
train/test. --per-class ảnh đầu tiên sống sót được lưu (JPEG RGB quality
90, tên <slug>_<index>.jpg) vào data/images/test/<class>/.

Usage:
    uv run python scripts/build_test_split.py               # 15 ảnh/lớp
    uv run python scripts/build_test_split.py --per-class 10
"""

import argparse
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

import imagehash
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.download_datasets import (  # noqa: E402
    IMAGE_EXTENSIONS,
    JPEG_QUALITY,
    is_duplicate_phash,
    is_min_size,
    is_quality_photo,
    next_image_path,
)

TRAIN_DIR = PROJECT_ROOT / "data" / "images" / "train"
VAL_DIR = PROJECT_ROOT / "data" / "images" / "val"
REFERENCES_DIR = PROJECT_ROOT / "data" / "images" / "references"
TEST_DIR = PROJECT_ROOT / "data" / "images" / "test"

DEFAULT_PER_CLASS = 15
LEAKAGE_DISTANCE = 6  # chặt hơn mức 4 trong-lớp: thà loại nhầm còn hơn leak
CRAWL_MULTIPLIER = 4  # tải dư vì nhiều ảnh sẽ bị loại (hỏng/nhỏ/trùng)
SLEEP_BETWEEN = 5  # giây giữa món — tránh Bing rate limit

# 8 lớp CV local. Keyword có suffix "việt nam"/địa danh để lọc ảnh sai.
DISHES = {
    "banh_mi_kep_thit": "bánh mì kẹp thịt việt nam",
    "banh_xeo": "bánh xèo việt nam",
    "com_tam": "cơm tấm sài gòn",
    "ha_cao": "há cảo hấp",
    "nem_nuong": "nem nướng nha trang",
    "pho_bo": "phở bò việt nam",
    "pho_ga": "phở gà hà nội",
    "xoi_xeo": "xôi xéo hà nội",
}


def open_verified_image(path: Path) -> Image.Image | None:
    """Mở ảnh sau khi verify; None nếu file hỏng/không phải ảnh."""
    try:
        with Image.open(path) as probe:
            probe.verify()
        image = Image.open(path)
        image.load()
    except Exception:
        return None
    return image


def hash_directory_images(directory: Path) -> list[imagehash.ImageHash]:
    """Tính phash mọi ảnh trong cây thư mục (đệ quy); ảnh hỏng bỏ qua."""
    if not directory.is_dir():
        return []
    hashes: list[imagehash.ImageHash] = []
    for path in sorted(directory.rglob("*")):
        if not (path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS):
            continue
        try:
            with Image.open(path) as image:
                hashes.append(imagehash.phash(image))
        except Exception:
            continue
    return hashes


def collect_known_hashes(
    slug: str,
    reference_hashes: list[imagehash.ImageHash],
    train_dir: Path = TRAIN_DIR,
    val_dir: Path = VAL_DIR,
) -> list[imagehash.ImageHash]:
    """Gom phash của train/<slug>, val/<slug> và toàn bộ references."""
    return [
        *hash_directory_images(train_dir / slug),
        *hash_directory_images(val_dir / slug),
        *reference_hashes,
    ]


@dataclass(frozen=True)
class SelectionResult:
    """Kết quả lọc staging: ảnh được nhận + số ảnh loại theo lý do."""

    accepted: list[Path]
    rejected_invalid: int
    rejected_small: int
    rejected_duplicate: int


def select_survivors(
    staging_dir: Path,
    known_hashes: list[imagehash.ImageHash],
    per_class: int,
    max_distance: int = LEAKAGE_DISTANCE,
) -> SelectionResult:
    """Chọn per_class ảnh đầu tiên qua được validate + dedup chống leakage."""
    seen = list(known_hashes)
    accepted: list[Path] = []
    rejected_invalid = rejected_small = rejected_duplicate = 0
    candidates = sorted(
        path
        for path in staging_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )
    for path in candidates:
        if len(accepted) >= per_class:
            break
        image = open_verified_image(path)
        if image is None:
            rejected_invalid += 1
            continue
        if not (is_min_size(image) and is_quality_photo(image)):
            rejected_small += 1
            continue
        candidate = imagehash.phash(image)
        if is_duplicate_phash(candidate, seen, max_distance):
            rejected_duplicate += 1
            continue
        seen.append(candidate)  # dedup luôn giữa các ảnh test với nhau
        accepted.append(path)
    return SelectionResult(
        accepted, rejected_invalid, rejected_small, rejected_duplicate
    )


def save_survivors(paths: list[Path], class_dir: Path, slug: str) -> int:
    """Lưu ảnh sống sót về JPEG RGB quality 90: <slug>_<index>.jpg."""
    class_dir.mkdir(parents=True, exist_ok=True)
    saved = 0
    for path in paths:
        target = next_image_path(class_dir, slug, saved)
        with Image.open(path) as image:
            image.convert("RGB").save(target, "JPEG", quality=JPEG_QUALITY)
        saved += 1
    return saved


def crawl_class(keyword: str, staging_dir: Path, max_num: int) -> None:
    """Tải ảnh Bing vào staging. Import icrawler TRONG hàm để test offline."""
    from icrawler.builtin import BingImageCrawler

    crawler = BingImageCrawler(
        storage={"root_dir": str(staging_dir)},
        downloader_threads=4,
    )
    crawler.crawl(keyword=keyword, max_num=max_num)


def fill_class(
    slug: str,
    keyword: str,
    per_class: int,
    reference_hashes: list[imagehash.ImageHash],
) -> SelectionResult:
    """Crawl → validate → dedup → lưu ảnh test cho một lớp."""
    with tempfile.TemporaryDirectory(prefix=f"test_split_{slug}_") as staging:
        staging_dir = Path(staging)
        crawl_class(keyword, staging_dir, per_class * CRAWL_MULTIPLIER)
        known_hashes = collect_known_hashes(slug, reference_hashes)
        result = select_survivors(staging_dir, known_hashes, per_class)
        save_survivors(result.accepted, TEST_DIR / slug, slug)
    return result


def run(per_class: int) -> None:
    """Chạy tuần tự 8 lớp, in accepted/rejected mỗi lớp + tổng kết."""
    print(f"Tính phash references tại {REFERENCES_DIR} ...")
    reference_hashes = hash_directory_images(REFERENCES_DIR)
    print(f"→ {len(reference_hashes)} hash references dùng chống leakage.\n")
    total_accepted = 0
    for index, (slug, keyword) in enumerate(DISHES.items()):
        print(f"[{index + 1}/{len(DISHES)}] Đang tải: {keyword} → {slug}")
        try:
            result = fill_class(slug, keyword, per_class, reference_hashes)
        except Exception as exc:  # noqa: BLE001 — một lớp fail không chặn lớp khác
            print(f"  ❌ Lỗi lớp {slug}: {exc}")
            continue
        total_accepted += len(result.accepted)
        print(
            f"  ✅ nhận {len(result.accepted)} | loại: hỏng "
            f"{result.rejected_invalid}, nhỏ {result.rejected_small}, "
            f"trùng {result.rejected_duplicate}"
        )
        if index < len(DISHES) - 1:
            time.sleep(SLEEP_BETWEEN)
    print(f"\n✅ Xong! Tổng {total_accepted} ảnh test trong {TEST_DIR}")


def build_parser() -> argparse.ArgumentParser:
    """CLI: số ảnh test mỗi lớp."""
    parser = argparse.ArgumentParser(
        description="Crawl + dedup ảnh test cho 8 lớp CV local (chống leakage)"
    )
    parser.add_argument(
        "--per-class", type=int, default=DEFAULT_PER_CLASS,
        help=f"Số ảnh test mỗi lớp (mặc định {DEFAULT_PER_CLASS})",
    )
    return parser


def main() -> None:
    """Parse CLI rồi chạy toàn bộ pipeline crawl-lọc-lưu."""
    arguments = build_parser().parse_args()
    run(arguments.per_class)


if __name__ == "__main__":
    main()
