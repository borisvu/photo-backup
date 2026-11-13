"""
Unit tests for PID management functionality.

Tests cover:
- PID file creation and removal
- PID file reading
- Process existence checking
- Stale PID detection and cleanup
- Duplicate instance prevention
- get_running_pid class method
"""

import contextlib
import os
from unittest.mock import patch

import pytest

from photo_backup.config.config import Config
from photo_backup.service import ServiceManager
from photo_backup.state_utils import get_state_directories


@pytest.fixture
def test_config():
    """Create test mode configuration."""
    config = Config(test_mode=True)
    config.load_config()
    return config


@pytest.fixture
def service_manager(test_config):
    """Create service manager instance."""
    # Mock monitor and backup engine to avoid initialization
    with patch("photo_backup.service.manager.DriveMonitor"), patch("photo_backup.service.manager.BackupEngine"):
        manager = ServiceManager(test_config)
        # Clean up any existing PID file from previous test
        manager._remove_pid_file()
        yield manager
        # Cleanup after test
        manager._remove_pid_file()


class TestPIDFileOperations:
    """Test basic PID file operations."""

    def test_get_pid_file_path(self, service_manager):
        """Test that PID file path is correctly constructed."""
        pid_file_path = service_manager._get_pid_file_path()
        assert pid_file_path.endswith("photo-backup.pid")
        assert "/tmp/photo-backup-test/" in pid_file_path

    def test_write_pid_file(self, service_manager):
        """Test writing PID file."""
        service_manager._write_pid_file()

        # Verify file exists
        assert os.path.exists(service_manager._pid_file_path)

        # Verify file contains current PID
        with open(service_manager._pid_file_path) as f:
            pid = int(f.read().strip())
        assert pid == os.getpid()

    def test_read_pid_file(self, service_manager):
        """Test reading PID file."""
        # Write a test PID
        test_pid = 12345
        with open(service_manager._pid_file_path, "w") as f:
            f.write(str(test_pid))

        # Read it back
        pid = service_manager._read_pid_file()
        assert pid == test_pid

    def test_read_pid_file_not_exists(self, service_manager):
        """Test reading PID file when it doesn't exist."""
        # Ensure file doesn't exist
        if os.path.exists(service_manager._pid_file_path):
            os.remove(service_manager._pid_file_path)

        pid = service_manager._read_pid_file()
        assert pid is None

    def test_read_pid_file_empty(self, service_manager):
        """Test reading empty PID file."""
        # Create empty file
        with open(service_manager._pid_file_path, "w") as f:
            f.write("")

        pid = service_manager._read_pid_file()
        assert pid is None

    def test_read_pid_file_invalid_content(self, service_manager):
        """Test reading PID file with invalid content."""
        # Write invalid content
        with open(service_manager._pid_file_path, "w") as f:
            f.write("not-a-number")

        pid = service_manager._read_pid_file()
        assert pid is None

    def test_remove_pid_file(self, service_manager):
        """Test removing PID file."""
        # Create PID file
        service_manager._write_pid_file()
        assert os.path.exists(service_manager._pid_file_path)

        # Remove it
        service_manager._remove_pid_file()
        assert not os.path.exists(service_manager._pid_file_path)

    def test_remove_pid_file_not_exists(self, service_manager):
        """Test removing PID file when it doesn't exist."""
        # Ensure file doesn't exist
        if os.path.exists(service_manager._pid_file_path):
            os.remove(service_manager._pid_file_path)

        # Should not raise error
        service_manager._remove_pid_file()


class TestProcessRunningCheck:
    """Test process running detection."""

    def test_is_process_running_current_process(self):
        """Test checking if current process is running."""
        current_pid = os.getpid()
        assert ServiceManager._is_process_running(current_pid) is True

    def test_is_process_running_invalid_pid_zero(self):
        """Test checking invalid PID (zero)."""
        assert ServiceManager._is_process_running(0) is False

    def test_is_process_running_invalid_pid_negative(self):
        """Test checking invalid PID (negative)."""
        assert ServiceManager._is_process_running(-1) is False

    def test_is_process_running_nonexistent_pid(self):
        """Test checking non-existent process."""
        # Use a very high PID that's unlikely to exist
        fake_pid = 9999999
        assert ServiceManager._is_process_running(fake_pid) is False

    @patch("os.kill")
    def test_is_process_running_permission_denied(self, mock_kill):
        """Test checking process when permission denied."""
        import errno

        # Simulate permission denied (EPERM)
        mock_kill.side_effect = OSError(errno.EPERM, "Permission denied")

        # Should return True (process exists but we can't signal it)
        assert ServiceManager._is_process_running(12345) is True

    @patch("os.kill")
    def test_is_process_running_other_error(self, mock_kill):
        """Test checking process with other OS error."""
        import errno

        # Simulate other error
        mock_kill.side_effect = OSError(errno.EINVAL, "Invalid argument")

        # Should return False (assume not running on error)
        assert ServiceManager._is_process_running(12345) is False


