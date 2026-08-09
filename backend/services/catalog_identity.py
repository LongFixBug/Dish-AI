"""Lexical guards for resolving Vision names to the nutrition catalog.

This module deliberately has no image-model or Qdrant dependency.  It is used
by the Vision-only runtime to prevent a fuzzy catalog lookup from silently
changing one dish into another dish with different nutrition.
"""

from backend.services.catalog_aliases import is_reviewed_catalog_alias
from backend.services.menu_vocabulary import (
    DISH_FAMILY_TOKENS,
    MENU_STOP_TOKENS,
    accent_tokens,
)


def _refinement_tokens(name: str) -> list[str]:
    """Return meaningful menu tokens while ignoring connector words."""
    return [token for token in accent_tokens(name) if token not in MENU_STOP_TOKENS]


def is_name_refinement(query_name: str, resolved_name: str) -> bool:
    """Allow only an exact lexical name or a same-family refinement."""
    query_tokens = _refinement_tokens(query_name)
    resolved_tokens = _refinement_tokens(resolved_name)
    if not query_tokens or not resolved_tokens:
        return False
    if query_tokens[0] != resolved_tokens[0]:
        return False
    if len(query_tokens) == 1 and query_tokens[0] in DISH_FAMILY_TOKENS:
        return query_tokens == resolved_tokens
    return set(query_tokens) <= set(resolved_tokens)


def is_catalog_identity_safe(query_name: str, resolved_name: str) -> bool:
    """Accept safe lexical refinements or an explicitly reviewed alias."""
    return is_name_refinement(query_name, resolved_name) or is_reviewed_catalog_alias(
        query_name,
        resolved_name,
    )
