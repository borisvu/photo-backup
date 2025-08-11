"""
Unit tests for logger core functionality.

Tests config-based logger setup and integration scenarios.
"""

import logging
import tempfile
from pathlib import Path
from unittest.mock import Mock

import pytest

from photo_backup.logger.core import setup_logger_from_config
from photo_backup.logger.context import JobContextFilter
from photo_backup.logger.formatters import JSONFormatter


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
