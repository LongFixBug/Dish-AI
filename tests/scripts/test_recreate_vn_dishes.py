"""Contracts for the demo-only canonical catalog copies."""

from scripts.recreate_vn_dishes import DEMO_CANONICAL_COPIES, DEMO_CANONICAL_COPY_SQL


def test_demo_canonical_copies_match_the_owner_mappings() -> None:
    assert DEMO_CANONICAL_COPIES == (
        ("Bánh canh thịt heo", "Bánh canh"),
        ("Canh cá lóc (Các quả) nấu chua", "Canh chua"),
        ("Bún nem nướng", "Bún thịt nướng"),
        ("Cá chày kho", "Cá kho tộ"),
    )


def test_demo_canonical_copy_parameters_have_explicit_postgres_types() -> None:
    """One bind used in INSERT and lower() must not rely on asyncpg inference."""
    sql = str(DEMO_CANONICAL_COPY_SQL)

    assert "CAST(:target_name AS VARCHAR)" in sql
    assert "CAST(:source_name AS VARCHAR)" in sql
