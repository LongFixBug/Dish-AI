"""Deterministic quality rules for the authoritative nutrition catalog.

The functions in this module are pure: they inspect dictionaries and return
issues or an explicit cleanup plan. Database scripts can therefore preview and
test every mutation before applying it.
"""

from __future__ import annotations

import unicodedata
from collections import defaultdict
from collections.abc import Mapping
from typing import Any

TINY_NEGATIVE_TOLERANCE = 0.001
MAX_KCAL_PER_GRAM = 9.0
MAX_MACRO_MASS_RATIO = 1.25
ENERGY_MISMATCH_RATIO = 0.50

INGREDIENT_NUTRIENT_FIELDS = (
    "calories_per_g",
    "protein_per_g",
    "fat_per_g",
    "carbs_per_g",
    "fiber_per_g",
)
DISH_NUTRIENT_FIELDS = (
    "total_calories",
    "total_protein_g",
    "total_fat_g",
    "total_carbs_g",
    "total_fiber_g",
)


def canonical_name_key(name: str) -> str:
    """Normalize case and spacing while preserving meaningful Vietnamese tones."""
    normalized = unicodedata.normalize("NFC", str(name or ""))
    return " ".join(normalized.strip().split()).casefold()


def accent_insensitive_name_key(name: str) -> str:
    """Build a search-style key used only to warn about ambiguous collisions."""
    value = unicodedata.normalize("NFKD", canonical_name_key(name).replace("đ", "d"))
    return "".join(char for char in value if not unicodedata.combining(char))


def _number(record: Mapping[str, object], field: str) -> float:
    value = record.get(field, 0.0)
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


def _record_id(record: Mapping[str, object]) -> str:
    return str(record.get("id", ""))


def _record_name(record: Mapping[str, object], entity_type: str) -> str:
    field = "dish_name" if entity_type in {"dish", "candidate"} else "ingredient_name"
    return str(record.get(field, ""))


def _energy_mismatch(record: Mapping[str, object], entity_type: str) -> float:
    if entity_type == "ingredient":
        calories = _number(record, "calories_per_g")
        protein = _number(record, "protein_per_g")
        fat = _number(record, "fat_per_g")
        carbs = _number(record, "carbs_per_g")
    else:
        calories = _number(record, "total_calories")
        protein = _number(record, "total_protein_g")
        fat = _number(record, "total_fat_g")
        carbs = _number(record, "total_carbs_g")
    if calories <= 0:
        return 1.0
    macro_calories = 4 * protein + 9 * fat + 4 * carbs
    return abs(calories - macro_calories) / calories


def _dish_physical_codes(record: Mapping[str, object]) -> list[str]:
    grams = _number(record, "typical_grams")
    if grams <= 0:
        return []
    codes: list[str] = []
    if _number(record, "total_calories") / grams > MAX_KCAL_PER_GRAM:
        codes.append("implausible_energy_density")
    macro_mass = sum(
        _number(record, field)
        for field in ("total_protein_g", "total_fat_g", "total_carbs_g", "total_fiber_g")
    )
    if macro_mass > grams * MAX_MACRO_MASS_RATIO:
        codes.append("implausible_macro_mass")
    return codes


def _quality_key(record: Mapping[str, object], entity_type: str) -> tuple[Any, ...]:
    nutrient_fields = (
        INGREDIENT_NUTRIENT_FIELDS if entity_type == "ingredient" else DISH_NUTRIENT_FIELDS
    )
    negative_count = sum(_number(record, field) < 0 for field in nutrient_fields)
    physical_count = len(_dish_physical_codes(record)) if entity_type == "dish" else 0
    completeness = sum(_number(record, field) > 0 for field in nutrient_fields)
    confidence = _number(record, "typical_grams_confidence")
    return (
        negative_count,
        physical_count,
        round(_energy_mismatch(record, entity_type), 8),
        -completeness,
        -confidence,
        _record_id(record),
    )


