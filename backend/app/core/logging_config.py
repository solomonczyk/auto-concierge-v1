"""
Structured logging configuration.

- JSON format in production for log aggregation (ELK, Loki, etc.)
- Fields: timestamp, level, message, service, environment, request_id (when available)
- Stack traces in logs; no secrets leaked to client
"""
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any

from app.core.config import settings

SERVICE_NAME = "autoservice-api"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()


class StructuredJSONFormatter(logging.Formatter):
    """JSON formatter for structured logs."""

    def format(self, record: logging.LogRecord) -> str:
        log_obj: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "service": SERVICE_NAME,
            "environment": settings.ENVIRONMENT,
        }
        if hasattr(record, "request_id") and record.request_id:
            log_obj["request_id"] = record.request_id
        if hasattr(record, "tenant_id") and record.tenant_id is not None:
            log_obj["tenant_id"] = record.tenant_id
        if hasattr(record, "correlation_id") and record.correlation_id:
            log_obj["correlation_id"] = record.correlation_id
        for k, v in record.__dict__.items():
            if k not in (
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "pathname", "process", "processName", "relativeCreated",
                "stack_info", "exc_info", "exc_text", "thread", "threadName",
                "message", "taskName", "request_id", "tenant_id", "correlation_id",
            ) and v is not None:
                log_obj[k] = v
        if record.exc_info:
            log_obj["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_obj, default=str, ensure_ascii=False)


class StructuredTextFormatter(logging.Formatter):
    """Human-readable structured format (dev)."""

    def format(self, record: logging.LogRecord) -> str:
        base = super().format(record)
        extras = []
        if hasattr(record, "request_id") and record.request_id:
            extras.append(f"rid={record.request_id}")
        if hasattr(record, "tenant_id") and record.tenant_id is not None:
            extras.append(f"tid={record.tenant_id}")
        if extras:
            return f"{base} [{', '.join(extras)}]"
        return base


def configure_logging() -> None:
    """Configure root logger with structured format."""
    root = logging.getLogger()
    root.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

    for h in root.handlers[:]:
        root.removeHandler(h)

    handler = logging.StreamHandler()
    handler.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

    if settings.is_production:
        handler.setFormatter(StructuredJSONFormatter())
    else:
        handler.setFormatter(
            StructuredTextFormatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
        )

    root.addHandler(handler)
    logging.getLogger("aiogram").setLevel(logging.INFO)
