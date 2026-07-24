"""Compatibility command that upgrades the database through Alembic.

Prefer running ``uv run alembic upgrade head`` directly. This wrapper keeps the
project's former setup command safe for existing documentation and workflows.
"""

import asyncio
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.db.postgres import engine  # noqa: E402


async def _needs_baseline_stamp() -> bool:
    """Detect a complete pre-Alembic catalog without guessing partial schemas."""
    async with engine.connect() as connection:
        result = await connection.execute(text("""
            SELECT
                to_regclass('public.alembic_version') IS NOT NULL,
                to_regclass('public.vn_ingredients') IS NOT NULL,
                to_regclass('public.vn_dishes') IS NOT NULL
        """))
        has_version, has_ingredients, has_dishes = result.one()

    if has_version:
        return False
    if has_ingredients != has_dishes:
        raise RuntimeError(
            "Partial legacy schema detected; inspect the database before stamping."
        )
    return has_ingredients and has_dishes


async def create_all() -> None:
    """Bring fresh or complete legacy databases to the latest revision."""
    config = Config(PROJECT_ROOT / "alembic.ini")
    if await _needs_baseline_stamp():
        await asyncio.to_thread(command.stamp, config, "0001_existing_schema")
    await asyncio.to_thread(command.upgrade, config, "head")
    await engine.dispose()
    print("Database schema is at the latest Alembic revision.")


if __name__ == "__main__":
    try:
        asyncio.run(create_all())
    except Exception as exc:
        print(f"Database migration failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
