"""Tạo tất cả bảng trong database FoodAI.

Chạy 1 lần duy nhất trước khi seed dữ liệu.

Usage:
    python scripts/create_tables.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backend.db.models import Base  # noqa: E402
from backend.db.postgres import engine, async_session  # noqa: E402
from sqlalchemy import text  # noqa: E402


async def create_all() -> None:
    """Tạo tất cả bảng từ model đã định nghĩa."""
    async with engine.begin() as conn:
        # Tạo extension vector nếu chưa có
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        # Tạo bảng từ SQLAlchemy models
        await conn.run_sync(Base.metadata.create_all)

    print("✅ Đã tạo xong tất cả bảng.")
    print("👉 Mở DBeaver → chuột phải vào Tables → Refresh để thấy.")
    await engine.dispose()


if __name__ == "__main__":
    import asyncio
    asyncio.run(create_all())
