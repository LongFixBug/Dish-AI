"""Shared test fixtures.

- `client`: FastAPI TestClient (sync) cho endpoint test đơn giản.
- `db_session`: AsyncSession thật (DB 5432) cho integration test cần
  query DB + SQL function `vn_norm`.

Lưu ý về engine: KHÔNG dùng global `async_session` từ backend.db.postgres
trong test, vì engine đó tạo ở import-time gắn với event loop của app runtime.
pytest-asyncio (mode=auto) tạo event loop riêng mỗi test → connection pool
cũ thuộc loop đã đóng → asyncpg InterfaceError. Fixture này tạo engine +
session factory RIÊNG cho mỗi test, dispose khi xong → sạch, không xung đột.
"""

from collections.abc import AsyncGenerator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.config import settings
from backend.main import app


@pytest.fixture
def client() -> TestClient:
    """FastAPI test client (sync)."""
    return TestClient(app)


@pytest.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """AsyncSession thật — engine riêng cho test, tự đóng + dispose khi xong.

    Dùng cho integration test cần query DB + SQL function vn_norm.
    Test tự cleanup data nó tạo (commit/rollback tùy test).
    """
    engine = create_async_engine(settings.database_url, echo=settings.debug)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    await engine.dispose()
