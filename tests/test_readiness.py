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
