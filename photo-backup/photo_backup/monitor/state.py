"""
Monitor state management.

This module provides persistent state management for the DriveMonitor,
allowing it to remember check times, change history, and statistics across restarts.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class MonitorState:
    """
    Represents the persistent state of the drive monitor.

    Tracks monitoring activity including check times, change detection,
    and historical statistics to maintain continuity across restarts.

    Attributes:
        last_check_time: Timestamp of last check performed
        last_change_time: Timestamp of last change detected
        total_checks: Number of checks performed
        total_changes_detected: Total number of changes detected
        change_history: Recent change events (limited to max_history_size)
        watch_path: Path being monitored
    """

    # Timing information
    last_check_time: datetime | None = None
    last_change_time: datetime | None = None

    # Statistics
    total_checks: int = 0
    total_changes_detected: int = 0

    # Change history (limited size)
    change_history: list[dict[str, Any]] = field(default_factory=list)

    # Configuration
    watch_path: str = ""

    # Maximum history entries to keep
    MAX_HISTORY_SIZE: int = 100

    def to_dict(self) -> dict[str, Any]:
        """
        Convert MonitorState to dictionary for JSON serialization.

        Returns:
            dict: Serialized state with datetime objects converted to ISO format
        """
        return {
            "last_check_time": self.last_check_time.isoformat() if self.last_check_time else None,
            "last_change_time": self.last_change_time.isoformat() if self.last_change_time else None,
            "total_checks": self.total_checks,
            "total_changes_detected": self.total_changes_detected,
            "change_history": self.change_history.copy(),
            "watch_path": self.watch_path,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "MonitorState":
        """
        Create MonitorState from dictionary (deserialization).

        Args:
            data: Dictionary with state data

        Returns:
            MonitorState: Reconstructed state object
        """
        # Parse datetime fields
        last_check_time = None
        if data.get("last_check_time"):
            last_check_time = datetime.fromisoformat(data["last_check_time"])

        last_change_time = None
        if data.get("last_change_time"):
            last_change_time = datetime.fromisoformat(data["last_change_time"])

        return cls(
            last_check_time=last_check_time,
            last_change_time=last_change_time,
            total_checks=data.get("total_checks", 0),
            total_changes_detected=data.get("total_changes_detected", 0),
            change_history=data.get("change_history", []),
            watch_path=data.get("watch_path", ""),
        )

    def add_change_event(self, event_type: str, file_path: str, timestamp: datetime | None = None) -> None:
        """
        Add a change event to history.

        Maintains a limited history size by removing oldest entries when full.

        Args:
            event_type: Type of event (e.g., "file_added", "file_modified")
            file_path: Path of the changed file
            timestamp: Event timestamp (defaults to now)
        """
        if timestamp is None:
            timestamp = datetime.now()

        event = {
            "timestamp": timestamp.isoformat(),
            "event_type": event_type,
            "file_path": file_path,
        }

        self.change_history.append(event)

        # Trim history to max size
        if len(self.change_history) > self.MAX_HISTORY_SIZE:
            self.change_history = self.change_history[-self.MAX_HISTORY_SIZE :]

    def update_check(self, timestamp: datetime | None = None) -> None:
        """
        Update state after a check is performed.

        Args:
            timestamp: Check timestamp (defaults to now)
        """
        if timestamp is None:
            timestamp = datetime.now()

        self.last_check_time = timestamp
        self.total_checks += 1

    def update_changes(self, change_count: int, timestamp: datetime | None = None) -> None:
        """
        Update state after changes are detected.

        Args:
            change_count: Number of changes detected
            timestamp: Change timestamp (defaults to now)
        """
        if timestamp is None:
            timestamp = datetime.now()

        if change_count > 0:
            self.last_change_time = timestamp
            self.total_changes_detected += change_count
