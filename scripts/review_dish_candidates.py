"""List, approve, or reject Vision dish candidates.

Examples:
    uv run python scripts/review_dish_candidates.py list
    uv run python scripts/review_dish_candidates.py approve <candidate-uuid>
    uv run python scripts/review_dish_candidates.py reject <candidate-uuid>
"""

import argparse
import asyncio
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.db.postgres import async_session  # noqa: E402
from backend.services.dish_candidates import (  # noqa: E402
    DishCandidateNotFoundError,
    DishCandidateStateError,
    approve_dish_candidate,
    list_pending_candidates,
    reject_dish_candidate,
)
from backend.services.vector_catalog import (  # noqa: E402
    CatalogRecord,
    CatalogType,
    upsert_catalog_record,
)


async def publish_reviewed_dish(dish: object) -> None:
    """Publish a committed catalog dish to the derived Qdrant index."""
    await upsert_catalog_record(CatalogRecord(
        record_id=str(dish.id),
        name=dish.dish_name,
        catalog_type=CatalogType.DISH,
        source=dish.source,
    ))


def build_parser() -> argparse.ArgumentParser:
    """Build the candidate-review command line interface."""
    parser = argparse.ArgumentParser(description="Review Vision dish candidates")
    commands = parser.add_subparsers(dest="command", required=True)
    list_command = commands.add_parser("list", help="List pending candidates")
    list_command.add_argument("--limit", type=int, default=50)
    for action in ("approve", "reject"):
        command = commands.add_parser(action, help=f"{action.title()} one candidate")
        command.add_argument("candidate_id")
    return parser


async def run(args: argparse.Namespace) -> None:
    """Execute one review operation in a database transaction."""
    async with async_session() as session:
        if args.command == "list":
            candidates = await list_pending_candidates(session, max(1, args.limit))
            if not candidates:
                print("No pending dish candidates.")
                return
            for candidate in candidates:
                print(
                    f"{candidate.id} | {candidate.dish_name} | "
                    f"observations={candidate.observation_count}"
                )
            return

        if args.command == "approve":
            dish = await approve_dish_candidate(session, args.candidate_id)
            await session.commit()
            try:
                await publish_reviewed_dish(dish)
            except Exception as exc:
                print(
                    "Warning: the dish was approved in PostgreSQL but Qdrant "
                    f"synchronization failed ({exc}). Run reindex_qdrant.py.",
                    file=sys.stderr,
                )
            print(f"Approved: {dish.dish_name} ({dish.id})")
            return

        candidate = await reject_dish_candidate(session, args.candidate_id)
        await session.commit()
        print(f"Rejected: {candidate.dish_name} ({candidate.id})")


def main() -> None:
    """Parse arguments and report expected review errors clearly."""
    try:
        asyncio.run(run(build_parser().parse_args()))
    except DishCandidateNotFoundError as exc:
        print(f"Candidate not found: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    except DishCandidateStateError as exc:
        print(f"Candidate is already reviewed (status={exc}).", file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
