"""
Unit tests for drive monitor module.

Tests the DriveMonitor class and monitoring events.
"""

from pathlib import Path

from photo_backup.config import Config
from photo_backup.monitor import ChangeSummary, DriveMonitor, MonitorEvent, MonitorState, MonitorStateData


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


class TestChangeSummary:
    """Tests for change summary functionality."""

    def test_summary_with_new_files(self, tmp_path):
        """Test summary generation with only new files."""
        test_dir = tmp_path / "test-photos"
        test_dir.mkdir()

        config = Config(test_mode=True)
        config.load_config()
        config._config["backup"]["source_path"] = str(test_dir)

        monitor = DriveMonitor(config=config)
        monitor.start()

        # Add files
        file1 = test_dir / "photo1.jpg"
        file1.write_text("photo 1 content")
        file2 = test_dir / "photo2.jpg"
        file2.write_text("photo 2 longer content")

        monitor.check_for_changes()

        # Get summary
        summary = monitor.get_change_summary()
        assert summary is not None
        assert summary.total_files == 2
        assert summary.added_count == 2
        assert summary.modified_count == 0
        assert summary.deleted_count == 0
        assert summary.total_size > 0
        assert "/" in summary.by_directory
        assert summary.by_directory["/"] == 2

    def test_summary_with_modified_files(self, tmp_path):
        """Test summary generation with modified files."""
        import time

        test_dir = tmp_path / "test-photos"
        test_dir.mkdir()

        # Create initial file
        test_file = test_dir / "photo.jpg"
        test_file.write_text("original")

        config = Config(test_mode=True)
        config.load_config()
        config._config["backup"]["source_path"] = str(test_dir)

        monitor = DriveMonitor(config=config)
        monitor.start()

        # Modify file
        time.sleep(0.01)
        test_file.write_text("modified content")

        monitor.check_for_changes()

        # Get summary
        summary = monitor.get_change_summary()
        assert summary is not None
        assert summary.total_files == 1
        assert summary.added_count == 0
        assert summary.modified_count == 1
        assert summary.deleted_count == 0
        assert summary.total_size > 0

    def test_summary_with_deleted_files(self, tmp_path):
        """Test summary generation with deleted files."""
        test_dir = tmp_path / "test-photos"
        test_dir.mkdir()

        # Create initial file
        test_file = test_dir / "photo.jpg"
        test_file.write_text("test photo")

        config = Config(test_mode=True)
        config.load_config()
        config._config["backup"]["source_path"] = str(test_dir)

        monitor = DriveMonitor(config=config)
        monitor.start()

        # Delete file
        test_file.unlink()

        monitor.check_for_changes()

        # Get summary
        summary = monitor.get_change_summary()
        assert summary is not None
        assert summary.total_files == 1
        assert summary.added_count == 0
        assert summary.modified_count == 0
        assert summary.deleted_count == 1
        assert summary.total_size == 0  # Deleted files don't contribute to size

    def test_summary_with_mixed_changes(self, tmp_path):
        """Test summary generation with mixed change types."""
        import time

        test_dir = tmp_path / "test-photos"
        test_dir.mkdir()

        # Create initial files
        existing_file = test_dir / "existing.jpg"
        existing_file.write_text("existing")
        to_delete = test_dir / "to_delete.jpg"
        to_delete.write_text("will be deleted")

        config = Config(test_mode=True)
        config.load_config()
        config._config["backup"]["source_path"] = str(test_dir)

        monitor = DriveMonitor(config=config)
        monitor.start()

        # Make mixed changes
        time.sleep(0.01)
        new_file = test_dir / "new.jpg"
        new_file.write_text("new content")
        existing_file.write_text("modified")
        to_delete.unlink()

        monitor.check_for_changes()

        # Get summary
        summary = monitor.get_change_summary()
        assert summary is not None
        assert summary.total_files == 3
        assert summary.added_count == 1
        assert summary.modified_count == 1
        assert summary.deleted_count == 1
        assert summary.total_size > 0  # From new and modified files

    def test_summary_directory_grouping(self, tmp_path):
        """Test that summary groups files by directory."""
        test_dir = tmp_path / "test-photos"
        test_dir.mkdir()

        # Create nested directory structure
        dir1 = test_dir / "subdir1"
        dir1.mkdir()
        dir2 = test_dir / "subdir2"
        dir2.mkdir()

        config = Config(test_mode=True)
        config.load_config()
        config._config["backup"]["source_path"] = str(test_dir)

        monitor = DriveMonitor(config=config)
        monitor.start()

        # Add files in different directories
        (test_dir / "root1.jpg").write_text("root 1")
        (test_dir / "root2.jpg").write_text("root 2")
        (dir1 / "sub1.jpg").write_text("sub 1")
        (dir1 / "sub2.jpg").write_text("sub 2")
        (dir2 / "sub3.jpg").write_text("sub 3")

        monitor.check_for_changes()

        # Get summary
        summary = monitor.get_change_summary()
        assert summary is not None
        assert summary.total_files == 5
        assert len(summary.by_directory) == 3
        assert summary.by_directory["/"] == 2
        assert summary.by_directory["subdir1"] == 2
        assert summary.by_directory["subdir2"] == 1

    def test_summary_size_calculations(self, tmp_path):
        """Test that summary calculates sizes correctly."""
        test_dir = tmp_path / "test-photos"
        test_dir.mkdir()

        config = Config(test_mode=True)
        config.load_config()
        config._config["backup"]["source_path"] = str(test_dir)

        monitor = DriveMonitor(config=config)
        monitor.start()

        # Add files with known sizes
        file1 = test_dir / "small.jpg"
        file1.write_text("x" * 100)  # 100 bytes
        file2 = test_dir / "large.jpg"
        file2.write_text("y" * 1000)  # 1000 bytes

        monitor.check_for_changes()

        # Get summary
        summary = monitor.get_change_summary()
        assert summary is not None
        assert summary.total_size == 1100
        assert summary.by_directory_size["/"] == 1100

    def test_summary_none_when_no_changes(self, tmp_path):
        """Test that summary returns None when no changes detected."""
        test_dir = tmp_path / "test-photos"
        test_dir.mkdir()

        config = Config(test_mode=True)
        config.load_config()
        config._config["backup"]["source_path"] = str(test_dir)

        monitor = DriveMonitor(config=config)
        monitor.start()

        # Check with no changes
        monitor.check_for_changes()

        # Get summary
        summary = monitor.get_change_summary()
        assert summary is None

    def test_summary_formatted_size(self):
        """Test formatted size output."""
        summary = ChangeSummary()

        # Test bytes
        summary.total_size = 500
        assert summary.get_formatted_size() == "500.0 B"

        # Test kilobytes
        summary.total_size = 2048
        assert summary.get_formatted_size() == "2.0 KB"

        # Test megabytes
        summary.total_size = 1048576 * 5
        assert summary.get_formatted_size() == "5.0 MB"

        # Test gigabytes
        summary.total_size = 1073741824 * 2
        assert summary.get_formatted_size() == "2.0 GB"

    def test_summary_handles_file_access_errors(self, tmp_path, monkeypatch):
        """Test that summary handles file access errors gracefully."""
        test_dir = tmp_path / "test-photos"
        test_dir.mkdir()

        config = Config(test_mode=True)
        config.load_config()
        config._config["backup"]["source_path"] = str(test_dir)

        monitor = DriveMonitor(config=config)
        monitor.start()

        # Add a file
        test_file = test_dir / "photo.jpg"
        test_file.write_text("test")

        monitor.check_for_changes()

        # Mock _get_file_size to simulate access error
        original_get_size = monitor._get_file_size

        def mock_get_size(path):
            if "photo.jpg" in path:
                return 0  # Simulate error
            return original_get_size(path)

        monkeypatch.setattr(monitor, "_get_file_size", mock_get_size)

        # Get summary - should handle error gracefully
        summary = monitor.get_change_summary()
        assert summary is not None
        assert summary.total_files == 1
        assert summary.total_size == 0  # Size is 0 due to error


