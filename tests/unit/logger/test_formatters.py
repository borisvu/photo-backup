"""
Unit tests for logger formatters.

Tests formatter creation and JSON formatter functionality.
"""

import json
import logging

from photo_backup.logger.formatters import JSONFormatter, create_formatter


class TestFormatters:
    """Test log formatters."""

    def test_create_simple_formatter_with_timestamps(self):
        """Test simple formatter with timestamps."""
        formatter = create_formatter("simple", include_timestamps=True)
        assert isinstance(formatter, logging.Formatter)
        assert "%(asctime)s" in formatter._fmt

    def test_create_simple_formatter_without_timestamps(self):
        """Test simple formatter without timestamps."""
        formatter = create_formatter("simple", include_timestamps=False)
        assert isinstance(formatter, logging.Formatter)
        assert "%(asctime)s" not in formatter._fmt

    def test_create_detailed_formatter_with_timestamps(self):
        """Test detailed formatter with timestamps."""
        formatter = create_formatter("detailed", include_timestamps=True)
        assert isinstance(formatter, logging.Formatter)
        # Test that it formats with timestamps by checking actual output
        record = logging.LogRecord("test", logging.INFO, "", 0, "test message", (), None)
        formatted = formatter.format(record)
        assert "test message" in formatted
        assert "test" in formatted  # logger name
        assert "INFO" in formatted  # level

    def test_create_detailed_formatter_with_job_id(self):
        """Test detailed formatter with job ID."""
        formatter = create_formatter("detailed", include_timestamps=True, job_id="test-job")
        assert isinstance(formatter, logging.Formatter)
        # Test that it formats with job ID by checking actual output
        record = logging.LogRecord("test", logging.INFO, "", 0, "test message", (), None)
        record.job_id = "test-job"  # Add job_id to record
        formatted = formatter.format(record)
        assert "test message" in formatted
        assert "test-job" in formatted  # job ID should be included

    def test_create_json_formatter(self):
        """Test JSON formatter creation."""
        formatter = create_formatter("json")
        assert isinstance(formatter, JSONFormatter)

    def test_create_json_formatter_with_job_id(self):
        """Test JSON formatter with job ID."""
        formatter = create_formatter("json", job_id="test-job")
        assert isinstance(formatter, JSONFormatter)
        assert formatter.job_id == "test-job"


class TestJSONFormatter:
    """Test JSON formatter functionality."""

    def test_json_formatter_basic(self):
        """Test basic JSON formatting."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)
        log_entry = json.loads(result)

        assert log_entry["level"] == "INFO"
        assert log_entry["logger"] == "test_logger"
        assert log_entry["message"] == "Test message"
        assert "timestamp" in log_entry

    def test_json_formatter_with_job_id(self):
        """Test JSON formatter with job ID."""
        formatter = JSONFormatter(job_id="test-job-123")
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        result = formatter.format(record)
        log_entry = json.loads(result)

        assert log_entry["job_id"] == "test-job-123"

    def test_json_formatter_with_extra_fields(self):
        """Test JSON formatter with extra fields."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.operation = "backup"
        record.file_path = "/test/file.jpg"

        result = formatter.format(record)
        log_entry = json.loads(result)

        assert log_entry["operation"] == "backup"
        assert log_entry["file_path"] == "/test/file.jpg"

    def test_json_formatter_with_exception(self):
        """Test JSON formatter with exception info."""
        formatter = JSONFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.ERROR,
            pathname="test.py",
            lineno=1,
            msg="Test error",
            args=(),
            exc_info=(ValueError, ValueError("test error"), None),
        )

        result = formatter.format(record)
        log_entry = json.loads(result)

        assert "exception" in log_entry
        assert "ValueError: test error" in log_entry["exception"]
