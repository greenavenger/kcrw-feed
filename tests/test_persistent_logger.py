"""Test custom JSON formatter and filter for logging module."""

import logging
import json
import datetime as dt
import io

from kcrw_feed.persistent_logger import JSONFormatter, NonErrorFilter, LOGGING_LEVEL_MAP


def test_logger_trace_enabled():
    """
    Test that a logger set to the TRACE level outputs trace messages.
    """
    logger = logging.getLogger("test_logger_trace_enabled")
    logger.setLevel(LOGGING_LEVEL_MAP["trace"])
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    formatter = logging.Formatter("%(levelname)s: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # Log a trace message. Since logger is set to TRACE, it should output.
    logger.trace("This is a trace message")
    handler.flush()
    output = stream.getvalue()
    assert "TRACE: This is a trace message" in output
    logger.removeHandler(handler)


def test_logger_trace_disabled():
    """
    Test that a logger with a level higher than TRACE (e.g. INFO) does not output trace messages.
    """
    logger = logging.getLogger("test_logger_trace_disabled")
    logger.setLevel(logging.INFO)
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    formatter = logging.Formatter("%(levelname)s: %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # This trace message should not be output because the logger level is INFO.
    logger.trace("This trace message should not appear")
    handler.flush()
    output = stream.getvalue()
    assert output == ""
    logger.removeHandler(handler)


def test_json_formatter_basic():
    """Test that the JSONFormatter returns valid JSON with expected fields."""
    record = logging.LogRecord(
        name="test_logger",
        level=logging.INFO,
        pathname=__file__,
        lineno=10,
        msg="Hello, world!",
        args=(),
        exc_info=None,
    )
    # Create formatter without custom fmt_keys.
    formatter = JSONFormatter()
    output = formatter.format(record)
    log_dict = json.loads(output)

    # Check that required fields are present and correctly formatted.
    assert log_dict["level"] == "INFO"
    assert log_dict["message"] == "Hello, world!"
    # Check that timestamp is a valid ISO format string.
    ts = log_dict.get("timestamp")
    assert ts is not None
    # Attempt to parse the timestamp
    dt.datetime.fromisoformat(ts)


def test_json_formatter_with_fmt_keys_and_extra_field():
    """Test that providing fmt_keys remaps fields and extra attributes are added."""
    fmt_keys = {
        "custom_level": "levelname",
        "custom_message": "message",
    }
    formatter = JSONFormatter(fmt_keys=fmt_keys)
    record = logging.LogRecord(
        name="test_logger",
        level=logging.DEBUG,
        pathname=__file__,
        lineno=20,
        msg="Test message",
        args=(),
        exc_info=None,
    )
    # Add an extra attribute that's not part of the built-in ones.
    record.custom_field = "extra_value"
    output = formatter.format(record)
    log_dict = json.loads(output)

    # The custom keys should be set from always_fields.
    assert log_dict["custom_level"] == "DEBUG"
    assert log_dict["custom_message"] == "Test message"
    # The remaining always field (timestamp) should be present.
    assert "timestamp" in log_dict
    # Extra non-built-in attribute should be added.
    assert log_dict.get("custom_field") == "extra_value"


def test_json_formatter_with_exception():
    """Test that the formatter includes exception info when exc_info is provided."""
    formatter = JSONFormatter()
    try:
        raise ValueError("Test error")
    except ValueError as e:
        # Create a log record with exc_info set.
        record = logging.LogRecord(
            name="test_logger",
            level=logging.ERROR,
            pathname=__file__,
            lineno=30,
            msg="An error occurred",
            args=(),
            exc_info=(type(e), e, e.__traceback__),
        )
        output = formatter.format(record)
        log_dict = json.loads(output)

        # Ensure that exc_info was captured and formatted.
        assert "exc_info" in log_dict
        # Check that the formatted exception info contains the exception type.
        assert "ValueError" in log_dict["exc_info"]


def test_non_error_filter():
    """Test that NonErrorFilter allows DEBUG and INFO but filters out WARNING and above."""
    non_error_filter = NonErrorFilter()
    record_debug = logging.LogRecord(
        "test", logging.DEBUG, __file__, 1, "debug", (), None)
    record_info = logging.LogRecord(
        "test", logging.INFO, __file__, 2, "info", (), None)
    record_warning = logging.LogRecord(
        "test", logging.WARNING, __file__, 3, "warning", (), None)
    record_error = logging.LogRecord(
        "test", logging.ERROR, __file__, 4, "error", (), None)

    # DEBUG (10) and INFO (20) should pass.
    assert non_error_filter.filter(record_debug) is True
    assert non_error_filter.filter(record_info) is True
    # WARNING (30) and ERROR (40) should be filtered out.
    assert non_error_filter.filter(record_warning) is False
    assert non_error_filter.filter(record_error) is False
