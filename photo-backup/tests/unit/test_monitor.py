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
        assert "files_tracked" in status
        assert "changes_pending" in status

        assert status["state"] == "idle"
        assert status["test_mode"] is True
        assert status["event_count"] == 0
        assert status["files_tracked"] == 0
        assert status["changes_pending"] == 0
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


class TestPathWatching:
    """Test path watching and change detection functionality."""

    def test_detect_new_files(self, tmp_path):
        """Test detection of newly added files."""
        test_dir = tmp_path / "test-photos"
        test_dir.mkdir()

        config = Config(test_mode=True)
        config.load_config()
        config._config["backup"]["source_path"] = str(test_dir)

        monitor = DriveMonitor(config=config)
        monitor.start()

        # Initially no files
        assert monitor.check_for_changes() is False
        assert len(monitor.get_changes()) == 0

        # Add a new file
        test_file = test_dir / "photo1.jpg"
        test_file.write_text("test photo")

        # Check for changes
        assert monitor.check_for_changes() is True
        changes = monitor.get_changes()
        assert len(changes) == 1
        assert changes[0][0] == "photo1.jpg"
        assert changes[0][1] == MonitorEvent.FILE_ADDED

    def test_detect_modified_files(self, tmp_path):
        """Test detection of modified files."""
        test_dir = tmp_path / "test-photos"
        test_dir.mkdir()

        # Create initial file
        test_file = test_dir / "photo1.jpg"
        test_file.write_text("original content")

        config = Config(test_mode=True)
        config.load_config()
        config._config["backup"]["source_path"] = str(test_dir)

        monitor = DriveMonitor(config=config)
        monitor.start()

        # No changes initially (snapshot just taken)
        assert monitor.check_for_changes() is False

        # Modify the file
        import time

        time.sleep(0.01)  # Ensure mtime changes
        test_file.write_text("modified content")

        # Check for changes
        assert monitor.check_for_changes() is True
        changes = monitor.get_changes()
        assert len(changes) == 1
        assert changes[0][0] == "photo1.jpg"
        assert changes[0][1] == MonitorEvent.FILE_MODIFIED

    def test_detect_deleted_files(self, tmp_path):
        """Test detection of deleted files."""
        test_dir = tmp_path / "test-photos"
        test_dir.mkdir()

        # Create initial file
        test_file = test_dir / "photo1.jpg"
        test_file.write_text("test photo")

        config = Config(test_mode=True)
        config.load_config()
        config._config["backup"]["source_path"] = str(test_dir)

        monitor = DriveMonitor(config=config)
        monitor.start()

        # Delete the file
        test_file.unlink()

        # Check for changes
        assert monitor.check_for_changes() is True
        changes = monitor.get_changes()
        assert len(changes) == 1
        assert changes[0][0] == "photo1.jpg"
        assert changes[0][1] == MonitorEvent.FILE_DELETED

    def test_detect_multiple_changes(self, tmp_path):
        """Test detection of multiple file changes at once."""
        test_dir = tmp_path / "test-photos"
        test_dir.mkdir()

        # Create initial files
        (test_dir / "photo1.jpg").write_text("photo 1")
        (test_dir / "photo2.jpg").write_text("photo 2")

        config = Config(test_mode=True)
        config.load_config()
        config._config["backup"]["source_path"] = str(test_dir)

        monitor = DriveMonitor(config=config)
        monitor.start()

        # Add, modify, delete
        import time

        time.sleep(0.01)
        (test_dir / "photo3.jpg").write_text("photo 3")  # New
        (test_dir / "photo1.jpg").write_text("modified photo 1")  # Modified
        (test_dir / "photo2.jpg").unlink()  # Deleted

        # Check for changes
        assert monitor.check_for_changes() is True
        changes = monitor.get_changes()
        assert len(changes) == 3

        # Verify each type of change is detected
        event_types = {change[1] for change in changes}
        assert MonitorEvent.FILE_ADDED in event_types
        assert MonitorEvent.FILE_MODIFIED in event_types
        assert MonitorEvent.FILE_DELETED in event_types

    def test_detect_nested_directory_files(self, tmp_path):
        """Test detection of files in nested directories."""
        test_dir = tmp_path / "test-photos"
        test_dir.mkdir()
        subdir = test_dir / "2024" / "January"
        subdir.mkdir(parents=True)

        config = Config(test_mode=True)
        config.load_config()
        config._config["backup"]["source_path"] = str(test_dir)

        monitor = DriveMonitor(config=config)
        monitor.start()

        # Add file in nested directory
        nested_file = subdir / "photo1.jpg"
        nested_file.write_text("nested photo")

        # Check for changes
        assert monitor.check_for_changes() is True
        changes = monitor.get_changes()
        assert len(changes) == 1
        # Path should be relative to watch_path
        assert "2024" in changes[0][0]
        assert "January" in changes[0][0]
        assert "photo1.jpg" in changes[0][0]

    def test_snapshot_taken_on_start(self, tmp_path):
        """Test that snapshot is taken when monitor starts."""
        test_dir = tmp_path / "test-photos"
        test_dir.mkdir()

        # Create some initial files
        (test_dir / "photo1.jpg").write_text("photo 1")
        (test_dir / "photo2.jpg").write_text("photo 2")

        config = Config(test_mode=True)
        config.load_config()
        config._config["backup"]["source_path"] = str(test_dir)

        monitor = DriveMonitor(config=config)

        # Before start, snapshot is empty
        status = monitor.get_status()
        assert status["files_tracked"] == 0

        # Start monitoring
        monitor.start()

        # After start, snapshot should have files
        status = monitor.get_status()
        assert status["files_tracked"] == 2

    def test_status_includes_files_tracked(self, tmp_path):
        """Test that status includes files_tracked information."""
        test_dir = tmp_path / "test-photos"
        test_dir.mkdir()
        (test_dir / "photo1.jpg").write_text("photo 1")
        (test_dir / "photo2.jpg").write_text("photo 2")

        config = Config(test_mode=True)
        config.load_config()
        config._config["backup"]["source_path"] = str(test_dir)

        monitor = DriveMonitor(config=config)
        monitor.start()

        status = monitor.get_status()
        assert "files_tracked" in status
        assert status["files_tracked"] == 2

    def test_status_includes_changes_pending(self, tmp_path):
        """Test that status includes changes_pending information."""
        test_dir = tmp_path / "test-photos"
        test_dir.mkdir()

        config = Config(test_mode=True)
        config.load_config()
        config._config["backup"]["source_path"] = str(test_dir)

        monitor = DriveMonitor(config=config)
        monitor.start()

        # Add some files
        (test_dir / "photo1.jpg").write_text("photo 1")
        (test_dir / "photo2.jpg").write_text("photo 2")

        # Detect changes
        monitor.check_for_changes()

        status = monitor.get_status()
        assert "changes_pending" in status
        assert status["changes_pending"] == 2

    def test_clear_changes(self, tmp_path):
        """Test clearing detected changes."""
        test_dir = tmp_path / "test-photos"
        test_dir.mkdir()

        config = Config(test_mode=True)
        config.load_config()
        config._config["backup"]["source_path"] = str(test_dir)

        monitor = DriveMonitor(config=config)
        monitor.start()

        # Add files
        (test_dir / "photo1.jpg").write_text("photo 1")
        monitor.check_for_changes()

        assert len(monitor.get_changes()) == 1

        # Clear changes
        monitor.clear_changes()
        assert len(monitor.get_changes()) == 0

    def test_check_for_changes_when_drive_not_mounted(self):
        """Test that check_for_changes handles unmounted drive gracefully."""
        config = Config(test_mode=True)
        config.load_config()
        config._config["backup"]["source_path"] = "/nonexistent/path"

        monitor = DriveMonitor(config=config)
        monitor.start()

        # Should return False and not crash
        assert monitor.check_for_changes() is False

    def test_get_changes_returns_copy(self, tmp_path):
        """Test that get_changes returns a copy of the changes list."""
        test_dir = tmp_path / "test-photos"
        test_dir.mkdir()

        config = Config(test_mode=True)
        config.load_config()
        config._config["backup"]["source_path"] = str(test_dir)

        monitor = DriveMonitor(config=config)
        monitor.start()

        # Add file
        (test_dir / "photo1.jpg").write_text("photo 1")
        monitor.check_for_changes()

        changes1 = monitor.get_changes()
        changes2 = monitor.get_changes()

        # Should be equal but not the same object
        assert changes1 == changes2
        assert changes1 is not changes2

        # Modifying one shouldn't affect the other
        changes1.append(("test.jpg", MonitorEvent.FILE_ADDED))
        assert len(changes1) != len(changes2)


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


