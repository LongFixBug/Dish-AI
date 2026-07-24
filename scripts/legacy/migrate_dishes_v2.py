"""Legacy migration v2: thêm cột cho bảng dishes + tạo bảng conversion_rates.

Bảng `dishes` đã tồn tại (có 1 row test 'cơm sườn'), nên không thể dùng
Base.metadata.create_all để thêm cột (nó chỉ tạo bảng mới, không ALTER).
Script này chạy ALTER TABLE ADD COLUMN IF NOT EXISTS — idempotent, chạy lại không lỗi.

Bảng `conversion_rates` mới → do create_all lo.

Usage:
    python scripts/migrate_dishes_v2.py
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402

from backend.db.models import Base  # noqa: E402
from backend.db.postgres import engine  # noqa: E402


# ─── SQL ────────────────────────────────────────────────────────────────────

# ALTER dishes: thêm 3 cột (idempotent qua IF NOT EXISTS)
ALTER_DISHES_SQL = """
ALTER TABLE dishes
    ADD COLUMN IF NOT EXISTS status         VARCHAR(20)  NOT NULL DEFAULT 'draft',
    ADD COLUMN IF NOT EXISTS contributor_id VARCHAR(100),
    ADD COLUMN IF NOT EXISTS usage_count    INTEGER      NOT NULL DEFAULT 0;
"""


async def migrate() -> None:
    """Chạy ALTER dishes + tạo bảng conversion_rates nếu chưa có."""
    async with engine.begin() as conn:
        # 1. Thêm cột cho dishes
        await conn.execute(text(ALTER_DISHES_SQL))
        print("✅ dishes: +3 cột (status, contributor_id, usage_count)")

        # 2. Tạo bảng conversion_rates (và mọi bảng mới khác) qua create_all
        #    create_all idempotent — chỉ tạo bảng chưa tồn tại
        await conn.run_sync(Base.metadata.create_all)
        print("✅ conversion_rates: tạo bảng (nếu chưa có)")

    print("\n👉 Mở DBeaver → Refresh bảng dishes + conversion_rates để verify.")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(migrate())
