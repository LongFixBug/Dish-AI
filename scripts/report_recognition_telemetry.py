"""Summarize recognition gates without reading or exporting image bytes."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Iterable

from sqlalchemy import select

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.db.models import RecognitionEvent  # noqa: E402
from backend.db.postgres import async_session  # noqa: E402

REPORTS_DIR = PROJECT_ROOT / "ml" / "evaluation" / "reports"


def _value(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None


def summarize_rows(rows: Iterable[SimpleNamespace]) -> dict[str, object]:
    """Aggregate decision metadata into an operator-friendly report."""
    source_counts: Counter[str] = Counter()
    reason_counts: Counter[str] = Counter()
    confusion_counts: Counter[tuple[str, str]] = Counter()
    events = 0
    for row in rows:
        events += 1
        source_counts[str(row.source)] += 1
        reason_counts[_value(row.fusion_reason) or "unknown"] += 1
        top1 = _value(row.cv_top1_name)
        top2 = _value(row.cv_top2_name)
        if top1 and top2 and top1 != top2:
            confusion_counts[(top1, top2)] += 1

    return {
        "events": events,
        "by_source": dict(sorted(source_counts.items())),
        "by_fusion_reason": dict(sorted(reason_counts.items())),
        "cv_confusions": [
            {"top1": top1, "top2": top2, "count": count}
            for (top1, top2), count in sorted(
                confusion_counts.items(),
                key=lambda item: (-item[1], item[0]),
            )
        ],
    }


async def load_rows() -> list[SimpleNamespace]:
    """Read only recognition metadata; images and object keys stay private."""
    async with async_session() as session:
        result = await session.execute(
            select(
                RecognitionEvent.source,
                RecognitionEvent.final_dish_name,
                RecognitionEvent.cv_top1_name,
                RecognitionEvent.cv_top2_name,
                RecognitionEvent.cv_top2_confidence,
                RecognitionEvent.fusion_reason,
            ).order_by(RecognitionEvent.created_at.desc())
        )
    return [SimpleNamespace(**row._mapping) for row in result]


async def build_report() -> dict[str, object]:
    return {
        "timestamp": datetime.now().astimezone().isoformat(),
        "suite": "recognition_telemetry",
        "privacy_policy": "metadata only; no image bytes or object keys",
        **summarize_rows(await load_rows()),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Report local recognition telemetry")
    parser.add_argument("--output", type=Path, default=None)
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    report = await build_report()
    output = args.output
    if output is None:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        output = REPORTS_DIR / f"recognition_telemetry_{datetime.now():%Y%m%d_%H%M%S}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"Report saved: {output}")


if __name__ == "__main__":
    asyncio.run(main())
