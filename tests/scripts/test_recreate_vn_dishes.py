"""Contracts for the demo-only canonical catalog copies."""

from scripts.recreate_vn_dishes import DEMO_CANONICAL_COPIES


def test_demo_canonical_copies_match_the_owner_mappings() -> None:
    assert DEMO_CANONICAL_COPIES == (
        ("Bánh canh thịt heo", "Bánh canh"),
        ("Canh cá lóc (Các quả) nấu chua", "Canh chua"),
        ("Bún nem nướng", "Bún thịt nướng"),
        ("Cá chày kho", "Cá kho tộ"),
    )
