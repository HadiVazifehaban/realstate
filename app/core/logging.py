"""Structured logging setup shared by local node and cloud hub."""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone

_CONFIGURED = False


class JsonFormatter(logging.Formatter):
    """Minimal JSON log formatter (no external dependency)."""

    def format(self, record: logging.LogRecord) -> str:  # noqa: A003
        payload = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Attach extra structured fields passed via ``logger.info(..., extra=...)``.
        for key in ("node_mode", "event", "license_status", "request_id"):
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(*, debug: bool = False, json_output: bool = False) -> None:
    """Idempotently configure the root logger."""
    global _CONFIGURED
    if _CONFIGURED:
        return
    handler = logging.StreamHandler(sys.stdout)
    if json_output:
        handler.setFormatter(JsonFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)-8s %(name)s: %(message)s")
        )
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.DEBUG if debug else logging.INFO)
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
