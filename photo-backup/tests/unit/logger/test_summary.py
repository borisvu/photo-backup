"""
Unit tests for logger summary functionality.

Tests summary statistics tracking and formatting.
"""

import time
from datetime import datetime, timedelta

import pytest

from photo_backup.logger.summary import SummaryStatistics


class TestSummaryStatistics:
    """Test summary statistics functionality."""

    def test_summary_statistics_initialization(self):
        """Test summary statistics initialization."""
        summary = SummaryStatistics("backup")
        
        assert summary.operation_type == "backup"
        assert summary.files_processed == 0
        assert summary.files_successful == 0
        assert summary.files_failed == 0
        assert summary.files_skipped == 0
        assert summary.bytes_processed == 0
        assert summary.bytes_transferred == 0
        assert summary.errors == []
        assert summary.start_time is not None

    def test_add_file_processed_success(self):
        """Test adding successfully processed file."""
        summary = SummaryStatistics("backup")
        
        summary.add_file_processed(size_bytes=1024, success=True)
        
        assert summary.files_processed == 1
        assert summary.files_successful == 1
        assert summary.files_failed == 0
        assert summary.files_skipped == 0
        assert summary.bytes_processed == 1024
        assert summary.bytes_transferred == 1024

    def test_add_file_processed_failure(self):
        """Test adding failed file."""
        summary = SummaryStatistics("backup")
        
        summary.add_file_processed(size_bytes=2048, success=False)
        
        assert summary.files_processed == 1
        assert summary.files_successful == 0
        assert summary.files_failed == 1
        assert summary.files_skipped == 0
        assert summary.bytes_processed == 2048
        assert summary.bytes_transferred == 0

    def test_add_file_processed_skipped(self):
        """Test adding skipped file."""
        summary = SummaryStatistics("backup")
        
        summary.add_file_processed(size_bytes=512, skipped=True)
        
        assert summary.files_processed == 1
        assert summary.files_successful == 0
        assert summary.files_failed == 0
        assert summary.files_skipped == 1
        assert summary.bytes_processed == 512
        assert summary.bytes_transferred == 0

    def test_add_error(self):
        """Test adding error message."""
        summary = SummaryStatistics("backup")
        
        summary.add_error("File not found")
        summary.add_error("Permission denied")
        
        assert len(summary.errors) == 2
        assert "File not found" in summary.errors
        assert "Permission denied" in summary.errors

    def test_duration_calculation(self):
        """Test duration calculation."""
        summary = SummaryStatistics("backup")
        
        # Small delay to ensure duration > 0
        time.sleep(0.1)
        
        duration = summary.duration
        assert duration is not None
        assert duration.total_seconds() > 0

    def test_duration_seconds(self):
        """Test duration in seconds."""
        summary = SummaryStatistics("backup")
        
        time.sleep(0.1)
        
        duration_seconds = summary.duration_seconds
        assert duration_seconds > 0

    def test_transfer_rate_calculation(self):
        """Test transfer rate calculation."""
        summary = SummaryStatistics("backup")
        
        # Add some data
        summary.add_file_processed(size_bytes=1024 * 1024, success=True)  # 1 MB
        
        time.sleep(0.1)
        
        rate = summary.transfer_rate_mbps
        assert rate > 0

    def test_success_rate_calculation(self):
        """Test success rate calculation."""
        summary = SummaryStatistics("backup")
        
        # Add mixed results
        summary.add_file_processed(size_bytes=100, success=True)
        summary.add_file_processed(size_bytes=200, success=True)
        summary.add_file_processed(size_bytes=300, success=False)
        summary.add_file_processed(size_bytes=400, skipped=True)
        
        success_rate = summary.success_rate
        assert success_rate == 50.0  # 2 successful out of 4 total

    def test_format_summary_basic(self):
        """Test basic summary formatting."""
        summary = SummaryStatistics("backup")
        
        # Add some data
        summary.add_file_processed(size_bytes=1024 * 1024, success=True)  # 1 MB
        summary.add_file_processed(size_bytes=512 * 1024, success=False)  # 0.5 MB failed
        summary.add_file_processed(size_bytes=256 * 1024, skipped=True)  # 0.25 MB skipped
        
        time.sleep(0.1)
        summary.end()
        
        formatted = summary.format_summary()
        
        assert "=== Backup Summary ===" in formatted
        assert "Duration:" in formatted
        assert "Files: 3 processed, 1 successful, 1 failed, 1 skipped" in formatted
        assert "Data:" in formatted
        assert "Rate:" in formatted
        assert "Success Rate: 33.3%" in formatted

    def test_format_summary_with_errors(self):
        """Test summary formatting with errors."""
        summary = SummaryStatistics("backup")
        
        summary.add_error("File not found: photo1.jpg")
        summary.add_error("Permission denied: photo2.jpg")
        
        formatted = summary.format_summary()
        
        assert "Errors:" in formatted
        assert "File not found: photo1.jpg" in formatted
        assert "Permission denied: photo2.jpg" in formatted

    def test_format_summary_without_errors(self):
        """Test summary formatting without errors."""
        summary = SummaryStatistics("backup")
        
        formatted = summary.format_summary(include_errors=False)
        
        assert "Errors:" not in formatted

    def test_to_dict(self):
        """Test dictionary conversion."""
        summary = SummaryStatistics("backup")
        
        summary.add_file_processed(size_bytes=1024, success=True)
        summary.add_error("Test error")
        
        time.sleep(0.1)
        summary.end()
        
        summary_dict = summary.to_dict()
        
        assert summary_dict["operation_type"] == "backup"
        assert summary_dict["files_processed"] == 1
        assert summary_dict["files_successful"] == 1
        assert summary_dict["files_failed"] == 0
        assert summary_dict["files_skipped"] == 0
        assert summary_dict["bytes_processed"] == 1024
        assert summary_dict["bytes_transferred"] == 1024
        assert summary_dict["errors"] == ["Test error"]
        assert summary_dict["duration_seconds"] > 0
        assert "duration_formatted" in summary_dict
        assert summary_dict["success_rate"] == 100.0

    def test_zero_duration_handling(self):
        """Test handling of zero duration."""
        summary = SummaryStatistics("backup")
        
        # End immediately
        summary.end()
        
        # Even with immediate end, there might be a tiny duration
        assert summary.duration_seconds >= 0.0
        assert summary.transfer_rate_mbps == 0.0

    def test_zero_files_handling(self):
        """Test handling of zero files."""
        summary = SummaryStatistics("backup")
        
        assert summary.success_rate == 0.0
        
        formatted = summary.format_summary()
        assert "Files: 0 processed, 0 successful, 0 failed, 0 skipped" in formatted

    def test_large_file_sizes(self):
        """Test handling of large file sizes."""
        summary = SummaryStatistics("backup")
        
        # Add 1 GB file
        summary.add_file_processed(size_bytes=1024 * 1024 * 1024, success=True)
        
        time.sleep(0.1)
        summary.end()
        
        formatted = summary.format_summary()
        assert "1024.0 MB" in formatted  # Should show in MB