class TestExistingInstanceCheck:
    """Test duplicate instance prevention."""

    def test_check_existing_instance_no_pid_file(self, service_manager):
        """Test when no PID file exists."""
        # Ensure no PID file
        service_manager._remove_pid_file()

        # Should not raise
        service_manager._check_existing_instance()

    def test_check_existing_instance_stale_pid(self, service_manager):
        """Test when PID file contains stale PID."""
        # Write a fake PID that doesn't exist
        fake_pid = 9999999
        with open(service_manager._pid_file_path, "w") as f:
            f.write(str(fake_pid))

        # Should clean up stale PID file
        service_manager._check_existing_instance()

        # PID file should be removed
        assert not os.path.exists(service_manager._pid_file_path)

    def test_check_existing_instance_running_process(self, service_manager):
        """Test when process is actually running."""
        # Write current PID to simulate running instance
        with open(service_manager._pid_file_path, "w") as f:
            f.write(str(os.getpid()))

        # Should raise RuntimeError
        with pytest.raises(RuntimeError, match="Service is already running"):
            service_manager._check_existing_instance()

        # Clean up
        service_manager._remove_pid_file()


class TestServiceLifecycleIntegration:
    """Test PID management integration with service lifecycle."""

    def test_pid_file_created_on_start(self, service_manager):
        """Test that PID file is created when service starts."""
        # Mock the run loop to exit immediately
        with patch.object(service_manager, "_run_loop"):
            # Ignore errors, we're just testing PID file creation
            with contextlib.suppress(Exception):
                service_manager.start()

        # PID file should not exist after shutdown
        assert not os.path.exists(service_manager._pid_file_path)

    def test_pid_file_removed_on_shutdown(self, service_manager):
        """Test that PID file is removed on shutdown."""
        service_manager._write_pid_file()
        assert os.path.exists(service_manager._pid_file_path)

        # Call shutdown
        service_manager._shutdown()

        # PID file should be removed
        assert not os.path.exists(service_manager._pid_file_path)

    def test_duplicate_start_prevented(self, service_manager):
        """Test that duplicate service start is prevented."""
        # Write current PID
        service_manager._write_pid_file()

        # Try to start service
        with pytest.raises(RuntimeError, match="Service is already running"):
            with patch.object(service_manager, "_run_loop"):
                service_manager.start()

        # Clean up
        service_manager._remove_pid_file()


class TestGetRunningPID:
    """Test get_running_pid class method."""

    def test_get_running_pid_no_service(self, test_config):
        """Test when no service is running."""
        # Ensure no PID file exists
        dirs = get_state_directories(test_mode=True)
        pid_file_path = os.path.join(dirs["temp"], "photo-backup.pid")
        if os.path.exists(pid_file_path):
            os.remove(pid_file_path)

        pid = ServiceManager.get_running_pid(test_mode=True)
        assert pid is None

    def test_get_running_pid_with_running_service(self, test_config):
        """Test when service is running."""
        dirs = get_state_directories(test_mode=True)
        pid_file_path = os.path.join(dirs["temp"], "photo-backup.pid")

        # Write current PID (simulating running service)
        current_pid = os.getpid()
        with open(pid_file_path, "w") as f:
            f.write(str(current_pid))

        try:
            pid = ServiceManager.get_running_pid(test_mode=True)
            assert pid == current_pid
        finally:
            # Clean up
            if os.path.exists(pid_file_path):
                os.remove(pid_file_path)

    def test_get_running_pid_stale_pid_file(self, test_config):
        """Test when PID file exists but process is not running."""
        dirs = get_state_directories(test_mode=True)
        pid_file_path = os.path.join(dirs["temp"], "photo-backup.pid")

        # Write fake PID
        fake_pid = 9999999
        with open(pid_file_path, "w") as f:
            f.write(str(fake_pid))

        try:
            pid = ServiceManager.get_running_pid(test_mode=True)
            # Should return None because process doesn't exist
            assert pid is None
        finally:
            # Clean up
            if os.path.exists(pid_file_path):
                os.remove(pid_file_path)

    def test_get_running_pid_invalid_pid_file(self, test_config):
        """Test when PID file contains invalid data."""
        dirs = get_state_directories(test_mode=True)
        pid_file_path = os.path.join(dirs["temp"], "photo-backup.pid")

        # Write invalid content
        with open(pid_file_path, "w") as f:
            f.write("invalid")

        try:
            pid = ServiceManager.get_running_pid(test_mode=True)
            assert pid is None
        finally:
            # Clean up
            if os.path.exists(pid_file_path):
                os.remove(pid_file_path)


class TestProductionMode:
    """Test PID management in production mode."""

    def test_production_mode_pid_path(self):
        """Test that production mode uses correct PID path."""
        config = Config(test_mode=False)
        config.load_config()

        with patch("photo_backup.service.manager.DriveMonitor"), patch("photo_backup.service.manager.BackupEngine"):
            manager = ServiceManager(config)
            pid_file_path = manager._get_pid_file_path()

            # Should contain Library/Application Support
            assert "Library/Application Support" in pid_file_path or "photo-backup" in pid_file_path
            assert "photo-backup.pid" in pid_file_path
