"""Build the explicit visual-review manifest used by the local-recognition demo.

This manifest is intentionally not a production provenance approval.  The
review decision is visual and conservative: obvious matches are approved,
ambiguous or polluted search results remain deferred for the owner to review.

Usage:
    uv run python scripts/build_demo_review_manifest.py
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ROOT = PROJECT_ROOT / "data/images/references_candidate"
DEFAULT_OUTPUT = PROJECT_ROOT / "data/eval/reference_candidate_demo_reviewed.json"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
_NUMERIC_NAME = re.compile(r"^(?P<slug>.+)_(?P<index>\d+)\.(?P<suffix>[^.]+)$")


def _range(start: int, stop: int) -> tuple[int, ...]:
    return tuple(range(start, stop + 1))


# These are the images that passed the visual pass on 2026-08-06.  Ranges are
# deliberately kept here instead of inferred from filenames so a new crawl
# cannot silently become approved.
APPROVED_NUMERIC_INDICES: dict[str, tuple[int, ...]] = {
    "banh_can": _range(0, 15),
    "banh_canh": _range(0, 20),
    "banh_chung": (0, 1, 2, 3, 4, 5, 6, 10, 11, 12, 13, 14, 15, 16, 17, 20, 21, 33, 34, 35),
    "banh_kem": tuple(index for index in _range(0, 49) if index != 46),
    "banh_khot": (*_range(0, 20), *_range(22, 29), 37, 39),
    "banh_mi_khong": (
        0, 2, 3, 4, 5, 6, 8, 9, 12, 14, 15, 16, 17, 18, 20, 21, 22, 23,
        29, 30, 34, 35, 36, 38, 43, 45, 46, 48, 49,
    ),
    "banh_tet": (
        0, 1, 2, 3, 4, 5, 6, 8, 10, 13, 14, 17, 18, 19, 20, 22, 24, 26,
        29, 31, 32, 35, 37, 39,
    ),
    "banh_trang_nuong": (
        0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 15, 16, 17, 18, 19,
        20, 21, 23, 24, 25, 26, 28, 30, 33, 35, 36, 37,
    ),
    "banh_xeo": (
        0, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18,
        19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 35, 36,
        37, 39,
    ),
    "bun_bo_hue": (0, 1, 2, 3, 4, 5, 7, 9, 10, 12),
    "hu_tieu": _range(0, 14),
    "pho_bo": (*_range(0, 7), *_range(9, 19)),
    "chocolate": tuple(index for index in _range(0, 49) if index not in {12, 19}),
    "coca_cola": (11, 12, 15, 22, 27, 29, 30, 33, 34, 40, 41, 43, 44, 45, 49),
    "com_trang": tuple(index for index in _range(0, 49) if index != 2),
    "ga_ran": (
        0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 14, 15, 16, 17, 19, 20,
        21, 22, 23, 24, 26, 27, 29, 35, 36, 37, 39, 40, 44, 45, 47, 48,
    ),
    "hamburger": (
        0, 1, 2, 3, 4, 5, 7, 9, 10, 11, 13, 14, 15, 16, 17, 19, 20, 21,
        22, 24, 25, 27, 29, 30, 31, 34, 35, 36, 37, 38, 42, 43, 44, 45,
    ),
    "khoai_luoc": (
        0, 1, 2, 3, 5, 6, 7, 11, 12, 13, 16, 17, 18, 19, 20, 21, 22, 23,
        24, 26, 27, 28, 29, 30, 35, 36, 41, 42,
    ),
    "pizza": (
        0, 1, 2, 3, 5, 6, 7, 8, 9, 12, 13, 14, 22, 24, 25, 26, 27, 28,
        29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 40, 41, 42, 43, 44, 45, 46,
        47, 48, 49,
    ),
    "sau_rieng": tuple(index for index in _range(0, 49) if index not in {33, 43, 49}),
    "sua_milo": (
        0, 1, 3, 4, 5, 9, 10, 13, 15, 16, 18, 19, 20, 23, 24, 25, 26, 28,
        29, 32, 34, 35, 36, 37, 39, 40, 44, 47, 48,
    ),
    "tra_sua": tuple(index for index in _range(0, 49) if index != 12),
    "tra_trai_cay": (
        0, 1, 2, 3, 4, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 18, 20, 21, 22,
        23, 25, 26, 27, 28, 29, 30, 32, 34, 35, 36, 37, 38, 39, 41, 42, 43,
        44, 45, 46, 47, 48, 49,
    ),
    "trung_chien": (
        0, 1, 2, 3, 4, 5, 7, 8, 9, 10, 12, 13, 17, 19, 20, 22, 23, 24, 26,
        30, 33, 34, 35, 42, 43, 44, 45, 46, 47, 48, 49,
    ),
    "trung_luoc": tuple(index for index in _range(0, 49) if index not in {13, 26}),
    "uc_ga": (
        0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 14, 15, 16, 17, 18, 19,
        21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 35, 36, 37, 39,
        40, 41, 43, 44, 47, 48, 49,
    ),
    "xoi_man": (
        0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18,
        19, 20, 21, 24, 25, 27, 28, 29, 30, 31, 32, 33, 35, 36, 44, 46, 49,
    ),
    "xuc_xich_nuong": (
        0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 15, 16, 20, 21, 22,
        23, 24, 25, 26, 27, 29, 30, 32, 35, 36, 37, 38, 39, 40, 41, 42, 43,
        44, 45, 46, 47, 48, 49,
    ),
}

EXTRA_NON_NUMERIC_CLASSES = {"bun_bo_hue", "hu_tieu"}
EXTRA_EXPLICIT_NAMES = {
    "banh_can": ("banh_can_commons_0.jpg",),
    "banh_xeo": ("banh_xeo_commons_0.jpg",),
    "hu_tieu": ("hu_tieu_commons_0.jpg",),
    "pho_bo": ("pho_bo_commons_0.jpg",),
}
CLASS_NOTES = {
    "banh_can": "Bỏ nhóm ảnh timestamp nhìn là bánh canh/nước; giữ ảnh đĩa bánh căn rõ hình.",
    "banh_mi_khong": "Chỉ giữ ổ bánh/bánh mì không nhìn rõ; bỏ phần lớn ảnh bánh mì có nhân.",
    "coca_cola": "Chỉ giữ chai/lon nhìn thấy rõ; bỏ ảnh sự kiện Coca-Cola không có sản phẩm chính.",
    "khoai_luoc": "Giữ củ khoai luộc/hấp nhìn rõ; bỏ nhóm khoai chiên và nguyên liệu khó phân biệt.",
    "sua_milo": "Chỉ giữ ảnh có nhận diện Milo rõ hoặc ly Milo đi kèm bao bì; bỏ ly cacao chung chung.",
    "trung_chien": "Giữ trứng chiên/ốp la/chả trứng đã chín; bỏ trứng sống và ảnh hướng dẫn không rõ món.",
    "uc_ga": "Giữ ức gà sống hoặc đã nướng áp chảo nhìn rõ; bỏ xúc xích, mì và ảnh nhiễu.",
}


def _numeric_name(slug: str, index: int) -> str:
    return f"{slug}_{index}.jpg"


def _iter_images(root: Path) -> Iterable[Path]:
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
            yield path


def _relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _approved_names(slug: str, indices: Iterable[int], extra_names: dict[str, tuple[str, ...]]) -> set[str]:
    names = {_numeric_name(slug, index) for index in indices}
    names.update(extra_names.get(slug, ()))
    return names


def build_manifest(
    root: Path,
    approved_indices: dict[str, tuple[int, ...]] | None = None,
    *,
    extra_names: dict[str, tuple[str, ...]] | None = None,
) -> dict[str, Any]:
    """Build a demo manifest and keep every non-approved image deferred."""
    selected_indices = approved_indices or APPROVED_NUMERIC_INDICES
    selected_extras = extra_names if extra_names is not None else EXTRA_EXPLICIT_NAMES
    all_images = list(_iter_images(root))
    approved: list[str] = []
    for path in all_images:
        slug = path.parent.name
        numeric_match = _NUMERIC_NAME.match(path.name)
        if numeric_match and numeric_match.group("slug") == slug:
            try:
                index = int(numeric_match.group("index"))
            except ValueError:
                index = -1
            if index in selected_indices.get(slug, ()):
                approved.append(_relative(path, root))
        elif path.name in selected_extras.get(slug, ()):
            approved.append(_relative(path, root))
        elif approved_indices is None and slug in EXTRA_NON_NUMERIC_CLASSES:
            approved.append(_relative(path, root))

    approved = sorted(set(approved))
    approved_set = set(approved)
    all_relative = sorted(_relative(path, root) for path in all_images)
    deferred = [path for path in all_relative if path not in approved_set]
    approved_by_class = Counter(path.split("/", 1)[0] for path in approved)
    deferred_by_class = Counter(path.split("/", 1)[0] for path in deferred)
    return {
        "schema_version": 1,
        "demo_only": True,
        "review_method": "codex_visual_review",
        "reviewed_at": "2026-08-06",
        "review_status": "reviewed",
        "provenance_status": "unverified_demo",
        "approved_paths": approved,
        "reviewed_paths": approved,
        "deferred_paths": deferred,
        "summary": {
            "candidate_images": len(all_relative),
            "approved_images": len(approved),
            "deferred_images": len(deferred),
            "approved_by_class": dict(sorted(approved_by_class.items())),
            "deferred_by_class": dict(sorted(deferred_by_class.items())),
        },
        "visual_review_notes": CLASS_NOTES,
        "provenance_records": [],
    }


def write_manifest(output: Path, manifest: dict[str, Any]) -> Path:
    """Write the deterministic demo manifest."""
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return output


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build the demo visual-review manifest")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    manifest = build_manifest(args.root)
    path = write_manifest(args.output, manifest)
    print(f"Manifest: {path}")
    print(json.dumps(manifest["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
