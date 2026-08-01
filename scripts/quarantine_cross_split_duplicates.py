"""Preview or recoverably quarantine pHash duplicates across train/val/test.

The default is a dry run: it writes JSON and Markdown manifests only. ``--apply``
moves the lower-priority side of every cross-split duplicate into a timestamped
backup tree. It never deletes or overwrites an image.

Usage:
    DEBUG=false uv run python scripts/quarantine_cross_split_duplicates.py
    DEBUG=false uv run python scripts/quarantine_cross_split_duplicates.py --apply
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import imagehash
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.download_datasets import IMAGE_EXTENSIONS  # noqa: E402

DEFAULT_IMAGE_ROOT = PROJECT_ROOT / "data" / "images"
DEFAULT_BACKUP_ROOT = DEFAULT_IMAGE_ROOT / "cross_split_duplicates_backup"
DEFAULT_REPORT_DIR = PROJECT_ROOT / "ml" / "evaluation" / "reports"
SPLITS = ("train", "val", "test")
DEFAULT_THRESHOLD = 6
DEFAULT_PRIORITIES = {"train": 1, "val": 2, "test": 3}
DEFAULT_TARGETS = {"train": 80, "val": 20, "test": 30}


@dataclass(frozen=True)
class ImageRecord:
    """One readable classified image and its 64-bit perceptual hash."""

    path: Path
    split: str
    label: str
    phash: int


@dataclass(frozen=True)
class Match:
    """A cross-split pHash pair at or below the configured distance."""

    left: ImageRecord
    right: ImageRecord
    distance: int


@dataclass(frozen=True)
class Decision:
    """The retained and quarantined sides of one duplicate match."""

    keep_path: Path
    quarantine_path: Path
    label_conflict: bool
    reason: str


@dataclass(frozen=True)
class RunResult:
    """Paths and outcome needed by callers and tests."""

    json_path: Path
    markdown_path: Path
    expected_move_count: int
    applied_count: int
    post_apply_cross_split_match_count: int | None


def _iter_image_paths(image_root: Path) -> Iterable[tuple[str, Path]]:
    for split in SPLITS:
        split_root = image_root / split
        if not split_root.is_dir():
            continue
        for path in sorted(split_root.rglob("*")):
            if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
                yield split, path


def _hash_image(item: tuple[str, Path]) -> tuple[ImageRecord | None, dict | None]:
    split, path = item
    try:
        with Image.open(path) as image:
            value = int(str(imagehash.phash(image)), 16)
    except Exception as exc:  # noqa: BLE001 - report unreadable data, do not mutate it
        return None, {"path": str(path), "error": f"{type(exc).__name__}: {exc}"}
    return ImageRecord(path=path, split=split, label=path.parent.name, phash=value), None


def scan_images(image_root: Path) -> tuple[list[ImageRecord], list[dict]]:
    """Read image hashes in deterministic order; unreadable files are reported."""
    items = list(_iter_image_paths(image_root))
    workers = min(12, max(1, len(items)))
    with ThreadPoolExecutor(max_workers=workers) as executor:
        scanned = list(executor.map(_hash_image, items))
    records = [record for record, _ in scanned if record is not None]
    invalid = [error for _, error in scanned if error is not None]
    return records, invalid


def _hash_chunks(value: int) -> Iterable[tuple[int, int]]:
    """Yield seven bit chunks; distance <=6 guarantees one equal chunk."""
    shift = 0
    for index, width in enumerate((10, 9, 9, 9, 9, 9, 9)):
        yield index, (value >> shift) & ((1 << width) - 1)
        shift += width


def find_cross_split_matches(
    records: Sequence[ImageRecord], threshold: int = DEFAULT_THRESHOLD
) -> list[Match]:
    """Find every cross-split near duplicate without quadratic comparisons."""
    if threshold < 0 or threshold > DEFAULT_THRESHOLD:
        raise ValueError(f"threshold must be between 0 and {DEFAULT_THRESHOLD}")
    index: dict[tuple[int, int], list[ImageRecord]] = defaultdict(list)
    matches: list[Match] = []
    for record in records:
        possible: list[ImageRecord] = []
        for chunk in _hash_chunks(record.phash):
            possible.extend(index[chunk])
        seen_paths: set[Path] = set()
        for prior in possible:
            if prior.path in seen_paths:
                continue
            seen_paths.add(prior.path)
            if prior.split == record.split:
                continue
            distance = (record.phash ^ prior.phash).bit_count()
            if distance <= threshold:
                matches.append(Match(left=prior, right=record, distance=distance))
        for chunk in _hash_chunks(record.phash):
            index[chunk].append(record)
    return matches


def decide_match(match: Match, priorities: Mapping[str, int] = DEFAULT_PRIORITIES) -> Decision:
    """Apply test > val > train; ties retain the lexicographically first path."""
    left_priority = priorities.get(match.left.split, 0)
    right_priority = priorities.get(match.right.split, 0)
    if left_priority > right_priority:
        keep, quarantine, reason = match.left, match.right, "higher_split_priority"
    elif right_priority > left_priority:
        keep, quarantine, reason = match.right, match.left, "higher_split_priority"
    elif str(match.left.path) <= str(match.right.path):
        keep, quarantine, reason = match.left, match.right, "same_priority_lexicographic"
    else:
        keep, quarantine, reason = match.right, match.left, "same_priority_lexicographic"
    return Decision(
        keep_path=keep.path,
        quarantine_path=quarantine.path,
        label_conflict=match.left.label != match.right.label,
        reason=reason,
    )


def _class_counts(image_root: Path) -> dict[str, dict[str, int]]:
    classes = sorted(
        {
            path.name
            for split in SPLITS
            if (image_root / split).is_dir()
            for path in (image_root / split).iterdir()
            if path.is_dir()
        }
    )
    counts: dict[str, dict[str, int]] = {}
    for split in SPLITS:
        counts[split] = {}
        for label in classes:
            directory = image_root / split / label
            counts[split][label] = sum(
                path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
                for path in directory.iterdir()
            ) if directory.is_dir() else 0
    return counts


def _project_counts(
    before: Mapping[str, Mapping[str, int]], quarantines: Iterable[Path], image_root: Path
) -> dict[str, dict[str, int]]:
    projected = {split: dict(values) for split, values in before.items()}
    for path in quarantines:
        relative = path.relative_to(image_root)
        split, label = relative.parts[:2]
        projected[split][label] -= 1
    return projected


def _target_shortfalls(
    counts: Mapping[str, Mapping[str, int]], targets: Mapping[str, int]
) -> dict[str, dict[str, int]]:
    return {
        split: {
            label: target - count
            for label, count in values.items()
            if count < target
        }
        for split, values in counts.items()
        if (target := targets.get(split, 0)) > 0
        and any(count < target for count in values.values())
    }


def _backup_destination(
    source: Path, image_root: Path, backup_root: Path, timestamp: str
) -> Path:
    return backup_root / timestamp / "data" / "images" / source.relative_to(image_root)


def _serialize_match(match: Match) -> dict:
    return {
        "distance": match.distance,
        "left": {"path": str(match.left.path), "split": match.left.split, "label": match.left.label},
        "right": {"path": str(match.right.path), "split": match.right.split, "label": match.right.label},
    }


def _serialize_decision(decision: Decision, image_root: Path, backup_root: Path, timestamp: str) -> dict:
    return {
        "keep_path": str(decision.keep_path),
        "quarantine_path": str(decision.quarantine_path),
        "backup_path": str(
            _backup_destination(decision.quarantine_path, image_root, backup_root, timestamp)
        ),
        "label_conflict": decision.label_conflict,
        "reason": decision.reason,
    }


def _markdown(manifest: Mapping) -> str:
    lines = [
        "# Cross-split duplicate quarantine manifest",
        "",
        f"- Timestamp: `{manifest['timestamp']}`",
        f"- Mode: `{manifest['mode']}`",
        f"- pHash threshold: `{manifest['threshold']}`",
        f"- Cross-split matches: `{manifest['cross_split_match_count']}`",
        f"- {'Applied' if manifest['mode'] == 'apply' else 'Expected'} moves: "
        f"`{manifest['expected_move_count']}`",
        "",
        "## Pair decisions",
        "",
        "| # | Distance | Left (split / label) | Right (split / label) | Keep | Quarantine | Label conflict |",
        "| ---: | ---: | --- | --- | --- | --- | :---: |",
    ]
    for index, (match, decision) in enumerate(
        zip(manifest["matches"], manifest["decisions"], strict=True), start=1
    ):
        lines.append(
            "| {index} | {distance} | {left_split} / {left_label} | "
            "{right_split} / {right_label} | `{keep}` | `{quarantine}` | {conflict} |".format(
                index=index,
                distance=match["distance"],
                left_split=match["left"]["split"],
                left_label=match["left"]["label"],
                right_split=match["right"]["split"],
                right_label=match["right"]["label"],
                keep=decision["keep_path"],
                quarantine=decision["quarantine_path"],
                conflict="yes" if decision["label_conflict"] else "no",
            )
        )
    if not manifest["matches"]:
        lines.append("| — | — | — | — | — | — | — |")
    lines.extend(["", "## Target shortfalls", ""])
    shortfalls = manifest["target_shortfalls"]
    if not shortfalls:
        lines.append("None.")
    else:
        for split, values in shortfalls.items():
            lines.append(f"- `{split}`: " + ", ".join(f"`{label}`: {missing}" for label, missing in values.items()))
    if manifest["mode"] == "apply":
        lines.extend(
            [
                "",
                "## Post-apply audit",
                "",
                f"Remaining cross-split pHash matches: `{manifest['post_apply_cross_split_match_count']}`",
            ]
        )
    return "\n".join(lines) + "\n"


def _write_manifest(report_dir: Path, timestamp: str, manifest: Mapping) -> tuple[Path, Path]:
    report_dir.mkdir(parents=True, exist_ok=True)
    stem = report_dir / f"cross_split_duplicate_quarantine_{timestamp}"
    json_path = stem.with_suffix(".json")
    markdown_path = stem.with_suffix(".md")
    json_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(_markdown(manifest), encoding="utf-8")
    return json_path, markdown_path


def run(
    *,
    image_root: Path = DEFAULT_IMAGE_ROOT,
    report_dir: Path = DEFAULT_REPORT_DIR,
    backup_root: Path = DEFAULT_BACKUP_ROOT,
    threshold: int = DEFAULT_THRESHOLD,
    apply: bool = False,
    timestamp: str | None = None,
    priorities: Mapping[str, int] = DEFAULT_PRIORITIES,
    targets: Mapping[str, int] = DEFAULT_TARGETS,
) -> RunResult:
    """Write a dry-run manifest or safely move the selected duplicate copies."""
    timestamp = timestamp or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    records, invalid_images = scan_images(image_root)
    matches = find_cross_split_matches(records, threshold)
    decisions = [decide_match(match, priorities) for match in matches]
    quarantines = sorted({decision.quarantine_path for decision in decisions})
    counts_before = _class_counts(image_root)
    projected_counts = _project_counts(counts_before, quarantines, image_root)

    manifest = {
        "timestamp": timestamp,
        "mode": "apply" if apply else "dry_run",
        "image_root": str(image_root),
        "backup_root": str(backup_root),
        "threshold": threshold,
        "priorities": dict(priorities),
        "images_scanned": len(records),
        "invalid_images": invalid_images,
        "cross_split_match_count": len(matches),
        "matches": [_serialize_match(match) for match in matches],
        "decisions": [
            _serialize_decision(decision, image_root, backup_root, timestamp)
            for decision in decisions
        ],
        "expected_move_count": len(quarantines),
        "counts_before": counts_before,
        "counts_after": projected_counts,
        "target_shortfalls": _target_shortfalls(projected_counts, targets),
        "post_apply_cross_split_match_count": None,
    }

    if not apply:
        json_path, markdown_path = _write_manifest(report_dir, timestamp, manifest)
        return RunResult(json_path, markdown_path, len(quarantines), 0, None)

    destinations = {
        source: _backup_destination(source, image_root, backup_root, timestamp)
        for source in quarantines
    }
    for source, destination in destinations.items():
        if not source.is_file():
            raise FileNotFoundError(f"Source image disappeared before quarantine: {source}")
        if destination.exists():
            raise FileExistsError(f"Refusing to overwrite backup target: {destination}")
    for source, destination in destinations.items():
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))

    remaining_records, remaining_invalid = scan_images(image_root)
    remaining_matches = find_cross_split_matches(remaining_records, threshold)
    manifest["images_scanned"] = len(remaining_records)
    manifest["invalid_images"] = remaining_invalid
    manifest["counts_after"] = _class_counts(image_root)
    manifest["target_shortfalls"] = _target_shortfalls(manifest["counts_after"], targets)
    manifest["post_apply_cross_split_match_count"] = len(remaining_matches)
    if remaining_matches:
        raise RuntimeError(
            f"Cross-split pHash matches remain after quarantine: {len(remaining_matches)}"
        )
    json_path, markdown_path = _write_manifest(report_dir, timestamp, manifest)
    return RunResult(
        json_path,
        markdown_path,
        len(quarantines),
        len(quarantines),
        len(remaining_matches),
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Preview or quarantine cross-split pHash image duplicates safely"
    )
    parser.add_argument("--image-root", type=Path, default=DEFAULT_IMAGE_ROOT)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--backup-root", type=Path, default=DEFAULT_BACKUP_ROOT)
    parser.add_argument("--threshold", type=int, default=DEFAULT_THRESHOLD)
    parser.add_argument("--apply", action="store_true")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    result = run(
        image_root=args.image_root,
        report_dir=args.report_dir,
        backup_root=args.backup_root,
        threshold=args.threshold,
        apply=args.apply,
    )
    action = "Moved" if args.apply else "Dry-run expects to move"
    count = result.applied_count if args.apply else result.expected_move_count
    print(f"{action} {count} image(s)")
    print(f"JSON manifest: {result.json_path}")
    print(f"Markdown manifest: {result.markdown_path}")


if __name__ == "__main__":
    main()
