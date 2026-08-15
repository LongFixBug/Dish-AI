"""Seed album ảnh tham chiếu + golden set từ mirror Hugging Face của 30VNFoods.

Dataset: TuyenTrungLe/vietnamese_food_images (25.136 ảnh, 30 lớp, split
train/validation/test). Dùng streaming=True nên KHÔNG BAO GIỜ tải trọn
4.5GB — chỉ đọc từng ảnh tới khi mọi lớp đủ số lượng cần rồi dừng.

- split "train" → data/images/references/<class_slug>/ (mặc định 40 ảnh/lớp)
- split "test"  → data/images/golden/<class_slug>/     (mặc định 15 ảnh/lớp)
- --training-splits → data/images/vn30/{train,val,test}/ cho fine-tune local,
  giữ nguyên album references, golden và dataset CV cũ.
- data/eval/class_names.json được merge thêm cặp slug → tên món hiển thị
  (giữ nguyên key đã có, key sort).

Ảnh lưu JPEG quality 90, RGB, tên <slug>_<index>.jpg. Bỏ ảnh nhỏ hơn
100px một cạnh. Dedup trong từng lớp bằng imagehash.phash (hamming <= 4
coi là trùng). Chạy lại an toàn: ảnh đã có được đếm vào cap và được nạp
vào registry dedup.

Usage:
    uv run python scripts/download_datasets.py
    uv run python scripts/download_datasets.py --refs-per-class 40 --golden-per-class 15
    uv run python scripts/download_datasets.py --classes pho_bo,banh_xeo
    uv run python scripts/download_datasets.py --training-splits
"""

import argparse
import json
import sys
import unicodedata
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path

import imagehash
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent

DATASET_ID = "TuyenTrungLe/vietnamese_food_images"
CLASS_NAMES_PATH = PROJECT_ROOT / "data" / "eval" / "class_names.json"
REFERENCES_DIR = PROJECT_ROOT / "data" / "images" / "references"
GOLDEN_DIR = PROJECT_ROOT / "data" / "images" / "golden"
TRAINING_ROOT = PROJECT_ROOT / "data" / "images" / "vn30"

DEFAULT_REFS_PER_CLASS = 40
DEFAULT_GOLDEN_PER_CLASS = 15
DEFAULT_TRAIN_PER_CLASS = 500
DEFAULT_VAL_PER_CLASS = 75
DEFAULT_TEST_PER_CLASS = 150
# ``banh_duc`` không có trong references/golden hiện hữu do nhiễu nhãn đã được
# review trước đó. Người dùng vẫn có thể đưa nó vào bằng --classes banh_duc.
DEFAULT_EXCLUDED_TRAINING_SLUGS = frozenset({"banh_duc"})
MIN_IMAGE_SIDE_PX = 100
PHASH_DUPLICATE_DISTANCE = 4
JPEG_QUALITY = 90
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")


def build_class_slug(label: str) -> str:
    """Tạo slug ascii snake_case từ tên lớp: bỏ dấu, thường hóa, _ nối từ."""
    replaced = label.replace("đ", "d").replace("Đ", "D")
    decomposed = unicodedata.normalize("NFD", replaced)
    ascii_text = decomposed.encode("ascii", "ignore").decode("ascii")
    words = "".join(
        char if char.isalnum() else " " for char in ascii_text.lower()
    ).split()
    return "_".join(words)


