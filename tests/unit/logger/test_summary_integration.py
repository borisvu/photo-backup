"""
Integration tests for summary statistics with operation context.

Tests summary statistics integration with OperationContext.
"""

import json
import logging
import tempfile
import time

from pathlib import Path

from photo_backup.logger.context import OperationContext
from photo_backup.logger.formatters import create_formatter


class TestSummaryIntegration:
    """Test summary statistics integration with operation context."""

    def test_operation_context_with_summary(self):
        """Test operation context includes summary statistics."""
        with OperationContext("backup", "Test backup") as op:
            # Add some file processing
            op.add_file_processed(size_bytes=1024, success=True)
            op.add_file_processed(size_bytes=2048, success=False)
            op.add_file_processed(size_bytes=512, skipped=True)

            # Add some errors
            op.add_error("File not found: photo1.jpg")

            # Verify summary is available
            summary = op.get_summary()
            assert summary.files_processed == 3
            assert summary.files_successful == 1
            assert summary.files_failed == 1
            assert summary.files_skipped == 1
            assert len(summary.errors) == 1

    def test_operation_context_summary_logging(self):
        """Test that operation context logs summary."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "test.log"

            # Set up file handler
            handler = logging.FileHandler(log_file)
            handler.setLevel(logging.INFO)
            formatter = create_formatter("detailed")
            handler.setFormatter(formatter)

            logger = logging.getLogger("test_summary_logging")
            logger.setLevel(logging.INFO)
            logger.addHandler(handler)
            logger.propagate = False

            with OperationContext("backup", "Test backup", logger) as op:
                op.add_file_processed(size_bytes=1024, success=True)
                op.add_file_processed(size_bytes=2048, success=False)
                time.sleep(0.1)  # Ensure some duration

            # Check log content
            log_content = log_file.read_text()
            assert "Operation summary:" in log_content
            assert "=== Backup Summary ===" in log_content
            assert "Files: 2 processed, 1 successful, 1 failed, 0 skipped" in log_content

    def test_operation_context_summary_json_logging(self):
        """Test that operation context includes summary in JSON logs."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "test.json"

            # Set up file handler with JSON formatter
            handler = logging.FileHandler(log_file)
            handler.setLevel(logging.INFO)
            formatter = create_formatter("json")
            handler.setFormatter(formatter)

            logger = logging.getLogger("test_summary_json")
            logger.setLevel(logging.INFO)
            logger.addHandler(handler)
            logger.propagate = False

            with OperationContext("backup", "Test backup", logger) as op:
                op.add_file_processed(size_bytes=1024, success=True)
                time.sleep(0.1)

            # Check JSON log content
            log_content = log_file.read_text()
            log_lines = log_content.strip().split("\n")

            # Find completion log entry
            completion_log = None
            for line in log_lines:
                if "Completed backup operation" in line:
                    completion_log = json.loads(line)
                    break

            assert completion_log is not None
            assert "summary" in completion_log
            summary_data = completion_log["summary"]
            assert summary_data["operation_type"] == "backup"
            assert summary_data["files_processed"] == 1
            assert summary_data["files_successful"] == 1

    def test_operation_context_summary_with_exception(self):
        """Test that operation context includes summary when operation fails."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "test.log"

            # Set up file handler
            handler = logging.FileHandler(log_file)
            handler.setLevel(logging.INFO)
            formatter = create_formatter("detailed")
            handler.setFormatter(formatter)

            logger = logging.getLogger("test_summary_exception")
            logger.setLevel(logging.INFO)
            logger.addHandler(handler)
            logger.propagate = False

            try:
                with OperationContext("backup", "Test backup", logger) as op:
                    op.add_file_processed(size_bytes=1024, success=True)
                    op.add_error("Test error")
                    raise ValueError("Operation failed")
            except ValueError:
                pass

            # Check log content
            log_content = log_file.read_text()
            assert "Operation summary:" in log_content
            assert "=== Backup Summary ===" in log_content
            assert "Test error" in log_content
            assert "Operation failed" in log_content

    def test_operation_context_summary_methods(self):
        """Test operation context summary methods."""
        with OperationContext("backup", "Test backup") as op:
            # Test add_file_processed
            op.add_file_processed(size_bytes=1024, success=True)
            op.add_file_processed(size_bytes=2048, success=False)
            op.add_file_processed(size_bytes=512, skipped=True)

            # Test add_error
            op.add_error("Test error 1")
            op.add_error("Test error 2")

            # Test get_summary
            summary = op.get_summary()
            assert summary.files_processed == 3
            assert summary.files_successful == 1
            assert summary.files_failed == 1
            assert summary.files_skipped == 1
            assert len(summary.errors) == 2
            assert "Test error 1" in summary.errors
            assert "Test error 2" in summary.errors
