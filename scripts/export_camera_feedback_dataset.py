"""Export only consented, human-reviewed camera photos for CV training.

The script deliberately treats PostgreSQL metadata as the gate.  A row is not
training data merely because a user uploaded it: it needs camera provenance,
explicit consent, an ``approved`` status, a reviewer label and a review time.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import shutil
import sys
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Iterable

from sqlalchemy import select

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.config import settings  # noqa: E402
from backend.db.models import FeedbackSubmission  # noqa: E402
from backend.db.postgres import async_session  # noqa: E402

DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data/images/feedback_camera_reviewed"
DEFAULT_MANIFEST = PROJECT_ROOT / "data/eval/camera_feedback_dataset_manifest.json"
HARD_CONFUSION_CLASSES = frozenset(
    {
        "banh_can",
        "banh_canh",
        "banh_chung",
        "banh_khot",
        "banh_tet",
        "banh_trang_nuong",
        "banh_xeo",
        "bun_bo_hue",
        "hu_tieu",
        "pho_bo",
    }
)


def is_exportable(row: object) -> bool:
    """Return whether one ORM-like row passed every camera training gate."""
    return bool(
        getattr(row, "status", None) == "approved"
        and getattr(row, "consent_to_training", False) is True
        and getattr(row, "capture_source", None) == "camera"
        and isinstance(getattr(row, "reviewed_dish_slug", None), str)
        and bool(getattr(row, "reviewed_dish_slug", "").strip())
        and getattr(row, "reviewed_at", None) is not None
    )


def split_for_submission(submission_id: str) -> str:
    """Deterministically assign one submission to train/val/test."""
    bucket = hashlib.sha256(submission_id.encode("utf-8")).digest()[0] % 10
    if bucket == 0:
        return "test"
    if bucket == 1:
        return "val"
    return "train"


def resolve_object_path(storage_root: Path, object_key: str) -> Path:
    """Resolve a filesystem object key without allowing path traversal."""
    pure_key = PurePosixPath(object_key)
    if pure_key.is_absolute() or ".." in pure_key.parts:
        raise ValueError("Object key must stay inside the storage root")
    root = storage_root.resolve()
    target = (root / Path(*pure_key.parts)).resolve()
    if target != root and root not in target.parents:
        raise ValueError("Object key must stay inside the storage root")
    return target


def build_dataset_manifest(
    rows: Iterable[object],
    *,
    minimum_total: int = 200,
    minimum_per_class: int = 20,
    required_classes: frozenset[str] = HARD_CONFUSION_CLASSES,
) -> dict[str, object]:
    """Summarize the hard gates without silently filling missing classes."""
    rows = list(rows)
    counts = Counter(str(row.reviewed_dish_slug) for row in rows)
    classes_below = sorted(
        class_slug
        for class_slug in (set(counts) | set(required_classes))
        if counts.get(class_slug, 0) < minimum_per_class
    )
    missing_by_class = {
        class_slug: minimum_per_class - counts.get(class_slug, 0)
        for class_slug in classes_below
    }
    camera_images = len(rows)
    return {
        "suite": "camera_feedback_dataset",
        "camera_images": camera_images,
        "minimum_total": minimum_total,
        "minimum_per_class": minimum_per_class,
        "by_class": dict(sorted(counts.items())),
        "required_hard_classes": sorted(required_classes),
        "classes_below_minimum": classes_below,
        "missing_by_class": missing_by_class,
        "ready": camera_images >= minimum_total and not classes_below,
        "blocking_reasons": [
            reason
            for reason in (
                "camera_images_below_minimum"
                if camera_images < minimum_total
                else None,
                "hard_classes_below_minimum" if classes_below else None,
            )
            if reason is not None
        ],
    }


async def load_rows() -> list[FeedbackSubmission]:
    async with async_session() as session:
        result = await session.execute(
            select(FeedbackSubmission)
            .where(
                FeedbackSubmission.status == "approved",
                FeedbackSubmission.consent_to_training.is_(True),
                FeedbackSubmission.capture_source == "camera",
                FeedbackSubmission.reviewed_dish_slug.is_not(None),
                FeedbackSubmission.reviewed_at.is_not(None),
            )
            .order_by(FeedbackSubmission.created_at.asc())
        )
        return list(result.scalars().all())


def export_rows(
    rows: Iterable[FeedbackSubmission],
    *,
    storage_root: Path,
    output_root: Path,
) -> int:
    """Copy approved camera objects into deterministic CV split folders."""
    copied = 0
    for row in rows:
        source = resolve_object_path(storage_root, row.object_key)
        if not source.is_file():
            raise FileNotFoundError(f"Feedback object not found: {source}")
        class_slug = str(row.reviewed_dish_slug)
        split = split_for_submission(str(row.id))
        destination_dir = output_root / split / class_slug
        destination_dir.mkdir(parents=True, exist_ok=True)
        destination = destination_dir / f"{row.id}{source.suffix.lower()}"
        shutil.copy2(source, destination)
        copied += 1
    return copied


async def main() -> None:
    parser = argparse.ArgumentParser(description="Export reviewed camera feedback")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args()

    if settings.object_storage_backend != "filesystem":
        raise SystemExit(
            "Export local hiện chỉ hỗ trợ OBJECT_STORAGE_BACKEND=filesystem; "
            "hãy thêm downloader S3 trước khi export production."
        )
    rows = await load_rows()
    report = build_dataset_manifest(rows)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    copied = export_rows(
        rows,
        storage_root=settings.object_storage_root,
        output_root=args.output_dir,
    )
    print(json.dumps({**report, "copied": copied}, ensure_ascii=False, indent=2))
    print(f"Manifest saved: {args.manifest}")


if __name__ == "__main__":
    asyncio.run(main())
