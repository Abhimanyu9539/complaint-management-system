import json
import logging
import sys

from cms.config.logging_config import TEXT_FORMAT, ContextFilter, JsonFormatter
from cms.observability.context import request_id_var, ticket_id_var


def _record(message: str = "hello", exc_info=None, **extra) -> logging.LogRecord:
    record = logging.makeLogRecord(
        {"name": "cms.test", "levelname": "INFO", "msg": message, "exc_info": exc_info, **extra}
    )
    ContextFilter().filter(record)
    return record


def test_json_line_carries_the_ids_that_are_set_and_the_extra_fields() -> None:
    request_token = request_id_var.set("req-1")
    ticket_token = ticket_id_var.set("t1")
    try:
        record = _record(duration_ms=12)
    finally:
        ticket_id_var.reset(ticket_token)
        request_id_var.reset(request_token)

    entry = json.loads(JsonFormatter().format(record))

    assert entry["message"] == "hello" and entry["level"] == "INFO" and entry["logger"] == "cms.test"
    assert entry["request_id"] == "req-1" and entry["ticket_id"] == "t1"
    # An id that is not set is left out rather than written as null.
    assert "run_id" not in entry
    assert entry["duration_ms"] == 12


def test_json_line_includes_the_exception() -> None:
    try:
        raise ValueError("boom")
    except ValueError:
        record = _record(exc_info=sys.exc_info())

    entry = json.loads(JsonFormatter().format(record))

    assert "ValueError: boom" in entry["exc_info"]


def test_text_line_has_no_brackets_without_ids() -> None:
    line = logging.Formatter(TEXT_FORMAT).format(_record())

    assert line.endswith("INFO     cms.test: hello")


def test_text_line_shows_the_ids() -> None:
    token = request_id_var.set("req-1")
    try:
        record = _record()
    finally:
        request_id_var.reset(token)

    assert "cms.test [request_id=req-1]: hello" in logging.Formatter(TEXT_FORMAT).format(record)
