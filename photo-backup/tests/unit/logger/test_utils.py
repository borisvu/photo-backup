"""
Unit tests for logger utility functions.

Tests log level parsing and job ID generation.
"""

import logging

import pytest

from photo_backup.logger.utils import _parse_log_level, generate_job_id


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
