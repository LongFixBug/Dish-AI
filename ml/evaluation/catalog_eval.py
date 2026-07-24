"""Run deterministic lookup evaluation for the FoodAI catalog.

Unlike LLM-as-a-judge evaluation, this report is fast, repeatable, and does
not require a cloud key. It measures whether known Vietnamese dish and
ingredient queries resolve to an expected catalog name.

Usage:
    DEBUG=false python -m ml.evaluation.catalog_eval --output reports/catalog_eval.md
"""

import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

from backend.db.postgres import async_session
from backend.services.dishes import lookup_dish, lookup_ingredient


CatalogCase = tuple[str, str, str, str]

CATALOG_CASES: tuple[CatalogCase, ...] = (
    ("dish", "com suon", "sườn", "accent-insensitive dish lookup"),
    ("dish", "pho thin", "phở thìn", "accent-insensitive dish lookup"),
    ("dish", "bun cha", "bún chả", "common dish lookup"),
    ("ingredient", "sua bo", "sữa bò", "accent-insensitive ingredient lookup"),
    ("ingredient", "ca chua", "cà chua", "accent-insensitive ingredient lookup"),
    ("ingredient", "xoai", "xoài", "accent-insensitive ingredient lookup"),
    ("dish", "mon khong ton tai foodai", "", "safe catalog miss"),
)


def aggregate_results(results: list[dict[str, object]]) -> dict[str, int | float]:
    """Calculate classification accuracy and match coverage from case results."""
    total = len(results)
    expected_matches = sum(bool(row["expected"]) for row in results)
    correct_matches = sum(
        bool(row["expected"]) and bool(row["matched"]) for row in results
    )
    correct_outcomes = sum(
        bool(row["expected"]) == bool(row["matched"]) for row in results
    )
    return {
        "total": total,
        "expected_matches": expected_matches,
        "correct_matches": correct_matches,
        "accuracy": round(correct_outcomes / total, 3) if total else 0.0,
        "coverage": round(correct_matches / expected_matches, 3)
        if expected_matches
        else 0.0,
    }


def render_markdown(report: dict[str, object]) -> str:
    """Render a compact, reviewable portfolio report."""
    summary = report["summary"]
    assert isinstance(summary, dict)
    lines = [
        "# FoodAI Catalog Evaluation",
        "",
        f"Generated: {report['generated_at']}",
        f"Suite: `{report['suite']}`",
        "",
        "## Summary",
        "",
        f"- Cases: {summary['total']}",
        f"- Accuracy: **{float(summary['accuracy']) * 100:.1f}%**",
        f"- Coverage: **{float(summary['coverage']) * 100:.1f}%**",
        f"- Correct expected matches: {summary['correct_matches']}/{summary['expected_matches']}",
        "",
        "## Cases",
        "",
        "| Catalog | Query | Expected | Resolved | Result |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in report["results"]:
        assert isinstance(row, dict)
        status = "PASS" if row["expected"] == row["matched"] else "FAIL"
        lines.append(
            "| {catalog} | {query} | {expected_name} | {resolved_name} | {status} |".format(
                catalog=row["catalog"],
                query=row["query"],
                expected_name=row["expected_name"] or "catalog miss",
                resolved_name=row["resolved_name"] or "catalog miss",
                status=status,
            )
        )
    return "\n".join(lines) + "\n"


async def evaluate_catalog() -> list[dict[str, object]]:
    """Resolve curated cases against the live catalog without an LLM judge."""
    results: list[dict[str, object]] = []
    async with async_session() as session:
        for catalog, query, expected_name, note in CATALOG_CASES:
            lookup = lookup_dish if catalog == "dish" else lookup_ingredient
            record = await lookup(session, query)
            resolved_name = ""
            if record is not None:
                resolved_name = (
                    record.dish_name if catalog == "dish" else record.ingredient_name
                )
            expected = bool(expected_name)
            matched = expected_name.casefold() in resolved_name.casefold()
            if not expected:
                matched = record is not None
            results.append(
                {
                    "catalog": catalog,
                    "query": query,
                    "expected_name": expected_name,
                    "resolved_name": resolved_name,
                    "expected": expected,
                    "matched": matched,
                    "note": note,
                }
            )
    return results


async def main(output: Path | None) -> None:
    """Create a JSON report or Markdown report for the current catalog state."""
    results = await evaluate_catalog()
    report = {
        "generated_at": datetime.now(UTC).isoformat(),
        "suite": "catalog_lookup",
        "summary": aggregate_results(results),
        "results": results,
    }
    markdown = render_markdown(report)
    if output is None:
        print(markdown, end="")
        return

    output.parent.mkdir(parents=True, exist_ok=True)
    if output.suffix == ".json":
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        output.write_text(markdown, encoding="utf-8")
    print(f"Saved evaluation report: {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Evaluate FoodAI catalog lookup")
    parser.add_argument("--output", type=Path)
    asyncio.run(main(parser.parse_args().output))
