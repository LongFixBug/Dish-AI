"""Deterministic display-name cleanup for Vietnamese ingredients."""

from __future__ import annotations

import unicodedata
from collections import defaultdict
from collections.abc import Iterable


_ENGLISH_PARENTHESES_MARKERS = frozenset(
    {
        "baked",
        "boiled",
        "chicken",
        "cooked",
        "cow",
        "dried",
        "fish",
        "flavour",
        "fluid",
        "fresh",
        "fruit",
        "heart",
        "high",
        "jackfruit",
        "lean",
        "leg",
        "loin",
        "meat",
        "milk",
        "noodles",
        "quality",
        "raw",
        "rice",
        "roasted",
        "sauce",
        "shrimp",
        "skin",
        "snail",
        "steamed",
        "style",
        "whole",
    }
)


def _trailing_parenthetical(name: str) -> tuple[int, str] | None:
    """Return the start and body of the final balanced parenthetical group."""
    if not name.endswith(")"):
        return None

    depth = 0
    for index in range(len(name) - 1, -1, -1):
        character = name[index]
        if character == ")":
            depth += 1
        elif character == "(":
            depth -= 1
        if depth == 0:
            return index, name[index + 1 : -1]
    return None


def clean_ingredient_name(name: str) -> str:
    """Remove trailing English translations while keeping Vietnamese qualifiers.

    A parenthetical group is considered English only when it contains ASCII
    letters and no non-ASCII characters. This preserves useful qualifiers such
    as ``(đỏ, trắng)`` while removing nested groups such as ``(Milk (Fluid))``.
    """
    cleaned = " ".join(unicodedata.normalize("NFC", str(name or "")).split())
    while True:
        parenthetical = _trailing_parenthetical(cleaned)
        if parenthetical is None:
            return cleaned

        start, body = parenthetical
        ascii_words = {
            word.casefold()
            for word in body.split()
            if word.isascii() and word.isalpha()
        }
        is_ascii_english = any(character.isascii() and character.isalpha() for character in body)
        has_non_ascii = any(not character.isascii() for character in body)
        mixed_english = bool(ascii_words & _ENGLISH_PARENTHESES_MARKERS)
        if not is_ascii_english or (has_non_ascii and not mixed_english):
            return cleaned
        cleaned = cleaned[:start].rstrip()


def clean_ingredient_name_batch(
    records: Iterable[tuple[str, str, str]],
) -> dict[str, str]:
    """Clean names and disambiguate source-level collisions deterministically.

    The catalog keeps one row per source/name pair. If two English aliases
    collapse to the same Vietnamese name, retain both rows and mark later
    rows with a Vietnamese sample suffix instead of dropping nutrition data.
    """
    prepared = [
        (record_id, name, source, clean_ingredient_name(name))
        for record_id, name, source in records
    ]
    grouped: dict[tuple[str, str], list[tuple[str, str]]] = defaultdict(list)
    for record_id, original_name, source, cleaned_name in sorted(
        prepared,
        key=lambda record: (
            record[2].casefold(),
            record[3].casefold(),
            record[1].casefold(),
            record[0],
        ),
    ):
        grouped[(source.casefold(), cleaned_name.casefold())].append(
            (record_id, cleaned_name)
        )

    result: dict[str, str] = {}
    for records_for_name in grouped.values():
        for index, (record_id, cleaned_name) in enumerate(records_for_name, start=1):
            result[record_id] = (
                cleaned_name if index == 1 else f"{cleaned_name} [mẫu {index}]"
            )
    return result
