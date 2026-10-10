import json
import logging

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
