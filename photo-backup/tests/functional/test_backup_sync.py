"""
Functional tests for backup sync operations.

These tests verify that the backup system can successfully sync test photos
to Minio in test mode.
"""

import contextlib

import docker
import pytest

from photo_backup.backup import BackupEngine, BackupJob, BackupStats
from photo_backup.config.config import Config


class TestBackupSync:
    """Test backup sync functionality with real Minio."""

    MINIO_PORT = 9005  # Unique port for this test suite

    @pytest.fixture
    def minio_container(self):
        """Manage Minio container lifecycle for backup sync testing."""
        from tests.functional.minio_test_utils import MinioTestUtils

        client = MinioTestUtils.get_docker_client()
        if client is None:
            pytest.skip("Docker not available or not running")

        container_name = "photo-backup-sync-test"

        # Start or reuse container
        try:
            container = MinioTestUtils.start_or_reuse_minio(client, container_name, port=self.MINIO_PORT)
            # Wait for Minio to be ready
            MinioTestUtils.wait_for_minio_ready(container.name, port=self.MINIO_PORT)

            yield container.id

        finally:
            # Cleanup - stop AND remove container
            if client is not None:
                with contextlib.suppress(docker.errors.NotFound, docker.errors.APIError):
                    try:
                        container = client.containers.get(container_name)
                        container.stop(timeout=5)
                        container.remove(force=True)
                    except Exception:
                        pass

    def _get_test_config(self) -> Config:
        """Create test configuration with proper credentials."""
        config = Config(test_mode=True)
        config.load_config()
        # Configure credentials explicitly
        storage = config._config.setdefault("storage", {})
        storage["endpoint"] = f"localhost:{self.MINIO_PORT}"
        storage["access_key"] = "minioadmin"
        storage["secret_key"] = "minioadmin"
        storage["use_ssl"] = False
        storage["bucket"] = "test-bucket"
        return config

    def test_sync_test_photos_to_minio(self, minio_container, test_photos):  # noqa: ARG002
        """Test syncing test photos to Minio bucket."""
        # The minio_container fixture ensures Minio is running
        # Create backup engine with proper config
        config = self._get_test_config()
        engine = BackupEngine(config=config, test_mode=True)

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

    def test_sync_dry_run_with_minio(self, minio_container, test_photos):  # noqa: ARG002
        """Test dry run sync with Minio."""
        # The minio_container fixture ensures Minio is running
        # Create backup engine with proper config
        config = self._get_test_config()
        engine = BackupEngine(config=config, test_mode=True)

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

    def test_sync_nonexistent_source(self, minio_container):  # noqa: ARG002
        """Test sync with nonexistent source directory."""
        # The minio_container fixture ensures Minio is running
        # Create backup engine with proper config
        config = self._get_test_config()
        engine = BackupEngine(config=config, test_mode=True)

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

    def test_sync_command_structure(self, minio_container, test_photos):  # noqa: ARG002
        """Test that sync generates correct rclone command structure."""
        # The minio_container fixture ensures Minio is running
        # Create backup engine with proper config
        config = self._get_test_config()
        engine = BackupEngine(config=config, test_mode=True)

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

    def test_sync_with_progress_parsing(self, minio_container, test_photos):  # noqa: ARG002
        """Test sync with progress parsing functionality."""
        # The minio_container fixture ensures Minio is running
        # Create backup engine with proper config
        config = self._get_test_config()
        engine = BackupEngine(config=config, test_mode=True)

        # Create backup job
        job = BackupJob(
            source_path=str(test_photos),
            destination="minio-test:my-photo-backup-bucket-test",
            dry_run=True,  # Use dry run for predictable results
        )

        # Execute sync with progress
        success, output, sync_info, backup_stats = engine.sync_with_progress(job)

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

    def test_sync_with_backup_stats(self, minio_container, test_photos):  # noqa: ARG002
        """Test sync_with_stats method returns comprehensive BackupStats."""
        # The minio_container fixture ensures Minio is running
        # Create backup engine with proper config
        config = self._get_test_config()
        engine = BackupEngine(config=config, test_mode=True)

        # Create backup job
        job = BackupJob(
            source_path=str(test_photos),
            destination="minio-test:my-photo-backup-bucket-test",
            dry_run=False,
        )

        # Execute sync with stats
        backup_stats = engine.sync_with_stats(job)

        # Verify BackupStats object
        assert isinstance(backup_stats, BackupStats)
        assert backup_stats.source_path == str(test_photos)
        assert backup_stats.destination == "minio-test:my-photo-backup-bucket-test"
        assert backup_stats.dry_run is False
        assert backup_stats.test_mode is True
        assert backup_stats.success is True
        assert backup_stats.duration_seconds > 0
        assert backup_stats.start_time is not None
        assert backup_stats.end_time is not None

        # Verify transfer metrics (note: values may be 0 for very quick transfers or dry runs)
        assert backup_stats.files_transferred >= 0
        assert backup_stats.bytes_transferred >= 0
        assert backup_stats.transfer_rate_mbps >= 0
        assert backup_stats.files_rate_per_second >= 0

        # Verify formatting methods work
        assert backup_stats.formatted_duration != "0.0s"  # Duration should always be > 0

        # Verify summary generation
        summary = backup_stats.get_summary()
        assert "SUCCESS" in summary
        assert "TEST MODE" in summary

        # Verify dictionary conversion
        stats_dict = backup_stats.to_dict()
        assert stats_dict["success"] is True
        assert stats_dict["test_mode"] is True
        assert stats_dict["files_transferred"] >= 0
        assert stats_dict["bytes_transferred"] >= 0
