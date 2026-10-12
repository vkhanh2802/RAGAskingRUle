import json
import logging
import sys

from regularag.core.logging import JsonFormatter


def test_json_formatter_emits_structured_log() -> None:
    record = logging.LogRecord(
        name="regularag.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="health check completed",
        args=(),
        exc_info=None,
    )

    payload = json.loads(JsonFormatter().format(record))

    assert payload["level"] == "INFO"
    assert payload["logger"] == "regularag.test"
    assert payload["message"] == "health check completed"
    assert payload["timestamp"].endswith("+00:00")


def test_formatter_keeps_exception_type_without_backend_message_or_traceback():
    try:
        raise OSError("password=EXCEPTION_CANARY")
    except OSError:
        record = logging.LogRecord(
            "regularag.test", logging.ERROR, __file__, 1, "backend failed", (), sys.exc_info()
        )
    payload = JsonFormatter().format(record)
    assert "OSError" in payload and "CANARY" not in payload and "Traceback" not in payload
