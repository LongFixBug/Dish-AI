"""Seed the reviewed Vietnamese nutrition reference snapshot into PostgreSQL."""

from __future__ import annotations

import argparse
import asyncio
import json
from datetime import datetime
from pathlib import Path

from sqlalchemy import delete
from sqlalchemy.dialects.postgresql import insert

from backend.db.models import NutritionReferenceTarget
from backend.db.postgres import async_session


async def seed(path: Path, apply: bool) -> int:
    payload = json.loads(path.read_text(encoding="utf-8"))
    records = payload["records"]
    if not apply:
        print(f"Dry run: {len(records)} records found in {path}")
        return len(records)

    async with async_session() as session:
        standard = payload["metadata"]["standard"]
        await session.execute(
            delete(NutritionReferenceTarget).where(
                NutritionReferenceTarget.standard == standard
            )
        )
        values = [
            {
                **record,
                "source_fetched_at": datetime.fromisoformat(record["fetched_at"]),
            }
            for record in records
        ]
        values = [
            {
                key: value
                for key, value in record.items()
                if key
                not in {
                    "fetched_at",
                    "standard",
                }
            }
            | {
                "standard": standard,
                "source_fetched_at": record["source_fetched_at"],
            }
            for record in values
        ]
        await session.execute(insert(NutritionReferenceTarget), values)
        await session.commit()
    print(f"Seeded {len(records)} records into nutrition_reference_targets")
    return len(records)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/vn_nutrition_reference_targets.json"),
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Delete the current standard and insert the snapshot.",
    )
    args = parser.parse_args()
    asyncio.run(seed(args.input, args.apply))


if __name__ == "__main__":
    main()
