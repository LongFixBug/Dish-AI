"""Conservatively clean the authoritative catalog with a recoverable journal.

The default is a dry run. ``--apply`` commits PostgreSQL first; optional
Qdrant deletion happens only after that commit succeeds.

Examples:
  uv run python scripts/cleanup_vn_dishes.py
  uv run python scripts/cleanup_vn_dishes.py --apply --sync-qdrant
  uv run python scripts/cleanup_vn_dishes.py --sync-qdrant
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select, update

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.db.models import CatalogCleanupLog, DishCandidate, VnDish, VnIngredient
from backend.db.postgres import async_session
from backend.services.catalog_quality import build_cleanup_plan
from backend.services.vector_catalog import delete_catalog_records

MODEL_BY_ENTITY = {
    "ingredient": VnIngredient,
    "dish": VnDish,
    "candidate": DishCandidate,
}


def _json_value(value: Any) -> Any:
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _row_dict(record: object) -> dict[str, object]:
    return {
        column.name: _json_value(getattr(record, column.name))
        for column in record.__table__.columns  # type: ignore[attr-defined]
    }


async def _load_records(session) -> tuple[list[object], list[object], list[object]]:
    ingredients = list((await session.scalars(select(VnIngredient))).all())
    dishes = list((await session.scalars(select(VnDish))).all())
    candidates = list((await session.scalars(select(DishCandidate))).all())
    return ingredients, dishes, candidates


async def create_plan() -> list[dict[str, object]]:
    """Build the exact mutation plan from a read-only catalog snapshot."""
    async with async_session() as session:
        ingredients, dishes, candidates = await _load_records(session)
    return build_cleanup_plan(
        ingredients=[_row_dict(row) for row in ingredients],
        dishes=[_row_dict(row) for row in dishes],
        candidates=[_row_dict(row) for row in candidates],
    )


async def apply_plan(plan: list[dict[str, object]]) -> int:
    """Journal and apply one plan atomically inside PostgreSQL."""
    async with async_session() as session:
        for action in plan:
            entity_type = str(action["entity_type"])
            record_id = str(action["record_id"])
            model = MODEL_BY_ENTITY[entity_type]
            record = await session.get(model, record_id)
            if record is None:
                raise RuntimeError(f"{entity_type} {record_id} changed after dry-run")

            session.add(CatalogCleanupLog(
                entity_type=entity_type,
                record_id=record_id,
                action=str(action["action"]),
                reason=str(action["reason"]),
                survivor_id=(
                    str(action["survivor_id"]) if action.get("survivor_id") else None
                ),
                snapshot=_row_dict(record),
                changes=dict(action.get("changes", {})),
            ))

            if action["action"] == "archive_duplicate":
                if entity_type == "dish":
                    await session.execute(
                        update(DishCandidate)
                        .where(DishCandidate.approved_dish_id == record_id)
                        .values(approved_dish_id=action["survivor_id"])
                    )
                await session.delete(record)
                continue

            for field, value in dict(action.get("changes", {})).items():
                setattr(record, field, value)
            if action["action"] == "reject_invalid_candidate":
                record.reviewed_at = datetime.now(timezone.utc)

        await session.commit()
    return len(plan)


async def sync_pending_qdrant_deletes() -> int:
    """Delete archived IDs from Qdrant, then mark only acknowledged logs."""
    async with async_session() as session:
        logs = list((await session.scalars(
            select(CatalogCleanupLog).where(
                CatalogCleanupLog.action == "archive_duplicate",
                CatalogCleanupLog.qdrant_synced_at.is_(None),
            )
        )).all())
        record_ids = [log.record_id for log in logs]

    deleted = await delete_catalog_records(record_ids)
    if not logs:
        return deleted

    synced_at = datetime.now(timezone.utc)
    async with async_session() as session:
        await session.execute(
            update(CatalogCleanupLog)
            .where(
                CatalogCleanupLog.action == "archive_duplicate",
                CatalogCleanupLog.qdrant_synced_at.is_(None),
                CatalogCleanupLog.record_id.in_(record_ids),
            )
            .values(qdrant_synced_at=synced_at)
        )
        await session.commit()
    return deleted


def _print_plan(plan: list[dict[str, object]]) -> None:
    if not plan:
        print("Catalog is already clean; no PostgreSQL mutations planned.")
        return
    print(f"Planned actions: {len(plan)}")
    for action in plan:
        print(json.dumps({
            "action": action["action"],
            "entity_type": action["entity_type"],
            "record_id": action["record_id"],
            "survivor_id": action.get("survivor_id"),
            "reason": action["reason"],
            "changes": action.get("changes", {}),
        }, ensure_ascii=False, default=str))


async def main() -> int:
    parser = argparse.ArgumentParser(description="Clean FoodAI catalog safely")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Commit the printed plan (without this flag the command is read-only)",
    )
    parser.add_argument(
        "--sync-qdrant",
        action="store_true",
        help="Delete archived PostgreSQL UUIDs from the derived Qdrant index",
    )
    args = parser.parse_args()

    plan = await create_plan()
    _print_plan(plan)
    if args.apply and plan:
        applied = await apply_plan(plan)
        print(f"Committed {applied} journaled PostgreSQL actions.")
    elif plan:
        print("Dry run only. Re-run with --apply after reviewing this plan.")

    if args.sync_qdrant:
        deleted = await sync_pending_qdrant_deletes()
        print(f"Qdrant acknowledged {deleted} archived point deletions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
