"""
Backup statistics and metrics.

This module provides comprehensive statistics tracking and reporting
for backup operations.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .errors import BackupError


@dataclass
class TransferStats:
    """Transfer statistics from rclone progress parser.

    This is a simple dataclass to match the expected interface from progress_parser.
    """

    files_transferred: int = 0
    files_total: int = 0
    bytes_transferred: int = 0
    bytes_total: int = 0
    transfer_rate_mbps: float = 0.0
    percentage: float = 0.0
    errors: int = 0


@dataclass
class BackupStats:
    """Comprehensive backup statistics and metrics."""

    # Basic metadata
    start_time: datetime
    end_time: datetime | None = None
    duration_seconds: float = 0.0

    # Transfer statistics
    files_transferred: int = 0
    files_total: int = 0
    bytes_transferred: int = 0
    bytes_total: int = 0
    errors: int = 0

    # Calculated metrics
    transfer_rate_mbps: float = 0.0
    files_rate_per_second: float = 0.0

    # Backup metadata
    source_path: str = ""
    destination: str = ""
    dry_run: bool = False
    test_mode: bool = False
    success: bool = False
    error_message: str | None = None
    detailed_errors: list[BackupError] = field(default_factory=list)
    error_summary: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_transfer_stats(
        cls,
        transfer_stats: Any,  # TransferStats from progress_parser
        start_time: datetime,
        end_time: datetime,
        source_path: str,
        destination: str,
        dry_run: bool,
        test_mode: bool,
        success: bool,
        error_message: str | None = None,
        detailed_errors: list[BackupError] | None = None,
        error_summary: dict[str, Any] | None = None,
    ) -> "BackupStats":
        """Create BackupStats from TransferStats and additional metadata.

        Args:
            transfer_stats: Transfer statistics from rclone progress parser
            start_time: Backup start time
            end_time: Backup end time
            source_path: Source directory path
            destination: Backup destination
            dry_run: Whether this was a dry run
            test_mode: Whether this was run in test mode
            success: Whether the backup completed successfully
            error_message: Error message if backup failed
            detailed_errors: List of detailed BackupError objects
            error_summary: Summary statistics about errors

        Returns:
            BackupStats instance with calculated metrics
        """
        duration = (end_time - start_time).total_seconds()

        # Calculate rates
        transfer_rate_mbps = 0.0
        files_rate_per_second = 0.0

        if duration > 0:
            # Convert bytes to MB and calculate rate
            mb_transferred = transfer_stats.bytes_transferred / (1024 * 1024)
            transfer_rate_mbps = mb_transferred / duration

            # Calculate files per second rate
            files_rate_per_second = transfer_stats.files_transferred / duration

        return cls(
            start_time=start_time,
            end_time=end_time,
            duration_seconds=duration,
            files_transferred=transfer_stats.files_transferred,
            files_total=transfer_stats.files_total,
            bytes_transferred=transfer_stats.bytes_transferred,
            bytes_total=transfer_stats.bytes_total,
            errors=transfer_stats.errors,
            transfer_rate_mbps=transfer_rate_mbps,
            files_rate_per_second=files_rate_per_second,
            source_path=source_path,
            destination=destination,
            dry_run=dry_run,
            test_mode=test_mode,
            success=success,
            error_message=error_message,
            detailed_errors=detailed_errors or [],
            error_summary=error_summary or {},
        )

    @property
    def files_percentage(self) -> float:
        """Calculate percentage of files transferred."""
        if self.files_total == 0:
            return 0.0
        return (self.files_transferred / self.files_total) * 100

    @property
    def bytes_percentage(self) -> float:
        """Calculate percentage of bytes transferred."""
        if self.bytes_total == 0:
            return 0.0
        return (self.bytes_transferred / self.bytes_total) * 100

    @property
    def formatted_bytes_transferred(self) -> str:
        """Format bytes transferred as human-readable string."""
        return self._format_bytes(self.bytes_transferred)

    @property
    def formatted_bytes_total(self) -> str:
        """Format total bytes as human-readable string."""
        return self._format_bytes(self.bytes_total)

    @property
    def formatted_duration(self) -> str:
        """Format duration as human-readable string."""
        if self.duration_seconds < 60:
            return f"{self.duration_seconds:.1f}s"
        elif self.duration_seconds < 3600:
            minutes = int(self.duration_seconds // 60)
            seconds = int(self.duration_seconds % 60)
            return f"{minutes}m {seconds}s"
        else:
            hours = int(self.duration_seconds // 3600)
            minutes = int((self.duration_seconds % 3600) // 60)
            return f"{hours}h {minutes}m"

    def _format_bytes(self, bytes_count: int) -> str:
        """Format bytes as human-readable string with appropriate units."""
        if bytes_count == 0:
            return "0 B"

        units = ["B", "KB", "MB", "GB", "TB"]
        size = float(bytes_count)
        unit_index = 0

        while size >= 1024 and unit_index < len(units) - 1:
            size /= 1024
            unit_index += 1

        if unit_index == 0:
            return f"{int(size)} {units[unit_index]}"
        else:
            return f"{size:.1f} {units[unit_index]}"

    def get_summary(self) -> str:
        """Get a human-readable summary of the backup statistics."""
        status = "SUCCESS" if self.success else "FAILED"
        mode = f"{'DRY RUN ' if self.dry_run else ''}{'TEST MODE' if self.test_mode else 'PRODUCTION'}"

        summary_lines = [
            f"Backup {status} ({mode})",
            f"Duration: {self.formatted_duration}",
            f"Files: {self.files_transferred:,}/{self.files_total:,} ({self.files_percentage:.1f}%)",
            f"Data: {self.formatted_bytes_transferred}/{self.formatted_bytes_total} ({self.bytes_percentage:.1f}%)",
            f"Transfer Rate: {self.transfer_rate_mbps:.1f} MB/s",
            f"Files Rate: {self.files_rate_per_second:.1f} files/s",
        ]

        if self.errors > 0:
            summary_lines.append(f"Errors: {self.errors}")

        if not self.success and self.error_message:
            summary_lines.append(f"Error: {self.error_message}")

        return "\n".join(summary_lines)

    def to_dict(self) -> dict[str, Any]:
        """Convert backup statistics to dictionary for JSON serialization."""
        return {
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": self.duration_seconds,
            "files_transferred": self.files_transferred,
            "files_total": self.files_total,
            "bytes_transferred": self.bytes_transferred,
            "bytes_total": self.bytes_total,
            "errors": self.errors,
            "transfer_rate_mbps": self.transfer_rate_mbps,
            "files_rate_per_second": self.files_rate_per_second,
            "files_percentage": self.files_percentage,
            "bytes_percentage": self.bytes_percentage,
            "source_path": self.source_path,
            "destination": self.destination,
            "dry_run": self.dry_run,
            "test_mode": self.test_mode,
            "success": self.success,
            "error_message": self.error_message,
            "formatted_bytes_transferred": self.formatted_bytes_transferred,
            "formatted_bytes_total": self.formatted_bytes_total,
            "formatted_duration": self.formatted_duration,
        }
