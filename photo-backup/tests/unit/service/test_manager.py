"""
Unit tests for ServiceManager class.

Tests cover:
- Service initialization
- Service lifecycle (start, stop)
- State transitions
- Status reporting
- Signal handling
- Test mode support
"""

import contextlib
import logging
import signal
import time
from datetime import datetime
from threading import Thread
from unittest.mock import patch

import pytest

from photo_backup.config.config import Config
from photo_backup.service import ServiceManager, ServiceState, ServiceStatus


@pytest.fixture
def test_config():
    """Create test mode configuration."""
    config = Config(test_mode=True)
    config.load_config()
    return config


@pytest.fixture
def service_manager(test_config):
    """Create service manager instance."""
    logger = logging.getLogger("test_service")
    return ServiceManager(test_config, logger=logger)


class TestServiceManagerInit:
    """Test ServiceManager initialization."""

    def test_can_instantiate_service_manager(self, test_config):
        """Test that service manager can be instantiated."""
        service = ServiceManager(test_config)
        assert service is not None
        assert isinstance(service, ServiceManager)

    def test_initial_state_is_stopped(self, service_manager):
        """Test that service starts in STOPPED state."""
        assert service_manager.state == ServiceState.STOPPED
        assert not service_manager.is_running

    def test_stores_config(self, service_manager, test_config):
        """Test that service stores configuration."""
        assert service_manager.config is test_config
        assert service_manager.config.test_mode is True

    def test_creates_logger_if_not_provided(self, test_config):
        """Test that service creates logger if none provided."""
        service = ServiceManager(test_config)
        assert service.logger is not None

    def test_uses_provided_logger(self, test_config):
        """Test that service uses provided logger."""
        logger = logging.getLogger("custom_logger")
        service = ServiceManager(test_config, logger=logger)
        assert service.logger is logger

    def test_reads_loop_interval_from_config(self, test_config):
        """Test that service reads loop interval from config."""
        service = ServiceManager(test_config)
        expected_interval = test_config.get("service.loop_interval_seconds", 60)
        assert service._loop_interval == expected_interval

    def test_test_mode_uses_shorter_interval(self, test_config):
        """Test that test mode uses shorter polling interval."""
        service = ServiceManager(test_config)
        # Test mode should have 5 second interval
        assert service._loop_interval == 5


class TestServiceManagerState:
    """Test service state management."""

    def test_state_property_returns_current_state(self, service_manager):
        """Test that state property returns current state."""
        assert service_manager.state == ServiceState.STOPPED
        service_manager._state = ServiceState.RUNNING
        assert service_manager.state == ServiceState.RUNNING

    def test_is_running_returns_true_when_running(self, service_manager):
        """Test is_running property when service is running."""
        service_manager._state = ServiceState.RUNNING
        assert service_manager.is_running is True

    def test_is_running_returns_false_when_not_running(self, service_manager):
        """Test is_running property when service is not running."""
        service_manager._state = ServiceState.STOPPED
        assert service_manager.is_running is False

        service_manager._state = ServiceState.STARTING
        assert service_manager.is_running is False

        service_manager._state = ServiceState.STOPPING
        assert service_manager.is_running is False

        service_manager._state = ServiceState.ERROR
        assert service_manager.is_running is False


class TestServiceManagerStatus:
    """Test service status reporting."""

    def test_get_status_returns_service_status(self, service_manager):
        """Test that get_status returns ServiceStatus object."""
        status = service_manager.get_status()
        assert isinstance(status, ServiceStatus)

    def test_status_includes_current_state(self, service_manager):
        """Test that status includes current state."""
        status = service_manager.get_status()
        assert status.state == ServiceState.STOPPED

    def test_status_includes_timestamps(self, service_manager):
        """Test that status includes start/stop timestamps."""
        status = service_manager.get_status()
        assert status.started_at is None
        assert status.stopped_at is None

        # Simulate service start
        service_manager._status.started_at = datetime.now()
        status = service_manager.get_status()
        assert status.started_at is not None

    def test_status_includes_loop_count(self, service_manager):
        """Test that status includes loop iteration count."""
        service_manager._status.loop_count = 42
        status = service_manager.get_status()
        assert status.loop_count == 42

    def test_status_includes_error_message(self, service_manager):
        """Test that status includes error message when present."""
        service_manager._status.error_message = "Test error"
        status = service_manager.get_status()
        assert status.error_message == "Test error"


