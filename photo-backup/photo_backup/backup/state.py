"""
Backup state management.

This module provides persistent state management for tracking backup
history, statistics, and error tracking across operations.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from ..state_utils import load_json_state, save_json_state
from .errors import BackupError, ErrorType
from .stats import BackupStats


@dataclass
class BackupState:
    """Represents the persistent state of a backup operation."""

    # Last sync information
    last_sync_time: datetime | None = None
    last_successful_sync: datetime | None = None

    # Statistics from last sync
    last_stats: BackupStats | None = None

    # Cumulative statistics
    total_syncs: int = 0
    successful_syncs: int = 0
    failed_syncs: int = 0
    total_files_transferred: int = 0
    total_bytes_transferred: int = 0
    total_sync_time: float = 0.0

    # Error tracking
    last_error: str | None = None
    consecutive_failures: int = 0
    error_history: list[dict[str, Any]] = field(default_factory=list)

    # Source and destination tracking
    source_path: str = ""
    destination: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert BackupState to dictionary for JSON serialization."""
        data = {
            "last_sync_time": self.last_sync_time.isoformat() if self.last_sync_time else None,
            "last_successful_sync": self.last_successful_sync.isoformat() if self.last_successful_sync else None,
            "last_stats": self.last_stats.to_dict() if self.last_stats else None,
            "total_syncs": self.total_syncs,
            "successful_syncs": self.successful_syncs,
            "failed_syncs": self.failed_syncs,
            "total_files_transferred": self.total_files_transferred,
            "total_bytes_transferred": self.total_bytes_transferred,
            "total_sync_time": self.total_sync_time,
            "last_error": self.last_error,
            "consecutive_failures": self.consecutive_failures,
            "error_history": self.error_history,
            "source_path": self.source_path,
            "destination": self.destination,
        }

        # Handle datetime serialization in last_stats
        if data["last_stats"] and isinstance(data["last_stats"], dict):
            last_stats = data["last_stats"]
            if "start_time" in last_stats and hasattr(last_stats["start_time"], "isoformat"):
                last_stats["start_time"] = last_stats["start_time"].isoformat()
            if "end_time" in last_stats and hasattr(last_stats["end_time"], "isoformat"):
                last_stats["end_time"] = last_stats["end_time"].isoformat()

            # Handle BackupError objects in detailed_errors
            if "detailed_errors" in last_stats and isinstance(last_stats["detailed_errors"], list):
                detailed_errors = last_stats["detailed_errors"]
                serialized_errors = []
                for error in detailed_errors:
                    if hasattr(error, "error_type"):  # It's a BackupError object
                        serialized_errors.append(
                            {
                                "error_type": error.error_type.value
                                if hasattr(error.error_type, "value")
                                else str(error.error_type),
                                "message": error.message,
                                "file_path": error.file_path,
                                "line_number": error.line_number,
                                "raw_output": error.raw_output,
                                "suggestion": error.suggestion,
                            }
                        )
                    else:
                        # Already serialized
                        serialized_errors.append(error)
                last_stats["detailed_errors"] = serialized_errors

        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "BackupState":
        """Create BackupState from dictionary (JSON deserialization)."""
        state = cls()

        # Parse datetime fields
        if data.get("last_sync_time"):
            state.last_sync_time = datetime.fromisoformat(data["last_sync_time"])
        if data.get("last_successful_sync"):
            state.last_successful_sync = datetime.fromisoformat(data["last_successful_sync"])

        # Parse last_stats if present
        if data.get("last_stats"):
            stats_data = data["last_stats"]
            # Parse datetime fields in stats
            if stats_data.get("start_time"):
                stats_data["start_time"] = datetime.fromisoformat(stats_data["start_time"])
            if stats_data.get("end_time"):
                stats_data["end_time"] = datetime.fromisoformat(stats_data["end_time"])

            # Reconstruct BackupError objects if present
            if "detailed_errors" in stats_data and isinstance(stats_data["detailed_errors"], list):
                detailed_errors = []
                for error_data in stats_data["detailed_errors"]:
                    if isinstance(error_data, dict) and "error_type" in error_data:
                        try:
                            error_type = (
                                ErrorType(error_data["error_type"])
                                if isinstance(error_data["error_type"], str)
                                else error_data["error_type"]
                            )
                            detailed_errors.append(
                                BackupError(
                                    error_type=error_type,
                                    message=error_data.get("message", ""),
                                    file_path=error_data.get("file_path", ""),
                                    line_number=error_data.get("line_number", 0),
                                    raw_output=error_data.get("raw_output", ""),
                                    suggestion=error_data.get("suggestion", ""),
                                )
                            )
                        except (ValueError, KeyError):
                            # Skip invalid error data
                            continue
                stats_data["detailed_errors"] = detailed_errors

            # Reconstruct BackupStats object
            state.last_stats = BackupStats(
                **{k: v for k, v in stats_data.items() if k in BackupStats.__dataclass_fields__}
            )

        # Set other fields
        state.total_syncs = data.get("total_syncs", 0)
        state.successful_syncs = data.get("successful_syncs", 0)
        state.failed_syncs = data.get("failed_syncs", 0)
        state.total_files_transferred = data.get("total_files_transferred", 0)
        state.total_bytes_transferred = data.get("total_bytes_transferred", 0)
        state.total_sync_time = data.get("total_sync_time", 0.0)
        state.last_error = data.get("last_error")
        state.consecutive_failures = data.get("consecutive_failures", 0)
        state.error_history = data.get("error_history", [])
        state.source_path = data.get("source_path", "")
        state.destination = data.get("destination", "")

        return state

    def update_from_stats(self, stats: BackupStats):
        """Update state with results from a backup operation."""
        self.last_sync_time = datetime.now()
        self.last_stats = stats
        self.source_path = stats.source_path
        self.destination = stats.destination

        # Update totals
        self.total_syncs += 1

        if stats.success:
            self.successful_syncs += 1
            self.last_successful_sync = self.last_sync_time
            self.consecutive_failures = 0
            self.last_error = None

            # Add to cumulative stats
            self.total_files_transferred += stats.files_transferred
            self.total_bytes_transferred += stats.bytes_transferred
            self.total_sync_time += stats.duration_seconds
        else:
            self.failed_syncs += 1
            self.consecutive_failures += 1
            self.last_error = stats.error_message

            # Add to error history (keep last 10)
            error_entry = {
                "timestamp": self.last_sync_time.isoformat(),
                "error": stats.error_message,
                "error_count": stats.errors,
                "duration": stats.duration_seconds,
            }
            self.error_history.append(error_entry)
            if len(self.error_history) > 10:
                self.error_history.pop(0)


