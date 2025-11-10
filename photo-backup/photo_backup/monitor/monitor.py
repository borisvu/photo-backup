"""
Drive monitoring for photo backup system.

This module provides the DriveMonitor class for detecting changes
in the photo directory and triggering backups accordingly.
"""

from pathlib import Path

from ..config import Config
from ..logger import get_logger
from .events import MonitorEvent, MonitorState


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

        # Initialize watch path based on mode
        self._initialize_watch_path()

        self.logger.info(f"DriveMonitor initialized in {'test' if self.config.test_mode else 'production'} mode")
        self.logger.debug(f"Monitoring path: {self.watch_path}")

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

    def get_status(self) -> dict:
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
        """
        return {
            "state": self.state.value,
            "watch_path": str(self.watch_path) if self.watch_path else None,
            "test_mode": self.is_test_mode,
            "event_count": len(self._event_history),
            "drive_mounted": self.is_drive_mounted(),
            "files_tracked": len(self._file_snapshot),
            "changes_pending": len(self._changes_detected),
        }

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

        Returns:
            bool: True if changes were detected, False otherwise
        """
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
            self.logger.info(f"Detected {len(self._changes_detected)} file changes")
            self._record_event(MonitorEvent.CHANGES_DETECTED, f"{len(self._changes_detected)} changes")
            return True
        else:
            self.logger.debug("No changes detected")
            self._record_event(MonitorEvent.NO_CHANGES, "")
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