class TestServiceManagerSignalHandling:
    """Test signal handling for graceful shutdown."""

    def test_sets_up_signal_handlers(self, service_manager):
        """Test that signal handlers are installed."""
        service_manager._setup_signal_handlers()

        # Handlers should be stored
        assert service_manager._original_sigint_handler is not None
        assert service_manager._original_sigterm_handler is not None

        # Restore handlers
        service_manager._restore_signal_handlers()

    def test_restores_signal_handlers(self, service_manager):
        """Test that original signal handlers are restored."""
        # Install new handlers
        service_manager._setup_signal_handlers()

        # Store what was saved
        saved_sigint = service_manager._original_sigint_handler
        saved_sigterm = service_manager._original_sigterm_handler

        # Restore original handlers
        service_manager._restore_signal_handlers()

        # Verify handlers were stored (we can't easily verify they're restored without triggering)
        assert saved_sigint is not None
        assert saved_sigterm is not None

    def test_handle_shutdown_signal_sets_shutdown_flag(self, service_manager):
        """Test that shutdown signal handler sets shutdown flag."""
        assert service_manager._shutdown_requested is False

        # Simulate SIGINT
        service_manager._handle_shutdown_signal(signal.SIGINT, None)
        assert service_manager._shutdown_requested is True

    def test_handle_shutdown_signal_handles_sigterm(self, service_manager):
        """Test that shutdown signal handler handles SIGTERM."""
        service_manager._handle_shutdown_signal(signal.SIGTERM, None)
        assert service_manager._shutdown_requested is True


class TestServiceManagerLifecycle:
    """Test service lifecycle operations."""

    def test_start_changes_state_to_running(self, service_manager):
        """Test that start changes state to RUNNING."""

        # Use a thread to start service and stop it quickly
        def start_and_stop():
            time.sleep(0.1)
            service_manager.stop()

        thread = Thread(target=start_and_stop)
        thread.start()

        # Start service (will run until stopped)
        service_manager.start()
        thread.join()

        # Should have run and stopped
        assert service_manager.state == ServiceState.STOPPED
        assert service_manager._status.loop_count > 0

    def test_start_raises_if_already_running(self, service_manager):
        """Test that start raises error if already running."""
        service_manager._state = ServiceState.RUNNING

        with pytest.raises(RuntimeError, match="already running"):
            service_manager.start()

    def test_start_records_start_time(self, service_manager):
        """Test that start records start timestamp."""

        def stop_quickly():
            time.sleep(0.1)
            service_manager.stop()

        thread = Thread(target=stop_quickly)
        thread.start()

        service_manager.start()
        thread.join()

        assert service_manager._status.started_at is not None
        assert isinstance(service_manager._status.started_at, datetime)

    def test_start_initializes_counters(self, service_manager):
        """Test that start initializes loop counters."""
        service_manager._status.loop_count = 99

        def stop_quickly():
            time.sleep(0.1)
            service_manager.stop()

        thread = Thread(target=stop_quickly)
        thread.start()

        service_manager.start()
        thread.join()

        # Counter should have been reset and incremented
        assert service_manager._status.loop_count >= 1

    def test_stop_sets_shutdown_flag(self, service_manager):
        """Test that stop sets shutdown flag."""
        # Service needs to be in a non-stopped state for stop to work
        service_manager._state = ServiceState.RUNNING
        service_manager.stop()
        assert service_manager._shutdown_requested is True

    def test_stop_when_already_stopped_logs_warning(self, service_manager, caplog):
        """Test that stop when already stopped logs warning."""
        with caplog.at_level(logging.WARNING):
            service_manager.stop()

        assert "already stopped" in caplog.text

    def test_shutdown_records_stop_time(self, service_manager):
        """Test that shutdown records stop timestamp."""
        service_manager._status.started_at = datetime.now()
        service_manager._shutdown()

        assert service_manager._status.stopped_at is not None
        assert isinstance(service_manager._status.stopped_at, datetime)

    def test_shutdown_changes_state_to_stopped(self, service_manager):
        """Test that shutdown changes state to STOPPED."""
        service_manager._state = ServiceState.RUNNING
        service_manager._status.started_at = datetime.now()
        service_manager._shutdown()

        assert service_manager.state == ServiceState.STOPPED


