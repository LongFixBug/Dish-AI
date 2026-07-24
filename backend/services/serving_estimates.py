"""Reproducible, low-confidence serving estimates for institute dish records.

The source catalog provides nutrition for one dish portion but not its weight.
These rules combine dish family and total energy only to supply an editable
default portion; they never claim to be measured serving sizes.
"""

import math
import re
import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class ServingEstimate:
    """One transparent serving-size estimate and its provenance."""

    grams: float
    category: str
    confidence: float
    source: str = "nutrition_heuristic_v1"


@dataclass(frozen=True)
class ServingProfile:
    """Portion bounds and reference energy for one Vietnamese dish family."""

    category: str
    keywords: tuple[str, ...]
    base_grams: float
    min_grams: float
    max_grams: float
    reference_calories: float
    confidence: float


_PROFILES = (
    ServingProfile(
        "dry_noodles",
        ("bun cha", "bun dau", "bun nam bo", "bun nem", "bun thit nuong"),
        400.0,
        300.0,
        450.0,
        450.0,
        0.55,
    ),
    ServingProfile(
        "protein_dish",
        ("pha lau",),
        250.0,
        150.0,
        400.0,
        350.0,
        0.35,
    ),
    ServingProfile(
        "snack",
        ("bim bim", "keo", "bong ngo", "bap rang"),
        50.0,
        25.0,
        100.0,
        150.0,
        0.3,
    ),
    ServingProfile(
        "hotpot",
        ("lau",),
        900.0,
        600.0,
        1400.0,
        650.0,
        0.35,
    ),
    ServingProfile(
        "noodle_soup",
        ("pho", "bun", "hu tieu", "mien", "mi quang", "banh canh"),
        500.0,
        400.0,
        650.0,
        350.0,
        0.5,
    ),
    ServingProfile(
        "porridge",
        ("chao",),
        400.0,
        300.0,
        550.0,
        250.0,
        0.45,
    ),
    ServingProfile(
        "rice_meal",
        ("com",),
        400.0,
        300.0,
        550.0,
        500.0,
        0.5,
    ),
    ServingProfile(
        "soup_or_stew",
        ("canh", "sup"),
        350.0,
        250.0,
        550.0,
        220.0,
        0.35,
    ),
    ServingProfile(
        "dessert",
        ("che", "caramen", "flan", "rau cau", "tau hu", "kem"),
        220.0,
        120.0,
        350.0,
        250.0,
        0.4,
    ),
    ServingProfile(
        "beverage",
        ("tra", "ca phe", "nuoc", "sinh to", "sua"),
        300.0,
        180.0,
        500.0,
        200.0,
        0.45,
    ),
    ServingProfile(
        "pastry",
        ("banh", "xoi"),
        125.0,
        50.0,
        300.0,
        220.0,
        0.35,
    ),
    ServingProfile(
        "protein_dish",
        ("thit", "ca", "tom", "muc", "ga", "vit", "bo", "suon", "dau phu"),
        200.0,
        100.0,
        400.0,
        300.0,
        0.3,
    ),
)
_FALLBACK = ServingProfile(
    "fallback",
    (),
    250.0,
    100.0,
    450.0,
    350.0,
    0.2,
)


def _normalize_name(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", name.casefold())
    no_tones = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", " ", no_tones.replace("đ", "d")).strip()


def _profile_for_name(dish_name: str) -> ServingProfile:
    normalized = f" {_normalize_name(dish_name)} "
    for profile in _PROFILES:
        if any(f" {keyword} " in normalized for keyword in profile.keywords):
            return profile
    return _FALLBACK


def _round_to_25(grams: float) -> float:
    return round(grams / 25.0) * 25.0


def estimate_serving_grams(
    dish_name: str,
    total_calories: float,
) -> ServingEstimate:
    """Estimate one default serving from food family and source total energy.

    Energy scales a family baseline by at most 25 percent in either direction,
    preventing unusual source portions from producing implausible weights.
    """
    profile = _profile_for_name(dish_name)
    if not math.isfinite(total_calories) or total_calories <= 0:
        grams = profile.base_grams
    else:
        scale = total_calories / profile.reference_calories
        grams = profile.base_grams * min(max(scale, 0.75), 1.25)
    bounded = min(max(grams, profile.min_grams), profile.max_grams)
    return ServingEstimate(
        grams=_round_to_25(bounded),
        category=profile.category,
        confidence=profile.confidence,
    )
