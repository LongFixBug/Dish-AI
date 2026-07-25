#!/usr/bin/env python3
"""Remove expired and long-revoked refresh-token records."""

import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, or_

from backend.db.models import RefreshToken
from backend.db.postgres import async_session, engine


async def purge() -> int:
    now = datetime.now(UTC)
    revoked_before = now - timedelta(days=30)
    async with async_session() as session:
        result = await session.execute(
            delete(RefreshToken).where(
                or_(
                    RefreshToken.expires_at <= now,
                    RefreshToken.revoked_at <= revoked_before,
                )
            )
        )
        await session.commit()
    await engine.dispose()
    return int(result.rowcount or 0)


if __name__ == "__main__":
    print(asyncio.run(purge()))
