"""Index labelled dish photos into the derived Qdrant ``dish_images`` collection.

The folder layout on disk is authoritative: ``<root>/<class_slug>/*.jpg``.
Each image is embedded through the SigLIP sidecar and published with a
deterministic uuid5 id so re-running the command stays idempotent.

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
    for offset in range(0, len(entries), EMBED_BATCH_SIZE):
        batch_entries = entries[offset : offset + EMBED_BATCH_SIZE]
        batch_bytes = payloads[offset : offset + EMBED_BATCH_SIZE]
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
) -> dict[str, int]:
    """Index every class folder under one root; return per-class counts."""
    per_class = selected_paths if selected_paths is not None else collect_image_paths(root, cap)
    _warn_unmapped(per_class, class_names)
    counts: dict[str, int] = {}
    for class_slug, paths in per_class.items():
        dish_name = resolve_dish_name(class_slug, class_names)
        counts[class_slug] = await _index_class(
            paths, dish_name, class_slug, source, embed_images,
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
) -> dict[str, int]:
    """Index all roots into ``dish_images`` and print a per-class summary."""
    if cap < 1:
        raise ValueError("--cap must be at least 1.")
    missing = [str(root) for root in roots if not root.is_dir()]
    if missing:
        raise FileNotFoundError(f"Image root(s) not found: {', '.join(missing)}")

    if manifest_path is not None and len(roots) != 1:
        raise ValueError("--manifest chỉ hỗ trợ một album root")
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
        )
        totals = _merge_counts(totals, counts)

    for class_slug in sorted(totals):
        print(f"{class_slug}: {totals[class_slug]} images indexed")
    print(f"Total: {sum(totals.values())} images indexed")
    return totals


def build_parser() -> argparse.ArgumentParser:
    """Build the image indexing command line interface."""
    parser = argparse.ArgumentParser(
        description="Index labelled dish photos into the Qdrant dish_images collection",
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
        "--source",
        default=DEFAULT_SOURCE,
        help='Payload source tag for the indexed points (default "seed").',
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Recreate the dish_images collection before indexing.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="JSON manifest of explicitly reviewed relative album paths.",
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
    ))


if __name__ == "__main__":
    main()
