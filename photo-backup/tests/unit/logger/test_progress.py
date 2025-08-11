"""
Unit tests for logger progress functionality.

Tests progress logger for tracking long-running operations.
"""

import json
import logging
import tempfile
import time

from pathlib import Path

from photo_backup.logger.context import OperationContext
from photo_backup.logger.formatters import create_formatter
from photo_backup.logger.progress import ProgressLogger


class TestProgressLogger:
    """Test progress logger functionality."""

    def test_progress_logger_initialization(self):
        """Test progress logger initialization."""
        logger = logging.getLogger("test_progress")
        logger.setLevel(logging.INFO)

        progress = ProgressLogger(total_items=100, operation_type="files", update_interval=2.0, logger=logger)

        assert progress.total_items == 100
        assert progress.operation_type == "files"
        assert progress.update_interval == 2.0
        assert progress.current_item == 0
        assert progress.completed is False
        assert progress.percentage == 0.0

    def test_progress_logger_update(self):
        """Test progress logger update functionality."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "test.log"

            # Set up file handler
            handler = logging.FileHandler(log_file)
            handler.setLevel(logging.INFO)
            formatter = create_formatter("detailed")
            handler.setFormatter(formatter)

            logger = logging.getLogger("test_progress_update")
            logger.setLevel(logging.INFO)
            logger.addHandler(handler)
            logger.propagate = False

            progress = ProgressLogger(
                total_items=10,
                operation_type="files",
                update_interval=0.01,  # Very short interval for testing
                logger=logger,
            )

            # Add a small delay to ensure the update is logged
            time.sleep(0.02)

            # Update progress
            progress.update(5, "Processing files")

            # Check log content
            log_content = log_file.read_text()
            assert "Progress: 5/10 files (50.0%)" in log_content
            assert "ETA:" in log_content

    def test_progress_logger_rate_limiting(self):
        """Test progress logger rate limiting."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "test.log"

            # Set up file handler
            handler = logging.FileHandler(log_file)
            handler.setLevel(logging.INFO)
            formatter = create_formatter("detailed")
            handler.setFormatter(formatter)

            logger = logging.getLogger("test_progress_rate_limit")
            logger.setLevel(logging.INFO)
            logger.addHandler(handler)
            logger.propagate = False

            # Test basic logging first
            logger.info("Test message")
            basic_log_content = log_file.read_text()
            assert "Test message" in basic_log_content

            progress = ProgressLogger(
                total_items=10,
                operation_type="files",
                update_interval=0.5,  # 0.5 second interval
                logger=logger,
            )

            # First update should be logged
            progress.update(1)

            # Update multiple times quickly (should not log due to rate limiting)
            progress.update(2)
            progress.update(3)

            # Check that only one update was logged (due to rate limiting)
            log_content = log_file.read_text()
            progress_lines = [line for line in log_content.split("\n") if "Progress:" in line and line.strip()]
            assert len(progress_lines) == 1

    def test_progress_logger_completion(self):
        """Test progress logger completion."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "test.log"

            # Set up file handler
            handler = logging.FileHandler(log_file)
            handler.setLevel(logging.INFO)
            formatter = create_formatter("detailed")
            handler.setFormatter(formatter)

            logger = logging.getLogger("test_progress_complete")
            logger.setLevel(logging.INFO)
            logger.addHandler(handler)
            logger.propagate = False

            progress = ProgressLogger(total_items=5, operation_type="files", update_interval=0.1, logger=logger)

            # Complete the operation
            progress.complete("All files processed successfully")

            # Check log content
            log_content = log_file.read_text()
            assert "Progress: 5/5 files (100.0%)" in log_content
            assert "Completed in" in log_content
            assert "All files processed successfully" in log_content

    def test_progress_logger_with_operation_context(self):
        """Test progress logger with operation context."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "test.log"

            # Set up file handler
            handler = logging.FileHandler(log_file)
            handler.setLevel(logging.INFO)
            formatter = create_formatter("json")
            handler.setFormatter(formatter)

            logger = logging.getLogger("test_progress_context")
            logger.setLevel(logging.INFO)
            logger.addHandler(handler)
            logger.propagate = False

            with OperationContext("backup", "Test backup", logger) as op:
                progress = ProgressLogger(
                    total_items=10,
                    operation_type="files",
                    update_interval=0.01,  # Very short interval for testing
                    logger=logger,
                    operation_context=op,
                )

                # Add a small delay to ensure the update is logged
                time.sleep(0.02)

                progress.update(5, "Processing files")

                # Check JSON log content
                log_content = log_file.read_text()
                log_lines = log_content.strip().split("\n")

                # Find progress log entry
                progress_log = None
                for line in log_lines:
                    if "Progress:" in line:
                        progress_log = json.loads(line)
                        break

                assert progress_log is not None
                assert progress_log["operation"] == "backup"
                assert progress_log["operation_id"] == op.operation_id
                assert progress_log["progress_percentage"] == 50.0
                assert progress_log["current_item"] == 5
                assert progress_log["total_items"] == 10

    def test_progress_logger_eta_calculation(self):
        """Test progress logger ETA calculation."""
        logger = logging.getLogger("test_progress_eta")
        logger.setLevel(logging.INFO)

        progress = ProgressLogger(total_items=100, operation_type="files", update_interval=0.1, logger=logger)

        # Simulate some time passing
        time.sleep(0.1)

        # Update progress
        progress.update(50)

        # Check that ETA is calculated
        assert progress.percentage == 50.0
        assert progress.elapsed_time.total_seconds() > 0

    def test_progress_logger_edge_cases(self):
        """Test progress logger edge cases."""
        logger = logging.getLogger("test_progress_edge")
        logger.setLevel(logging.INFO)

        # Test with zero total items
        progress = ProgressLogger(total_items=0, logger=logger)
        assert progress.percentage == 0.0

        # Test with negative current item
        progress = ProgressLogger(total_items=10, logger=logger)
        progress.update(-5)
        assert progress.current_item == 0

        # Test with current item exceeding total
        progress.update(15)
        assert progress.current_item == 10

    def test_progress_logger_properties(self):
        """Test progress logger properties."""
        logger = logging.getLogger("test_progress_props")
        logger.setLevel(logging.INFO)

        progress = ProgressLogger(total_items=20, operation_type="bytes", update_interval=1.0, logger=logger)

        # Test initial state
        assert progress.percentage == 0.0
        assert progress.elapsed_time.total_seconds() >= 0

        # Test after update
        progress.update(10)
        assert progress.percentage == 50.0
        assert progress.current_item == 10

        # Test completion
        progress.complete()
        assert progress.percentage == 100.0
        assert progress.completed is True
