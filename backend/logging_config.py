"""Structured JSON logging with request correlation and secret redaction."""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, datetime

from backend.request_context import get_request_id

BEARER_PATTERN = re.compile(
    r"(?i)(authorization\s*[:=]?\s*bearer\s+)[^\s,;]+"
)
API_KEY_PATTERN = re.compile(r"\b(?:sk|key)-[A-Za-z0-9_-]{8,}\b")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        message = _redact(record.getMessage())
        payload: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": message,
            "request_id": get_request_id(),
        }
        if record.exc_info:
            payload["exception"] = _redact(self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level.upper())


def _redact(value: str) -> str:
    value = BEARER_PATTERN.sub(r"\1[REDACTED]", value)
    return API_KEY_PATTERN.sub("[REDACTED]", value)
