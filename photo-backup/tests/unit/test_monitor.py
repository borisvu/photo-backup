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
        assert "drive_mounted" in status

        assert status["state"] == "idle"
        assert status["test_mode"] is True
        assert status["event_count"] == 0
        # drive_mounted depends on whether test directory exists
        assert isinstance(status["drive_mounted"], bool)

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


class TestDriveDetection:
    """Test drive detection functionality."""

    def test_drive_mounted_in_test_mode(self, tmp_path):
        """Test that drive detection works in test mode with existing directory."""
        # Create a test directory
        test_dir = tmp_path / "test-photos"
        test_dir.mkdir()

        # Create config pointing to this directory
        config = Config(test_mode=True)
        config.load_config()  # Load config to initialize _config
        # Override the source path to point to our test directory
        config._config["backup"]["source_path"] = str(test_dir)

        monitor = DriveMonitor(config=config)

        # Drive should be mounted (directory exists)
        assert monitor.is_drive_mounted() is True

    def test_drive_not_mounted_nonexistent_path(self):
        """Test drive detection with non-existent path."""
        config = Config(test_mode=True)
        config.load_config()  # Load config to initialize _config
        # Override to point to non-existent path
        config._config["backup"]["source_path"] = "/nonexistent/path/to/photos"

        monitor = DriveMonitor(config=config)

        # Drive should not be mounted
        assert monitor.is_drive_mounted() is False

    def test_drive_mounted_with_file_not_directory(self, tmp_path):
        """Test drive detection when path is a file, not a directory."""
        # Create a file instead of directory
        test_file = tmp_path / "test-file.txt"
        test_file.write_text("test")

        config = Config(test_mode=True)
        config.load_config()  # Load config to initialize _config
        config._config["backup"]["source_path"] = str(test_file)

        monitor = DriveMonitor(config=config)

        # Should return False because it's not a directory
        assert monitor.is_drive_mounted() is False

    def test_drive_mounted_with_none_path(self):
        """Test drive detection when watch path is None."""
        config = Config(test_mode=True)
        config.load_config()  # Load config to initialize _config
        config._config["backup"]["source_path"] = None

        monitor = DriveMonitor(config=config)

        # Should handle None gracefully
        assert monitor.watch_path is None
        assert monitor.is_drive_mounted() is False

    def test_status_includes_drive_mounted(self, tmp_path):
        """Test that status includes drive_mounted information."""
        # Create test directory
        test_dir = tmp_path / "test-photos"
        test_dir.mkdir()

        config = Config(test_mode=True)
        config.load_config()  # Load config to initialize _config
        config._config["backup"]["source_path"] = str(test_dir)

        monitor = DriveMonitor(config=config)
        status = monitor.get_status()

        assert "drive_mounted" in status
        assert status["drive_mounted"] is True

    def test_status_drive_not_mounted(self):
        """Test status when drive is not mounted."""
        config = Config(test_mode=True)
        config.load_config()  # Load config to initialize _config
        config._config["backup"]["source_path"] = "/nonexistent/path"

        monitor = DriveMonitor(config=config)
        status = monitor.get_status()

        assert "drive_mounted" in status
        assert status["drive_mounted"] is False

    def test_drive_detection_state_changes(self, tmp_path):
        """Test drive detection across directory creation and deletion."""
        test_dir = tmp_path / "test-photos"

        config = Config(test_mode=True)
        config.load_config()  # Load config to initialize _config
        config._config["backup"]["source_path"] = str(test_dir)

        monitor = DriveMonitor(config=config)

        # Initially not mounted
        assert monitor.is_drive_mounted() is False

        # Create directory - now mounted
        test_dir.mkdir()
        assert monitor.is_drive_mounted() is True

        # Remove directory - no longer mounted
        test_dir.rmdir()
        assert monitor.is_drive_mounted() is False


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