def _duplicate_groups(
    records: list[Mapping[str, object]], entity_type: str
) -> list[list[Mapping[str, object]]]:
    groups: dict[tuple[str, ...], list[Mapping[str, object]]] = defaultdict(list)
    for record in records:
        source = str(record.get("source", "")) if entity_type == "ingredient" else ""
        groups[(source, canonical_name_key(_record_name(record, entity_type)))].append(record)
    return [group for group in groups.values() if len(group) > 1]


def deduplicate_catalog_rows(
    records: list[Mapping[str, object]], *, entity_type: str
) -> list[Mapping[str, object]]:
    """Return one deterministic survivor per canonical source/name group.

    Vietnamese tones remain part of the key. Ingredient names are unique only
    inside one source because two institutions may legitimately publish the
    same food with different measurements.
    """
    if entity_type not in {"ingredient", "dish"}:
        raise ValueError("entity_type must be 'ingredient' or 'dish'")

    grouped: dict[tuple[str, ...], list[tuple[int, Mapping[str, object]]]] = defaultdict(list)
    for position, record in enumerate(records):
        source = str(record.get("source", "")) if entity_type == "ingredient" else ""
        key = (source, canonical_name_key(_record_name(record, entity_type)))
        grouped[key].append((position, record))

    survivors: list[tuple[int, Mapping[str, object]]] = []
    for group in grouped.values():
        survivors.append(
            min(
                group,
                key=lambda item: (_quality_key(item[1], entity_type), item[0]),
            )
        )
    survivors.sort(key=lambda item: item[0])
    return [record for _, record in survivors]


def build_cleanup_plan(
    *,
    ingredients: list[Mapping[str, object]],
    dishes: list[Mapping[str, object]],
    candidates: list[Mapping[str, object]],
) -> list[dict[str, object]]:
    """Plan only conservative repairs; ambiguous data remains an audit warning."""
    actions: list[dict[str, object]] = []
    archived_ids: set[str] = set()
    for entity_type, records in (("ingredient", ingredients), ("dish", dishes)):
        for group in _duplicate_groups(records, entity_type):
            survivor = min(group, key=lambda record: _quality_key(record, entity_type))
            for record in group:
                record_id = _record_id(record)
                if record_id == _record_id(survivor):
                    continue
                archived_ids.add(record_id)
                actions.append(
                    {
                        "action": "archive_duplicate",
                        "entity_type": entity_type,
                        "record_id": record_id,
                        "survivor_id": _record_id(survivor),
                        "reason": "case_or_whitespace_duplicate",
                        "changes": {},
                        "before": dict(record),
                    }
                )

    for record in ingredients:
        record_id = _record_id(record)
        if record_id in archived_ids:
            continue
        changes = {
            field: 0.0
            for field in INGREDIENT_NUTRIENT_FIELDS
            if -TINY_NEGATIVE_TOLERANCE <= _number(record, field) < 0
        }
        if changes:
            actions.append(
                {
                    "action": "clamp_tiny_negative",
                    "entity_type": "ingredient",
                    "record_id": record_id,
                    "reason": "rounding_artifact",
                    "changes": changes,
                    "before": dict(record),
                }
            )

    for record in dishes:
        record_id = _record_id(record)
        if record_id in archived_ids:
            continue
        physical_codes = _dish_physical_codes(record)
        if physical_codes:
            actions.append(
                {
                    "action": "quarantine_serving_weight",
                    "entity_type": "dish",
                    "record_id": record_id,
                    "reason": ",".join(physical_codes),
                    "changes": {
                        "typical_grams": None,
                        "typical_grams_source": "catalog_audit_quarantine",
                        "typical_grams_confidence": 0.0,
                        "typical_grams_rule": "+".join(physical_codes),
                    },
                    "before": dict(record),
                }
            )

    for record in candidates:
        if record.get("status") != "pending":
            continue
        if _number(record, "typical_grams") > 0 and _number(record, "total_calories") > 0:
            continue
        actions.append(
            {
                "action": "reject_invalid_candidate",
                "entity_type": "candidate",
                "record_id": _record_id(record),
                "reason": "missing_positive_weight_or_calories",
                "changes": {"status": "rejected"},
                "before": dict(record),
            }
        )

    actions.sort(key=lambda action: (str(action["action"]), str(action["record_id"])))
    return actions

