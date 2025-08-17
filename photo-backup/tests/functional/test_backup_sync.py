"""
Functional tests for backup sync operations.

These tests verify that the backup system can successfully sync test photos
to Minio in test mode.
"""

import pytest

from photo_backup.backup import BackupEngine, BackupJob


@pytest.fixture
def _minio_container(minio_container):
    """Alias for minio_container fixture to satisfy ruff ARG002."""
    return minio_container


class TestBackupSync:
    """Test backup sync functionality with real Minio."""

    def test_sync_test_photos_to_minio(self, _minio_container, test_photos):
        """Test syncing test photos to Minio bucket."""
        # The _minio_container fixture ensures Minio is running
        # Create backup engine in test mode
        engine = BackupEngine(test_mode=True)

        # Verify environment is ready
        is_valid, errors = engine.validate_backup_environment()
        assert is_valid, f"Environment validation failed: {errors}"

        # Create backup job with test photos
        job = BackupJob(
            source_path=str(test_photos),
            destination="minio-test:my-photo-backup-bucket-test",
            dry_run=False,  # Actually perform the sync
        )

        # Execute sync
        success, output, sync_info = engine.sync(job)

        # Verify sync succeeded
        assert success, f"Sync failed: {output}"
        assert sync_info["return_code"] == 0
        assert sync_info["test_mode"] is True
        assert sync_info["dry_run"] is False

        # Verify timing information
        assert "duration_seconds" in sync_info
        assert sync_info["duration_seconds"] > 0

        # Verify job status updated
        assert job.status == "completed"
        assert job.error is None

        # Verify output contains transfer information
        assert "STDOUT:" in output
        # Should show some transfer activity (exact output depends on photos)

    def test_sync_dry_run_with_minio(self, _minio_container, test_photos):
        """Test dry run sync with Minio."""
        # The _minio_container fixture ensures Minio is running
        # Create backup engine in test mode
        engine = BackupEngine(test_mode=True)

        # Create backup job with dry run
        job = BackupJob(source_path=str(test_photos), destination="minio-test:my-photo-backup-bucket-test", dry_run=True)

        # Execute sync
        success, output, sync_info = engine.sync(job)

        # Verify dry run succeeded
        assert success, f"Dry run failed: {output}"
        assert sync_info["return_code"] == 0
        assert sync_info["dry_run"] is True

        # Verify dry run flag was used in command
        assert "--dry-run" in sync_info["command"]

        # Verify job status updated
        assert job.status == "completed"

    def test_sync_nonexistent_source(self, _minio_container):
        """Test sync with nonexistent source directory."""
        # The _minio_container fixture ensures Minio is running
        # Create backup engine in test mode
        engine = BackupEngine(test_mode=True)

        # Create backup job with nonexistent source
        job = BackupJob(source_path="/nonexistent/path", destination="minio-test:my-photo-backup-bucket-test", dry_run=False)

        # Execute sync
        success, output, sync_info = engine.sync(job)

        # Verify sync failed as expected
        assert not success
        assert sync_info["return_code"] != 0

        # Verify job status reflects error
        assert job.status == "error"
        assert job.error is not None

        # Verify error output contains meaningful information
        assert "STDERR:" in output

    def test_sync_command_structure(self, _minio_container, test_photos):
        """Test that sync generates correct rclone command structure."""
        # The _minio_container fixture ensures Minio is running
        # Create backup engine in test mode
        engine = BackupEngine(test_mode=True)

        # Create backup job
        job = BackupJob(source_path=str(test_photos), destination="minio-test:my-photo-backup-bucket-test", dry_run=True)

        # Execute sync
        success, output, sync_info = engine.sync(job)

        # Verify command structure
        command = sync_info["command"]

        # Basic command structure
        assert command[0] == "rclone"
        assert command[1] == "sync"
        assert command[2] == str(test_photos)
        assert command[3] == "test:my-photo-backup-bucket-test"

        # Key options should be present
        assert "--config" in command
        assert "--transfers" in command
        assert "--checkers" in command
        assert "--stats" in command
        assert "--dry-run" in command  # Since job.dry_run is True

        # Config file should be temporary
        config_index = command.index("--config") + 1
        config_file = command[config_index]
        assert config_file.endswith(".conf")
        assert "tmp" in config_file.lower()

    def test_sync_with_progress_parsing(self, _minio_container, test_photos):
        """Test sync with progress parsing functionality."""
        # The _minio_container fixture ensures Minio is running
        # Create backup engine in test mode
        engine = BackupEngine(test_mode=True)

        # Create backup job
        job = BackupJob(
            source_path=str(test_photos),
            destination="minio-test:my-photo-backup-bucket-test",
            dry_run=True,  # Use dry run for predictable results
        )

        # Execute sync with progress
        success, output, sync_info = engine.sync_with_progress(job)

        # Verify sync succeeded
        assert success, f"Sync with progress failed: {output}"
        assert sync_info["return_code"] == 0

        # Verify progress statistics are included
        assert "transfer_stats" in sync_info
        transfer_stats = sync_info["transfer_stats"]

        # Check that transfer statistics structure is correct
        assert "files_transferred" in transfer_stats
        assert "files_total" in transfer_stats
        assert "bytes_transferred" in transfer_stats
        assert "bytes_total" in transfer_stats
        assert "transfer_rate_mbps" in transfer_stats
        assert "percentage" in transfer_stats
        assert "errors" in transfer_stats

        # Verify that transfer stats are reasonable (values depend on rclone output)
        assert transfer_stats["files_transferred"] >= 0
        assert transfer_stats["files_total"] >= 0
        assert transfer_stats["bytes_transferred"] >= 0
        assert transfer_stats["bytes_total"] >= 0
        assert transfer_stats["percentage"] >= 0.0
        assert transfer_stats["errors"] >= 0