class TestTimer:
    """Tests for periodic check timer functionality."""

    def test_should_check_initially(self, tmp_path):
        """Test that monitor should check immediately on first call."""
        test_dir = tmp_path / "test-photos"
        test_dir.mkdir()

        config = Config(test_mode=True)
        config.load_config()
        config._config["backup"]["source_path"] = str(test_dir)

        monitor = DriveMonitor(config=config)

        # Should check immediately before any checks performed
        assert monitor.should_check() is True
        assert monitor.get_time_since_last_check() is None

    def test_timer_interval_from_config(self):
        """Test that check interval is loaded from config."""
        config = Config(test_mode=True)
        config.load_config()
        check_interval_hours = config.get("monitoring.check_interval_hours")

        # Should be 0.1 hours (6 minutes) in test mode
        assert check_interval_hours == 0.1

        # Create monitor and verify it uses the config value
        monitor = DriveMonitor(config=config)
        assert monitor._check_interval_seconds == 0.1 * 3600  # 360 seconds

    def test_should_not_check_before_interval(self, tmp_path):
        """Test that monitor should not check before interval elapses."""
        test_dir = tmp_path / "test-photos"
        test_dir.mkdir()

        config = Config(test_mode=True)
        config.load_config()
        config._config["backup"]["source_path"] = str(test_dir)

        monitor = DriveMonitor(config=config)
        monitor.start()

        # Perform initial check
        monitor.check_for_changes()

        # Should not check immediately after
        assert monitor.should_check() is False
        time_since = monitor.get_time_since_last_check()
        assert time_since is not None
        assert time_since < 1.0  # Very recent

    def test_should_check_after_interval(self, tmp_path):
        """Test that monitor should check after interval elapses."""
        import time

        test_dir = tmp_path / "test-photos"
        test_dir.mkdir()

        config = Config(test_mode=True)
        config.load_config()
        config._config["backup"]["source_path"] = str(test_dir)
        # Set very short interval for testing
        config._config["monitoring"]["check_interval_hours"] = 0.0001  # ~0.36 seconds

        monitor = DriveMonitor(config=config)
        monitor.start()

        # Perform initial check
        monitor.check_for_changes()
        assert monitor.should_check() is False

        # Wait for interval to elapse
        time.sleep(0.5)

        # Should check now
        assert monitor.should_check() is True
        time_since = monitor.get_time_since_last_check()
        assert time_since is not None
        assert time_since >= 0.5

    def test_timer_resets_after_check(self, tmp_path):
        """Test that timer resets after each check."""
        import time

        test_dir = tmp_path / "test-photos"
        test_dir.mkdir()

        config = Config(test_mode=True)
        config.load_config()
        config._config["backup"]["source_path"] = str(test_dir)
        config._config["monitoring"]["check_interval_hours"] = 0.0001  # ~0.36 seconds

        monitor = DriveMonitor(config=config)
        monitor.start()

        # First check
        monitor.check_for_changes()
        assert monitor.should_check() is False

        # Wait and check again
        time.sleep(0.5)
        assert monitor.should_check() is True

        # Perform another check - timer should reset
        monitor.check_for_changes()
        assert monitor.should_check() is False
        time_since = monitor.get_time_since_last_check()
        assert time_since is not None
        assert time_since < 0.1  # Very recent after reset

    def test_get_time_since_last_check_accuracy(self, tmp_path):
        """Test that get_time_since_last_check returns accurate time."""
        import time

        test_dir = tmp_path / "test-photos"
        test_dir.mkdir()

        config = Config(test_mode=True)
        config.load_config()
        config._config["backup"]["source_path"] = str(test_dir)

        monitor = DriveMonitor(config=config)
        monitor.start()

        # Perform check
        monitor.check_for_changes()

        # Wait a bit
        time.sleep(0.2)

        # Check elapsed time
        time_since = monitor.get_time_since_last_check()
        assert time_since is not None
        assert 0.2 <= time_since < 0.3  # Should be around 0.2 seconds

    def test_status_includes_timer_info(self, tmp_path):
        """Test that status includes timer information."""
        test_dir = tmp_path / "test-photos"
        test_dir.mkdir()

        config = Config(test_mode=True)
        config.load_config()
        config._config["backup"]["source_path"] = str(test_dir)

        monitor = DriveMonitor(config=config)

        # Check status before any checks
        status = monitor.get_status()
        assert "time_since_last_check" in status
        assert "should_check_now" in status
        assert "check_interval_seconds" in status

        assert status["time_since_last_check"] is None
        assert status["should_check_now"] is True
        assert status["check_interval_seconds"] == 0.1 * 3600  # Test mode

        # Perform a check
        monitor.start()
        monitor.check_for_changes()

        # Check status after check
        status = monitor.get_status()
        assert status["time_since_last_check"] is not None
        assert status["should_check_now"] is False

    def test_timer_independent_of_changes(self, tmp_path):
        """Test that timer tracks checks regardless of whether changes exist."""
        import time

        test_dir = tmp_path / "test-photos"
        test_dir.mkdir()

        config = Config(test_mode=True)
        config.load_config()
        config._config["backup"]["source_path"] = str(test_dir)
        config._config["monitoring"]["check_interval_hours"] = 0.0001

        monitor = DriveMonitor(config=config)
        monitor.start()

        # Check with no changes
        assert monitor.check_for_changes() is False
        assert monitor.should_check() is False

        # Wait for interval
        time.sleep(0.5)

        # Should check again even though no changes last time
        assert monitor.should_check() is True

        # Add a file and check
        test_file = test_dir / "photo.jpg"
        test_file.write_text("test")
        assert monitor.check_for_changes() is True

        # Timer should still reset
        assert monitor.should_check() is False


