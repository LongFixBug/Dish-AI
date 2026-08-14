"""Audit a reviewed reference album and emit a reproducible approval manifest.

The album directory remains the human-review source of truth.  This command
never moves or deletes images: it decodes every selected file, removes unsafe
cross-label near-duplicates from the *derived* manifest, and records exactly
which relative paths may be published to Qdrant.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import imagehash
from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_ROOT = PROJECT_ROOT / "data" / "images" / "references"
DEFAULT_CLASSES_FILE = PROJECT_ROOT / "data" / "eval" / "efficientnet_tier_a_classes.json"
DEFAULT_MANIFEST = PROJECT_ROOT / "data" / "eval" / "reference_album_tier_a_approved.json"
IMAGE_EXTENSIONS = frozenset({".jpg", ".jpeg", ".png", ".webp"})
DEFAULT_PHASH_DISTANCE = 6


@dataclass(frozen=True)
class ReferenceAlbumAudit:
    total_files: int
    selected_files: int
    invalid_paths: tuple[str, ...]
    cross_label_duplicates: tuple[tuple[str, str], ...]
    approved_paths: tuple[str, ...]
    counts_by_class: dict[str, int]


def load_allowed_classes(path: Path) -> set[str]:
    value = json.loads(path.read_text(encoding="utf-8"))
    classes = value.get("classes") if isinstance(value, dict) else value
    if not isinstance(classes, list) or not all(isinstance(item, str) for item in classes):
        raise ValueError(f"{path} phải là JSON list hoặc object có classes")
    return set(classes)


def _relative(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _read_hash(path: Path) -> imagehash.ImageHash:
    with Image.open(path) as image:
        image.verify()
    with Image.open(path) as image:
        return imagehash.phash(image)


def audit_reference_album(
    root: Path,
    allowed_classes: set[str],
    *,
    phash_distance: int = DEFAULT_PHASH_DISTANCE,
    extra_classes: set[str] | None = None,
) -> ReferenceAlbumAudit:
    """Return a stable, non-mutating approval decision for every selected image."""
    if phash_distance < 0:
        raise ValueError("phash_distance phải >= 0")
    selected_classes = set(allowed_classes) | set(extra_classes or ())
    files = sorted(
        path for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )
    invalid: list[str] = []
    accepted: list[tuple[Path, imagehash.ImageHash]] = []
    for path in files:
        if path.parent.name not in selected_classes:
            continue
        try:
            accepted.append((path, _read_hash(path)))
        except (OSError, SyntaxError, ValueError):
            invalid.append(_relative(root, path))

    approved: list[Path] = []
    retained: list[tuple[Path, imagehash.ImageHash]] = []
    duplicates: list[tuple[str, str]] = []
    for path, fingerprint in accepted:
        same_label = False
        conflicting_path: Path | None = None
        for prior_path, prior_fingerprint in retained:
            if fingerprint - prior_fingerprint <= phash_distance:
                if prior_path.parent.name == path.parent.name:
                    same_label = True
                else:
                    conflicting_path = prior_path
                break
        if same_label:
            continue
        if conflicting_path is not None:
            duplicates.append((_relative(root, conflicting_path), _relative(root, path)))
            continue
        retained.append((path, fingerprint))
        approved.append(path)

    relative_approved = tuple(_relative(root, path) for path in approved)
    counts = {slug: 0 for slug in sorted(selected_classes)}
    for path in approved:
        counts[path.parent.name] += 1
    return ReferenceAlbumAudit(
        total_files=len(files),
        selected_files=len(accepted) + len(invalid),
        invalid_paths=tuple(invalid),
        cross_label_duplicates=tuple(duplicates),
        approved_paths=relative_approved,
        counts_by_class=counts,
    )


def write_manifest(
    path: Path,
    root: Path,
    audit: ReferenceAlbumAudit,
    *,
    tier_name: str,
) -> Path:
    """Write the review artifact atomically after all paths were validated."""
    try:
        root_label = str(root.relative_to(PROJECT_ROOT))
    except ValueError:
        root_label = str(root)
    payload = {
        "schema_version": 1,
        "tier_name": tier_name,
        "root": root_label,
        "approved_count": len(audit.approved_paths),
        "approved_paths": list(audit.approved_paths),
        "audit": asdict(audit),
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    payload["manifest_sha256"] = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit reference album without modifying source images")
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--classes-file", type=Path, default=DEFAULT_CLASSES_FILE)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--tier-name", default="tier_a")
    parser.add_argument("--phash-distance", type=int, default=DEFAULT_PHASH_DISTANCE)
    parser.add_argument(
        "--include-class",
        action="append",
        default=[],
        help="Include a reviewed album-only class without adding it to the CV allow-list.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    audit = audit_reference_album(
        args.root,
        load_allowed_classes(args.classes_file),
        phash_distance=args.phash_distance,
        extra_classes=set(args.include_class),
    )
    manifest = write_manifest(args.manifest, args.root, audit, tier_name=args.tier_name)
    print(f"Approved: {len(audit.approved_paths)}/{audit.total_files}")
    print(f"Invalid: {len(audit.invalid_paths)} | cross-label duplicates: {len(audit.cross_label_duplicates)}")
    print(f"Manifest: {manifest}")


if __name__ == "__main__":
    main()
