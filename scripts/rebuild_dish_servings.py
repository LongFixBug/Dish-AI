"""Rebuild default serving estimates for institute dishes.

The Institute catalog contains a dish-portion nutrition total but not its
weight. This command estimates an editable default serving from dish family and
total energy, then records the rule and confidence. It never overwrites reviewed
Vision dishes.

Usage:
    uv run python scripts/rebuild_dish_servings.py
    uv run python scripts/rebuild_dish_servings.py --apply
"""

import argparse
import asyncio
import sys
from collections import Counter
from pathlib import Path

from sqlalchemy import text

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.db.postgres import async_session  # noqa: E402
from backend.services.serving_estimates import estimate_serving_grams  # noqa: E402


async def rebuild(*, apply: bool) -> tuple[int, Counter[str]]:
    """Preview or persist a reproducible estimate for every institute dish."""
    async with async_session() as session:
        result = await session.execute(text("""
            SELECT id::text, dish_name, total_calories
            FROM vn_dishes
            WHERE source = 'vnmeal'
            ORDER BY dish_name
        """))
        rows = result.all()
        estimates = [
            (dish_id, dish_name, estimate_serving_grams(dish_name, calories))
            for dish_id, dish_name, calories in rows
        ]
        categories = Counter(estimate.category for _, _, estimate in estimates)

        for _, dish_name, estimate in estimates[:20]:
            print(
                f"{dish_name[:48]:48s} {estimate.grams:>4.0f} g "
                f"{estimate.category} ({estimate.confidence:.0%})"
            )
        print(f"\nEstimated {len(estimates)} institute dishes: {dict(categories)}")

        if apply:
            for dish_id, _, estimate in estimates:
                await session.execute(text("""
                    UPDATE vn_dishes
                    SET typical_grams = :grams,
                        typical_grams_source = :source,
                        typical_grams_confidence = :confidence,
                        typical_grams_rule = :rule
                    WHERE id = CAST(:dish_id AS uuid)
                """), {
                    "dish_id": dish_id,
                    "grams": estimate.grams,
                    "source": estimate.source,
                    "confidence": estimate.confidence,
                    "rule": estimate.category,
                })
            await session.commit()
            print("Applied serving estimates to vnmeal dishes.")
        return len(estimates), categories


def main() -> None:
    """Require an explicit flag before changing catalog data."""
    parser = argparse.ArgumentParser(description="Rebuild institute serving estimates")
    parser.add_argument("--apply", action="store_true", help="Persist estimates")
    args = parser.parse_args()
    asyncio.run(rebuild(apply=args.apply))


if __name__ == "__main__":
    main()
