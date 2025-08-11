"""
Summary statistics for operations.

This module provides summary tracking and formatting for operations,
including files processed, bytes transferred, and timing information.
"""

import time
from datetime import datetime, timedelta
from typing import Optional

from .utils import format_duration


class SummaryStatistics:
    """Track and format operation summary statistics."""

    def __init__(self, operation_type: str = "operation"):
        """Initialize summary statistics.

        Args:
            operation_type: Type of operation (e.g., 'backup', 'scan', 'sync')
        """
        self.operation_type = operation_type
        self.start_time: Optional[datetime] = None
        self.end_time: Optional[datetime] = None
        
        # File statistics
        self.files_processed = 0
        self.files_successful = 0
        self.files_failed = 0
        self.files_skipped = 0
        
        # Size statistics
        self.bytes_processed = 0
        self.bytes_transferred = 0
        
        # Error tracking
        self.errors: list[str] = []
        
        # Start timing
        self.start()

    def start(self) -> None:
        """Start timing the operation."""
        self.start_time = datetime.now()

    def end(self) -> None:
        """End timing the operation."""
        self.end_time = datetime.now()

    def add_file_processed(self, size_bytes: int = 0, success: bool = True, skipped: bool = False) -> None:
        """Add a processed file to the statistics.

        Args:
            size_bytes: Size of the file in bytes
            success: Whether the file was processed successfully
            skipped: Whether the file was skipped
        """
        self.files_processed += 1
        self.bytes_processed += size_bytes
        
        if skipped:
            self.files_skipped += 1
        elif success:
            self.files_successful += 1
            self.bytes_transferred += size_bytes
        else:
            self.files_failed += 1

    def add_error(self, error_message: str) -> None:
        """Add an error to the summary.

        Args:
            error_message: Description of the error
        """
        self.errors.append(error_message)

    @property
    def duration(self) -> Optional[timedelta]:
        """Get the operation duration."""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        elif self.start_time:
            return datetime.now() - self.start_time
        return None

    @property
    def duration_seconds(self) -> float:
        """Get the operation duration in seconds."""
        duration = self.duration
        return duration.total_seconds() if duration else 0.0

    @property
    def transfer_rate_mbps(self) -> float:
        """Get the transfer rate in MB/s."""
        if self.duration_seconds > 0 and self.bytes_transferred > 0:
            return (self.bytes_transferred / 1024 / 1024) / self.duration_seconds
        return 0.0

    @property
    def success_rate(self) -> float:
        """Get the success rate as a percentage."""
        if self.files_processed > 0:
            return (self.files_successful / self.files_processed) * 100
        return 0.0

    def format_summary(self, include_errors: bool = True) -> str:
        """Format the summary as a human-readable string.

        Args:
            include_errors: Whether to include error details

        Returns:
            Formatted summary string
        """
        duration_str = format_duration(self.duration_seconds) if self.duration else "unknown"
        
        # Format file sizes
        processed_mb = self.bytes_processed / 1024 / 1024
        transferred_mb = self.bytes_transferred / 1024 / 1024
        
        summary_lines = [
            f"=== {self.operation_type.title()} Summary ===",
            f"Duration: {duration_str}",
            f"Files: {self.files_processed} processed, {self.files_successful} successful, {self.files_failed} failed, {self.files_skipped} skipped",
            f"Data: {processed_mb:.1f} MB processed, {transferred_mb:.1f} MB transferred",
            f"Rate: {self.transfer_rate_mbps:.1f} MB/s",
            f"Success Rate: {self.success_rate:.1f}%"
        ]
        
        if include_errors and self.errors:
            summary_lines.append("")
            summary_lines.append("Errors:")
            for error in self.errors:
                summary_lines.append(f"  - {error}")
        
        return "\n".join(summary_lines)

    def to_dict(self) -> dict:
        """Convert summary to dictionary for JSON logging.

        Returns:
            Dictionary representation of the summary
        """
        return {
            "operation_type": self.operation_type,
            "duration_seconds": self.duration_seconds,
            "duration_formatted": format_duration(self.duration_seconds) if self.duration else "unknown",
            "files_processed": self.files_processed,
            "files_successful": self.files_successful,
            "files_failed": self.files_failed,
            "files_skipped": self.files_skipped,
            "bytes_processed": self.bytes_processed,
            "bytes_transferred": self.bytes_transferred,
            "transfer_rate_mbps": self.transfer_rate_mbps,
            "success_rate": self.success_rate,
            "errors": self.errors.copy() if self.errors else []
        }
