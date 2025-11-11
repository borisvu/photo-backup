"""
Monitoring events for photo backup system.

This module defines the various events that can be detected
during file system monitoring.
"""

from dataclasses import dataclass, field
from enum import Enum


class MonitorEvent(Enum):
    """Types of monitoring events that can be detected."""

    # File system events
    FILE_ADDED = "file_added"
    FILE_MODIFIED = "file_modified"
    FILE_DELETED = "file_deleted"

    # Directory events
    DIRECTORY_ADDED = "directory_added"
    DIRECTORY_DELETED = "directory_deleted"

    # Drive events
    DRIVE_MOUNTED = "drive_mounted"
    DRIVE_UNMOUNTED = "drive_unmounted"

    # Timer events
    TIMER_ELAPSED = "timer_elapsed"
    CHECK_INTERVAL = "check_interval"

    # State events
    MONITOR_STARTED = "monitor_started"
    MONITOR_STOPPED = "monitor_stopped"
    CHANGES_DETECTED = "changes_detected"
    NO_CHANGES = "no_changes"
    CHANGES_RESET = "changes_reset"
    STATE_CLEARED = "state_cleared"


class MonitorState(Enum):
    """States of the monitor system."""

    IDLE = "idle"
    WATCHING = "watching"
    PROCESSING = "processing"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class ChangeSummary:
    """
    Summary of detected file system changes.

    Provides aggregated statistics about changes including counts,
    sizes, and grouping by directory.

    Attributes:
        total_files: Total number of changed files
        total_size: Total size of changed files in bytes
        added_count: Number of new files
        modified_count: Number of modified files
        deleted_count: Number of deleted files
        by_directory: Mapping of directory path to file count
        by_directory_size: Mapping of directory path to total size in bytes
    """

    total_files: int = 0
    total_size: int = 0
    added_count: int = 0
    modified_count: int = 0
    deleted_count: int = 0
    by_directory: dict[str, int] = field(default_factory=dict)
    by_directory_size: dict[str, int] = field(default_factory=dict)

    def get_formatted_size(self) -> str:
        """
        Get total size formatted as human-readable string.

        Returns:
            str: Formatted size (e.g., "1.5 GB", "234 MB", "5.2 KB")
        """
        size = float(self.total_size)
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} PB"
