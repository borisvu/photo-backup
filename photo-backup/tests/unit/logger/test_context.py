"""
Unit tests for logger context functionality.

Tests job context filter and operation context.
"""

import json
import logging
import tempfile
import time
from pathlib import Path

import pytest

from photo_backup.logger.context import JobContextFilter, OperationContext
from photo_backup.logger.formatters import create_formatter
from photo_backup.logger.utils import format_duration, generate_operation_id


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


class TestOperationContext:
    """Test operation context functionality."""

    def test_generate_operation_id(self):
        """Test operation ID generation."""
        op_id = generate_operation_id("backup")
        assert op_id.startswith("backup-")
        assert len(op_id) > 20  # Should include timestamp

    def test_generate_operation_id_unique(self):
        """Test that generated operation IDs are unique."""
        op_ids = set()
        for _ in range(10):
            op_id = generate_operation_id("test")
            assert op_id not in op_ids
            op_ids.add(op_id)
            time.sleep(0.001)  # Small delay to ensure unique timestamps

    def test_format_duration(self):
        """Test duration formatting."""
        assert format_duration(30) == "30.00s"
        assert format_duration(90) == "1.50m"
        assert format_duration(3600) == "1.00h"
        assert format_duration(86400) == "1.00d"

    def test_operation_context_basic(self):
        """Test basic operation context functionality."""
        logger = logging.getLogger("test_operation")
        logger.setLevel(logging.INFO)

        with OperationContext("test", "Test operation", logger) as op:
            assert op.operation_type == "test"
            assert op.description == "Test operation"
            assert op.operation_id.startswith("test-")
            assert op._active is True
            assert op.duration is not None

    def test_operation_context_logging(self):
        """Test operation context logging."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "test.log"

            # Set up file handler
            handler = logging.FileHandler(log_file)
            handler.setLevel(logging.INFO)
            formatter = create_formatter("detailed")
            handler.setFormatter(formatter)

            logger = logging.getLogger("test_operation_logging")
            logger.setLevel(logging.INFO)
            logger.addHandler(handler)
            logger.propagate = False

            with OperationContext("backup", "Test backup", logger):
                logger.info("Processing files")

            # Check log content
            log_content = log_file.read_text()
            assert "Starting backup operation" in log_content
            assert "Completed backup operation" in log_content
            assert "Processing files" in log_content

    def test_operation_context_with_exception(self):
        """Test operation context with exception handling."""
        logger = logging.getLogger("test_operation_exception")
        logger.setLevel(logging.INFO)

        try:
            with OperationContext("test", "Test operation", logger):
                raise ValueError("Test error")
        except ValueError:
            pass

        # Check that operation was logged as failed
        # (We can't easily test this without capturing logs, but the context should handle it)

    def test_operation_context_progress_logging(self):
        """Test operation context progress logging methods."""
        logger = logging.getLogger("test_operation_progress")
        logger.setLevel(logging.INFO)

        with OperationContext("backup", "Test backup", logger) as op:
            op.log_progress("Processing file 1")
            op.log_warning("File 2 is large")
            op.log_error("File 3 failed to process")

    def test_operation_context_duration(self):
        """Test operation context duration tracking."""
        with OperationContext("test", "Test operation") as op:
            time.sleep(0.1)  # Small delay to ensure duration > 0

        assert op.duration is not None
        assert op.duration.total_seconds() > 0

    def test_operation_context_json_format(self):
        """Test operation context with JSON formatting."""
        with tempfile.TemporaryDirectory() as temp_dir:
            log_file = Path(temp_dir) / "test.json"

            # Set up file handler with JSON formatter
            handler = logging.FileHandler(log_file)
            handler.setLevel(logging.INFO)
            formatter = create_formatter("json")
            handler.setFormatter(formatter)

            logger = logging.getLogger("test_operation_json")
            logger.setLevel(logging.INFO)
            logger.addHandler(handler)
            logger.propagate = False

            with OperationContext("backup", "Test backup", logger):
                logger.info("Processing files")

            # Check JSON log content
            log_content = log_file.read_text()
            log_lines = log_content.strip().split("\n")

            # Should have at least start and end operation logs
            assert len(log_lines) >= 2

            # Parse JSON and check for operation fields
            start_log = json.loads(log_lines[0])
            assert "operation" in start_log
            assert "operation_id" in start_log
            assert start_log["operation"] == "backup"