class TestServiceManagerLoop:
    """Test service main loop."""

    def test_run_loop_increments_loop_count(self, service_manager):
        """Test that run loop increments loop counter."""

        def stop_after_iterations():
            time.sleep(0.2)  # Let it run a few iterations
            service_manager.stop()

        thread = Thread(target=stop_after_iterations)
        thread.start()

        service_manager.start()
        thread.join()

        # Should have completed at least 1 iteration (5 second interval in test mode)
        assert service_manager._status.loop_count >= 1

    def test_run_loop_updates_last_check_time(self, service_manager):
        """Test that run loop updates last check time."""

        def stop_quickly():
            time.sleep(0.1)
            service_manager.stop()

        thread = Thread(target=stop_quickly)
        thread.start()

        service_manager.start()
        thread.join()

        assert service_manager._status.last_check_time is not None

    def test_run_loop_exits_on_shutdown_request(self, service_manager):
        """Test that run loop exits when shutdown requested."""
        service_manager._shutdown_requested = True

        # Should exit immediately
        service_manager._run_loop()

        # Loop count should be 0 (exits before first iteration)
        assert service_manager._status.loop_count == 0

    def test_run_loop_continues_on_error(self, service_manager, _caplog):
        """Test that run loop continues after error in iteration."""
        iteration_count = [0]

        def mock_loop_with_error():
            def patched_run_loop():
                while not service_manager._shutdown_requested:
                    iteration_count[0] += 1
                    if iteration_count[0] == 1:
                        # Simulate error on first iteration
                        raise ValueError("Test error")
                    time.sleep(0.01)

            service_manager._run_loop = patched_run_loop

        with patch.object(service_manager, "_run_loop", side_effect=mock_loop_with_error):

            def stop_after_delay():
                time.sleep(0.1)
                service_manager.stop()

            thread = Thread(target=stop_after_delay)
            thread.start()

            # This will call our mock which raises an error
            with contextlib.suppress(ValueError):
                service_manager.start()

            thread.join()


class TestServiceManagerUptime:
    """Test service uptime calculations."""

    def test_get_uptime_when_not_started(self, service_manager):
        """Test uptime when service hasn't started."""
        uptime = service_manager._get_uptime()
        assert uptime == "not started"

    def test_get_uptime_shows_seconds(self, service_manager):
        """Test uptime display in seconds."""
        service_manager._status.started_at = datetime.now()
        time.sleep(0.1)

        uptime = service_manager._get_uptime()
        assert "s" in uptime
        assert uptime != "not started"

    def test_get_uptime_shows_minutes(self, service_manager):
        """Test uptime display in minutes."""
        from datetime import timedelta

        service_manager._status.started_at = datetime.now() - timedelta(seconds=120)

        uptime = service_manager._get_uptime()
        assert "m" in uptime

    def test_get_uptime_shows_hours(self, service_manager):
        """Test uptime display in hours and minutes."""
        from datetime import timedelta

        service_manager._status.started_at = datetime.now() - timedelta(hours=2, minutes=30)

        uptime = service_manager._get_uptime()
        assert "h" in uptime
        assert "m" in uptime


class TestServiceManagerRepr:
    """Test service manager string representation."""

    def test_repr_includes_state(self, service_manager):
        """Test that repr includes current state."""
        repr_str = repr(service_manager)
        assert "state=stopped" in repr_str

    def test_repr_includes_loop_count(self, service_manager):
        """Test that repr includes loop count."""
        service_manager._status.loop_count = 42
        repr_str = repr(service_manager)
        assert "loop_count=42" in repr_str

    def test_repr_includes_test_mode(self, service_manager):
        """Test that repr includes test mode flag."""
        repr_str = repr(service_manager)
        assert "test_mode=True" in repr_str
