"""
Unit tests for state management functionality.

This module tests the BackupState and StateManager classes,
ensuring proper state persistence, serialization, and error handling.
"""

import tempfile
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from photo_backup.backup import BackupState, BackupStats, StateManager


class TestBackupState:
    """Tests for BackupState class."""

    def test_backup_state_init(self):
        """Test BackupState initialization with default values."""
        state = BackupState()

        assert state.last_sync_time is None
        assert state.last_successful_sync is None
        assert state.last_stats is None
        assert state.total_syncs == 0
        assert state.successful_syncs == 0
        assert state.failed_syncs == 0
        assert state.total_files_transferred == 0
        assert state.total_bytes_transferred == 0
        assert state.total_sync_time == 0.0
        assert state.last_error is None
        assert state.consecutive_failures == 0
        assert state.error_history == []
        assert state.source_path == ""
        assert state.destination == ""

    def test_backup_state_to_dict_empty(self):
        """Test BackupState to_dict conversion with empty state."""
        state = BackupState()
        data = state.to_dict()

        expected = {
            "last_sync_time": None,
            "last_successful_sync": None,
            "last_stats": None,
            "total_syncs": 0,
            "successful_syncs": 0,
            "failed_syncs": 0,
            "total_files_transferred": 0,
            "total_bytes_transferred": 0,
            "total_sync_time": 0.0,
            "last_error": None,
            "consecutive_failures": 0,
            "error_history": [],
            "source_path": "",
            "destination": "",
        }

        assert data == expected

    def test_backup_state_to_dict_with_data(self):
        """Test BackupState to_dict conversion with populated state."""
        now = datetime.now()
        stats = BackupStats(
            start_time=now,
            end_time=now + timedelta(seconds=30),
            duration_seconds=30.0,
            files_transferred=10,
            bytes_transferred=1000,
            success=True,
            source_path="/test/source",
            destination="test:backup",
        )

        state = BackupState()
        state.last_sync_time = now
        state.last_successful_sync = now
        state.last_stats = stats
        state.total_syncs = 1
        state.successful_syncs = 1
        state.source_path = "/test/source"
        state.destination = "test:backup"

        data = state.to_dict()

        assert data["last_sync_time"] == now.isoformat()
        assert data["last_successful_sync"] == now.isoformat()
        assert data["last_stats"] is not None
        assert data["last_stats"]["start_time"] == now.isoformat()
        assert data["last_stats"]["end_time"] == (now + timedelta(seconds=30)).isoformat()
        assert data["total_syncs"] == 1
        assert data["successful_syncs"] == 1
        assert data["source_path"] == "/test/source"
        assert data["destination"] == "test:backup"

    def test_backup_state_from_dict_empty(self):
        """Test BackupState from_dict creation with empty data."""
        data = {}
        state = BackupState.from_dict(data)

        assert state.last_sync_time is None
        assert state.last_successful_sync is None
        assert state.total_syncs == 0
        assert state.successful_syncs == 0

    def test_backup_state_from_dict_with_data(self):
        """Test BackupState from_dict creation with populated data."""
        now = datetime.now()
        data = {
            "last_sync_time": now.isoformat(),
            "last_successful_sync": now.isoformat(),
            "total_syncs": 5,
            "successful_syncs": 4,
            "failed_syncs": 1,
            "total_files_transferred": 100,
            "total_bytes_transferred": 10000,
            "total_sync_time": 150.0,
            "consecutive_failures": 0,
            "source_path": "/test/source",
            "destination": "test:backup",
            "error_history": [{"timestamp": now.isoformat(), "error": "test error"}],
        }

        state = BackupState.from_dict(data)

        assert state.last_sync_time == now
        assert state.last_successful_sync == now
        assert state.total_syncs == 5
        assert state.successful_syncs == 4
        assert state.failed_syncs == 1
        assert state.total_files_transferred == 100
        assert state.total_bytes_transferred == 10000
        assert state.total_sync_time == 150.0
        assert state.consecutive_failures == 0
        assert state.source_path == "/test/source"
        assert state.destination == "test:backup"
        assert len(state.error_history) == 1

    def test_backup_state_from_dict_with_stats(self):
        """Test BackupState from_dict creation with BackupStats data."""
        now = datetime.now()
        data = {
            "last_stats": {
                "start_time": now.isoformat(),
                "end_time": (now + timedelta(seconds=30)).isoformat(),
                "duration_seconds": 30.0,
                "files_transferred": 10,
                "files_total": 10,
                "bytes_transferred": 1000,
                "bytes_total": 1000,
                "errors": 0,
                "transfer_rate_mbps": 2.5,
                "files_rate_per_second": 0.33,
                "source_path": "/test/source",
                "destination": "test:backup",
                "dry_run": False,
                "test_mode": True,
                "success": True,
                "error_message": None,
                "detailed_errors": [],
                "error_summary": {},
            }
        }

        state = BackupState.from_dict(data)

        assert state.last_stats is not None
        assert state.last_stats.start_time == now
        assert state.last_stats.end_time == now + timedelta(seconds=30)
        assert state.last_stats.duration_seconds == 30.0
        assert state.last_stats.files_transferred == 10
        assert state.last_stats.success is True

    def test_backup_state_round_trip_serialization(self):
        """Test complete round-trip serialization."""
        now = datetime.now()
        stats = BackupStats(
            start_time=now,
            end_time=now + timedelta(seconds=45),
            duration_seconds=45.0,
            files_transferred=20,
            bytes_transferred=2000,
            success=True,
            source_path="/test/source2",
            destination="test:backup2",
        )

        original_state = BackupState()
        original_state.update_from_stats(stats)

        # Convert to dict and back
        data = original_state.to_dict()
        restored_state = BackupState.from_dict(data)

        # Verify all fields are preserved
        assert restored_state.last_sync_time is not None  # Will be set by update_from_stats
        assert restored_state.last_successful_sync is not None
        assert restored_state.total_syncs == 1
        assert restored_state.successful_syncs == 1
        assert restored_state.failed_syncs == 0
        assert restored_state.total_files_transferred == 20
        assert restored_state.total_bytes_transferred == 2000
        assert restored_state.source_path == "/test/source2"
        assert restored_state.destination == "test:backup2"

    def test_update_from_stats_successful(self):
        """Test updating state from successful backup stats."""
        stats = BackupStats(
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(seconds=60),
            duration_seconds=60.0,
            files_transferred=25,
            bytes_transferred=2500,
            success=True,
            source_path="/test/photos",
            destination="wasabi:backup",
        )

        state = BackupState()
        state.update_from_stats(stats)

        assert state.total_syncs == 1
        assert state.successful_syncs == 1
        assert state.failed_syncs == 0
        assert state.consecutive_failures == 0
        assert state.last_error is None
        assert state.total_files_transferred == 25
        assert state.total_bytes_transferred == 2500
        assert state.total_sync_time == 60.0
        assert state.source_path == "/test/photos"
        assert state.destination == "wasabi:backup"
        assert state.last_successful_sync is not None

    def test_update_from_stats_failed(self):
        """Test updating state from failed backup stats."""
        stats = BackupStats(
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(seconds=30),
            duration_seconds=30.0,
            files_transferred=0,
            bytes_transferred=0,
            success=False,
            error_message="Connection failed",
            source_path="/test/photos",
            destination="wasabi:backup",
        )

        state = BackupState()
        state.update_from_stats(stats)

        assert state.total_syncs == 1
        assert state.successful_syncs == 0
        assert state.failed_syncs == 1
        assert state.consecutive_failures == 1
        assert state.last_error == "Connection failed"
        assert state.total_files_transferred == 0
        assert state.total_bytes_transferred == 0
        assert state.total_sync_time == 0  # Don't count failed sync time in totals
        assert len(state.error_history) == 1
        assert state.error_history[0]["error"] == "Connection failed"

    def test_update_from_stats_multiple_operations(self):
        """Test updating state from multiple backup operations."""
        state = BackupState()

        # First successful backup
        stats1 = BackupStats(
            start_time=datetime.now(),
            duration_seconds=30.0,
            files_transferred=10,
            bytes_transferred=1000,
            success=True,
            source_path="/test/photos",
            destination="wasabi:backup",
        )
        state.update_from_stats(stats1)

        # Second failed backup
        stats2 = BackupStats(
            start_time=datetime.now(),
            duration_seconds=15.0,
            files_transferred=0,
            bytes_transferred=0,
            success=False,
            error_message="Permission denied",
            source_path="/test/photos",
            destination="wasabi:backup",
        )
        state.update_from_stats(stats2)

        # Third successful backup
        stats3 = BackupStats(
            start_time=datetime.now(),
            duration_seconds=45.0,
            files_transferred=15,
            bytes_transferred=1500,
            success=True,
            source_path="/test/photos",
            destination="wasabi:backup",
        )
        state.update_from_stats(stats3)

        assert state.total_syncs == 3
        assert state.successful_syncs == 2
        assert state.failed_syncs == 1
        assert state.consecutive_failures == 0  # Reset after successful backup
        assert state.last_error is None  # Cleared after successful backup
        assert state.total_files_transferred == 25  # Only successful backups count
        assert state.total_bytes_transferred == 2500
        assert state.total_sync_time == 75.0  # Only successful backups count
        assert len(state.error_history) == 1

    def test_error_history_limit(self):
        """Test that error history is limited to 10 entries."""
        state = BackupState()

        # Add 12 failed backups
        for i in range(12):
            stats = BackupStats(
                start_time=datetime.now(),
                duration_seconds=10.0,
                success=False,
                error_message=f"Error {i}",
                source_path="/test/photos",
                destination="wasabi:backup",
            )
            state.update_from_stats(stats)

        # Should only keep last 10 errors
        assert len(state.error_history) == 10
        assert state.error_history[0]["error"] == "Error 2"  # First 2 should be dropped
        assert state.error_history[-1]["error"] == "Error 11"
        assert state.consecutive_failures == 12


