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
        """
        if self.state != MonitorState.IDLE:
            self.logger.warning(f"Cannot start monitor from {self.state.value} state")
            return

        self.logger.info("Starting drive monitor")
        self.state = MonitorState.WATCHING
        self._record_event(MonitorEvent.MONITOR_STARTED, str(self.watch_path))

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
        """
        return {
            "state": self.state.value,
            "watch_path": str(self.watch_path) if self.watch_path else None,
            "test_mode": self.is_test_mode,
            "event_count": len(self._event_history),
            "drive_mounted": self.is_drive_mounted(),
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