class TestDebouncing:
    """Tests for change debouncing functionality."""

    def test_no_debouncing_initially(self, tmp_path):
        """Test that monitor is not debouncing before any changes."""
        test_dir = tmp_path / "test-photos"
        test_dir.mkdir()

        config = Config(test_mode=True)
        config.load_config()
        config._config["backup"]["source_path"] = str(test_dir)

        monitor = DriveMonitor(config=config)

        # No changes yet, should not be debouncing
        assert not monitor.is_debouncing()
        assert monitor.get_time_since_last_change() is None

        # Status should reflect no debouncing
        status = monitor.get_status()
        assert status["debouncing"] is False
        assert status["time_since_last_change"] is None

    def test_debouncing_after_changes(self, tmp_path):
        """Test that monitor enters debounce mode after detecting changes."""
        test_dir = tmp_path / "test-photos"
        test_dir.mkdir()

        config = Config(test_mode=True)
        config.load_config()
        config._config["backup"]["source_path"] = str(test_dir)

        monitor = DriveMonitor(config=config)
        monitor.start()

        # Add a file
        test_file = test_dir / "photo.jpg"
        test_file.write_text("test photo")

        # Check for changes
        assert monitor.check_for_changes() is True

        # Should be debouncing immediately after changes
        assert monitor.is_debouncing() is True
        time_since = monitor.get_time_since_last_change()
        assert time_since is not None
        assert time_since < 0.1  # Very recent

        # Status should reflect debouncing
        status = monitor.get_status()
        assert status["debouncing"] is True
        assert status["time_since_last_change"] is not None

    def test_debounce_window_expires(self, tmp_path):
        """Test that debounce window expires after configured delay."""
        import time

        test_dir = tmp_path / "test-photos"
        test_dir.mkdir()

        config = Config(test_mode=True)
        config.load_config()
        config._config["backup"]["source_path"] = str(test_dir)

        monitor = DriveMonitor(config=config)
        monitor.start()

        # Add a file to trigger changes
        test_file = test_dir / "photo.jpg"
        test_file.write_text("test photo")
        assert monitor.check_for_changes() is True

        # Should be debouncing immediately
        assert monitor.is_debouncing() is True

        # Wait for debounce delay to expire (test mode is 0.5s)
        time.sleep(0.6)

        # Should no longer be debouncing
        assert monitor.is_debouncing() is False
        time_since = monitor.get_time_since_last_change()
        assert time_since is not None
        assert time_since >= 0.6  # At least 0.6 seconds have passed

    def test_rapid_changes_stay_in_debounce(self, tmp_path):
        """Test that rapid changes keep monitor in debounce window."""
        import time

        test_dir = tmp_path / "test-photos"
        test_dir.mkdir()

        config = Config(test_mode=True)
        config.load_config()
        config._config["backup"]["source_path"] = str(test_dir)

        monitor = DriveMonitor(config=config)
        monitor.start()

        # Add first file
        file1 = test_dir / "photo1.jpg"
        file1.write_text("photo 1")
        assert monitor.check_for_changes() is True
        assert monitor.is_debouncing() is True

        # Wait a bit but not enough for debounce to expire
        time.sleep(0.2)

        # Add second file - should reset debounce timer
        file2 = test_dir / "photo2.jpg"
        file2.write_text("photo 2")
        assert monitor.check_for_changes() is True

        # Should still be debouncing with fresh timer
        assert monitor.is_debouncing() is True
        time_since = monitor.get_time_since_last_change()
        assert time_since is not None
        assert time_since < 0.1  # Timer should be reset

        # Wait another bit
        time.sleep(0.2)

        # Add third file - should reset debounce timer again
        file3 = test_dir / "photo3.jpg"
        file3.write_text("photo 3")
        assert monitor.check_for_changes() is True

        # Should still be debouncing with fresh timer
        assert monitor.is_debouncing() is True
        time_since = monitor.get_time_since_last_change()
        assert time_since is not None
        assert time_since < 0.1  # Timer should be reset again

    def test_debounce_delay_from_config(self):
        """Test that debounce delay is loaded from config."""
        # Create config with custom debounce delay
        config = Config(test_mode=True)
        config.load_config()
        custom_delay = config.get("monitoring.debounce_delay_seconds")

        # Should be 0.5 in test mode
        assert custom_delay == 0.5

        # Create monitor and verify it uses the config value
        monitor = DriveMonitor(config=config)
        assert monitor._debounce_delay == 0.5

    def test_no_debounce_when_no_changes(self, tmp_path):
        """Test that monitor doesn't enter debounce when no changes detected."""
        test_dir = tmp_path / "test-photos"
        test_dir.mkdir()

        config = Config(test_mode=True)
        config.load_config()
        config._config["backup"]["source_path"] = str(test_dir)

        monitor = DriveMonitor(config=config)
        monitor.start()

        # Check for changes when there are none
        assert monitor.check_for_changes() is False

        # Should not be debouncing
        assert monitor.is_debouncing() is False
        assert monitor.get_time_since_last_change() is None

        # Status should reflect no debouncing
        status = monitor.get_status()
        assert status["debouncing"] is False
        assert status["time_since_last_change"] is None

    def test_debounce_persists_across_checks(self, tmp_path):
        """Test that debounce state persists across multiple check calls."""
        import time

        test_dir = tmp_path / "test-photos"
        test_dir.mkdir()

        config = Config(test_mode=True)
        config.load_config()
        config._config["backup"]["source_path"] = str(test_dir)

        monitor = DriveMonitor(config=config)
        monitor.start()

        # Add a file to trigger changes
        test_file = test_dir / "photo.jpg"
        test_file.write_text("test photo")
        assert monitor.check_for_changes() is True
        assert monitor.is_debouncing() is True

        # Check again without changes - should still be debouncing
        time.sleep(0.1)
        assert monitor.check_for_changes() is False
        assert monitor.is_debouncing() is True  # Still within 0.5s window

        # Wait for debounce to expire
        time.sleep(0.5)
        assert monitor.is_debouncing() is False