class TestMonitorState:
    """Tests for monitor state persistence functionality."""

    def test_state_saves_correctly(self, tmp_path):
        """Test that state saves to disk correctly."""
        test_dir = tmp_path / "test-photos"
        test_dir.mkdir()

        config = Config(test_mode=True)
        config.load_config()
        config._config["backup"]["source_path"] = str(test_dir)

        monitor = DriveMonitor(config=config)
        monitor.start()

        # Perform a check
        monitor.check_for_changes()

        # Save state
        assert monitor.save_state() is True

        # Verify state object was updated
        assert monitor._monitor_state.total_checks == 1
        assert monitor._monitor_state.watch_path == str(test_dir)

    def test_state_loads_correctly(self, tmp_path):
        """Test that state loads from disk correctly."""
        test_dir = tmp_path / "test-photos"
        test_dir.mkdir()

        config = Config(test_mode=True)
        config.load_config()
        config._config["backup"]["source_path"] = str(test_dir)

        # Create first monitor and save state
        monitor1 = DriveMonitor(config=config)
        monitor1.start()
        monitor1.check_for_changes()
        monitor1.save_state()

        # Create second monitor and load state
        monitor2 = DriveMonitor(config=config)
        assert monitor2.load_state() is True

        # Verify state was loaded
        assert monitor2._monitor_state.total_checks == 1
        assert monitor2._monitor_state.watch_path == str(test_dir)

    def test_state_persists_across_instances(self, tmp_path):
        """Test that state persists across multiple monitor instances."""
        test_dir = tmp_path / "test-photos"
        test_dir.mkdir()

        config = Config(test_mode=True)
        config.load_config()
        config._config["backup"]["source_path"] = str(test_dir)

        # First instance - perform 3 checks
        monitor1 = DriveMonitor(config=config)
        monitor1.start()
        for _ in range(3):
            monitor1.check_for_changes()

        # Second instance - load and perform 2 more checks
        monitor2 = DriveMonitor(config=config)
        monitor2.load_state()
        monitor2.start()
        for _ in range(2):
            monitor2.check_for_changes()

        # Third instance - verify cumulative state
        monitor3 = DriveMonitor(config=config)
        monitor3.load_state()

        # Should have 5 total checks
        assert monitor3._monitor_state.total_checks == 5

    def test_state_updates_after_checks(self, tmp_path):
        """Test that state updates correctly after checks."""
        test_dir = tmp_path / "test-photos"
        test_dir.mkdir()

        config = Config(test_mode=True)
        config.load_config()
        config._config["backup"]["source_path"] = str(test_dir)

        monitor = DriveMonitor(config=config)
        monitor.start()

        # Initial state
        assert monitor._monitor_state.total_checks == 0
        assert monitor._monitor_state.total_changes_detected == 0

        # Perform check with no changes
        monitor.check_for_changes()
        assert monitor._monitor_state.total_checks == 1
        assert monitor._monitor_state.total_changes_detected == 0

        # Add files and check
        (test_dir / "photo1.jpg").write_text("test 1")
        (test_dir / "photo2.jpg").write_text("test 2")
        monitor.check_for_changes()

        assert monitor._monitor_state.total_checks == 2
        assert monitor._monitor_state.total_changes_detected == 2

    def test_state_handles_missing_file(self, tmp_path):
        """Test that loading state handles missing file gracefully."""
        test_dir = tmp_path / "test-photos"
        test_dir.mkdir()

        config = Config(test_mode=True)
        config.load_config()
        config._config["backup"]["source_path"] = str(test_dir)

        monitor = DriveMonitor(config=config)

        # Turn off auto-save to ensure no state file is created
        monitor._auto_save_state = False

        # Use a unique state file name to avoid conflicts with other tests
        monitor._state_file = "test_missing_monitor_state.json"

        # Try to load non-existent state
        assert monitor.load_state() is False

        # Should start with fresh state
        assert monitor._monitor_state.total_checks == 0

    def test_change_history_limited_to_max_size(self, tmp_path):
        """Test that change history is limited to maximum size."""
        test_dir = tmp_path / "test-photos"
        test_dir.mkdir()

        config = Config(test_mode=True)
        config.load_config()
        config._config["backup"]["source_path"] = str(test_dir)

        monitor = DriveMonitor(config=config)
        monitor.start()

        # Add many files to trigger history
        for i in range(15):
            (test_dir / f"photo{i}.jpg").write_text(f"test {i}")

        monitor.check_for_changes()

        # History should be limited (only first 10 from _update_state_from_check)
        assert len(monitor._monitor_state.change_history) == 10

    def test_state_uses_test_directory(self, tmp_path):
        """Test that state files use test directory in test mode."""
        test_dir = tmp_path / "test-photos"
        test_dir.mkdir()

        config = Config(test_mode=True)
        config.load_config()
        config._config["backup"]["source_path"] = str(test_dir)

        monitor = DriveMonitor(config=config)
        monitor.start()
        monitor.check_for_changes()
        monitor.save_state()

        # State file should be in test state directory
        from photo_backup.state_utils import get_state_directories

        dirs = get_state_directories(test_mode=True)
        state_file = Path(dirs["state"]) / monitor._state_file
        assert state_file.exists()

    def test_state_no_previous_state(self, tmp_path):
        """Test starting with no previous state (fresh start)."""
        test_dir = tmp_path / "test-photos"
        test_dir.mkdir()

        config = Config(test_mode=True)
        config.load_config()
        config._config["backup"]["source_path"] = str(test_dir)

        monitor = DriveMonitor(config=config)

        # Fresh state
        assert monitor._monitor_state.total_checks == 0
        assert monitor._monitor_state.total_changes_detected == 0
        assert monitor._monitor_state.last_check_time is None
        assert monitor._monitor_state.last_change_time is None
        assert len(monitor._monitor_state.change_history) == 0

    def test_state_serialization(self):
        """Test MonitorStateData serialization and deserialization."""
        from datetime import datetime

        # Create state with data
        state1 = MonitorStateData(
            total_checks=5,
            total_changes_detected=10,
            watch_path="/test/path",
        )
        state1.update_check(datetime(2025, 1, 1, 12, 0, 0))
        state1.update_changes(3, datetime(2025, 1, 1, 12, 0, 0))

        # Serialize
        data = state1.to_dict()
        # total_checks should be 6 now (5 + 1 from update_check)
        assert data["total_checks"] == 6
        # total_changes_detected should be 13 (10 + 3 from update_changes)
        assert data["total_changes_detected"] == 13
        assert data["watch_path"] == "/test/path"
        assert data["last_check_time"] is not None

        # Deserialize
        state2 = MonitorStateData.from_dict(data)
        assert state2.total_checks == 6
        assert state2.total_changes_detected == 13
        assert state2.watch_path == "/test/path"
        assert state2.last_check_time == datetime(2025, 1, 1, 12, 0, 0)


