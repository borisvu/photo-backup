"""
Drive monitoring for photo backup system.

This module provides the DriveMonitor class for detecting changes
in the photo directory and triggering backups accordingly.
"""

import time
from datetime import datetime
from typing import Any

from pathlib import Path

from ..config import Config
from ..logger import get_logger
from ..state_utils import load_json_state, save_json_state
from .events import ChangeSummary, MonitorEvent, MonitorState
from .state import MonitorState as MonitorStateData


class DriveMonitor:
    """
    Monitor for detecting changes in photo directory.

    In test mode, monitors a test directory. In production mode,
    monitors the configured photo source directory.

    Attributes:
        config: Configuration object with test mode and paths
        state: Current state of the monitor
        watch_path: Path being monitored
    """

    def __init__(self, config: Config | None = None):
        """
        Initialize the drive monitor.

        Args:
            config: Configuration object. If None, creates default config.
        """
        self.config = config or Config()
        self.logger = get_logger(__name__)
        self.state = MonitorState.IDLE
        self._watch_path: Path | None = None
        self._event_history: list[tuple[MonitorEvent, str]] = []

        # File watching state
        self._file_snapshot: dict[str, float] = {}  # path -> mtime mapping
        self._changes_detected: list[tuple[str, MonitorEvent]] = []  # (path, event) list

        # Debouncing state
        self._last_change_time: float | None = None
        self._debounce_delay: float = self.config.get("monitoring.debounce_delay_seconds", 30.0)

        # Timer state
        self._last_check_time: float | None = None
        check_interval_hours = self.config.get("monitoring.check_interval_hours", 4.0)
        self._check_interval_seconds: float = check_interval_hours * 3600

        # State persistence
        self._monitor_state: MonitorStateData = MonitorStateData()
        self._state_file: str = "monitor_state.json"
        self._auto_save_state: bool = True

        # Initialize watch path based on mode
        self._initialize_watch_path()

        self.logger.info(f"DriveMonitor initialized in {'test' if self.config.test_mode else 'production'} mode")
        self.logger.debug(f"Monitoring path: {self.watch_path}")
        self.logger.debug(f"Debounce delay: {self._debounce_delay}s")
        self.logger.debug(f"Check interval: {check_interval_hours}h ({self._check_interval_seconds}s)")

    def _initialize_watch_path(self) -> None:
        """Initialize the path to watch based on configuration."""
        # Get source path from config (works for both test and production modes)
        source_path = self.config.get("backup.source_path")
        self._watch_path = Path(source_path) if source_path else None

        if self._watch_path:
            self.logger.debug(f"Watch path set to: {self._watch_path}")
        else:
            self.logger.warning("No watch path configured")

    @property
    def watch_path(self) -> Path | None:
        """Get the path being monitored."""
        return self._watch_path

    @property
    def is_test_mode(self) -> bool:
        """Check if monitor is running in test mode."""
        return self.config.test_mode

    def is_drive_mounted(self) -> bool:
        """
        Check if the monitored drive/directory is mounted and accessible.

        In test mode, checks if the test directory exists.
        In production mode, checks if the source drive is mounted.

        Returns:
            bool: True if the path exists and is accessible, False otherwise
        """
        if self.watch_path is None:
            self.logger.debug("No watch path configured, cannot check mount status")
            return False

        try:
            # Check if path exists and is a directory
            is_mounted = self.watch_path.exists() and self.watch_path.is_dir()

            if is_mounted:
                self.logger.debug(f"Drive mounted: {self.watch_path}")
            else:
                self.logger.debug(f"Drive not mounted: {self.watch_path}")

            return is_mounted

        except PermissionError:
            self.logger.warning(f"Permission denied accessing path: {self.watch_path}")
            return False
        except OSError as e:
            self.logger.warning(f"Error checking mount status for {self.watch_path}: {e}")
            return False

    def start(self) -> None:
        """
        Start monitoring for changes.

        Transitions the monitor from IDLE to WATCHING state.
        Takes an initial snapshot of files for change detection.
        """
        if self.state != MonitorState.IDLE:
            self.logger.warning(f"Cannot start monitor from {self.state.value} state")
            return

        self.logger.info("Starting drive monitor")
        self.state = MonitorState.WATCHING
        self._record_event(MonitorEvent.MONITOR_STARTED, str(self.watch_path))

        # Take initial snapshot of files
        self._update_snapshot()

    def stop(self) -> None:
        """
        Stop monitoring for changes.

        Transitions the monitor to STOPPED state.
        """
        self.logger.info("Stopping drive monitor")
        self.state = MonitorState.STOPPED
        self._record_event(MonitorEvent.MONITOR_STOPPED, str(self.watch_path))

    def get_status(self) -> dict[str, Any]:
        """
        Get current monitor status.

        Returns:
            dict: Status information including:
                - state: Current monitor state
                - watch_path: Path being monitored
                - test_mode: Whether in test mode
                - event_count: Number of events recorded
                - drive_mounted: Whether the drive is currently mounted
                - files_tracked: Number of files in snapshot
                - changes_pending: Number of changes detected
                - debouncing: Whether currently in debounce window
                - time_since_last_change: Seconds since last change (None if no changes)
                - time_since_last_check: Seconds since last check (None if never checked)
                - should_check_now: Whether check interval has elapsed
                - check_interval_seconds: Configured check interval
                - persistent_state: Persistent state data (total_checks, total_changes, etc.)
        """
        status: dict[str, Any] = {
            "state": self.state.value,
            "watch_path": str(self.watch_path) if self.watch_path else None,
            "test_mode": self.is_test_mode,
            "event_count": len(self._event_history),
            "drive_mounted": self.is_drive_mounted(),
            "files_tracked": len(self._file_snapshot),
            "changes_pending": len(self._changes_detected),
            "debouncing": self.is_debouncing(),
            "time_since_last_change": self.get_time_since_last_change(),
            "time_since_last_check": self.get_time_since_last_check(),
            "should_check_now": self.should_check(),
            "check_interval_seconds": self._check_interval_seconds,
        }

        # Add persistent state information
        status["persistent_state"] = {
            "total_checks": self._monitor_state.total_checks,
            "total_changes_detected": self._monitor_state.total_changes_detected,
            "last_check_time": (
                self._monitor_state.last_check_time.isoformat() if self._monitor_state.last_check_time else None
            ),
            "last_change_time": (
                self._monitor_state.last_change_time.isoformat() if self._monitor_state.last_change_time else None
            ),
            "change_history_count": len(self._monitor_state.change_history),
        }

        return status

    def get_detailed_status(self) -> dict[str, Any]:
        """
        Get detailed monitor status including change history.

        Returns:
            dict: Comprehensive status information including:
                - All fields from get_status()
                - pending_changes: List of pending change details
                - recent_history: Recent change events from persistent state
        """
        status = self.get_status()

        # Add detailed pending changes
        status["pending_changes"] = [
            {"file": file_path, "event": event.value} for file_path, event in self._changes_detected
        ]

        # Add recent change history (last 10 events)
        status["recent_history"] = self._monitor_state.change_history[-10:]

        return status

    def get_pending_changes(self) -> list[dict]:
        """
        Get list of pending changes with details.

        Returns:
            list[dict]: List of pending changes with file path and event type
        """
        return [{"file": file_path, "event": event.value} for file_path, event in self._changes_detected]

    def format_status(self) -> str:
        """
        Format monitor status as human-readable string.

        Returns:
            str: Formatted status report
        """
        status = self.get_status()
        persistent = status["persistent_state"]

        lines = [
            "=== Drive Monitor Status ===",
            f"State: {status['state']}",
            f"Watch Path: {status['watch_path']}",
            f"Mode: {'Test' if status['test_mode'] else 'Production'}",
            "",
            "=== Current Session ===",
            f"Drive Mounted: {status['drive_mounted']}",
            f"Files Tracked: {status['files_tracked']}",
            f"Pending Changes: {status['changes_pending']}",
            f"Event Count: {status['event_count']}",
            "",
            "=== Timing ===",
            f"Debouncing: {status['debouncing']}",
        ]

        if status["time_since_last_change"] is not None:
            lines.append(f"Time Since Last Change: {status['time_since_last_change']:.1f}s")
        else:
            lines.append("Time Since Last Change: Never")

        if status["time_since_last_check"] is not None:
            lines.append(f"Time Since Last Check: {status['time_since_last_check']:.1f}s")
        else:
            lines.append("Time Since Last Check: Never")

        lines.extend(
            [
                f"Should Check Now: {status['should_check_now']}",
                f"Check Interval: {status['check_interval_seconds']:.0f}s",
                "",
                "=== Persistent State ===",
                f"Total Checks: {persistent['total_checks']}",
                f"Total Changes Detected: {persistent['total_changes_detected']}",
                f"Last Check: {persistent['last_check_time'] or 'Never'}",
                f"Last Change: {persistent['last_change_time'] or 'Never'}",
                f"History Events: {persistent['change_history_count']}",
            ]
        )

        return "\n".join(lines)

    def reset_changes(self) -> None:
        """
        Reset change tracking after backup.

        Clears the list of pending changes and resets the last change time.
        This should be called after a successful backup to prepare for
        tracking the next batch of changes.

        Note: Does not affect persistent state or file snapshot.
        """
        changes_count = len(self._changes_detected)
        self._changes_detected = []
        self._last_change_time = None

        if changes_count > 0:
            self.logger.info(f"Reset {changes_count} pending changes after backup")
            self._record_event(MonitorEvent.CHANGES_RESET, f"{changes_count} changes cleared")
        else:
            self.logger.debug("Reset called with no pending changes")

    def clear_all_state(self) -> None:
        """
        Clear all monitoring state (for testing or reset scenarios).

        This is a more aggressive reset that clears:
        - Pending changes
        - File snapshot
        - Change times
        - Event history

        Does not affect persistent state on disk.
        Use with caution - typically only needed for testing or complete resets.
        """
        self._changes_detected = []
        self._file_snapshot = {}
        self._last_change_time = None
        self._last_check_time = None
        self._event_history = []

        self.logger.warning("Cleared all monitoring state (snapshot, changes, history)")
        self._record_event(MonitorEvent.STATE_CLEARED, "All state cleared")

    def _record_event(self, event: MonitorEvent, details: str = "") -> None:
        """
        Record a monitoring event.

        Args:
            event: The type of event that occurred
            details: Additional details about the event
        """
        self._event_history.append((event, details))
        self.logger.debug(f"Recorded event: {event.value} - {details}")

    def get_event_history(self) -> list[tuple[MonitorEvent, str]]:
        """
        Get the history of monitoring events.

        Returns:
            list: List of (event, details) tuples
        """
        return self._event_history.copy()

    def clear_event_history(self) -> None:
        """Clear the event history."""
        self._event_history.clear()
        self.logger.debug("Event history cleared")

    def _scan_directory(self) -> dict[str, float]:
        """
        Scan the watch directory and return a snapshot of files with their modification times.

        Returns:
            dict: Mapping of file paths (relative to watch_path) to modification times
        """
        snapshot: dict[str, float] = {}

        if not self.watch_path or not self.is_drive_mounted():
            return snapshot

        try:
            # Recursively scan all files in the directory
            for file_path in self.watch_path.rglob("*"):
                if file_path.is_file():
                    try:
                        # Get relative path and modification time
                        rel_path = str(file_path.relative_to(self.watch_path))
                        mtime = file_path.stat().st_mtime
                        snapshot[rel_path] = mtime
                    except (OSError, ValueError) as e:
                        self.logger.warning(f"Error scanning file {file_path}: {e}")

        except PermissionError as e:
            self.logger.warning(f"Permission denied scanning directory {self.watch_path}: {e}")
        except OSError as e:
            self.logger.warning(f"Error scanning directory {self.watch_path}: {e}")

        return snapshot

    def _update_snapshot(self) -> None:
        """Update the file snapshot to current state."""
        self._file_snapshot = self._scan_directory()
        self.logger.debug(f"Updated snapshot with {len(self._file_snapshot)} files")

    def check_for_changes(self) -> bool:
        """
        Check for file changes since last snapshot.

        Compares current directory state with the stored snapshot to detect:
        - New files (FILE_ADDED)
        - Modified files (FILE_MODIFIED)
        - Deleted files (FILE_DELETED)

        Updates the last check time for timer tracking.

        Returns:
            bool: True if changes were detected, False otherwise
        """
        # Update check time
        self._last_check_time = time.time()

        if not self.is_drive_mounted():
            self.logger.debug("Drive not mounted, skipping change detection")
            return False

        # Get current state
        current_snapshot = self._scan_directory()

        # Clear previous changes
        self._changes_detected.clear()

        # Detect new and modified files
        for file_path, mtime in current_snapshot.items():
            if file_path not in self._file_snapshot:
                # New file
                self._changes_detected.append((file_path, MonitorEvent.FILE_ADDED))
                self._record_event(MonitorEvent.FILE_ADDED, file_path)
                self.logger.debug(f"Detected new file: {file_path}")
            elif self._file_snapshot[file_path] != mtime:
                # Modified file
                self._changes_detected.append((file_path, MonitorEvent.FILE_MODIFIED))
                self._record_event(MonitorEvent.FILE_MODIFIED, file_path)
                self.logger.debug(f"Detected modified file: {file_path}")

        # Detect deleted files
        for file_path in self._file_snapshot:
            if file_path not in current_snapshot:
                self._changes_detected.append((file_path, MonitorEvent.FILE_DELETED))
                self._record_event(MonitorEvent.FILE_DELETED, file_path)
                self.logger.debug(f"Detected deleted file: {file_path}")

        # Update snapshot
        self._file_snapshot = current_snapshot

        # Log summary
        if self._changes_detected:
            # Update last change time for debouncing
            self._last_change_time = time.time()
            self.logger.info(f"Detected {len(self._changes_detected)} file changes")
            self._record_event(MonitorEvent.CHANGES_DETECTED, f"{len(self._changes_detected)} changes")

            # Update persistent state
            self._update_state_from_check(len(self._changes_detected))
            return True
        else:
            self.logger.debug("No changes detected")
            self._record_event(MonitorEvent.NO_CHANGES, "")

            # Update persistent state (no changes)
            self._update_state_from_check(0)
            return False

    def get_changes(self) -> list[tuple[str, MonitorEvent]]:
        """
        Get the list of detected changes since last check.

        Returns:
            list: List of (file_path, event_type) tuples
        """
        return self._changes_detected.copy()

    def clear_changes(self) -> None:
        """Clear the list of detected changes."""
        self._changes_detected.clear()
        self.logger.debug("Cleared detected changes")

    def is_debouncing(self) -> bool:
        """
        Check if monitor is currently in debounce window.

        Returns True if changes were detected and we're still within the
        debounce delay period (waiting for activity to settle).

        Returns:
            bool: True if in debounce window, False otherwise
        """
        if self._last_change_time is None:
            return False

        elapsed = time.time() - self._last_change_time
        return elapsed < self._debounce_delay

    def get_time_since_last_change(self) -> float | None:
        """
        Get the time elapsed since the last change was detected.

        Returns:
            float | None: Seconds since last change, or None if no changes detected
        """
        if self._last_change_time is None:
            return None

        return time.time() - self._last_change_time

    def should_check(self) -> bool:
        """
        Determine if it's time to check for changes based on the configured interval.

        Returns True if:
        - Never checked before (initial check)
        - Check interval has elapsed since last check

        This provides a passive timer mechanism - the caller should query this
        method to determine if a check is needed.

        Returns:
            bool: True if check interval has elapsed or never checked
        """
        if self._last_check_time is None:
            # Never checked before - should check immediately
            return True

        elapsed = time.time() - self._last_check_time
        return elapsed >= self._check_interval_seconds

    def get_time_since_last_check(self) -> float | None:
        """
        Get the time elapsed since the last check was performed.

        Returns:
            float | None: Seconds since last check, or None if never checked
        """
        if self._last_check_time is None:
            return None

        return time.time() - self._last_check_time

    def _get_file_size(self, relative_path: str) -> int:
        """
        Get the size of a file in bytes.

        Args:
            relative_path: Path relative to watch_path

        Returns:
            int: File size in bytes, or 0 if file cannot be accessed
        """
        if not self.watch_path:
            return 0

        try:
            full_path = self.watch_path / relative_path
            return full_path.stat().st_size
        except (OSError, FileNotFoundError) as e:
            self.logger.debug(f"Could not get size for {relative_path}: {e}")
            return 0

    def get_change_summary(self) -> ChangeSummary | None:
        """
        Get a summary of detected changes with statistics.

        Provides aggregated information about changes including:
        - Counts by change type (added/modified/deleted)
        - Total size of changed files
        - Grouping by directory

        Returns:
            ChangeSummary | None: Summary object with statistics, or None if no changes
        """
        if not self._changes_detected:
            return None

        summary = ChangeSummary()
        summary.total_files = len(self._changes_detected)

        # Track by directory
        for file_path, event_type in self._changes_detected:
            # Count by event type
            if event_type == MonitorEvent.FILE_ADDED:
                summary.added_count += 1
                file_size = self._get_file_size(file_path)
                summary.total_size += file_size
            elif event_type == MonitorEvent.FILE_MODIFIED:
                summary.modified_count += 1
                file_size = self._get_file_size(file_path)
                summary.total_size += file_size
            elif event_type == MonitorEvent.FILE_DELETED:
                summary.deleted_count += 1
                # Deleted files don't contribute to size

            # Group by directory
            dir_path = str(Path(file_path).parent)
            if dir_path == ".":
                dir_path = "/"  # Root of watch directory

            # Update directory counts
            summary.by_directory[dir_path] = summary.by_directory.get(dir_path, 0) + 1

            # Update directory sizes (only for added/modified files)
            if event_type in (MonitorEvent.FILE_ADDED, MonitorEvent.FILE_MODIFIED):
                file_size = self._get_file_size(file_path)
                summary.by_directory_size[dir_path] = summary.by_directory_size.get(dir_path, 0) + file_size

        self.logger.debug(
            f"Change summary: {summary.total_files} files, "
            f"{summary.added_count} added, "
            f"{summary.modified_count} modified, "
            f"{summary.deleted_count} deleted, "
            f"{summary.get_formatted_size()}"
        )

        return summary

    def load_state(self) -> bool:
        """
        Load monitor state from disk.

        Attempts to load previously saved state from the state file.
        If the file doesn't exist or is invalid, starts with fresh state.

        Returns:
            bool: True if state was loaded successfully, False otherwise
        """
        try:
            data, error = load_json_state(self._state_file, test_mode=self.config.test_mode)
            if data:
                self._monitor_state = MonitorStateData.from_dict(data)
                self.logger.info(f"Loaded monitor state: {self._monitor_state.total_checks} checks recorded")
                return True
            else:
                self.logger.debug(f"No previous state found: {error}")
                return False
        except Exception as e:
            self.logger.warning(f"Failed to load monitor state: {e}")
            return False

    def save_state(self) -> bool:
        """
        Save monitor state to disk.

        Persists current monitoring state including check times, change history,
        and statistics for continuity across restarts.

        Returns:
            bool: True if state was saved successfully, False otherwise
        """
        try:
            # Update state with current watch path
            if self.watch_path:
                self._monitor_state.watch_path = str(self.watch_path)

            # Save to disk
            save_json_state(
                self._monitor_state.to_dict(),
                self._state_file,
                test_mode=self.config.test_mode,
            )
            self.logger.debug("Monitor state saved successfully")
            return True
        except Exception as e:
            self.logger.error(f"Failed to save monitor state: {e}")
            return False

    def _update_state_from_check(self, changes_detected: int) -> None:
        """
        Update persistent state after a check.

        Args:
            changes_detected: Number of changes detected in the check
        """
        # Update check time
        check_time = datetime.now()
        self._monitor_state.update_check(check_time)

        # Update changes if any detected
        if changes_detected > 0:
            self._monitor_state.update_changes(changes_detected, check_time)

            # Add change events to history
            for file_path, event_type in self._changes_detected[:10]:  # Limit to first 10
                self._monitor_state.add_change_event(event_type.value, file_path, check_time)

        # Auto-save if enabled
        if self._auto_save_state:
            self.save_state()
