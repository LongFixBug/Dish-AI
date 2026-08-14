"""Index labelled dish photos into the configured Qdrant image collection.

The folder layout on disk is authoritative: ``<root>/<class_slug>/*.jpg``.
Each image is embedded through the configured image sidecar and published
with a deterministic uuid5 id so re-running the command stays idempotent.

Usage:
    uv run python scripts/index_dish_images.py
    uv run python scripts/index_dish_images.py data/images/references --cap 30 --force
"""

import argparse
import asyncio
import json
import logging
import sys
import uuid
from pathlib import Path

from PIL import Image

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.services.dish_image_index import (  # noqa: E402
    DishImageEntry,
    init_dish_images_collection,
    upsert_dish_image_vectors,
)

CLASS_NAMES_PATH = PROJECT_ROOT / "data" / "eval" / "class_names.json"
IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp")
EMBED_BATCH_SIZE = 16
DEFAULT_CAP_PER_CLASS = 50
DEFAULT_SOURCE = "seed"
CANDIDATE_ROOT_NAME = "references_candidate"

logger = logging.getLogger("index_dish_images")


def _resolve_embedder():
    """Import the sidecar client lazily so this module stays importable alone."""
    from backend.services.image_embeddings import embed_images

    return embed_images


def default_roots() -> list[Path]:
    """Use only the curated runtime album, never classifier training images."""
    references = PROJECT_ROOT / "data" / "images" / "references"
    return [references]


def load_class_names(path: Path | None = None) -> dict[str, str]:
    """Read the slug -> display-name mapping used for Qdrant payloads."""
    resolved = CLASS_NAMES_PATH if path is None else path
    if not resolved.is_file():
        logger.warning("Class-name mapping %s not found; using slug fallback.", resolved)
        return {}
    data = json.loads(resolved.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{resolved} must contain a JSON object of slug -> name.")
    return {str(slug): str(name) for slug, name in data.items()}


def resolve_dish_name(class_slug: str, class_names: dict[str, str]) -> str:
    """Prefer the accented display name; otherwise derive one from the slug."""
    display_name = class_names.get(class_slug)
    if display_name:
        return display_name
    return class_slug.replace("_", " ").capitalize()


def collect_image_paths(root: Path, cap: int) -> dict[str, list[Path]]:
    """Deterministically pick up to ``cap`` sorted images per class folder."""
    selected: dict[str, list[Path]] = {}
    for class_dir in sorted(path for path in root.iterdir() if path.is_dir()):
        files = sorted(
            path
            for path in class_dir.iterdir()
            if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
        )
        if files:
            selected[class_dir.name] = files[:cap]
    return selected


def load_manifest_image_paths(root: Path, manifest_path: Path) -> dict[str, list[Path]]:
    """Load only reviewed, relative paths from an album-approval manifest."""
    value = json.loads(manifest_path.read_text(encoding="utf-8"))
    paths = value.get("approved_paths") if isinstance(value, dict) else None
    if not isinstance(paths, list) or not all(isinstance(path, str) for path in paths):
        raise ValueError(f"{manifest_path} phải có approved_paths là JSON list")
    root_resolved = root.resolve()
    selected: dict[str, list[Path]] = {}
    seen: set[Path] = set()
    for raw_path in paths:
        relative = Path(raw_path)
        if relative.is_absolute():
            raise ValueError("Manifest path must stay inside album root")
        candidate = (root / relative).resolve()
        if not candidate.is_relative_to(root_resolved):
            raise ValueError("Manifest path points outside album root")
        if candidate in seen:
            raise ValueError(f"Manifest has duplicate path: {raw_path}")
        if not candidate.is_file() or candidate.suffix.lower() not in IMAGE_EXTENSIONS:
            raise ValueError(f"Manifest image is missing or unsupported: {raw_path}")
        if candidate.parent.parent != root_resolved:
            raise ValueError(f"Manifest image must use <class>/<file>: {raw_path}")
        seen.add(candidate)
        selected.setdefault(candidate.parent.name, []).append(candidate)
    return {slug: sorted(paths) for slug, paths in sorted(selected.items())}


def require_reviewed_candidate_manifest(
    root: Path,
    manifest_path: Path | None,
    *,
    demo_unverified: bool = False,
) -> None:
    """Block accidental publication of an unreviewed crawl candidate.

    Status flags alone are not evidence: every indexed path must also have a
    review record and a source/license record.  This keeps a future operator
    from changing two strings in the JSON and bypassing the candidate gate.
    """
    if root.name != CANDIDATE_ROOT_NAME:
        return
    if manifest_path is None:
        raise ValueError(
            "references_candidate chỉ được index khi có manifest review và provenance; "
            "demo cần demo_only=true và --demo-unverified"
        )
    value = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Candidate manifest phải là JSON object")
    is_demo_manifest = (
        value.get("demo_only") is True
        and value.get("review_status") == "reviewed"
        and value.get("provenance_status") == "unverified_demo"
    )
    if demo_unverified:
        if not is_demo_manifest:
            raise ValueError(
                "--demo-unverified cần manifest demo_only=true, "
                "review_status=reviewed và provenance_status=unverified_demo"
            )
    elif (
        value.get("review_status") != "reviewed"
        or value.get("provenance_status") != "reviewed"
    ):
        raise ValueError(
            "references_candidate cần manifest có review_status=reviewed "
            "và provenance_status=reviewed; nếu là demo phải dùng --demo-unverified"
        )
    approved_paths = value.get("approved_paths")
    reviewed_paths = value.get("reviewed_paths")
    if (
        not isinstance(approved_paths, list)
        or not all(isinstance(path, str) for path in approved_paths)
        or not isinstance(reviewed_paths, list)
        or not all(isinstance(path, str) for path in reviewed_paths)
        or set(approved_paths) != set(reviewed_paths)
    ):
        raise ValueError(
            "references_candidate cần reviewed_paths khớp toàn bộ approved_paths"
        )

    if demo_unverified:
        return

    records = value.get("provenance_records")
    if not isinstance(records, list):
        raise ValueError(
            "references_candidate cần provenance_records cho toàn bộ approved_paths"
        )
    by_path: dict[str, dict] = {}
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get("path"), str):
            raise ValueError("provenance_records có path không hợp lệ")
        path = record["path"]
        if path in by_path:
            raise ValueError(f"provenance_records trùng path: {path}")
        by_path[path] = record
    if set(by_path) != set(approved_paths):
        raise ValueError(
            "provenance_records phải phủ đúng toàn bộ approved_paths"
        )
    allowed_license_statuses = {
        "internal_permission",
        "user_consent",
        "public_domain",
        "cc0",
        "cc_by",
        "licensed",
    }
    for path in approved_paths:
        record = by_path[path]
        source_url = record.get("source_url")
        license_status = record.get("license_status")
        if (
            not isinstance(source_url, str)
            or not source_url.startswith(("http://", "https://"))
            or license_status not in allowed_license_statuses
        ):
            raise ValueError(
                f"provenance chưa đủ source_url/license_status: {path}"
            )


