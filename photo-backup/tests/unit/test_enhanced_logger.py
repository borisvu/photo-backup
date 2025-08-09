"""
Unit tests for enhanced logger functionality.

Tests config-based logger setup, formatters, job context, and JSON logging.
"""

import json
import logging
import os
import tempfile
from datetime import datetime, timedelta
from unittest.mock import Mock

import pytest
from pathlib import Path

from photo_backup.logger import (
    JobContextFilter,
    JSONFormatter,
    _parse_log_level,
    cleanup_old_logs,
    create_formatter,
    generate_job_id,
    setup_logger_from_config,
)


class TestLogLevelParsing:
    """Test log level string parsing."""

    def test_parse_valid_log_levels(self):
        """Test parsing of valid log level strings."""
        assert _parse_log_level("DEBUG") == logging.DEBUG
        assert _parse_log_level("INFO") == logging.INFO
        assert _parse_log_level("WARNING") == logging.WARNING
        assert _parse_log_level("ERROR") == logging.ERROR
        assert _parse_log_level("CRITICAL") == logging.CRITICAL

    def test_parse_case_insensitive(self):
        """Test that log level parsing is case insensitive."""
        assert _parse_log_level("debug") == logging.DEBUG
        assert _parse_log_level("Info") == logging.INFO
        assert _parse_log_level("warning") == logging.WARNING

    def test_parse_invalid_log_level(self):
        """Test that invalid log levels raise ValueError."""
        with pytest.raises(ValueError, match="Invalid log level"):
            _parse_log_level("INVALID")

    def test_parse_empty_string(self):
        """Test that empty string raises ValueError."""
        with pytest.raises(ValueError, match="Invalid log level"):
            _parse_log_level("")


class TestJobIdGeneration:
    """Test job ID generation."""

    def test_generate_job_id_default_prefix(self):
        """Test job ID generation with default prefix."""
        job_id = generate_job_id()
        assert job_id.startswith("job-")
        assert len(job_id) == 12  # "job-" + 8 hex chars

    def test_generate_job_id_custom_prefix(self):
        """Test job ID generation with custom prefix."""
        job_id = generate_job_id("backup")
        assert job_id.startswith("backup-")
        assert len(job_id) == 15  # "backup-" + 8 hex chars

    def test_generate_job_id_unique(self):
        """Test that generated job IDs are unique."""
        job_ids = set()
        for _ in range(100):
            job_id = generate_job_id()
            assert job_id not in job_ids
            job_ids.add(job_id)


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
        assert "%(asctime)s" in formatter._fmt
        assert "%(name)s" in formatter._fmt

    def test_create_detailed_formatter_with_job_id(self):
        """Test detailed formatter with job ID."""
        formatter = create_formatter("detailed", include_timestamps=True, job_id="test-job")
        assert isinstance(formatter, logging.Formatter)
        assert "%(job_id)s" in formatter._fmt

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


class TestJobContextFilter:
    """Test job context filter."""

    def test_job_context_filter_adds_job_id(self):
        """Test that job context filter adds job_id to record."""
        filter_obj = JobContextFilter("test-job-123")
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        result = filter_obj.filter(record)

        assert result is True
        assert record.job_id == "test-job-123"


