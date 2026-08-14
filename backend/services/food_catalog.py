"""Shared resolver for the reviewed and crawled nutrition catalogs."""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Iterable
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from backend.db.models import NrihcmFood, VnDish, VnIngredient
from backend.services.dishes import (
    _nrihcm_food_to_per_gram,
    _vn_dish_to_per_gram,
    _vn_ingredient_to_per_gram,
    _has_weight,
    lookup_dish,
    lookup_dish_exact,
    lookup_ingredient,
    lookup_ingredient_text,
    lookup_nrihcm_food,
    lookup_nrihcm_food_exact,
)
from schemas.nutrition import NutritionPerGram

FoodCatalogType = Literal["vn_dish", "vn_ingredient", "nrihcm_food"]

_PRIORITY: dict[FoodCatalogType, int] = {
    "vn_dish": 3,
    "vn_ingredient": 2,
    "nrihcm_food": 1,
}


@dataclass(frozen=True)
class FoodMatch:
    """One authoritative row candidate returned by the shared resolver."""

    record_id: str
    canonical_name: str
    catalog_type: FoodCatalogType
    source: str
    nutrition_basis: str
    review_status: Literal["reviewed", "raw"]
    row: VnDish | VnIngredient | NrihcmFood

    @classmethod
    def from_row(
        cls,
        row: VnDish | VnIngredient | NrihcmFood,
        catalog_type: FoodCatalogType,
    ) -> "FoodMatch":
        if catalog_type == "vn_dish":
            name = row.dish_name
            source = row.source
            basis = "per_gram" if _has_weight(row) else "source_serving"
            status: Literal["reviewed", "raw"] = "reviewed"
        elif catalog_type == "vn_ingredient":
            name = row.ingredient_name
            source = row.source
            basis = "per_100g"
            status = "reviewed"
        else:
            name = row.name_vi
            source = "nrihcm_raw"
            basis = "per_100g"
            status = "raw"

        return cls(
            record_id=str(row.id),
            canonical_name=name,
            catalog_type=catalog_type,
            source=source,
            nutrition_basis=basis,
            review_status=status,
            row=row,
        )

    def as_dict(self) -> dict[str, str]:
        """Serialize only safe candidate metadata for the mobile client."""
        return {
            "record_id": self.record_id,
            "canonical_name": self.canonical_name,
            "catalog_type": self.catalog_type,
            "source": self.source,
            "nutrition_basis": self.nutrition_basis,
            "review_status": self.review_status,
        }


async def lookup_food_matches(
    session: AsyncSession,
    name: str,
    *,
    limit: int = 5,
) -> list[FoodMatch]:
    """Search all three catalogs, exact first and guarded fallbacks second."""
    cleaned = name.strip() if isinstance(name, str) else ""
    if not cleaned:
        return []

    exact_rows = [
        (await lookup_dish_exact(session, cleaned), "vn_dish"),
        (await lookup_ingredient_text(session, cleaned), "vn_ingredient"),
        (await lookup_nrihcm_food_exact(session, cleaned), "nrihcm_food"),
    ]
    exact_matches = _deduplicate(
        FoodMatch.from_row(row, catalog_type) for row, catalog_type in exact_rows if row is not None
    )
    if exact_matches:
        return exact_matches[:limit]

    fallback_rows = [
        (await lookup_dish(session, cleaned), "vn_dish"),
        (await lookup_ingredient(session, cleaned), "vn_ingredient"),
        (await lookup_nrihcm_food(session, cleaned), "nrihcm_food"),
    ]
    return _deduplicate(
        FoodMatch.from_row(row, catalog_type)
        for row, catalog_type in fallback_rows
        if row is not None
    )[:limit]


def choose_food_match(matches: list[FoodMatch]) -> FoodMatch | None:
    """Choose the highest-trust unique match, otherwise signal ambiguity."""
    if not matches:
        return None
    highest_priority = max(_PRIORITY[match.catalog_type] for match in matches)
    top = [match for match in matches if _PRIORITY[match.catalog_type] == highest_priority]
    return top[0] if len(top) == 1 else None


def match_to_per_gram(match: FoodMatch) -> NutritionPerGram:
    """Map any catalog row to the common nutrition-per-gram contract."""
    if match.catalog_type == "vn_dish":
        return _vn_dish_to_per_gram(match.row)
    if match.catalog_type == "vn_ingredient":
        return _vn_ingredient_to_per_gram(match.row)
    return _nrihcm_food_to_per_gram(match.row)


def _deduplicate(matches: Iterable[FoodMatch]) -> list[FoodMatch]:
    unique: dict[tuple[str, str], FoodMatch] = {}
    for match in matches:
        unique[(match.catalog_type, match.record_id)] = match
    return sorted(
        unique.values(),
        key=lambda match: (-_PRIORITY[match.catalog_type], match.canonical_name),
    )
