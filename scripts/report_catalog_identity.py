"""Report canonical catalog readiness for the closed EfficientNet class set.

The report deliberately distinguishes an exact PostgreSQL dish from a Qdrant
semantic variant.  A semantic hit is useful for investigation, but it is not
silently promoted to the runtime catalog identity because its nutrition basis
may describe a different preparation.

Usage:
    DEBUG=false uv run python scripts/report_catalog_identity.py
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.db.postgres import async_session  # noqa: E402
from backend.services.dishes import lookup_dish, lookup_dish_exact  # noqa: E402
from backend.services.catalog_aliases import is_reviewed_catalog_alias  # noqa: E402
from backend.services.recognition_cascade import is_name_refinement  # noqa: E402

DEFAULT_CLASSES_FILE = PROJECT_ROOT / "data/eval/efficientnet_tier_a_classes.json"
DEFAULT_NAMES_FILE = PROJECT_ROOT / "data/eval/class_names.json"
DEFAULT_REPORT_DIR = PROJECT_ROOT / "ml/evaluation/reports"

ResolutionStatus = Literal[
    "exact",
    "curated_alias",
    "semantic_variant_pending_review",
    "semantic_incompatible",
    "missing",
]


@dataclass(frozen=True)
class CatalogResolution:
    """One closed-set class and the catalog identity it can safely use."""

    slug: str
    requested_name: str
    status: ResolutionStatus
    catalog_name: str | None
    catalog_id: str | None
    source: str | None
    typical_grams: float | None
    typical_grams_source: str | None
    typical_grams_confidence: float | None
    typical_grams_rule: str | None
    requires_human_review: bool


def load_target_classes(classes_path: Path, names_path: Path) -> dict[str, str]:
    """Load the closed-set slugs and require a display name for every slug."""
    classes_value = json.loads(classes_path.read_text(encoding="utf-8"))
    classes = classes_value.get("classes") if isinstance(classes_value, dict) else classes_value
    if not isinstance(classes, list) or not all(isinstance(item, str) for item in classes):
        raise ValueError(f"{classes_path} phải là JSON list hoặc object có classes")

    names_value = json.loads(names_path.read_text(encoding="utf-8"))
    if not isinstance(names_value, dict):
        raise ValueError(f"{names_path} phải là JSON object slug -> tên")
    missing = sorted(set(classes) - set(names_value))
    if missing:
        raise ValueError(f"Thiếu tên hiển thị cho class: {', '.join(missing)}")
    return {slug: str(names_value[slug]) for slug in sorted(set(classes))}


def classify_resolution(
    requested_name: str,
    canonical_name: str | None,
    catalog_id: str | None,
    *,
    exact: bool,
    alias_reviewed: bool = False,
    slug: str = "",
) -> CatalogResolution:
    """Classify exact, semantic-variant, incompatible, and missing matches."""
    if not canonical_name or not catalog_id:
        status: ResolutionStatus = "missing"
    elif exact:
        status = "exact"
    elif alias_reviewed:
        status = "curated_alias"
    elif is_name_refinement(requested_name, canonical_name):
        status = "semantic_variant_pending_review"
    else:
        status = "semantic_incompatible"
    return CatalogResolution(
        slug=slug,
        requested_name=requested_name,
        status=status,
        catalog_name=canonical_name,
        catalog_id=catalog_id,
        source=None,
        typical_grams=None,
        typical_grams_source=None,
        typical_grams_confidence=None,
        typical_grams_rule=None,
        requires_human_review=status not in {"exact", "curated_alias"},
    )


def summarize_resolutions(resolutions: list[CatalogResolution]) -> dict[str, int | bool]:
    """Return the small gate summary used by CI and the plan document."""
    counts = {status: 0 for status in ResolutionStatus.__args__}
    for resolution in resolutions:
        counts[resolution.status] += 1
    review_count = sum(resolution.requires_human_review for resolution in resolutions)
    return {
        "total": len(resolutions),
        **counts,
        "requires_human_review": review_count,
        "ready": bool(resolutions)
        and counts["exact"] + counts["curated_alias"] == len(resolutions),
    }


async def collect_resolutions(class_names: dict[str, str]) -> list[CatalogResolution]:
    """Resolve each class through exact PostgreSQL, then guarded semantic lookup."""
    resolutions: list[CatalogResolution] = []
    async with async_session() as session:
        for slug, requested_name in class_names.items():
            exact_row = await lookup_dish_exact(session, requested_name)
            row = exact_row or await lookup_dish(session, requested_name)
            resolution = classify_resolution(
                requested_name,
                row.dish_name if row is not None else None,
                str(row.id) if row is not None else None,
                exact=exact_row is not None,
                alias_reviewed=(
                    exact_row is None
                    and row is not None
                    and is_reviewed_catalog_alias(requested_name, row.dish_name)
                ),
                slug=slug,
            )
            if row is not None:
                resolution = replace(
                    resolution,
                    source=row.source,
                    typical_grams=float(row.typical_grams)
                    if row.typical_grams is not None
                    else None,
                    typical_grams_source=row.typical_grams_source,
                    typical_grams_confidence=float(row.typical_grams_confidence),
                    typical_grams_rule=row.typical_grams_rule,
                )
            resolutions.append(resolution)
    return resolutions


def write_report(
    report_path: Path,
    class_names: dict[str, str],
    resolutions: list[CatalogResolution],
) -> Path:
    """Write a deterministic catalog-readiness artifact."""
    payload = {
        "schema_version": 1,
        "generated_at": datetime.now(UTC).isoformat(),
        "class_source": "data/eval/efficientnet_tier_a_classes.json",
        "catalog": "vn_dishes",
        "semantic_lookup_required_for_non_exact": True,
        "requested_classes": class_names,
        "summary": summarize_resolutions(resolutions),
        "resolutions": [asdict(resolution) for resolution in resolutions],
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return report_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Report catalog identity readiness")
    parser.add_argument("--classes-file", type=Path, default=DEFAULT_CLASSES_FILE)
    parser.add_argument("--names-file", type=Path, default=DEFAULT_NAMES_FILE)
    parser.add_argument("--output", type=Path, default=None)
    return parser


async def async_main(args: argparse.Namespace) -> Path:
    class_names = load_target_classes(args.classes_file, args.names_file)
    resolutions = await collect_resolutions(class_names)
    report_path = args.output or (
        DEFAULT_REPORT_DIR
        / f"catalog_identity_readiness_{datetime.now(UTC):%Y%m%d_%H%M%S}.json"
    )
    return write_report(report_path, class_names, resolutions)


def main() -> None:
    args = build_parser().parse_args()
    path = asyncio.run(async_main(args))
    print(f"Report: {path}")


if __name__ == "__main__":
    main()
