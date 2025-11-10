"""
Monitoring events for photo backup system.

This module defines the various events that can be detected
during file system monitoring.
"""

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


class MonitorState(Enum):
    """States of the monitor system."""

    IDLE = "idle"
    WATCHING = "watching"
    PROCESSING = "processing"
    STOPPED = "stopped"
    ERROR = "error"