def read_valid_image(path: Path) -> bytes | None:
    """Return the raw bytes of one decodable image, or None with a warning."""
    try:
        with Image.open(path) as image:
            image.verify()
        return path.read_bytes()
    except (OSError, SyntaxError, ValueError) as error:
        logger.warning("Skipping unreadable image %s: %s", path, error)
        return None


def record_id_for(path: Path) -> str:
    """Stable uuid5 from the repo-relative path so re-indexing is idempotent."""
    resolved = path.resolve()
    try:
        key = str(resolved.relative_to(PROJECT_ROOT))
    except ValueError:
        key = str(resolved)
    return str(uuid.uuid5(uuid.NAMESPACE_URL, key))


def _warn_unmapped(per_class: dict[str, list[Path]], class_names: dict[str, str]) -> None:
    unmapped = sorted(slug for slug in per_class if slug not in class_names)
    if unmapped:
        logger.warning(
            "No display name for class slugs %s; using slug-derived names.",
            ", ".join(unmapped),
        )


async def _index_class(
    paths: list[Path],
    dish_name: str,
    class_slug: str,
    source: str,
    embed_images,
    batch_size: int,
) -> int:
    """Embed one class in batches and publish the vectors; return the count."""
    readable = [(path, read_valid_image(path)) for path in paths]
    entries = [
        DishImageEntry(
            record_id=record_id_for(path),
            dish_name=dish_name,
            class_slug=class_slug,
            source=source,
        )
        for path, data in readable
        if data is not None
    ]
    payloads = [data for _, data in readable if data is not None]
    indexed = 0
    for offset in range(0, len(entries), batch_size):
        batch_entries = entries[offset : offset + batch_size]
        batch_bytes = payloads[offset : offset + batch_size]
        vectors = await embed_images(batch_bytes)
        indexed += await upsert_dish_image_vectors(batch_entries, vectors)
    return indexed


