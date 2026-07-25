"""Request tracing, structured logging and metrics contracts."""

import json
import logging

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.logging_config import JsonFormatter
from backend.middleware.observability import ObservabilityMiddleware
from backend import main


def test_request_id_is_returned_and_untrusted_value_is_replaced() -> None:
    app = FastAPI()
    app.add_middleware(ObservabilityMiddleware)

    @app.get("/items/{item_id}")
    async def item(item_id: str) -> dict[str, str]:
        return {"id": item_id}

    with TestClient(app) as client:
        generated = client.get("/items/123", headers={"x-request-id": "bad value!"})
        preserved = client.get(
            "/items/456",
            headers={"x-request-id": "mobile-request-123"},
        )

    assert generated.headers["x-request-id"] != "bad value!"
    assert preserved.headers["x-request-id"] == "mobile-request-123"


def test_json_formatter_includes_request_id_and_redacts_bearer_token() -> None:
    formatter = JsonFormatter()
    record = logging.LogRecord(
        name="foodai.test",
        level=logging.ERROR,
        pathname=__file__,
        lineno=1,
        msg="Authorization: Bearer secret-token-value",
        args=(),
        exc_info=None,
    )

    payload = json.loads(formatter.format(record))

    assert payload["level"] == "ERROR"
    assert payload["logger"] == "foodai.test"
    assert "secret-token-value" not in payload["message"]
    assert "[REDACTED]" in payload["message"]


def test_metrics_endpoint_requires_configured_bearer_token(
    anonymous_client,
    monkeypatch,
) -> None:
    monkeypatch.setattr(main.settings, "metrics_token", "metrics-secret")

    rejected = anonymous_client.get("/metrics")
    accepted = anonymous_client.get(
        "/metrics",
        headers={"Authorization": "Bearer metrics-secret"},
    )

    assert rejected.status_code == 401
    assert accepted.status_code == 200
    assert "foodai_http_requests_total" in accepted.text