class TestMonitorStatus:
    """Tests for enhanced monitor status reporting functionality."""

    def test_get_status_includes_persistent_state(self, tmp_path):
        """Test that get_status includes persistent state information."""
        test_dir = tmp_path / "test-photos"
        test_dir.mkdir()

        config = Config(test_mode=True)
        config.load_config()
        config._config["backup"]["source_path"] = str(test_dir)

        monitor = DriveMonitor(config=config)
        monitor.start()

        # Perform some checks
        monitor.check_for_changes()
        (test_dir / "photo1.jpg").write_text("test")
        monitor.check_for_changes()

        # Get status
        status = monitor.get_status()

        # Verify basic status fields exist
        assert "state" in status
        assert "watch_path" in status
        assert "changes_pending" in status

        # Verify persistent state is included
        assert "persistent_state" in status
        persistent = status["persistent_state"]
        assert persistent["total_checks"] == 2
        assert persistent["total_changes_detected"] == 1
        assert persistent["last_check_time"] is not None
        assert persistent["change_history_count"] >= 0

    def test_get_detailed_status_includes_changes(self, tmp_path):
        """Test that get_detailed_status includes pending changes and history."""
        test_dir = tmp_path / "test-photos"
        test_dir.mkdir()

        config = Config(test_mode=True)
        config.load_config()
        config._config["backup"]["source_path"] = str(test_dir)

        monitor = DriveMonitor(config=config)
        monitor.start()
        monitor.check_for_changes()

        # Add files
        (test_dir / "photo1.jpg").write_text("test 1")
        (test_dir / "photo2.jpg").write_text("test 2")
        monitor.check_for_changes()

        # Get detailed status
        status = monitor.get_detailed_status()

        # Verify pending changes are included
        assert "pending_changes" in status
        assert len(status["pending_changes"]) == 2
        assert all("file" in change and "event" in change for change in status["pending_changes"])

        # Verify recent history is included
        assert "recent_history" in status
        assert isinstance(status["recent_history"], list)

    def test_get_pending_changes_returns_list(self, tmp_path):
        """Test that get_pending_changes returns correct format."""
        test_dir = tmp_path / "test-photos"
        test_dir.mkdir()

        config = Config(test_mode=True)
        config.load_config()
        config._config["backup"]["source_path"] = str(test_dir)

        monitor = DriveMonitor(config=config)
        monitor.start()
        monitor.check_for_changes()

        # No changes initially
        changes = monitor.get_pending_changes()
        assert changes == []

        # Add a file
        (test_dir / "photo.jpg").write_text("test")
        monitor.check_for_changes()

        # Should have one change
        changes = monitor.get_pending_changes()
        assert len(changes) == 1
        assert changes[0]["file"] == "photo.jpg"
        assert changes[0]["event"] == "file_added"

    def test_format_status_produces_readable_output(self, tmp_path):
        """Test that format_status produces human-readable output."""
        test_dir = tmp_path / "test-photos"
        test_dir.mkdir()

        config = Config(test_mode=True)
        config.load_config()
        config._config["backup"]["source_path"] = str(test_dir)

        monitor = DriveMonitor(config=config)
        monitor.start()
        monitor.check_for_changes()

        # Get formatted status
        status_str = monitor.format_status()

        # Verify key sections are present
        assert "=== Drive Monitor Status ===" in status_str
        assert "=== Current Session ===" in status_str
        assert "=== Timing ===" in status_str
        assert "=== Persistent State ===" in status_str

        # Verify key fields are present
        assert "State:" in status_str
        assert "Watch Path:" in status_str
        assert "Mode:" in status_str
        assert "Total Checks:" in status_str
        assert "Pending Changes:" in status_str

    def test_status_shows_last_check_time(self, tmp_path):
        """Test that status shows last check time from persistent state."""
        test_dir = tmp_path / "test-photos"
        test_dir.mkdir()

        config = Config(test_mode=True)
        config.load_config()
        config._config["backup"]["source_path"] = str(test_dir)

        monitor = DriveMonitor(config=config)
        monitor.start()

        # Initially no last check
        status = monitor.get_status()
        assert status["persistent_state"]["last_check_time"] is None

        # After check, should have time
        monitor.check_for_changes()
        status = monitor.get_status()
        assert status["persistent_state"]["last_check_time"] is not None

    def test_status_tracks_cumulative_statistics(self, tmp_path):
        """Test that status tracks cumulative statistics across checks."""
        test_dir = tmp_path / "test-photos"
        test_dir.mkdir()

        config = Config(test_mode=True)
        config.load_config()
        config._config["backup"]["source_path"] = str(test_dir)

        monitor = DriveMonitor(config=config)
        monitor.start()

        # Perform multiple checks with changes
        for i in range(3):
            (test_dir / f"photo{i}.jpg").write_text(f"test {i}")
            monitor.check_for_changes()

        status = monitor.get_status()
        persistent = status["persistent_state"]

        # Should have cumulative counts
        assert persistent["total_checks"] == 3
        assert persistent["total_changes_detected"] == 3

    def test_status_shows_pending_changes_count(self, tmp_path):
        """Test that status correctly shows pending changes count."""
        test_dir = tmp_path / "test-photos"
        test_dir.mkdir()

        config = Config(test_mode=True)
        config.load_config()
        config._config["backup"]["source_path"] = str(test_dir)

        monitor = DriveMonitor(config=config)
        monitor.start()
        monitor.check_for_changes()

        # No changes initially
        status = monitor.get_status()
        assert status["changes_pending"] == 0

        # Add files
        (test_dir / "photo1.jpg").write_text("test 1")
        (test_dir / "photo2.jpg").write_text("test 2")
        (test_dir / "photo3.jpg").write_text("test 3")
        monitor.check_for_changes()

        # Should show 3 pending
        status = monitor.get_status()
        assert status["changes_pending"] == 3

    def test_detailed_status_limits_history(self, tmp_path):
        """Test that detailed status limits history to last 10 events."""
        test_dir = tmp_path / "test-photos"
        test_dir.mkdir()

        config = Config(test_mode=True)
        config.load_config()
        config._config["backup"]["source_path"] = str(test_dir)

        monitor = DriveMonitor(config=config)
        monitor.start()

        # Add many files to generate history
        for i in range(15):
            (test_dir / f"photo{i}.jpg").write_text(f"test {i}")

        monitor.check_for_changes()

        # Get detailed status
        status = monitor.get_detailed_status()

        # Recent history should be limited to 10
        assert len(status["recent_history"]) <= 10

    def test_format_status_handles_never_checked(self, tmp_path):
        """Test that format_status handles case when never checked."""
        test_dir = tmp_path / "test-photos"
        test_dir.mkdir()

        config = Config(test_mode=True)
        config.load_config()
        config._config["backup"]["source_path"] = str(test_dir)

        monitor = DriveMonitor(config=config)
        monitor.start()

        # Format status before any checks
        status_str = monitor.format_status()

        # Should show "Never" for times
        assert "Time Since Last Check: Never" in status_str
        assert "Last Check: Never" in status_str