async def index_root(
    root: Path,
    class_names: dict[str, str],
    cap: int,
    source: str,
    embed_images,
    selected_paths: dict[str, list[Path]] | None = None,
    batch_size: int = EMBED_BATCH_SIZE,
) -> dict[str, int]:
    """Index every class folder under one root; return per-class counts."""
    per_class = selected_paths if selected_paths is not None else collect_image_paths(root, cap)
    _warn_unmapped(per_class, class_names)
    counts: dict[str, int] = {}
    for class_slug, paths in per_class.items():
        dish_name = resolve_dish_name(class_slug, class_names)
        counts[class_slug] = await _index_class(
            paths, dish_name, class_slug, source, embed_images, batch_size,
        )
    return counts


def _merge_counts(left: dict[str, int], right: dict[str, int]) -> dict[str, int]:
    """Combine per-class counts from multiple roots without mutating either."""
    merged = dict(left)
    for class_slug, count in right.items():
        merged[class_slug] = merged.get(class_slug, 0) + count
    return merged


async def run(
    roots: list[Path],
    cap: int = DEFAULT_CAP_PER_CLASS,
    source: str = DEFAULT_SOURCE,
    force: bool = False,
    class_names_path: Path | None = None,
    manifest_path: Path | None = None,
    demo_unverified: bool = False,
    batch_size: int = EMBED_BATCH_SIZE,
) -> dict[str, int]:
    """Index all roots into the configured image collection and print a summary."""
    if cap < 1:
        raise ValueError("--cap must be at least 1.")
    if batch_size < 1:
        raise ValueError("--batch-size must be at least 1.")
    missing = [str(root) for root in roots if not root.is_dir()]
    if missing:
        raise FileNotFoundError(f"Image root(s) not found: {', '.join(missing)}")

    if manifest_path is not None and len(roots) != 1:
        raise ValueError("--manifest chỉ hỗ trợ một album root")
    require_reviewed_candidate_manifest(
        roots[0], manifest_path, demo_unverified=demo_unverified,
    )
    selected_paths = (
        load_manifest_image_paths(roots[0], manifest_path)
        if manifest_path is not None
        else None
    )
    class_names = load_class_names(class_names_path)
    embed_images = _resolve_embedder()
    await asyncio.to_thread(init_dish_images_collection, force)

    totals: dict[str, int] = {}
    for index, root in enumerate(roots):
        counts = await index_root(
            root,
            class_names,
            cap,
            source,
            embed_images,
            selected_paths=selected_paths if index == 0 else None,
            batch_size=batch_size,
        )
        totals = _merge_counts(totals, counts)

    for class_slug in sorted(totals):
        print(f"{class_slug}: {totals[class_slug]} images indexed")
    print(f"Total: {sum(totals.values())} images indexed")
    return totals


def build_parser() -> argparse.ArgumentParser:
    """Build the image indexing command line interface."""
    parser = argparse.ArgumentParser(
        description="Index labelled dish photos into the configured Qdrant image collection",
    )
    parser.add_argument(
        "roots",
        nargs="*",
        type=Path,
        help="Image roots laid out as <root>/<class_slug>/*.jpg "
        "(default: data/images/references only).",
    )
    parser.add_argument(
        "--cap",
        type=int,
        default=DEFAULT_CAP_PER_CLASS,
        help="Maximum images per class per root.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=EMBED_BATCH_SIZE,
        help="Number of images embedded per request (reduce on low-memory machines).",
    )
    parser.add_argument(
        "--source",
        default=DEFAULT_SOURCE,
        help='Payload source tag for the indexed points (default "seed").',
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Recreate the configured image collection before indexing.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="JSON manifest of explicitly reviewed relative album paths.",
    )
    parser.add_argument(
        "--demo-unverified",
        action="store_true",
        dest="demo_unverified",
        help=(
            "Allow an explicitly reviewed candidate manifest marked demo_only; "
            "does not satisfy production provenance requirements."
        ),
    )
    return parser


def main() -> None:
    """Parse command line arguments and run the asynchronous workflow."""
    logging.basicConfig(level=logging.INFO)
    arguments = build_parser().parse_args()
    roots = arguments.roots or default_roots()
    asyncio.run(run(
        roots,
        cap=arguments.cap,
        source=arguments.source,
        force=arguments.force,
        manifest_path=arguments.manifest,
        demo_unverified=arguments.demo_unverified,
        batch_size=arguments.batch_size,
    ))


if __name__ == "__main__":
    main()