class StateManager:
    """Manages persistent backup state across operations."""

    def __init__(self, test_mode: bool = False):
        """Initialize StateManager.

        Args:
            test_mode: If True, use test mode state directory
        """
        self.test_mode = test_mode
        self.state_filename = "backup_state.json"
        self.logger = logging.getLogger(__name__)

    def load_state(self) -> BackupState:
        """Load backup state from persistent storage.

        Returns:
            BackupState object (creates new if file doesn't exist)
        """
        state_data, error = load_json_state(self.state_filename, test_mode=self.test_mode)

        if error:
            self.logger.debug(f"No existing state found, creating new: {error}")
            return BackupState()

        try:
            return BackupState.from_dict(state_data)
        except Exception as e:
            self.logger.warning(f"Failed to parse existing state, creating new: {e}")
            return BackupState()

    def save_state(self, state: BackupState) -> tuple[bool, str | None]:
        """Save backup state to persistent storage.

        Args:
            state: BackupState object to save

        Returns:
            Tuple of (success, error_message)
        """
        try:
            state_dict = state.to_dict()
            return save_json_state(state_dict, self.state_filename, test_mode=self.test_mode)
        except Exception as e:
            error_msg = f"Failed to serialize state: {e}"
            self.logger.error(error_msg)
            return False, error_msg

    def update_and_save_state(self, stats: BackupStats) -> tuple[bool, str | None]:
        """Load state, update with new stats, and save.

        Args:
            stats: BackupStats from completed backup operation

        Returns:
            Tuple of (success, error_message)
        """
        state = self.load_state()
        state.update_from_stats(stats)
        return self.save_state(state)

    def get_state_summary(self) -> dict[str, Any]:
        """Get a summary of the current backup state.

        Returns:
            Dictionary with key state metrics
        """
        state = self.load_state()

        return {
            "last_sync_time": state.last_sync_time.isoformat() if state.last_sync_time else None,
            "last_successful_sync": state.last_successful_sync.isoformat() if state.last_successful_sync else None,
            "total_syncs": state.total_syncs,
            "successful_syncs": state.successful_syncs,
            "failed_syncs": state.failed_syncs,
            "success_rate": (state.successful_syncs / state.total_syncs * 100) if state.total_syncs > 0 else 0,
            "consecutive_failures": state.consecutive_failures,
            "total_files_transferred": state.total_files_transferred,
            "total_bytes_transferred": state.total_bytes_transferred,
            "total_sync_time": state.total_sync_time,
            "last_error": state.last_error,
            "source_path": state.source_path,
            "destination": state.destination,
        }
