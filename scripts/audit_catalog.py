"""Audit the PostgreSQL nutrition catalog without mutating it.

Examples:
  uv run python scripts/audit_catalog.py
  uv run python scripts/audit_catalog.py --format json --fail-on error
  uv run python scripts/audit_catalog.py --output artifacts/catalog-audit.md
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from sqlalchemy import select

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.db.models import DishCandidate, VnDish, VnIngredient
from backend.db.postgres import async_session
from backend.services.catalog_audit import audit_catalog_records, render_markdown_report


def _row_dict(record: object) -> dict[str, object]:
    return {
        column.name: getattr(record, column.name)
        for column in record.__table__.columns  # type: ignore[attr-defined]
    }


async def create_report() -> dict[str, object]:
    """Read a consistent catalog snapshot and evaluate all quality rules."""
    async with async_session() as session:
        ingredients = list((await session.scalars(select(VnIngredient))).all())
        dishes = list((await session.scalars(select(VnDish))).all())
        candidates = list((await session.scalars(select(DishCandidate))).all())
    return audit_catalog_records(
        ingredients=[_row_dict(row) for row in ingredients],
        dishes=[_row_dict(row) for row in dishes],
        candidates=[_row_dict(row) for row in candidates],
    )


def _should_fail(report: dict[str, object], threshold: str) -> bool:
    summary = report["summary"]
    assert isinstance(summary, dict)
    if threshold == "warning":
        return bool(summary["errors"] or summary["warnings"])
    if threshold == "error":
        return bool(summary["errors"])
    return False


async def main() -> int:
    parser = argparse.ArgumentParser(description="Audit FoodAI catalog quality")
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--fail-on",
        choices=("error", "warning", "never"),
        default="never",
        help="Exit 1 when the selected severity is present (default: never)",
    )
    args = parser.parse_args()

    report = await create_report()
    rendered = (
        json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n"
        if args.format == "json"
        else render_markdown_report(report)
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(f"Catalog audit written to {args.output}")
    else:
        print(rendered, end="")
    return 1 if _should_fail(report, args.fail_on) else 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
