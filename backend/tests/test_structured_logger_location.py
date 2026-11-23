"""Unhandled errors are logged with where they happened (file:line:function), never with values."""

import json
import logging

import pytest
from backend.infrastructure.logging.structured_logger import JSONFormatter

pytestmark = pytest.mark.unit


def _boom(secret_text):
    raise IndexError("index 785 is out of bounds")


def test_error_location_lists_frames_without_values():
    try:
        _boom("reader typed this private note")
    except IndexError as exc:
        record = logging.LogRecord("t", logging.ERROR, __file__, 1, "Unhandled exception", None, (type(exc), exc, exc.__traceback__))
    out = json.loads(JSONFormatter().format(record))
    assert out["error_type"] == "IndexError"
    assert out["error_location"][-1].startswith("test_structured_logger_location.py:") and out["error_location"][-1].endswith(":_boom")
    assert "private note" not in json.dumps(out)
