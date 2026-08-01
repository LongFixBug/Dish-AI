"""Create a read-only active-learning queue from recognition metadata and feedback.

The report never promotes a feedback image into training.  It only identifies
which source paths have human labels that differ from the displayed answer so
an admin can review those consent-backed submissions first.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import unicodedata
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Iterable

from sqlalchemy import and_, select

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.db.models import FeedbackSubmission, RecognitionEvent  # noqa: E402
from backend.db.postgres import async_session  # noqa: E402

REPORTS_DIR = PROJECT_ROOT / "ml" / "evaluation" / "reports"
REVIEWABLE_STATUSES = frozenset({"pending", "approved"})


def _slugify(value: str | None) -> str:
    if not value:
        return ""
    decomposed = unicodedata.normalize("NFKD", value.replace("Đ", "D").replace("đ", "d"))
    plain = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"[-\s]+", "_", re.sub(r"[^\w\s-]", "", plain).strip().lower())


def summarize_rows(rows: Iterable[SimpleNamespace]) -> dict[str, object]:
    """Summarize source volume and label disagreements without trusting them yet."""
    by_source: dict[str, dict[str, int]] = defaultdict(
        lambda: {
            "events": 0,
            "linked_feedback": 0,
            "label_disagreements_pending_review": 0,
        }
    )
    queue: list[dict[str, str]] = []
    for row in rows:
        source = str(row.source)
        summary = by_source[source]
        summary["events"] += 1
        feedback_slug = row.feedback_slug
        feedback_status = row.feedback_status
        if not isinstance(feedback_slug, str) or feedback_status not in REVIEWABLE_STATUSES:
            continue
        summary["linked_feedback"] += 1
        if feedback_slug == _slugify(row.final_dish_name):
            continue
        summary["label_disagreements_pending_review"] += 1
        queue.append(
            {
                "source": source,
                "predicted_dish": str(row.final_dish_name or ""),
                "human_label_slug": feedback_slug,
                "feedback_status": str(feedback_status),
            }
        )
    return {
        "by_source": dict(sorted(by_source.items())),
        "review_queue": sorted(
            queue,
            key=lambda item: (
                item["source"],
                item["predicted_dish"],
                item["human_label_slug"],
            ),
        ),
    }


async def load_rows() -> list[SimpleNamespace]:
    """Read events and same-user feedback with no image payload or object key."""
    async with async_session() as session:
        result = await session.execute(
            select(
                RecognitionEvent.source,
                RecognitionEvent.final_dish_name,
                FeedbackSubmission.dish_name_slug,
                FeedbackSubmission.status,
            )
            .outerjoin(
                FeedbackSubmission,
                and_(
                    FeedbackSubmission.recognition_event_id == RecognitionEvent.id,
                    FeedbackSubmission.status.in_(REVIEWABLE_STATUSES),
                ),
            )
            .order_by(RecognitionEvent.created_at.desc())
        )
    return [
        SimpleNamespace(
            source=row.source,
            final_dish_name=row.final_dish_name,
            feedback_slug=row.dish_name_slug,
            feedback_status=row.status,
        )
        for row in result
    ]


async def build_report() -> dict[str, object]:
    report = summarize_rows(await load_rows())
    return {
        "timestamp": datetime.now().astimezone().isoformat(),
        "suite": "recognition_active_learning",
        "feedback_policy": "labels stay pending review; this report never trains or reindexes them",
        **report,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Report recognition active-learning queue")
    parser.add_argument("--output", type=Path, default=None)
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    report = await build_report()
    output = args.output
    if output is None:
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        output = REPORTS_DIR / f"active_learning_{datetime.now():%Y%m%d_%H%M%S}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print(f"Report saved: {output}")


if __name__ == "__main__":
    asyncio.run(main())