class TestConfigBasedLogger:
    """Test config-based logger setup."""

    def test_setup_logger_from_config_basic(self):
        """Test basic config-based logger setup."""
        config_obj = Mock()
        config_obj.get.side_effect = lambda key, default=None: {
            "logging.level": "INFO",
            "logging.format": "detailed",
            "logging.console_output": True,
            "logging.file_output": False,
            "logging.include_timestamps": True,
        }.get(key, default)

        logger = setup_logger_from_config(config_obj)

        assert logger.name == "photo_backup"
        assert logger.level == logging.INFO
        assert len(logger.handlers) == 1  # Console handler only

    def test_setup_logger_from_config_with_job_id(self):
        """Test config-based logger setup with job ID."""
        config_obj = Mock()
        config_obj.get.side_effect = lambda key, default=None: {
            "logging.level": "DEBUG",
            "logging.format": "detailed",
            "logging.console_output": True,
            "logging.file_output": False,
            "logging.include_timestamps": True,
        }.get(key, default)

        logger = setup_logger_from_config(config_obj, job_id="test-job")

        assert logger.name == "photo_backup"
        assert logger.level == logging.DEBUG
        assert len(logger.filters) == 1  # Job context filter

    def test_setup_logger_from_config_json_format(self):
        """Test config-based logger setup with JSON format."""
        config_obj = Mock()
        config_obj.get.side_effect = lambda key, default=None: {
            "logging.level": "INFO",
            "logging.format": "json",
            "logging.console_output": True,
            "logging.file_output": False,
            "logging.include_timestamps": True,
        }.get(key, default)

        logger = setup_logger_from_config(config_obj)

        assert logger.name == "photo_backup"
        assert isinstance(logger.handlers[0].formatter, JSONFormatter)

    def test_setup_logger_from_config_file_output(self):
        """Test config-based logger setup with file output."""
        with tempfile.TemporaryDirectory() as temp_dir:
            config_obj = Mock()
            config_obj.get.side_effect = lambda key, default=None: {
                "logging.level": "INFO",
                "logging.format": "detailed",
                "logging.console_output": True,
                "logging.file_output": True,
                "logging.directory": temp_dir,
                "logging.max_size_mb": 10,
                "logging.backup_count": 3,
                "logging.include_timestamps": True,
            }.get(key, default)

            logger = setup_logger_from_config(config_obj)

            assert logger.name == "photo_backup"
            assert len(logger.handlers) == 2  # Console + file handler

            # Test that log file was created
            log_file = Path(temp_dir) / "photo-backup.log"
            logger.info("Test message")
            assert log_file.exists()

    def test_setup_logger_from_config_file_output_fallback(self):
        """Test config-based logger setup with file output fallback."""
        config_obj = Mock()
        config_obj.get.side_effect = lambda key, default=None: {
            "logging.level": "INFO",
            "logging.format": "detailed",
            "logging.console_output": False,
            "logging.file_output": True,
            "logging.directory": "/invalid/path",
            "logging.max_size_mb": 10,
            "logging.backup_count": 3,
            "logging.include_timestamps": True,
        }.get(key, default)

        logger = setup_logger_from_config(config_obj)

        # Should fall back to console output if file logging fails
        assert logger.name == "photo_backup"
        assert len(logger.handlers) == 1  # Console handler as fallback

    def test_setup_logger_from_config_no_console(self):
        """Test config-based logger setup without console output."""
        config_obj = Mock()
        config_obj.get.side_effect = lambda key, default=None: {
            "logging.level": "INFO",
            "logging.format": "detailed",
            "logging.console_output": False,
            "logging.file_output": False,
            "logging.include_timestamps": True,
        }.get(key, default)

        logger = setup_logger_from_config(config_obj)

        assert logger.name == "photo_backup"
        assert len(logger.handlers) == 0  # No handlers

    def test_setup_logger_from_config_custom_name(self):
        """Test config-based logger setup with custom name."""
        config_obj = Mock()
        config_obj.get.side_effect = lambda key, default=None: {
            "logging.level": "INFO",
            "logging.format": "detailed",
            "logging.console_output": True,
            "logging.file_output": False,
            "logging.include_timestamps": True,
        }.get(key, default)

        logger = setup_logger_from_config(config_obj, name="custom_logger")

        assert logger.name == "custom_logger"

    def test_setup_logger_from_config_invalid_level(self):
        """Test config-based logger setup with invalid log level."""
        config_obj = Mock()
        config_obj.get.side_effect = lambda key, default=None: {
            "logging.level": "INVALID",
            "logging.format": "detailed",
            "logging.console_output": True,
            "logging.file_output": False,
            "logging.include_timestamps": True,
        }.get(key, default)

        with pytest.raises(ValueError, match="Invalid log level"):
            setup_logger_from_config(config_obj)


class TestLoggerIntegration:
    """Test logger integration scenarios."""

    def test_logger_with_job_context_logging(self):
        """Test that logger with job context includes job ID in messages."""
        config_obj = Mock()
        config_obj.get.side_effect = lambda key, default=None: {
            "logging.level": "DEBUG",
            "logging.format": "detailed",
            "logging.console_output": True,
            "logging.file_output": False,
            "logging.include_timestamps": True,
        }.get(key, default)

        logger = setup_logger_from_config(config_obj, job_id="test-job-123")

        # Test that job context filter is added
        job_filters = [f for f in logger.filters if isinstance(f, JobContextFilter)]
        assert len(job_filters) >= 1
        # Check that at least one filter has the correct job ID
        job_ids = [f.job_id for f in job_filters]
        assert "test-job-123" in job_ids

    def test_json_logger_output(self):
        """Test that JSON logger produces valid JSON output."""
        config_obj = Mock()
        config_obj.get.side_effect = lambda key, default=None: {
            "logging.level": "INFO",
            "logging.format": "json",
            "logging.console_output": True,
            "logging.file_output": False,
            "logging.include_timestamps": True,
        }.get(key, default)

        logger = setup_logger_from_config(config_obj, job_id="test-job-123")

        # Test that JSON formatter is used
        assert len(logger.handlers) == 1
        assert isinstance(logger.handlers[0].formatter, JSONFormatter)
        assert logger.handlers[0].formatter.job_id == "test-job-123"


