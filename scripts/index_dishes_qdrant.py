"""Index vn_dishes vào Qdrant để vector search semantic fallback.

Phiên bản Jul 23: chỉ index vn_dishes (bỏ user dishes — model Dish đã xóa).
Chạy: uv run python scripts/index_dishes_qdrant.py
"""

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from backend.db.postgres import async_session
from backend.services.qdrant_dishes import index_all_dishes, init_collection

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


async def main() -> None:
    init_collection(force=True)

    async with async_session() as session:
        r = await session.execute(
            text("SELECT dish_name, id::text FROM vn_dishes ORDER BY dish_name")
        )
        vn = [(row[0], row[1]) for row in r.fetchall()]
        logger.info("vn_dishes: %d", len(vn))

    count = await index_all_dishes(vn)
    logger.info("Done: %d/%d indexed", count, len(vn))


if __name__ == "__main__":
    asyncio.run(main())
