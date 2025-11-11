"""
Unit tests for drive monitor module.

Tests the DriveMonitor class and monitoring events.
"""

from photo_backup.config import Config
from photo_backup.monitor import DriveMonitor, MonitorEvent, MonitorState


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