class TestChangeReset:
    """Tests for change reset functionality."""

    def test_reset_changes_clears_pending_list(self, tmp_path):
        """Test that reset_changes clears the pending changes list."""
        test_dir = tmp_path / "test-photos"
        test_dir.mkdir()

        config = Config(test_mode=True)
        config.load_config()
        config._config["backup"]["source_path"] = str(test_dir)

        monitor = DriveMonitor(config=config)
        monitor.start()
        monitor.check_for_changes()

        # Add files and detect changes
        (test_dir / "photo1.jpg").write_text("test 1")
        (test_dir / "photo2.jpg").write_text("test 2")
        monitor.check_for_changes()

        # Should have pending changes
        assert len(monitor._changes_detected) == 2

        # Reset changes
        monitor.reset_changes()

        # Pending changes should be cleared
        assert len(monitor._changes_detected) == 0

    def test_reset_changes_clears_last_change_time(self, tmp_path):
        """Test that reset_changes clears the last change time."""
        test_dir = tmp_path / "test-photos"
        test_dir.mkdir()

        config = Config(test_mode=True)
        config.load_config()
        config._config["backup"]["source_path"] = str(test_dir)

        monitor = DriveMonitor(config=config)
        monitor.start()
        monitor.check_for_changes()

        # Add file and detect change
        (test_dir / "photo.jpg").write_text("test")
        monitor.check_for_changes()

        # Should have last change time
        assert monitor._last_change_time is not None

        # Reset changes
        monitor.reset_changes()

        # Last change time should be cleared
        assert monitor._last_change_time is None

    def test_reset_changes_logs_event(self, tmp_path):
        """Test that reset_changes logs an event."""
        test_dir = tmp_path / "test-photos"
        test_dir.mkdir()

        config = Config(test_mode=True)
        config.load_config()
        config._config["backup"]["source_path"] = str(test_dir)

        monitor = DriveMonitor(config=config)
        monitor.start()
        monitor.check_for_changes()

        # Add files
        (test_dir / "photo1.jpg").write_text("test 1")
        (test_dir / "photo2.jpg").write_text("test 2")
        (test_dir / "photo3.jpg").write_text("test 3")
        monitor.check_for_changes()

        initial_event_count = len(monitor._event_history)

        # Reset changes
        monitor.reset_changes()

        # Should have new event
        assert len(monitor._event_history) == initial_event_count + 1
        last_event = monitor._event_history[-1]
        assert last_event[0] == MonitorEvent.CHANGES_RESET
        assert "3 changes cleared" in last_event[1]

    def test_reset_changes_preserves_snapshot(self, tmp_path):
        """Test that reset_changes preserves the file snapshot."""
        test_dir = tmp_path / "test-photos"
        test_dir.mkdir()

        config = Config(test_mode=True)
        config.load_config()
        config._config["backup"]["source_path"] = str(test_dir)

        monitor = DriveMonitor(config=config)
        monitor.start()

        # Add files
        (test_dir / "photo1.jpg").write_text("test 1")
        (test_dir / "photo2.jpg").write_text("test 2")
        monitor.check_for_changes()

        snapshot_size = len(monitor._file_snapshot)

        # Reset changes
        monitor.reset_changes()

        # Snapshot should be preserved
        assert len(monitor._file_snapshot) == snapshot_size

    def test_reset_changes_with_no_pending(self, tmp_path):
        """Test that reset_changes handles no pending changes gracefully."""
        test_dir = tmp_path / "test-photos"
        test_dir.mkdir()

        config = Config(test_mode=True)
        config.load_config()
        config._config["backup"]["source_path"] = str(test_dir)

        monitor = DriveMonitor(config=config)
        monitor.start()
        monitor.check_for_changes()

        # No pending changes
        assert len(monitor._changes_detected) == 0

        # Reset should work without error
        monitor.reset_changes()

        # Still no pending changes
        assert len(monitor._changes_detected) == 0

    def test_reset_allows_new_changes_detection(self, tmp_path):
        """Test that after reset, new changes are detected properly."""
        test_dir = tmp_path / "test-photos"
        test_dir.mkdir()

        config = Config(test_mode=True)
        config.load_config()
        config._config["backup"]["source_path"] = str(test_dir)

        monitor = DriveMonitor(config=config)
        monitor.start()
        monitor.check_for_changes()

        # First batch of changes
        (test_dir / "photo1.jpg").write_text("test 1")
        monitor.check_for_changes()
        assert len(monitor._changes_detected) == 1

        # Reset
        monitor.reset_changes()
        assert len(monitor._changes_detected) == 0

        # Second batch of changes
        (test_dir / "photo2.jpg").write_text("test 2")
        (test_dir / "photo3.jpg").write_text("test 3")
        monitor.check_for_changes()

        # Should detect new changes
        assert len(monitor._changes_detected) == 2

    def test_clear_all_state_comprehensive(self, tmp_path):
        """Test that clear_all_state clears everything."""
        test_dir = tmp_path / "test-photos"
        test_dir.mkdir()

        config = Config(test_mode=True)
        config.load_config()
        config._config["backup"]["source_path"] = str(test_dir)

        monitor = DriveMonitor(config=config)
        monitor.start()

        # Add files and detect changes
        (test_dir / "photo1.jpg").write_text("test 1")
        (test_dir / "photo2.jpg").write_text("test 2")
        monitor.check_for_changes()

        # Verify state is populated
        assert len(monitor._changes_detected) > 0
        assert len(monitor._file_snapshot) > 0
        assert len(monitor._event_history) > 0
        assert monitor._last_check_time is not None

        # Clear all state
        monitor.clear_all_state()

        # Everything should be cleared
        assert len(monitor._changes_detected) == 0
        assert len(monitor._file_snapshot) == 0
        assert monitor._last_change_time is None
        assert monitor._last_check_time is None
        # Note: event_history will have 1 entry from STATE_CLEARED event itself
        assert monitor._event_history[-1][0] == MonitorEvent.STATE_CLEARED

    def test_clear_all_state_logs_warning(self, tmp_path):
        """Test that clear_all_state logs a warning event."""
        test_dir = tmp_path / "test-photos"
        test_dir.mkdir()

        config = Config(test_mode=True)
        config.load_config()
        config._config["backup"]["source_path"] = str(test_dir)

        monitor = DriveMonitor(config=config)
        monitor.start()

        # Clear all state
        monitor.clear_all_state()

        # Should have STATE_CLEARED event
        last_event = monitor._event_history[-1]
        assert last_event[0] == MonitorEvent.STATE_CLEARED

    def test_reset_after_backup_workflow(self, tmp_path):
        """Test typical workflow: detect changes, backup, reset, detect new changes."""
        test_dir = tmp_path / "test-photos"
        test_dir.mkdir()

        config = Config(test_mode=True)
        config.load_config()
        config._config["backup"]["source_path"] = str(test_dir)

        monitor = DriveMonitor(config=config)
        monitor.start()
        monitor.check_for_changes()

        # 1. Detect first batch of changes
        (test_dir / "photo1.jpg").write_text("test 1")
        (test_dir / "photo2.jpg").write_text("test 2")
        monitor.check_for_changes()
        assert len(monitor._changes_detected) == 2

        # 2. Simulate successful backup and reset
        # (In real workflow, backup engine would call this)
        monitor.reset_changes()
        assert len(monitor._changes_detected) == 0

        # 3. Detect second batch of changes
        (test_dir / "photo3.jpg").write_text("test 3")
        monitor.check_for_changes()
        assert len(monitor._changes_detected) == 1

        # Verify snapshot still tracks all files
        assert len(monitor._file_snapshot) == 3
