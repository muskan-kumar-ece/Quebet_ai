import contextvars
import json
import logging
import re
from datetime import datetime, timezone
from typing import Any

# ContextVar for request-scoped correlation ID
request_id_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar("request_id", default=None)

SENSITIVE_PATTERNS = [
    re.compile(r"bearer\s+[a-zA-Z0-9_\-\.]+", re.IGNORECASE),
    re.compile(r"sk-[a-zA-Z0-9_\-]{20,}", re.IGNORECASE),
    re.compile(r"password['\"]?\s*[:=]\s*['\"][^'\"]+['\"]", re.IGNORECASE),
]


def sanitize_log_message(msg: str) -> str:
    """Redacts passwords, JWTs, and API keys from log strings."""
    redacted = msg
    for pattern in SENSITIVE_PATTERNS:
        redacted = pattern.sub("[REDACTED]", redacted)
    return redacted


class JSONFormatter(logging.Formatter):
    """
    Standard structured JSON log formatter for production observability.
    Emits timestamp, level, service, environment, request_id, and event.
    """

    def __init__(self, service: str = "quebet-backend", environment: str = "production"):
        super().__init__()
        self.service = service
        self.environment = environment

    def format(self, record: logging.LogRecord) -> str:
        req_id = request_id_ctx.get() or getattr(record, "request_id", None)
        raw_msg = record.getMessage()
        safe_msg = sanitize_log_message(raw_msg)

        log_record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "service": self.service,
            "environment": self.environment,
            "logger": record.name,
            "request_id": req_id,
            "event": safe_msg,
        }

        if record.exc_info and not record.exc_text:
            record.exc_text = self.formatException(record.exc_info)
        if record.exc_text:
            log_record["exception"] = sanitize_log_message(record.exc_text)

        return json.dumps(log_record)


def configure_logging(level: int = logging.INFO) -> None:
    """Configures structured JSON logging on the root logger."""
    root = logging.getLogger()
    root.setLevel(level)

    # Avoid duplicate handlers if called multiple times
    if not any(isinstance(h.formatter, JSONFormatter) for h in root.handlers):
        handler = logging.StreamHandler()
        handler.setFormatter(JSONFormatter())
        root.handlers = [handler]
