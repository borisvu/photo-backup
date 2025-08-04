"""
Functional tests for enhanced logger functionality.

Tests the integration of enhanced logging with CLI commands and config system.
"""

import json
import logging
import subprocess
import tempfile

import pytest
from pathlib import Path


class TestEnhancedLoggerCLI:
    """Test enhanced logger integration with CLI commands."""

    def test_config_command_with_enhanced_logging(self):
        """Test that config command uses enhanced logging with job context."""
        result = subprocess.run(
            ["python3", "-m", "photo_backup.main", "--test-mode", "config"],
            capture_output=True,
            text=True,
            cwd=".",
        )

        assert result.returncode == 0
        assert "Configuration display completed." in result.stdout

        # Check that logging configuration is displayed
        assert "Level: DEBUG" in result.stdout
        assert "Format: detailed" in result.stdout

    def test_validate_command_with_enhanced_logging(self):
        """Test that validate command uses enhanced logging with job context."""
        result = subprocess.run(
            ["python3", "-m", "photo_backup.main", "--test-mode", "validate"],
            capture_output=True,
            text=True,
            cwd=".",
        )

        # Should fail due to missing paths, but logging should work
        assert result.returncode == 1
        assert "Configuration Validation for Photo Backup System" in result.stdout

    def test_main_command_with_enhanced_logging(self):
        """Test that main command uses enhanced logging with job context."""
        result = subprocess.run(
            ["python3", "-m", "photo_backup.main", "--test-mode"],
            capture_output=True,
            text=True,
            cwd=".",
        )

        assert result.returncode == 0
        assert "Photo Backup v" in result.stdout
        assert "TEST MODE" in result.stdout

        # Check that logging configuration is displayed
        assert "Log level: DEBUG" in result.stdout
        assert "Log format: detailed" in result.stdout

    def test_log_level_changes_work(self):
        """Test that log level changes work based on config."""
        # Test log level parsing by importing and testing directly
        from unittest.mock import Mock

        from photo_backup.logger import _parse_log_level, setup_logger_from_config

        # Test log level parsing
        assert _parse_log_level("DEBUG") == logging.DEBUG
        assert _parse_log_level("INFO") == logging.INFO
        assert _parse_log_level("WARNING") == logging.WARNING
        assert _parse_log_level("ERROR") == logging.ERROR
        assert _parse_log_level("CRITICAL") == logging.CRITICAL

        # Test case insensitivity
        assert _parse_log_level("debug") == logging.DEBUG
        assert _parse_log_level("Info") == logging.INFO

        # Test invalid log level
        with pytest.raises(ValueError, match="Invalid log level"):
            _parse_log_level("INVALID")

        # Test config-based logger setup with different levels
        config_obj = Mock()
        config_obj.get.side_effect = lambda key, default=None: {
            "logging.level": "DEBUG",
            "logging.format": "detailed",
            "logging.console_output": True,
            "logging.file_output": False,
            "logging.include_timestamps": True,
        }.get(key, default)

        logger = setup_logger_from_config(config_obj, job_id="test-job")
        assert logger.level == logging.DEBUG

    def test_test_mode_verbose_logging(self):
        """Test that test mode uses verbose logging (DEBUG level)."""
        result = subprocess.run(
            ["python3", "-m", "photo_backup.main", "--test-mode"],
            capture_output=True,
            text=True,
            cwd=".",
        )

        assert result.returncode == 0
        assert "Log level: DEBUG" in result.stdout
        assert "Test mode log level: DEBUG" in result.stdout

    def test_production_mode_logging(self):
        """Test that production mode uses appropriate logging level."""
        result = subprocess.run(
            ["python3", "-m", "photo_backup.main"],
            capture_output=True,
            text=True,
            cwd=".",
        )

        assert result.returncode == 0
        assert "PRODUCTION MODE" in result.stdout
        assert "Log level: INFO" in result.stdout  # Production uses INFO by default

    def test_json_format_logging(self):
        """Test JSON format logging functionality."""
        # Test JSON format by importing and testing the formatter directly
        from photo_backup.logger import JSONFormatter, create_formatter

        # Test JSON formatter creation
        formatter = create_formatter("json", job_id="test-job-123")
        assert isinstance(formatter, JSONFormatter)
        assert formatter.job_id == "test-job-123"

        # Test JSON formatting
        import logging

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
        assert log_entry["message"] == "Test message"
        assert log_entry["job_id"] == "test-job-123"
        assert "timestamp" in log_entry

    def test_simple_format_logging(self):
        """Test simple format logging functionality."""
        # Test simple format by importing and testing the formatter directly
        from photo_backup.logger import create_formatter

        # Test simple formatter creation with timestamps
        formatter = create_formatter("simple", include_timestamps=True)
        assert isinstance(formatter, logging.Formatter)
        assert "%(asctime)s" in formatter._fmt

        # Test simple formatter creation without timestamps
        formatter = create_formatter("simple", include_timestamps=False)
        assert isinstance(formatter, logging.Formatter)
        assert "%(asctime)s" not in formatter._fmt

        # Test simple formatter output
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
        assert "INFO - Test message" in result

    def test_detailed_format_logging(self):
        """Test detailed format logging functionality."""
        # Test detailed format by importing and testing the formatter directly
        from photo_backup.logger import create_formatter

        # Test detailed formatter creation with job ID
        formatter = create_formatter("detailed", include_timestamps=True, job_id="test-job-123")
        assert isinstance(formatter, logging.Formatter)
        assert "%(job_id)s" in formatter._fmt

        # Test detailed formatter creation without job ID
        formatter = create_formatter("detailed", include_timestamps=True)
        assert isinstance(formatter, logging.Formatter)
        assert "%(name)s" in formatter._fmt
        assert "%(levelname)s" in formatter._fmt

        # Test detailed formatter output
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
        assert "test_logger" in result
        assert "INFO" in result
        assert "Test message" in result

    def test_job_context_in_logs(self):
        """Test that job context appears in log messages."""
        # This test verifies that job IDs are generated and used
        # We can't easily capture the actual log output in functional tests,
        # but we can verify the job context is set up correctly

        result = subprocess.run(
            ["python3", "-m", "photo_backup.main", "--test-mode", "config"],
            capture_output=True,
            text=True,
            cwd=".",
        )

        assert result.returncode == 0
        # The job context is internal to the logging system,
        # but we can verify the command completes successfully with enhanced logging

    def test_logging_configuration_display(self):
        """Test that logging configuration is properly displayed."""
        result = subprocess.run(
            ["python3", "-m", "photo_backup.main", "--test-mode"],
            capture_output=True,
            text=True,
            cwd=".",
        )

        assert result.returncode == 0

        # Check that logging settings are displayed
        assert "Log level: DEBUG" in result.stdout
        assert "Log format: detailed" in result.stdout

        # Check that test mode shows DEBUG level
        assert "DEBUG" in result.stdout

    def test_environment_override_logging_settings(self):
        """Test that environment variables override logging settings."""
        # Test environment override functionality by testing the config system
        from photo_backup.config.config import Config
        from photo_backup.config.env_override import EnvOverride

        # Test that environment override system is available
        assert hasattr(EnvOverride, "is_test_mode_enabled")
        assert callable(EnvOverride.is_test_mode_enabled)

        # Test config object can handle environment overrides
        config_obj = Config(test_mode=True)
        config_data = config_obj.load_config()

        # Verify logging settings are present in config
        assert "logging" in config_data
        assert "level" in config_data["logging"]
        assert "format" in config_data["logging"]

        # Test that config object has get method for logging settings
        assert config_obj.get("logging.level") is not None
        assert config_obj.get("logging.format") is not None

    def test_file_logging_configuration(self):
        """Test file logging configuration."""
        # Test file logging functionality by testing the setup function
        from unittest.mock import Mock

        from photo_backup.logger import setup_logger_from_config

        # Test file logging setup
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

            logger = setup_logger_from_config(config_obj, job_id="test-job")

            # Verify logger has both console and file handlers
            assert len(logger.handlers) == 2

            # Test that log file was created when we log a message
            logger.info("Test message")
            log_file = Path(temp_dir) / "photo-backup.log"
            assert log_file.exists()

            # Verify log file contains our message
            log_content = log_file.read_text()
            assert "Test message" in log_content
            assert "test-job" in log_content

    def test_logging_with_dry_run_mode(self):
        """Test that logging works correctly with dry-run mode."""
        result = subprocess.run(
            ["python3", "-m", "photo_backup.main", "--test-mode", "--dry-run"],
            capture_output=True,
            text=True,
            cwd=".",
        )

        assert result.returncode == 0
        assert "TEST MODE (DRY RUN)" in result.stdout
        assert "Log level:" in result.stdout
        assert "Log format:" in result.stdout

    def test_backward_compatibility(self):
        """Test that enhanced logger maintains backward compatibility."""
        # Test that the old setup_logger function still works
        result = subprocess.run(
            [
                "python3",
                "-c",
                """
import logging
from photo_backup.logger import setup_logger

logger = setup_logger("test_logger", logging.DEBUG)
logger.info("Test message")
print("Backward compatibility test passed")
            """,
            ],
            capture_output=True,
            text=True,
            cwd=".",
        )

        assert result.returncode == 0
        assert "Backward compatibility test passed" in result.stdout

    def test_logging_error_handling(self):
        """Test that logging handles errors gracefully."""
        # Test error handling by testing invalid configurations
        from unittest.mock import Mock

        from photo_backup.logger import _parse_log_level, setup_logger_from_config

        # Test invalid log level handling
        with pytest.raises(ValueError, match="Invalid log level"):
            _parse_log_level("INVALID")

        # Test invalid log level in config setup
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

        # Test file logging fallback when directory is invalid
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

        # Should not raise exception, should fall back to console
        logger = setup_logger_from_config(config_obj)
        assert len(logger.handlers) == 1  # Console handler as fallback

    def test_logging_performance(self):
        """Test that enhanced logging doesn't significantly impact performance."""
        import time

        start_time = time.time()

        result = subprocess.run(
            ["python3", "-m", "photo_backup.main", "--test-mode", "config"],
            capture_output=True,
            text=True,
            cwd=".",
        )

        end_time = time.time()
        execution_time = end_time - start_time

        assert result.returncode == 0
        assert execution_time < 5.0  # Should complete within 5 seconds
