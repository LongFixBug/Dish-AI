"""Database connection — SQLAlchemy async engine + session factory.

Dùng asyncpg driver cho PostgreSQL (async, connection pool tự động).

Usage:
    from backend.db.postgres import get_session

    async with get_session() as session:
        result = await session.execute(...)
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.config import settings

# Engine — quản lý connection pool, không tự đóng
engine = create_async_engine(
    settings.database_url,
    pool_size=10,           # 10 connections sẵn sàng
    max_overflow=5,         # thêm tối đa 5 khi quá tải
    pool_pre_ping=True,     # loại connection đã chết trước khi giao cho request
    pool_recycle=1800,      # tránh connection sống lâu hơn timeout hạ tầng
    echo=settings.debug,    # in SQL ra console khi debug=True
)

# Session factory — mỗi request gọi 1 lần
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # để object còn dùng được sau commit
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Trả về 1 async session, tự đóng khi xong (dùng với async with)."""
    async with async_session() as session:
        yield session
