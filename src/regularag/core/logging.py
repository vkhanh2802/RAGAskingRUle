import json
import logging
from datetime import UTC, datetime

from regularag.core.tracing import request_id


class JsonFormatter(logging.Formatter):
    """Emit one JSON object per log event for local and hosted environments."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if identifier := getattr(record, "request_id", None) or request_id():
            payload["request_id"] = identifier
        if record.name == "regularag.trace" and hasattr(record, "trace"):
            payload["trace"] = record.trace
        if record.exc_info:
            payload["exception_type"] = record.exc_info[0].__name__
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(level)
    # HTTP client info/debug logs can include query strings, outside the trace allowlist.
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
