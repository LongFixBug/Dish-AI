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
    assert head == "0017_recognition_events"
    assert len(head) <= 32
    assert revision.down_revision == "0016_meal_logs"
    assert scripts.get_revision("0004_dish_nutrition_basis").down_revision == (
        "0003_schema_contract"
    )
    assert scripts.get_revision("0001_existing_schema").down_revision is None


def test_schema_changes_only_use_alembic_revisions() -> None:
    assert not list((PROJECT_ROOT / "scripts").rglob("migrate_*.py"))