class TestStateManager:
    """Tests for StateManager class."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir

    def test_state_manager_init(self):
        """Test StateManager initialization."""
        manager = StateManager(test_mode=True)
        assert manager.test_mode is True
        assert manager.state_filename == "backup_state.json"
        assert manager.logger is not None

    def test_load_state_nonexistent(self):
        """Test loading state when no state file exists."""
        with patch("photo_backup.backup.state.load_json_state") as mock_load:
            mock_load.return_value = (None, "State file does not exist")

            manager = StateManager(test_mode=True)
            state = manager.load_state()

            assert isinstance(state, BackupState)
            assert state.total_syncs == 0
            mock_load.assert_called_once_with("backup_state.json", test_mode=True)

    def test_load_state_existing(self):
        """Test loading state from existing file."""
        now = datetime.now()
        state_data = {"last_sync_time": now.isoformat(), "total_syncs": 3, "successful_syncs": 2, "failed_syncs": 1}

        with patch("photo_backup.backup.state.load_json_state") as mock_load:
            mock_load.return_value = (state_data, None)

            manager = StateManager(test_mode=True)
            state = manager.load_state()

            assert state.total_syncs == 3
            assert state.successful_syncs == 2
            assert state.failed_syncs == 1
            assert state.last_sync_time == now

    def test_load_state_corrupted(self):
        """Test loading state when file is corrupted."""
        corrupted_data = {"invalid": "data structure"}

        with patch("photo_backup.backup.state.load_json_state") as mock_load:
            mock_load.return_value = (corrupted_data, None)

            manager = StateManager(test_mode=True)
            state = manager.load_state()

            # Should create new state when parsing fails
            assert isinstance(state, BackupState)
            assert state.total_syncs == 0

    def test_save_state(self):
        """Test saving state to file."""
        state = BackupState()
        state.total_syncs = 5

        with patch("photo_backup.backup.state.save_json_state") as mock_save:
            mock_save.return_value = (True, None)

            manager = StateManager(test_mode=True)
            success, error = manager.save_state(state)

            assert success is True
            assert error is None
            mock_save.assert_called_once()

            # Verify the data passed to save_json_state
            call_args = mock_save.call_args
            saved_data = call_args[0][0]  # First argument
            filename = call_args[0][1]  # Second argument
            test_mode = call_args[1]["test_mode"]  # Keyword argument

            assert saved_data["total_syncs"] == 5
            assert filename == "backup_state.json"
            assert test_mode is True

    def test_save_state_failure(self):
        """Test saving state when file operation fails."""
        state = BackupState()

        with patch("photo_backup.backup.state.save_json_state") as mock_save:
            mock_save.return_value = (False, "Permission denied")

            manager = StateManager(test_mode=True)
            success, error = manager.save_state(state)

            assert success is False
            assert error == "Permission denied"

    def test_save_state_serialization_error(self):
        """Test saving state when serialization fails."""
        # Create a state with problematic data
        state = BackupState()

        # Mock to_dict to raise an exception
        with patch.object(BackupState, "to_dict") as mock_to_dict:
            mock_to_dict.side_effect = Exception("Serialization failed")

            manager = StateManager(test_mode=True)
            success, error = manager.save_state(state)

            assert success is False
            assert "Failed to serialize state" in error

    def test_update_and_save_state(self):
        """Test updating and saving state in one operation."""
        stats = BackupStats(
            start_time=datetime.now(),
            duration_seconds=30.0,
            files_transferred=10,
            bytes_transferred=1000,
            success=True,
            source_path="/test/photos",
            destination="wasabi:backup",
        )

        # Mock load and save operations
        with (
            patch("photo_backup.backup.state.load_json_state") as mock_load,
            patch("photo_backup.backup.state.save_json_state") as mock_save,
        ):
            # Mock existing state
            existing_data = {"total_syncs": 2, "successful_syncs": 1}
            mock_load.return_value = (existing_data, None)
            mock_save.return_value = (True, None)

            manager = StateManager(test_mode=True)
            success, error = manager.update_and_save_state(stats)

            assert success is True
            assert error is None

            # Verify save was called with updated data
            call_args = mock_save.call_args
            saved_data = call_args[0][0]

            assert saved_data["total_syncs"] == 3  # Incremented from existing
            assert saved_data["successful_syncs"] == 2  # Incremented from existing

    def test_get_state_summary(self):
        """Test getting state summary."""
        now = datetime.now()
        state_data = {
            "last_sync_time": now.isoformat(),
            "last_successful_sync": now.isoformat(),
            "total_syncs": 10,
            "successful_syncs": 8,
            "failed_syncs": 2,
            "consecutive_failures": 0,
            "total_files_transferred": 1000,
            "total_bytes_transferred": 100000,
            "total_sync_time": 300.0,
            "last_error": None,
            "source_path": "/test/photos",
            "destination": "wasabi:backup",
        }

        with patch("photo_backup.backup.state.load_json_state") as mock_load:
            mock_load.return_value = (state_data, None)

            manager = StateManager(test_mode=True)
            summary = manager.get_state_summary()

            assert summary["total_syncs"] == 10
            assert summary["successful_syncs"] == 8
            assert summary["failed_syncs"] == 2
            assert summary["success_rate"] == 80.0
            assert summary["consecutive_failures"] == 0
            assert summary["total_files_transferred"] == 1000
            assert summary["total_bytes_transferred"] == 100000
            assert summary["total_sync_time"] == 300.0
            assert summary["last_error"] is None
            assert summary["source_path"] == "/test/photos"
            assert summary["destination"] == "wasabi:backup"

    def test_get_state_summary_empty(self):
        """Test getting state summary with no previous backups."""
        with patch("photo_backup.backup.state.load_json_state") as mock_load:
            mock_load.return_value = (None, "No state file")

            manager = StateManager(test_mode=True)
            summary = manager.get_state_summary()

            assert summary["total_syncs"] == 0
            assert summary["successful_syncs"] == 0
            assert summary["success_rate"] == 0

    def test_test_mode_flag_propagation(self):
        """Test that test_mode flag is properly propagated to state operations."""
        # Test production mode
        manager_prod = StateManager(test_mode=False)

        with patch("photo_backup.backup.state.load_json_state") as mock_load:
            mock_load.return_value = (None, "No state")
            manager_prod.load_state()
            mock_load.assert_called_with("backup_state.json", test_mode=False)

        # Test test mode
        manager_test = StateManager(test_mode=True)

        with patch("photo_backup.backup.state.load_json_state") as mock_load:
            mock_load.return_value = (None, "No state")
            manager_test.load_state()
            mock_load.assert_called_with("backup_state.json", test_mode=True)
