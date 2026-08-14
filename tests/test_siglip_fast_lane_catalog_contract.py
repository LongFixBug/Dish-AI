"""The SigLIP fast-lane classes must have stable display names."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_every_fast_lane_slug_has_a_display_name() -> None:
    config = json.loads(
        (ROOT / "data/config/siglip_fast_lane.json").read_text(encoding="utf-8")
    )
    class_names = json.loads(
        (ROOT / "data/eval/class_names.json").read_text(encoding="utf-8")
    )

    slugs = config["classes"]
    assert len(slugs) == len(set(slugs))
    assert all(isinstance(class_names.get(slug), str) for slug in slugs)


def test_new_fast_lane_slugs_use_the_agreed_vietnamese_names() -> None:
    class_names = json.loads(
        (ROOT / "data/eval/class_names.json").read_text(encoding="utf-8")
    )

    assert {
        slug: class_names[slug]
        for slug in (
            "che",
            "khoai_lang_luoc",
            "rau_luoc",
            "uc_ga_luoc",
        )
    } == {
        "che": "Chè",
        "khoai_lang_luoc": "Khoai lang luộc",
        "rau_luoc": "Rau luộc",
        "uc_ga_luoc": "Ức gà luộc",
    }
