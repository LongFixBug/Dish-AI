"""Liveness and readiness must report real dependency state."""

import asyncio

from backend import main
from backend.services import readiness


def test_liveness_does_not_depend_on_external_services(anonymous_client) -> None:
    response = anonymous_client.get("/live")

    assert response.status_code == 200
    assert response.json()["status"] == "alive"


def test_readiness_returns_503_with_failed_component(
    anonymous_client,
    monkeypatch,
) -> None:
    async def not_ready():
        return {
            "status": "not_ready",
            "components": {
                "postgres": {"ready": False, "detail": "unavailable"},
                "qdrant": {"ready": True, "detail": "ok"},
            },
        }

    monkeypatch.setattr(main, "check_readiness", not_ready)

    response = anonymous_client.get("/ready")

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"


def test_readiness_returns_200_when_required_components_are_ready(
    anonymous_client,
    monkeypatch,
) -> None:
    async def ready():
        return {
            "status": "ready",
            "components": {
                "postgres": {"ready": True, "detail": "ok"},
                "qdrant": {"ready": True, "detail": "ok"},
            },
        }

    monkeypatch.setattr(main, "check_readiness", ready)

    response = anonymous_client.get("/ready")

    assert response.status_code == 200
    assert response.json()["status"] == "ready"


async def test_readiness_component_timeout_is_reported_not_hung(
    monkeypatch,
) -> None:
    async def never_returns() -> None:
        await asyncio.Event().wait()

    monkeypatch.setattr(readiness, "CHECK_TIMEOUT_SECONDS", 0.01)

    result = await asyncio.wait_for(
        readiness._run_check(never_returns),
        timeout=0.1,
    )

    assert result == {"ready": False, "detail": "TimeoutError"}


async def test_enabled_chat_requires_local_llm_readiness(monkeypatch) -> None:
    async def ok() -> None:
        return None

    async def unavailable() -> None:
        raise RuntimeError("llama.cpp is unavailable")

    monkeypatch.setattr(readiness, "_check_postgres", ok)
    monkeypatch.setattr(readiness.object_storage, "healthcheck", ok)
    monkeypatch.setattr(readiness, "_check_chat_llm", unavailable, raising=False)
    monkeypatch.setattr(readiness.settings, "chat_enabled", True)
    monkeypatch.setattr(readiness.settings, "qdrant_required", False)
    monkeypatch.setattr(readiness.settings, "rate_limit_backend", "memory")
    monkeypatch.setattr(readiness.settings, "vision_enabled", False)
    monkeypatch.setattr(readiness.settings, "cv_enabled", False)

    report = await readiness._probe_components()

    assert report["status"] == "not_ready"
    assert report["components"]["llm"] == {
        "ready": False,
        "detail": "RuntimeError",
    }


async def test_readiness_does_not_probe_retired_image_matching(monkeypatch) -> None:
    async def ok() -> None:
        return None

    monkeypatch.setattr(readiness, "_check_postgres", ok)
    monkeypatch.setattr(readiness.object_storage, "healthcheck", ok)
    monkeypatch.setattr(readiness.settings, "chat_enabled", False)
    monkeypatch.setattr(readiness.settings, "qdrant_required", False)
    monkeypatch.setattr(readiness.settings, "rate_limit_backend", "memory")
    monkeypatch.setattr(readiness.settings, "vision_enabled", False)
    monkeypatch.setattr(readiness.settings, "cv_enabled", False)

    report = await readiness._probe_components()

    assert report["status"] == "ready"
    assert "image_embedding" not in report["components"]


async def test_lifespan_skips_optional_qdrant_initialization(monkeypatch) -> None:
    async def fail_if_called() -> None:
        raise AssertionError("optional Qdrant must not initialize")

    monkeypatch.setattr(main.settings, "qdrant_required", False)
    monkeypatch.setattr(main.settings, "cv_enabled", False)
    monkeypatch.setattr(main.settings, "chat_enabled", False)
    monkeypatch.setattr(
        "backend.services.vector_catalog.init_collection",
        fail_if_called,
    )

    async with main.lifespan(main.app):
        pass
