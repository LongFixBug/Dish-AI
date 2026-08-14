"""Load the fast-lane class allowlist from one versioned JSON contract."""

from __future__ import annotations

import json
from pathlib import Path


class FastLaneConfigError(ValueError):
    """Fast-lane configuration is missing or cannot be trusted."""


def load_fast_lane_classes(path: str | Path) -> frozenset[str]:
    """Return class slugs from the shared trainer/runtime config file."""
    config_path = Path(path)
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FastLaneConfigError(
            f"Cannot read fast-lane config: {config_path}"
        ) from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise FastLaneConfigError("Fast-lane config must use schema_version 1")
    raw_classes = payload.get("classes")
    if (
        not isinstance(raw_classes, list)
        or len(raw_classes) < 2
        or len(raw_classes) > 32
        or any(not isinstance(slug, str) or not slug.strip() for slug in raw_classes)
    ):
        raise FastLaneConfigError(
            "Fast-lane config must contain 2-32 non-empty class slugs"
        )
    classes = tuple(slug.strip() for slug in raw_classes)
    if len(set(classes)) != len(classes):
        raise FastLaneConfigError("Fast-lane config contains duplicate classes")
    return frozenset(classes)
