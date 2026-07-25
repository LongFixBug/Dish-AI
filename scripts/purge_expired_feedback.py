#!/usr/bin/env python3
"""Delete expired feedback objects and retain an auditable tombstone."""

import asyncio
from datetime import UTC, datetime

from sqlalchemy import select

from backend.config import settings
from backend.db.models import FeedbackSubmission
from backend.db.postgres import async_session, engine
from backend.services.object_storage import create_object_storage


async def purge() -> int:
    storage = create_object_storage(settings)
    now = datetime.now(UTC)
    deleted = 0
    async with async_session() as session:
        submissions = list(
            await session.scalars(
                select(FeedbackSubmission).where(
                    FeedbackSubmission.retention_until <= now,
                    FeedbackSubmission.status != "deleted",
                )
            )
        )
        for submission in submissions:
            await storage.delete(submission.object_key)
            submission.status = "deleted"
            submission.reviewed_at = now
            deleted += 1
        await session.commit()
    await engine.dispose()
    return deleted


if __name__ == "__main__":
    print(asyncio.run(purge()))
