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

from collections.abc import AsyncGenerator, Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from backend.config import settings
from backend.main import app
from backend.services.auth import TokenManager


@pytest.fixture(autouse=True)
def _album_offline_by_default(monkeypatch) -> None:
    """Tắt image cascade trong test để suite kín (hermetic).

    Khi sidecar :8082 + Qdrant thật đang chạy trên máy dev, analyze/feedback
    test sẽ gọi NHẦM vào hạ tầng thật: ăn kết quả album thật và ghi rác vào
    collection ``dish_images``. Test nào cần đường album thì tự bật lại
    ``image_embed_enabled=True`` và mock embed/upsert.
    """
    monkeypatch.setattr(settings, "image_embed_enabled", False)


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """Authenticated FastAPI test client for existing endpoint contracts."""
    token, _ = TokenManager.from_settings(settings).create_access_token(
        user_id="00000000-0000-0000-0000-000000000001",
        role="user",
    )
    with TestClient(
        app,
        headers={"Authorization": f"Bearer {token}"},
    ) as test_client:
        yield test_client


@pytest.fixture
def anonymous_client() -> Generator[TestClient, None, None]:
    """FastAPI client without implicit authentication."""
    with TestClient(app) as test_client:
        yield test_client


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