def merge_class_names(path: Path, new_names: Mapping[str, str]) -> dict[str, str]:
    """Đọc-merge-ghi class_names.json; key đã có giữ nguyên, key sort."""
    existing: dict[str, str] = {}
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
    merged = dict(sorted({**new_names, **existing}.items()))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(merged, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return merged


def find_dataset_columns(features: Mapping[str, object]) -> tuple[str, str, list[str]]:
    """Tìm (cột ảnh, cột nhãn, danh sách tên nhãn) từ features của dataset."""
    image_column: str | None = None
    label_column: str | None = None
    label_names: list[str] = []
    for name, feature in features.items():
        names = getattr(feature, "names", None)
        if isinstance(names, list) and names:
            label_column, label_names = name, list(names)
        elif (
            type(feature).__name__ == "Image"
            or getattr(feature, "dtype", "") == "PIL.Image.Image"
        ):
            image_column = name
    if image_column is None or label_column is None:
        raise RuntimeError(
            f"Không tìm thấy cột ảnh/ClassLabel trong features: {list(features)}"
        )
    return image_column, label_column, label_names


def is_min_size(image: Image.Image, min_side: int = MIN_IMAGE_SIDE_PX) -> bool:
    """Ảnh đạt chuẩn khi cạnh nhỏ nhất >= min_side."""
    return min(image.size) >= min_side


def is_quality_photo(
    image: Image.Image,
    min_side: int = MIN_IMAGE_SIDE_PX,
    max_aspect: float = 2.2,
    min_aspect: float = 0.45,
    min_std: float = 22.0,
    max_light_bg_ratio: float = 0.30,
) -> bool:
    """Lọc ảnh rác: bỏ ảnh quá méo, flat graphic/clipart hoặc nền phòng thu/nền sáng quảng cáo."""
    w, h = image.size
    if min(w, h) < min_side:
        return False
    aspect = w / h
    if aspect > max_aspect or aspect < min_aspect:
        return False
    try:
        import numpy as np

        rgb = image.convert("RGB")
        arr = np.array(rgb)
        if float(np.std(arr)) < min_std:
            return False
        gray = np.mean(arr, axis=2)
        if float(np.mean(gray > 215)) > max_light_bg_ratio:
            return False
    except Exception:
        pass
    return True



def is_duplicate_phash(
    candidate: imagehash.ImageHash,
    seen: Iterable[imagehash.ImageHash],
    max_distance: int = PHASH_DUPLICATE_DISTANCE,
) -> bool:
    """Trùng khi hamming distance tới bất kỳ hash đã thấy <= max_distance."""
    return any(candidate - previous <= max_distance for previous in seen)


def iter_image_files(directory: Path) -> Iterator[Path]:
    """Liệt kê file ảnh trực tiếp trong một thư mục (không đệ quy)."""
    if not directory.is_dir():
        return
    for path in sorted(directory.iterdir()):
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
            yield path


def next_image_path(class_dir: Path, slug: str, start_index: int) -> Path:
    """Chọn đường dẫn <slug>_<index>.jpg chưa tồn tại, bắt đầu từ start_index."""
    index = start_index
    while (class_dir / f"{slug}_{index}.jpg").exists():
        index += 1
    return class_dir / f"{slug}_{index}.jpg"


def load_existing_state(
    out_dir: Path, slugs: Iterable[str]
) -> tuple[dict[str, int], dict[str, list[imagehash.ImageHash]]]:
    """Đếm ảnh + tính phash sẵn có của từng lớp để chạy lại không trùng."""
    counts: dict[str, int] = {}
    hashes: dict[str, list[imagehash.ImageHash]] = {}
    for slug in slugs:
        class_hashes: list[imagehash.ImageHash] = []
        for path in iter_image_files(out_dir / slug):
            try:
                with Image.open(path) as image:
                    class_hashes.append(imagehash.phash(image))
            except Exception:
                continue  # ảnh hỏng sẵn có: bỏ qua, không chặn cả lớp
        counts[slug] = len(class_hashes)
        hashes[slug] = class_hashes
    return counts, hashes


@dataclass(frozen=True)
class SplitResult:
    """Kết quả gom một split: số ảnh lưu mỗi lớp + số ảnh bị loại."""

    saved: dict[str, int]
    skipped_small: int
    skipped_duplicate: int
    error: str | None


def _row_slug(label_value: object, slugs: list[str]) -> str:
    """Đổi giá trị nhãn (int ClassLabel hoặc chuỗi tên) về class_slug."""
    if isinstance(label_value, str):
        return build_class_slug(label_value)
    return slugs[int(label_value)]  # type: ignore[arg-type]


def _save_row_image(image: Image.Image, class_dir: Path, slug: str, index: int) -> None:
    """Lưu một ảnh về JPEG RGB quality 90 với tên <slug>_<index>.jpg."""
    class_dir.mkdir(parents=True, exist_ok=True)
    target = next_image_path(class_dir, slug, index)
    image.convert("RGB").save(target, "JPEG", quality=JPEG_QUALITY)


def collect_split(
    rows: Iterable[Mapping[str, object]],
    image_column: str,
    label_column: str,
    label_names: list[str],
    out_dir: Path,
    per_class: int,
    wanted: set[str] | None = None,
    blocked_hashes: Mapping[str, list[imagehash.ImageHash]] | None = None,
) -> SplitResult:
    """Gom ảnh từ một split tới khi mọi lớp mục tiêu đủ per_class ảnh.

    Lỗi giữa chừng (đứt mạng...) không văng traceback: trả về SplitResult
    với tiến độ đã đạt và thông điệp lỗi trong .error.
    """
    slugs = [build_class_slug(name) for name in label_names]
    targets = sorted(wanted) if wanted else sorted(set(slugs))
    counts, hashes = load_existing_state(out_dir, targets)
    remaining = {slug for slug in targets if counts[slug] < per_class}
    skipped_small = skipped_duplicate = 0
    error: str | None = None
    if not remaining:
        return SplitResult(dict(counts), skipped_small, skipped_duplicate, error)
    try:
        for row in rows:
            slug = _row_slug(row[label_column], slugs)
            if slug not in remaining:
                continue
            image = row[image_column]
            if not is_min_size(image):
                skipped_small += 1
                continue
            candidate = imagehash.phash(image)
            seen_hashes = [*hashes[slug], *(blocked_hashes or {}).get(slug, [])]
            if is_duplicate_phash(candidate, seen_hashes):
                skipped_duplicate += 1
                continue
            _save_row_image(image, out_dir / slug, slug, counts[slug])
            counts[slug] += 1
            hashes[slug].append(candidate)
            if counts[slug] >= per_class:
                remaining.discard(slug)
                if not remaining:
                    break
    except Exception as exc:  # noqa: BLE001 — báo tiến độ thay vì traceback
        error = f"{type(exc).__name__}: {exc}"
    return SplitResult(dict(counts), skipped_small, skipped_duplicate, error)


def load_blocked_hashes(
    roots: Iterable[Path], slugs: Iterable[str]
) -> dict[str, list[imagehash.ImageHash]]:
    """Gom pHash từ các split trước để chặn leakage giữa train/val/test."""
    targets = list(slugs)
    blocked = {slug: [] for slug in targets}
    for root in roots:
        _, hashes = load_existing_state(root, targets)
        for slug, values in hashes.items():
            blocked[slug].extend(values)
    return blocked


def stream_split(dataset_id: str, split: str):
    """Mở một split ở chế độ streaming (import datasets tại đây cho nhẹ)."""
    from datasets import load_dataset

    dataset = load_dataset(dataset_id, split=split, streaming=True)
    if dataset.features is None:
        raise RuntimeError(
            f"Split '{split}' không công bố features khi streaming; "
            "cần kiểm tra lại cấu trúc dataset trên Hugging Face."
        )
    return dataset


def parse_wanted_classes(raw: str | None, slugs: list[str]) -> set[str] | None:
    """Đổi --classes thành set slug hợp lệ; báo lỗi rõ nếu slug không tồn tại."""
    if not raw:
        return None
    wanted = {part.strip() for part in raw.split(",") if part.strip()}
    unknown = sorted(wanted - set(slugs))
    if unknown:
        raise SystemExit(
            f"Slug không có trong dataset: {', '.join(unknown)}. "
            f"Các slug hợp lệ: {', '.join(sorted(set(slugs)))}"
        )
    return wanted


def print_summary(
    slugs: list[str],
    references: SplitResult,
    golden: SplitResult,
) -> None:
    """In bảng tổng kết mỗi lớp: số ảnh references / golden đã lưu."""
    print(f"\n{'class_slug':<24}{'references':>12}{'golden':>10}")
    print("-" * 46)
    for slug in slugs:
        ref_count = references.saved.get(slug, 0)
        gold_count = golden.saved.get(slug, 0)
        print(f"{slug:<24}{ref_count:>12}{gold_count:>10}")
    print("-" * 46)
    print(
        f"{'TỔNG':<24}{sum(references.saved.values()):>12}"
        f"{sum(golden.saved.values()):>10}"
    )
    print(
        f"Loại (nhỏ/trùng): references {references.skipped_small}/"
        f"{references.skipped_duplicate}, golden {golden.skipped_small}/"
        f"{golden.skipped_duplicate}"
    )


def print_training_summary(
    slugs: list[str], results: Mapping[str, SplitResult]
) -> None:
    """In số ảnh train/val/test đã lưu cho dataset fine-tune riêng."""
    print(f"\n{'class_slug':<24}{'train':>10}{'val':>10}{'test':>10}")
    print("-" * 54)
    for slug in slugs:
        print(
            f"{slug:<24}{results['train'].saved.get(slug, 0):>10}"
            f"{results['validation'].saved.get(slug, 0):>10}"
            f"{results['test'].saved.get(slug, 0):>10}"
        )
    print("-" * 54)
    print(
        f"{'TỔNG':<24}{sum(results['train'].saved.values()):>10}"
        f"{sum(results['validation'].saved.values()):>10}"
        f"{sum(results['test'].saved.values()):>10}"
    )
def run(refs_per_class: int, golden_per_class: int, classes: str | None) -> int:
    """Stream 2 split, lưu ảnh, merge class_names.json, in tổng kết."""
    train_stream = stream_split(DATASET_ID, "train")
    image_column, label_column, label_names = find_dataset_columns(
        train_stream.features
    )
    slug_to_name = {build_class_slug(name): name for name in label_names}
    merge_class_names(CLASS_NAMES_PATH, slug_to_name)
    print(f"Đã merge {len(slug_to_name)} lớp vào {CLASS_NAMES_PATH}")

    wanted = parse_wanted_classes(classes, list(slug_to_name))
    print(f"Đang stream split train → {REFERENCES_DIR} ...")
    references = collect_split(
        train_stream, image_column, label_column, label_names,
        REFERENCES_DIR, refs_per_class, wanted,
    )
    if references.error:
        print(f"⚠️ Split train dừng giữa chừng: {references.error}")

    print(f"Đang stream split test → {GOLDEN_DIR} ...")
    golden = SplitResult({}, 0, 0, "chưa chạy")
    try:
        test_stream = stream_split(DATASET_ID, "test")
        golden = collect_split(
            test_stream, image_column, label_column, label_names,
            GOLDEN_DIR, golden_per_class, wanted,
        )
    except Exception as exc:  # noqa: BLE001 — vẫn in tiến độ references
        golden = SplitResult({}, 0, 0, f"{type(exc).__name__}: {exc}")
    if golden.error:
        print(f"⚠️ Split test dừng giữa chừng: {golden.error}")

    print_summary(sorted(wanted) if wanted else sorted(slug_to_name), references, golden)
    return 1 if references.error or golden.error else 0


def run_training_splits(
    training_root: Path,
    train_per_class: int,
    val_per_class: int,
    test_per_class: int,
    classes: str | None,
) -> int:
    """Tải 3 split 30VNFoods vào root riêng, chống pHash leakage chéo."""
    train_stream = stream_split(DATASET_ID, "train")
    image_column, label_column, label_names = find_dataset_columns(
        train_stream.features
    )
    slug_to_name = {build_class_slug(name): name for name in label_names}
    merge_class_names(CLASS_NAMES_PATH, slug_to_name)

    explicitly_wanted = parse_wanted_classes(classes, list(slug_to_name))
    wanted = explicitly_wanted or (
        set(slug_to_name) - DEFAULT_EXCLUDED_TRAINING_SLUGS
    )
    selected_slugs = sorted(wanted)
    split_specs = (
        ("train", train_per_class, train_stream, []),
        ("validation", val_per_class, None, [training_root / "train"]),
        (
            "test",
            test_per_class,
            None,
            [training_root / "train", training_root / "val"],
        ),
    )
    output_names = {"train": "train", "validation": "val", "test": "test"}
    results: dict[str, SplitResult] = {}

    for split, per_class, stream, prior_roots in split_specs:
        print(f"Đang stream split {split} → {training_root / output_names[split]} ...")
        try:
            rows = stream if stream is not None else stream_split(DATASET_ID, split)
            blocked = load_blocked_hashes(prior_roots, selected_slugs)
            results[split] = collect_split(
                rows,
                image_column,
                label_column,
                label_names,
                training_root / output_names[split],
                per_class,
                wanted,
                blocked,
            )
        except Exception as exc:  # noqa: BLE001 — in được split còn lại
            results[split] = SplitResult({}, 0, 0, f"{type(exc).__name__}: {exc}")
        if results[split].error:
            print(f"⚠️ Split {split} dừng giữa chừng: {results[split].error}")

    print_training_summary(selected_slugs, results)
    return 1 if any(result.error for result in results.values()) else 0


def build_parser() -> argparse.ArgumentParser:
    """CLI: số ảnh mỗi lớp cho references/golden + lọc lớp."""
    parser = argparse.ArgumentParser(
        description="Seed references + golden set từ mirror 30VNFoods (streaming)"
    )
    parser.add_argument(
        "--refs-per-class", type=int, default=DEFAULT_REFS_PER_CLASS,
        help=f"Số ảnh references mỗi lớp (mặc định {DEFAULT_REFS_PER_CLASS})",
    )
    parser.add_argument(
        "--golden-per-class", type=int, default=DEFAULT_GOLDEN_PER_CLASS,
        help=f"Số ảnh golden mỗi lớp (mặc định {DEFAULT_GOLDEN_PER_CLASS})",
    )
    parser.add_argument(
        "--classes", default=None,
        help="Chỉ tải các slug này (phân tách bằng dấu phẩy), vd: pho_bo,banh_xeo",
    )
    parser.add_argument(
        "--training-splits",
        action="store_true",
        help="Tải 29 lớp 30VNFoods vào data/images/vn30/{train,val,test}.",
    )
    parser.add_argument(
        "--training-dir",
        type=Path,
        default=TRAINING_ROOT,
        help="Root cho --training-splits (mặc định: data/images/vn30).",
    )
    parser.add_argument(
        "--train-per-class",
        type=int,
        default=DEFAULT_TRAIN_PER_CLASS,
        help=f"Ảnh train mỗi lớp cho --training-splits (mặc định {DEFAULT_TRAIN_PER_CLASS}).",
    )
    parser.add_argument(
        "--val-per-class",
        type=int,
        default=DEFAULT_VAL_PER_CLASS,
        help=f"Ảnh val mỗi lớp cho --training-splits (mặc định {DEFAULT_VAL_PER_CLASS}).",
    )
    parser.add_argument(
        "--test-per-class",
        type=int,
        default=DEFAULT_TEST_PER_CLASS,
        help=f"Ảnh test mỗi lớp cho --training-splits (mặc định {DEFAULT_TEST_PER_CLASS}).",
    )
    return parser


def main() -> None:
    """Parse CLI rồi chạy; lỗi mạng ngay từ đầu cũng báo gọn, không traceback."""
    arguments = build_parser().parse_args()
    try:
        exit_code = (
            run_training_splits(
                arguments.training_dir,
                arguments.train_per_class,
                arguments.val_per_class,
                arguments.test_per_class,
                arguments.classes,
            )
            if arguments.training_splits
            else run(
                arguments.refs_per_class,
                arguments.golden_per_class,
                arguments.classes,
            )
        )
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        print(f"❌ Không stream được dataset {DATASET_ID}: {exc}")
        exit_code = 1
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
