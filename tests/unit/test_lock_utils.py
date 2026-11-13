import os

import pytest

from photo_backup.lock_utils import acquire_lock, release_lock
from photo_backup.state_utils import get_state_directories


class TestProcessLock:
    """Test cases for acquire_lock and release_lock functions."""

    @pytest.mark.unit
    def test_acquire_and_release_lock(self, tmp_path, monkeypatch):
        # Patch expanduser to use tmp_path for home
        monkeypatch.setattr(
            "photo_backup.state_utils.os.path.expanduser",
            lambda p: str(tmp_path / "Library/Application Support/photo-backup") if p.startswith("~") else p,
        )
        lock_name = "test.lock"
        # Acquire lock
        success, error = acquire_lock(lock_name=lock_name, test_mode=False)
        assert success is True
        assert error is None
        # Try to acquire again (should fail)
        success, error = acquire_lock(lock_name=lock_name, test_mode=False)
        assert success is False
        assert "Lock already acquired" in error
        # Release lock
        success, error = release_lock(lock_name=lock_name, test_mode=False)
        assert success is True
        assert error is None
        # Release again (should fail)
        success, error = release_lock(lock_name=lock_name, test_mode=False)
        assert success is False
        assert "does not exist" in error

    @pytest.mark.unit
    def test_release_lock_wrong_pid(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "photo_backup.state_utils.os.path.expanduser",
            lambda p: str(tmp_path / "Library/Application Support/photo-backup") if p.startswith("~") else p,
        )
        lock_name = "test2.lock"
        dirs = get_state_directories(test_mode=False)
        temp_dir = dirs["temp"]
        lock_path = os.path.join(temp_dir, lock_name)
        # Write a fake PID
        with open(lock_path, "w") as f:
            f.write("999999")
        # Try to release (should fail)
        success, error = release_lock(lock_name=lock_name, test_mode=False)
        assert success is False
        assert "owned by PID" in error

    @pytest.mark.unit
    def test_acquire_lock_stale_pid(self, tmp_path, monkeypatch):
        monkeypatch.setattr(
            "photo_backup.state_utils.os.path.expanduser",
            lambda p: str(tmp_path / "Library/Application Support/photo-backup") if p.startswith("~") else p,
        )
        lock_name = "test3.lock"
        dirs = get_state_directories(test_mode=False)
        temp_dir = dirs["temp"]
        lock_path = os.path.join(temp_dir, lock_name)
        # Write a stale PID (should not exist)
        with open(lock_path, "w") as f:
            f.write("999999")
        # Should acquire lock (stale PID)
        success, error = acquire_lock(lock_name=lock_name, test_mode=False)
        assert success is True
        assert error is None
        # Clean up
        release_lock(lock_name=lock_name, test_mode=False)
