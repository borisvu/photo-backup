"""
Unit tests for logger cleanup functionality.

Tests log file cleanup operations.
"""

import os
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock

import pytest

from photo_backup.logger.cleanup import cleanup_old_logs


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
            logger = Mock()

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

            # Run cleanup directly
            result = cleanup_old_logs(temp_dir, config_obj)
            assert result == 1  # Should delete 1 old file

            # Check that old file is deleted but new file remains
            assert not old_file.exists()
            assert new_file.exists()
