"""
Unit tests for drive monitor module.

Tests the DriveMonitor class and monitoring events.
"""

from pathlib import Path

from photo_backup.config import Config
from photo_backup.monitor import DriveMonitor, MonitorStateData


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
