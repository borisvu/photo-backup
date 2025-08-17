"""
Progress parsing for rclone output.

This module provides functionality to parse rclone progress output and extract
transfer statistics, progress percentages, and emit progress events.
"""

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass

from .logger.progress import ProgressLogger


@dataclass
class TransferStats:
    """Transfer statistics extracted from rclone output."""

    files_transferred: int = 0
    files_total: int = 0
    bytes_transferred: int = 0
    bytes_total: int = 0
    transfer_rate_mbps: float = 0.0
    eta_seconds: int | None = None
    percentage: float = 0.0
    errors: int = 0

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


class RcloneProgressParser:
    """Parser for rclone progress output."""

    def __init__(self, logger: logging.Logger | None = None):
        """Initialize the progress parser.

        Args:
            logger: Optional logger for debug output
        """
        self.logger = logger or logging.getLogger(__name__)
        self.progress_logger: ProgressLogger | None = None
        self.last_stats = TransferStats()

        # Callback for progress events
        self.progress_callback: Callable[[TransferStats], None] | None = None

        # Regex patterns for parsing rclone output
        self.patterns = {
            # Pattern for --stats-one-line output:
            # "Transferred: 5 / 10 files, 1.5 MiB / 3.0 MiB, 50% complete, 1.2 MiB/s, ETA 2s"
            "stats_one_line": re.compile(
                r"Transferred:\s*(\d+)\s*/\s*(\d+)\s*files?,\s*"
                r"([\d.]+)\s*([KMGT]?)i?B\s*/\s*([\d.]+)\s*([KMGT]?)i?B,?\s*"
                r"(\d+)%\s*complete(?:,\s*([\d.]+)\s*([KMGT]?)i?B/s)?(?:,\s*ETA\s*(\d+[smhd]?))?"
            ),
            # Pattern for errors: "ERROR : file.jpg: error message"
            "error": re.compile(r"ERROR\s*:\s*(.+)"),
            # Pattern for "Transferred: X files (Y MiB)" summary
            "final_summary": re.compile(r"Transferred:\s*(\d+)\s*files?\s*\(([\d.]+)\s*([KMGT]?)i?B\)"),
            # Pattern for checking/transfer counts
            "checking": re.compile(r"checking\s*(\d+)\s*/\s*(\d+)"),
            "transferring": re.compile(r"transferring\s*(\d+)\s*/\s*(\d+)"),
        }

    def set_progress_callback(self, callback: Callable[[TransferStats], None]) -> None:
        """Set callback function for progress events.

        Args:
            callback: Function to call with TransferStats on each progress update
        """
        self.progress_callback = callback

    def init_progress_logger(self, total_files: int, operation_type: str = "backup") -> None:
        """Initialize progress logger with total file count.

        Args:
            total_files: Total number of files to transfer
            operation_type: Type of operation for logging
        """
        self.progress_logger = ProgressLogger(
            total_items=total_files,
            operation_type=operation_type,
            update_interval=2.0,  # Update every 2 seconds
            logger=self.logger,
        )

    def parse_line(self, line: str) -> TransferStats | None:
        """Parse a single line of rclone output.

        Args:
            line: Line of rclone output to parse

        Returns:
            TransferStats if progress information was extracted, None otherwise
        """
        line = line.strip()
        if not line:
            return None

        # Try to parse stats-one-line format
        stats = self._parse_stats_one_line(line)
        if stats:
            # Preserve error count from previous stats
            stats.errors = self.last_stats.errors
            self.last_stats = stats
            self._emit_progress(stats)
            return stats

        # Try to parse final summary
        stats = self._parse_final_summary(line)
        if stats:
            # Preserve error count from previous stats
            stats.errors = self.last_stats.errors
            self.last_stats = stats
            self._emit_progress(stats)
            return stats

        # Check for errors
        if self._parse_error(line):
            self.last_stats.errors += 1
            # Don't emit progress for errors, just increment count
            return None

        return None

    def _parse_stats_one_line(self, line: str) -> TransferStats | None:
        """Parse --stats-one-line format output."""
        match = self.patterns["stats_one_line"].search(line)
        if not match:
            return None

        try:
            files_transferred = int(match.group(1))
            files_total = int(match.group(2))
            bytes_transferred = self._parse_size(match.group(3), match.group(4))
            bytes_total = self._parse_size(match.group(5), match.group(6))
            percentage = float(match.group(7))

            # Parse transfer rate if present
            transfer_rate_mbps = 0.0
            if match.group(8) and match.group(9):
                rate_bytes_per_sec = self._parse_size(match.group(8), match.group(9))
                transfer_rate_mbps = rate_bytes_per_sec / (1024 * 1024)  # Convert to MB/s

            # Parse ETA if present
            eta_seconds = None
            if match.group(10):
                eta_seconds = self._parse_duration(match.group(10))

            return TransferStats(
                files_transferred=files_transferred,
                files_total=files_total,
                bytes_transferred=bytes_transferred,
                bytes_total=bytes_total,
                transfer_rate_mbps=transfer_rate_mbps,
                eta_seconds=eta_seconds,
                percentage=percentage,
            )
        except (ValueError, AttributeError) as e:
            self.logger.debug(f"Failed to parse stats line: {line} - {e}")
            return None

    def _parse_final_summary(self, line: str) -> TransferStats | None:
        """Parse final transfer summary."""
        match = self.patterns["final_summary"].search(line)
        if not match:
            return None

        try:
            files_transferred = int(match.group(1))
            bytes_transferred = self._parse_size(match.group(2), match.group(3))

            # Create stats with 100% completion
            return TransferStats(
                files_transferred=files_transferred,
                files_total=files_transferred,  # Assume all files were transferred
                bytes_transferred=bytes_transferred,
                bytes_total=bytes_transferred,
                percentage=100.0,
            )
        except (ValueError, AttributeError) as e:
            self.logger.debug(f"Failed to parse summary line: {line} - {e}")
            return None

    def _parse_error(self, line: str) -> bool:
        """Parse error lines."""
        match = self.patterns["error"].search(line)
        if match:
            error_msg = match.group(1)
            self.logger.warning(f"rclone error: {error_msg}")
            return True
        return False

    def _parse_size(self, size_str: str, unit: str) -> int:
        """Parse size string with unit into bytes."""
        try:
            size = float(size_str)

            # Convert to bytes based on unit
            multipliers = {"": 1, "K": 1024, "M": 1024 * 1024, "G": 1024 * 1024 * 1024, "T": 1024 * 1024 * 1024 * 1024}

            multiplier = multipliers.get(unit.upper(), 1)
            return int(size * multiplier)
        except (ValueError, KeyError):
            return 0

    def _parse_duration(self, duration_str: str) -> int | None:
        """Parse duration string into seconds."""
        try:
            if duration_str.endswith("s"):
                return int(duration_str[:-1])
            elif duration_str.endswith("m"):
                return int(duration_str[:-1]) * 60
            elif duration_str.endswith("h"):
                return int(duration_str[:-1]) * 3600
            elif duration_str.endswith("d"):
                return int(duration_str[:-1]) * 86400
            else:
                return int(duration_str)  # Assume seconds
        except ValueError:
            return None

    def _emit_progress(self, stats: TransferStats) -> None:
        """Emit progress event via callback and progress logger."""
        # Call custom callback if set
        if self.progress_callback:
            try:
                self.progress_callback(stats)
            except Exception as e:
                self.logger.error(f"Progress callback error: {e}")

        # Update progress logger if initialized
        if self.progress_logger and stats.files_total > 0:
            message = f"{stats.bytes_transferred / (1024 * 1024):.1f} MB transferred"
            if stats.transfer_rate_mbps > 0:
                message += f" at {stats.transfer_rate_mbps:.1f} MB/s"

            self.progress_logger.update(stats.files_transferred, message)

    def complete(self) -> None:
        """Mark progress as complete."""
        if self.progress_logger:
            self.progress_logger.complete("Transfer completed")

    def get_final_stats(self) -> TransferStats:
        """Get the final transfer statistics."""
        return self.last_stats
