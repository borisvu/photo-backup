"""
Unit tests for drive monitor module.

Tests the DriveMonitor class and monitoring events.
"""

from photo_backup.config import Config
from photo_backup.monitor import ChangeSummary, DriveMonitor, MonitorEvent


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
