"""
Unit tests for drive monitor module.

Tests the DriveMonitor class and monitoring events.
"""

from pathlib import Path

from photo_backup.config import Config
from photo_backup.monitor import DriveMonitor, MonitorEvent, MonitorState


class TestMonitorEvents:
    """Test monitoring event definitions."""

    def test_monitor_event_enum(self):
        """Test that MonitorEvent enum is properly defined."""
        # File system events
        assert MonitorEvent.FILE_ADDED.value == "file_added"
        assert MonitorEvent.FILE_MODIFIED.value == "file_modified"
        assert MonitorEvent.FILE_DELETED.value == "file_deleted"

        # Directory events
        assert MonitorEvent.DIRECTORY_ADDED.value == "directory_added"
        assert MonitorEvent.DIRECTORY_DELETED.value == "directory_deleted"

        # Drive events
        assert MonitorEvent.DRIVE_MOUNTED.value == "drive_mounted"
        assert MonitorEvent.DRIVE_UNMOUNTED.value == "drive_unmounted"

        # Timer events
        assert MonitorEvent.TIMER_ELAPSED.value == "timer_elapsed"
        assert MonitorEvent.CHECK_INTERVAL.value == "check_interval"

        # State events
        assert MonitorEvent.MONITOR_STARTED.value == "monitor_started"
        assert MonitorEvent.MONITOR_STOPPED.value == "monitor_stopped"
        assert MonitorEvent.CHANGES_DETECTED.value == "changes_detected"
        assert MonitorEvent.NO_CHANGES.value == "no_changes"

    def test_monitor_state_enum(self):
        """Test that MonitorState enum is properly defined."""
        assert MonitorState.IDLE.value == "idle"
        assert MonitorState.WATCHING.value == "watching"
        assert MonitorState.PROCESSING.value == "processing"
        assert MonitorState.STOPPED.value == "stopped"
        assert MonitorState.ERROR.value == "error"


class TestDriveMonitor:
    """Test DriveMonitor class."""

    def test_instantiate_with_defaults(self):
        """Test that monitor can be instantiated with default config."""
        monitor = DriveMonitor()

        assert monitor is not None
        assert monitor.config is not None
        assert monitor.state == MonitorState.IDLE
        assert isinstance(monitor.watch_path, Path) or monitor.watch_path is None

    def test_instantiate_with_test_mode(self):
        """Test monitor instantiation in test mode."""
        config = Config(test_mode=True)
        monitor = DriveMonitor(config=config)

        assert monitor.is_test_mode is True
        assert monitor.config.test_mode is True
        assert monitor.state == MonitorState.IDLE

    def test_instantiate_with_production_mode(self):
        """Test monitor instantiation in production mode."""
        config = Config(test_mode=False)
        monitor = DriveMonitor(config=config)

        assert monitor.is_test_mode is False
        assert monitor.config.test_mode is False
        assert monitor.state == MonitorState.IDLE

    def test_watch_path_in_test_mode(self):
        """Test that watch path is set correctly in test mode."""
        config = Config(test_mode=True)
        monitor = DriveMonitor(config=config)

        # Should have a watch path from test config
        assert monitor.watch_path is not None
        assert isinstance(monitor.watch_path, Path)

        # Should be the test source path
        test_source = config.get("backup.source_path")
        assert str(monitor.watch_path) == test_source

    def test_get_status(self):
        """Test getting monitor status."""
        config = Config(test_mode=True)
        monitor = DriveMonitor(config=config)

        status = monitor.get_status()

        assert "state" in status
        assert "watch_path" in status
        assert "test_mode" in status
        assert "event_count" in status

        assert status["state"] == "idle"
        assert status["test_mode"] is True
        assert status["event_count"] == 0

    def test_start_monitor(self):
        """Test starting the monitor."""
        monitor = DriveMonitor(config=Config(test_mode=True))

        assert monitor.state == MonitorState.IDLE

        monitor.start()

        assert monitor.state == MonitorState.WATCHING

        # Check that start event was recorded
        history = monitor.get_event_history()
        assert len(history) == 1
        assert history[0][0] == MonitorEvent.MONITOR_STARTED

    def test_stop_monitor(self):
        """Test stopping the monitor."""
        monitor = DriveMonitor(config=Config(test_mode=True))
        monitor.start()

        assert monitor.state == MonitorState.WATCHING

        monitor.stop()

        assert monitor.state == MonitorState.STOPPED

        # Check that stop event was recorded
        history = monitor.get_event_history()
        assert len(history) == 2
        assert history[0][0] == MonitorEvent.MONITOR_STARTED
        assert history[1][0] == MonitorEvent.MONITOR_STOPPED

    def test_start_from_non_idle_state(self):
        """Test that starting from non-idle state is handled."""
        monitor = DriveMonitor(config=Config(test_mode=True))
        monitor.start()

        # Already in WATCHING state
        monitor.start()

        # Should still be in WATCHING state, not started again
        assert monitor.state == MonitorState.WATCHING

        # Should only have one start event
        history = monitor.get_event_history()
        assert len(history) == 1

    def test_event_history(self):
        """Test event history tracking."""
        monitor = DriveMonitor(config=Config(test_mode=True))

        # Initially empty
        history = monitor.get_event_history()
        assert len(history) == 0

        # Start and stop
        monitor.start()
        monitor.stop()

        # Should have two events
        history = monitor.get_event_history()
        assert len(history) == 2

        # Clear history
        monitor.clear_event_history()
        history = monitor.get_event_history()
        assert len(history) == 0

    def test_event_history_is_copy(self):
        """Test that get_event_history returns a copy."""
        monitor = DriveMonitor(config=Config(test_mode=True))
        monitor.start()

        history1 = monitor.get_event_history()
        history2 = monitor.get_event_history()

        # Should be equal but not the same object
        assert history1 == history2
        assert history1 is not history2

        # Modifying one shouldn't affect the other
        history1.append((MonitorEvent.FILE_ADDED, "test"))
        assert len(history1) != len(history2)


class TestDriveMonitorIntegration:
    """Integration tests for DriveMonitor."""

    def test_full_lifecycle(self):
        """Test complete monitor lifecycle."""
        config = Config(test_mode=True)
        monitor = DriveMonitor(config=config)

        # Initial state
        assert monitor.state == MonitorState.IDLE
        status = monitor.get_status()
        assert status["state"] == "idle"
        assert status["event_count"] == 0

        # Start monitoring
        monitor.start()
        assert monitor.state == MonitorState.WATCHING
        status = monitor.get_status()
        assert status["state"] == "watching"
        assert status["event_count"] == 1

        # Stop monitoring
        monitor.stop()
        assert monitor.state == MonitorState.STOPPED
        status = monitor.get_status()
        assert status["state"] == "stopped"
        assert status["event_count"] == 2

        # Verify event history
        history = monitor.get_event_history()
        assert len(history) == 2
        assert history[0][0] == MonitorEvent.MONITOR_STARTED
        assert history[1][0] == MonitorEvent.MONITOR_STOPPED

    def test_multiple_monitors_independent(self):
        """Test that multiple monitor instances are independent."""
        config1 = Config(test_mode=True)
        config2 = Config(test_mode=True)

        monitor1 = DriveMonitor(config=config1)
        monitor2 = DriveMonitor(config=config2)

        # Start only monitor1
        monitor1.start()

        assert monitor1.state == MonitorState.WATCHING
        assert monitor2.state == MonitorState.IDLE

        # Event histories should be independent
        assert len(monitor1.get_event_history()) == 1
        assert len(monitor2.get_event_history()) == 0