class TestLogCleanup:
    """Test log cleanup functionality."""

    def test_cleanup_old_logs_no_directory(self):
        """Test cleanup when log directory doesn't exist."""
        result = cleanup_old_logs("/nonexistent/directory")
        assert result == 0

    def test_cleanup_old_logs_empty_directory(self):
        """Test cleanup when log directory is empty."""
        with tempfile.TemporaryDirectory() as temp_dir:
            result = cleanup_old_logs(temp_dir)
            assert result == 0

    def test_cleanup_old_logs_age_based(self):
        """Test age-based log cleanup."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir)

            # Create test log files with different ages
            old_file = log_dir / "old.log"
            new_file = log_dir / "new.log"

            # Create old file (2 days ago)
            old_file.write_text("old log content")
            old_timestamp = (datetime.now() - timedelta(days=2)).timestamp()
            os.utime(old_file, (old_timestamp, old_timestamp))

            # Create new file (today)
            new_file.write_text("new log content")

            # Clean up files older than 1 day (use config to override default)
            config_obj = Mock()
            config_obj.get.side_effect = lambda key, default=None: {
                "logging.auto_cleanup": True,
                "logging.cleanup_days": 1,
                "logging.cleanup_count": 10,
                "logging.cleanup_mode": "age",
            }.get(key, default)

            result = cleanup_old_logs(temp_dir, config_obj)
            assert result == 1  # Should delete 1 old file

            # Check that old file is deleted but new file remains
            assert not old_file.exists()
            assert new_file.exists()

    def test_cleanup_old_logs_count_based(self):
        """Test count-based log cleanup."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir)

            # Create multiple test log files
            files = []
            for i in range(5):
                file = log_dir / f"log_{i}.log"
                file.write_text(f"log content {i}")
                files.append(file)

            # Configure cleanup to keep only 3 files
            config_obj = Mock()
            config_obj.get.side_effect = lambda key, default=None: {
                "logging.auto_cleanup": True,
                "logging.cleanup_days": 30,
                "logging.cleanup_count": 3,
                "logging.cleanup_mode": "count",
            }.get(key, default)

            # Clean up excess files
            result = cleanup_old_logs(temp_dir, config_obj)
            assert result == 2  # Should delete 2 files (5 - 3)

            # Check that only 3 files remain
            remaining_files = list(log_dir.glob("*.log"))
            assert len(remaining_files) == 3

    def test_cleanup_old_logs_disabled(self):
        """Test cleanup when auto_cleanup is disabled."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir)

            # Create a test log file
            test_file = log_dir / "test.log"
            test_file.write_text("test content")

            # Configure cleanup to be disabled
            config_obj = Mock()
            config_obj.get.side_effect = lambda key, default=None: {
                "logging.auto_cleanup": False,
            }.get(key, default)

            # Run cleanup
            result = cleanup_old_logs(temp_dir, config_obj)
            assert result == 0  # Should not delete any files

            # Check that file still exists
            assert test_file.exists()

    def test_cleanup_old_logs_with_logger(self):
        """Test cleanup with logger instance."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir)

            # Create a test log file
            test_file = log_dir / "test.log"
            test_file.write_text("test content")

            # Create a logger
            logger = logging.getLogger("test_cleanup")
            logger.setLevel(logging.DEBUG)

            # Run cleanup with logger
            result = cleanup_old_logs(temp_dir, logger=logger)
            assert result == 0  # Should not delete recent file

    def test_cleanup_old_logs_integration(self):
        """Test cleanup integration with logger setup."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test log files
            log_dir = Path(temp_dir)
            old_file = log_dir / "old.log"
            new_file = log_dir / "new.log"

            # Create old file (2 days ago)
            old_file.write_text("old log content")
            old_timestamp = (datetime.now() - timedelta(days=2)).timestamp()
            os.utime(old_file, (old_timestamp, old_timestamp))

            # Create new file (today)
            new_file.write_text("new log content")

            # Configure logger with cleanup
            config_obj = Mock()
            config_obj.get.side_effect = lambda key, default=None: {
                "logging.level": "INFO",
                "logging.format": "detailed",
                "logging.console_output": True,
                "logging.file_output": False,
                "logging.directory": temp_dir,
                "logging.auto_cleanup": True,
                "logging.cleanup_days": 1,
                "logging.cleanup_count": 10,
                "logging.cleanup_mode": "age",
            }.get(key, default)

            # Set up logger (which should run cleanup)
            _logger = setup_logger_from_config(config_obj)

            # Check that old file is deleted but new file remains
            assert not old_file.exists()
            assert new_file.exists()


if __name__ == "__main__":
    pytest.main([__file__])
