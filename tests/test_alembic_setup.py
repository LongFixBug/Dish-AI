"""Alembic must own schema evolution and keep historical scripts isolated."""

from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_alembic_has_linear_baseline_and_schema_revision() -> None:
    config = Config(PROJECT_ROOT / "alembic.ini")
    scripts = ScriptDirectory.from_config(config)
    head = scripts.get_current_head()
    revision = scripts.get_revision(head)

    assert revision is not None
    assert head == "0012_production_hardening"
    assert len(head) <= 32
    assert revision.down_revision == "0011_feedback"
    assert scripts.get_revision("0004_dish_nutrition_basis").down_revision == (
        "0003_schema_contract"
    )
    assert scripts.get_revision("0001_existing_schema").down_revision is None


def test_legacy_migrations_are_isolated_from_active_scripts() -> None:
    legacy_dir = PROJECT_ROOT / "scripts" / "legacy"

    assert (legacy_dir / "README.md").exists()
    assert not list((PROJECT_ROOT / "scripts").glob("migrate_*.py"))
    assert len(list(legacy_dir.glob("migrate_*.py"))) == 5
