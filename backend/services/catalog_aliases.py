"""Explicitly reviewed aliases from model labels to nutrition catalog rows."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from backend.services.menu_vocabulary import accent_tokens

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ALIAS_PATH = PROJECT_ROOT / "data/eval/catalog_identity_overrides.json"


def _normalized_key(name: str) -> str:
    """Create the accent-insensitive key used by the alias contract."""
    return " ".join(accent_tokens(name))


def load_catalog_aliases(path: Path = DEFAULT_ALIAS_PATH) -> dict[str, str]:
    """Load only well-formed, explicitly reviewed query → canonical aliases."""
    try:
        payload: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    rows = payload.get("aliases") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return {}

    aliases: dict[str, str] = {}
    for row in rows:
        if not isinstance(row, dict) or row.get("status") != "reviewed":
            continue
        query = row.get("query")
        canonical = row.get("canonical_name")
        query_key = _normalized_key(query) if isinstance(query, str) else ""
        if not query_key or not isinstance(canonical, str) or not canonical.strip():
            continue
        aliases[query_key] = canonical.strip()
    return aliases


@lru_cache(maxsize=1)
def _default_catalog_aliases() -> dict[str, str]:
    """Cache the versioned runtime alias file for the process lifetime."""
    return load_catalog_aliases(DEFAULT_ALIAS_PATH)


def get_reviewed_catalog_alias(name: str) -> str | None:
    """Return the canonical target for one reviewed alias, if present."""
    if not isinstance(name, str) or not name.strip():
        return None
    return _default_catalog_aliases().get(_normalized_key(name))


def is_reviewed_catalog_alias(query: str, canonical_name: str) -> bool:
    """Check both sides so an unrelated row cannot pass the alias gate."""
    target = get_reviewed_catalog_alias(query)
    if target is None or not isinstance(canonical_name, str):
        return False
    return _normalized_key(target) == _normalized_key(canonical_name)
