"""
Unit tests for drive monitor module.

Tests the DriveMonitor class and monitoring events.
"""

from photo_backup.config import Config
from photo_backup.monitor import DriveMonitor


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
