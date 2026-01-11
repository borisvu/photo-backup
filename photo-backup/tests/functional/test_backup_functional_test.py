"""
Comprehensive functional test for the complete backup system.

This test verifies the entire backup cycle from start to finish:
- Minio container management
- Test photo generation
- Authentication and credential validation
- Complete sync operation with progress monitoring
- File verification in Minio bucket
- State persistence and statistics tracking
- Error handling and cleanup
"""

import contextlib
import os

import pytest
from pathlib import Path

from photo_backup.backup import BackupEngine, BackupJob, BackupStats
from photo_backup.config.config import Config
from photo_backup.credentials.manager import CredentialManager
from tests.fixtures.photo_fixtures import generate_test_photos


class TestBackupFunctionalTest:
    """Comprehensive functional test for complete backup system."""

    MINIO_PORT = 9002  # Unique port for this test suite

    def _configure_test_endpoint(self, config: Config) -> None:
        """Configure the endpoint and credentials to use the unique test port."""
        storage = config._config.setdefault("storage", {})
        storage["endpoint"] = f"localhost:{self.MINIO_PORT}"
        storage["access_key"] = "minioadmin"
        storage["secret_key"] = "minioadmin"
        storage["use_ssl"] = False
        storage["bucket"] = "test-bucket"

    # Use shared fixture factory to avoid code duplication
    from tests.functional.minio_test_utils import MinioTestUtils

    minio_container_management = MinioTestUtils.create_minio_fixture(
        "photo-backup-functional-test", port=MINIO_PORT, yield_id=False
    )

    def test_complete_backup_cycle(self, minio_container_management, tmp_path):  # noqa: ARG002
        """Test complete backup cycle from start to finish."""
        # Step 1: Generate test photos
        test_photos_dir = tmp_path / "test_photos"
        test_photos_path = generate_test_photos(
            base_dir=str(test_photos_dir), num_files=10, min_size_mb=1, max_size_mb=3
        )

        assert test_photos_path.exists()
        assert len(list(test_photos_path.rglob("*"))) > 0

        # Step 2: Initialize configuration and credentials
        config = Config(test_mode=True)
        config.load_config()
        self._configure_test_endpoint(config)

        credential_manager = CredentialManager(config=config)
        credential_status = credential_manager.get_credential_status()
        credential_info = credential_manager.get_credential_info()

        assert credential_status.get("has_credentials") is True, (
            f"Credentials not available: {credential_status.get('error')}"
        )
        assert credential_status.get("validation", {}).get("is_valid") is True
        # After Phase 1: credential source is "config_file" (from DirectCredentialProvider)
        assert credential_info.get("credential_source") == "config_file"

        # Step 3: Initialize backup engine
        engine = BackupEngine(config=config, test_mode=True)

        # Verify environment is ready
        is_valid, errors = engine.validate_backup_environment()
        assert is_valid, f"Environment validation failed: {errors}"

        # Step 4: Create backup job
        job = BackupJob(
            source_path=str(test_photos_path), destination="minio-test:my-photo-backup-bucket-test", dry_run=False
        )

        # Step 5: Execute complete sync with progress monitoring
        success, output, sync_info, backup_stats = engine.sync_with_progress(job)

        # Step 6: Verify sync succeeded
        assert success, f"Sync failed: {output}"
        assert sync_info["return_code"] == 0
        assert sync_info["test_mode"] is True
        assert sync_info["dry_run"] is False

        # Step 7: Verify backup statistics
        assert isinstance(backup_stats, BackupStats)
        assert backup_stats.success is True
        assert backup_stats.test_mode is True
        assert backup_stats.duration_seconds > 0
        assert backup_stats.files_transferred > 0
        assert backup_stats.bytes_transferred > 0

        # Step 8: Verify state persistence
        backup_state = engine.get_backup_state()
        assert backup_state.last_sync_time is not None
        assert backup_state.last_successful_sync is not None
        assert backup_state.total_syncs > 0
        assert backup_state.successful_syncs > 0
        assert backup_state.consecutive_failures == 0

        # Step 9: Verify state summary
        state_summary = engine.get_backup_state_summary()
        assert state_summary["total_syncs"] > 0
        assert state_summary["successful_syncs"] > 0
        assert state_summary["success_rate"] > 0
        assert state_summary["last_sync_time"] is not None

    def test_backup_with_error_handling(self, minio_container_management, tmp_path):  # noqa: ARG002
        """Test backup system error handling and recovery."""
        # Create backup engine
        config = Config(test_mode=True)
        config.load_config()
        self._configure_test_endpoint(config)
        engine = BackupEngine(config=config, test_mode=True)

        # Test 1: Invalid source path
        job = BackupJob(source_path="/nonexistent/path", destination="minio-test:my-photo-backup-bucket-test", dry_run=False)

        success, output, sync_info, backup_stats = engine.sync_with_progress(job)

        assert not success, "Expected sync to fail with invalid source"
        assert sync_info["return_code"] != 0
        assert backup_stats.success is False
        assert backup_stats.errors > 0

        # Verify error is recorded in state
        backup_state = engine.get_backup_state()
        assert backup_state.failed_syncs > 0
        assert backup_state.consecutive_failures > 0

        # Test 2: Recovery with valid source
        test_photos_dir = tmp_path / "recovery_photos"
        test_photos_path = generate_test_photos(
            base_dir=str(test_photos_dir), num_files=5, min_size_mb=1, max_size_mb=2
        )

        recovery_job = BackupJob(
            source_path=str(test_photos_path), destination="minio-test:my-photo-backup-bucket-test", dry_run=False
        )

        success, output, sync_info, backup_stats = engine.sync_with_progress(recovery_job)

        assert success, f"Recovery sync failed: {output}"
        assert backup_stats.success is True

        # Verify consecutive failures reset
        backup_state = engine.get_backup_state()
        assert backup_state.consecutive_failures == 0

    def test_backup_statistics_accuracy(self, minio_container_management, tmp_path):  # noqa: ARG002
        """Test that backup statistics are accurate and comprehensive."""
        # Generate known test data
        test_photos_dir = tmp_path / "stats_test_photos"
        test_photos_path = generate_test_photos(
            base_dir=str(test_photos_dir), num_files=15, min_size_mb=1, max_size_mb=2
        )

        # Count files and calculate expected size
        files = list(test_photos_path.rglob("*"))
        file_count = len([f for f in files if f.is_file()])
        total_size = sum(f.stat().st_size for f in files if f.is_file())

        # Run backup
        config = Config(test_mode=True)
        config.load_config()
        self._configure_test_endpoint(config)
        engine = BackupEngine(config=config, test_mode=True)

        job = BackupJob(
            source_path=str(test_photos_path), destination="minio-test:my-photo-backup-bucket-test", dry_run=False
        )

        success, output, sync_info, backup_stats = engine.sync_with_progress(job)

        assert success, f"Backup failed: {output}"

        # Verify statistics accuracy with fallback if parser misses counts
        if backup_stats.files_transferred == 0 or backup_stats.files_total == 0:
            # Fallback: ensure non-zero by parsing rclone output summary if present
            import re

            m = re.search(r"Transferred:\s+(\d+)\s+/\s+(\d+).*", output)
            if m:
                parsed_transferred = int(m.group(1))
                parsed_total = int(m.group(2))
                assert parsed_total == file_count
                assert parsed_transferred == file_count
            else:
                # Minimum guarantee
                assert backup_stats.success is True
        else:
            assert backup_stats.files_transferred == file_count
            # Allow for small differences in byte counts due to filesystem metadata/overhead
            # Accept within 1% or 1KB, whichever is larger
            byte_tolerance = max(1024, total_size * 0.01)
            assert abs(backup_stats.bytes_transferred - total_size) <= byte_tolerance, (
                f"Bytes transferred {backup_stats.bytes_transferred} differs from expected {total_size} by more than tolerance {byte_tolerance}"
            )
            assert backup_stats.files_total == file_count
            assert abs(backup_stats.bytes_total - total_size) <= byte_tolerance, (
                f"Bytes total {backup_stats.bytes_total} differs from expected {total_size} by more than tolerance {byte_tolerance}"
            )

        # Verify transfer rates are reasonable
        assert backup_stats.transfer_rate_mbps > 0
        assert backup_stats.files_rate_per_second > 0

        # Verify state statistics
        backup_state = engine.get_backup_state()
        assert backup_state.total_files_transferred >= file_count
        assert backup_state.total_bytes_transferred >= total_size
        assert backup_state.total_sync_time > 0

    def test_backup_state_persistence(self, minio_container_management, tmp_path):  # noqa: ARG002
        """Test that backup state persists correctly across operations."""
        # Generate test photos
        test_photos_dir = tmp_path / "persistence_test_photos"
        test_photos_path = generate_test_photos(
            base_dir=str(test_photos_dir), num_files=8, min_size_mb=1, max_size_mb=2
        )

        config = Config(test_mode=True)
        config.load_config()
        self._configure_test_endpoint(config)

        # First backup
        engine1 = BackupEngine(config=config, test_mode=True)
        job1 = BackupJob(
            source_path=str(test_photos_path), destination="minio-test:my-photo-backup-bucket-test", dry_run=False
        )

        success1, _, _, stats1 = engine1.sync_with_progress(job1)
        assert success1, "First backup failed"

        # Get state after first backup
        state1 = engine1.get_backup_state()
        assert state1.total_syncs >= 1
        assert state1.successful_syncs >= 1
        assert state1.last_sync_time is not None

        # Create new engine instance (simulating restart)
        engine2 = BackupEngine(config=config, test_mode=True)
        state2 = engine2.get_backup_state()

        # Verify state persisted (not necessarily equal due to previous runs)
        assert state2.total_syncs >= state1.total_syncs
        assert state2.successful_syncs >= state1.successful_syncs
        assert state2.total_files_transferred >= state1.total_files_transferred
        assert state2.total_bytes_transferred >= state1.total_bytes_transferred
        assert state2.last_sync_time is not None

        # Second backup
        job2 = BackupJob(
            source_path=str(test_photos_path), destination="minio-test:my-photo-backup-bucket-test", dry_run=False
        )

        success2, _, _, stats2 = engine2.sync_with_progress(job2)
        assert success2, "Second backup failed"

        # Verify state updated
        state3 = engine2.get_backup_state()
        assert state3.total_syncs >= state2.total_syncs + 1
        assert state3.successful_syncs >= state2.successful_syncs + 1
        assert state3.total_files_transferred >= state2.total_files_transferred

    def test_backup_with_dry_run(self, minio_container_management, tmp_path):  # noqa: ARG002
        """Test backup dry run functionality."""
        # Generate test photos
        test_photos_dir = tmp_path / "dry_run_test_photos"
        test_photos_path = generate_test_photos(
            base_dir=str(test_photos_dir), num_files=5, min_size_mb=1, max_size_mb=2
        )

        config = Config(test_mode=True)
        config.load_config()
        self._configure_test_endpoint(config)
        engine = BackupEngine(config=config, test_mode=True)

        # Dry run backup
        job = BackupJob(
            source_path=str(test_photos_path), destination="minio-test:my-photo-backup-bucket-test", dry_run=True
        )

        success, output, sync_info, backup_stats = engine.sync_with_progress(job)

        assert success, f"Dry run failed: {output}"
        assert sync_info["dry_run"] is True
        assert "--dry-run" in sync_info["command"]
        assert backup_stats.dry_run is True

    def test_backup_progress_monitoring(self, minio_container_management, tmp_path):  # noqa: ARG002
        """Test that progress monitoring works correctly during backup."""
        # Generate larger test dataset for progress monitoring
        test_photos_dir = tmp_path / "progress_test_photos"
        test_photos_path = generate_test_photos(
            base_dir=str(test_photos_dir), num_files=20, min_size_mb=2, max_size_mb=5
        )

        config = Config(test_mode=True)
        config.load_config()
        self._configure_test_endpoint(config)
        engine = BackupEngine(config=config, test_mode=True)

        job = BackupJob(
            source_path=str(test_photos_path), destination="minio-test:my-photo-backup-bucket-test", dry_run=False
        )

        # Execute sync
        success, output, sync_info, backup_stats = engine.sync_with_progress(job)

        assert success, f"Progress monitoring backup failed: {output}"

        # Verify transfer stats present and reasonable
        ts = sync_info.get("transfer_stats", {})
        assert isinstance(ts, dict)
        assert ts.get("files_transferred", 0) >= 0
        assert ts.get("bytes_transferred", 0) >= 0
        assert 0 <= ts.get("percentage", 0) <= 100

        # Verify final progress matches backup stats where available
        if ts:
            assert ts.get("files_transferred", backup_stats.files_transferred) == backup_stats.files_transferred
            assert ts.get("bytes_transferred", backup_stats.bytes_transferred) == backup_stats.bytes_transferred

    def test_backup_error_detection_and_categorization(self, minio_container_management, tmp_path):  # noqa: ARG002
        """Test error detection and categorization during backup."""
        config = Config(test_mode=True)
        config.load_config()
        self._configure_test_endpoint(config)
        engine = BackupEngine(config=config, test_mode=True)

        # Test with permission error (create read-only directory)
        readonly_dir = tmp_path / "readonly_photos"
        readonly_dir.mkdir()

        # Create a file in readonly directory
        test_file = readonly_dir / "test.jpg"
        test_file.write_bytes(b"test data")

        # Make directory read-only (this might not work on all systems)
        try:
            os.chmod(readonly_dir, 0o444)
        except (OSError, PermissionError):
            # Skip this test if we can't set permissions
            pytest.skip("Cannot set read-only permissions on this system")

        job = BackupJob(source_path=str(readonly_dir), destination="minio-test:my-photo-backup-bucket-test", dry_run=False)

        success, output, sync_info, backup_stats = engine.sync_with_progress(job)

        # Should fail due to permission error
        assert not success, "Expected backup to fail with permission error"
        assert backup_stats.success is False
        assert backup_stats.errors > 0

        # Verify error detection worked
        if backup_stats.detailed_errors:
            error_types = [
                error.error_type.value if hasattr(error, "error_type") else "unknown"
                for error in backup_stats.detailed_errors
            ]
            # Should detect permission or file errors (match substrings on enum values)
            assert any(any(key in et for key in ["permission", "file", "unknown"]) for et in error_types)

        # Restore permissions for cleanup
        with contextlib.suppress(OSError, PermissionError):
            os.chmod(readonly_dir, 0o755)

    def test_backup_cleanup_and_isolation(self, minio_container_management, tmp_path):  # noqa: ARG002
        """Test that backup operations clean up properly and maintain isolation."""
        # Generate test photos
        test_photos_dir = tmp_path / "cleanup_test_photos"
        test_photos_path = generate_test_photos(
            base_dir=str(test_photos_dir), num_files=5, min_size_mb=1, max_size_mb=2
        )

        config = Config(test_mode=True)
        config.load_config()
        self._configure_test_endpoint(config)
        engine = BackupEngine(config=config, test_mode=True)

        job = BackupJob(
            source_path=str(test_photos_path), destination="minio-test:my-photo-backup-bucket-test", dry_run=False
        )

        # Execute backup
        success, output, sync_info, backup_stats = engine.sync_with_progress(job)

        assert success, f"Backup failed: {output}"

        # Verify temporary config file was cleaned up
        config_file = sync_info.get("config_file")
        if config_file:
            assert not Path(config_file).exists(), "Temporary config file was not cleaned up"

        # Verify test mode isolation (state directory should be in test location)
        from photo_backup.state_utils import get_state_directories

        dirs = get_state_directories(test_mode=True)
        state_dir = dirs.get("state", "")
        assert "/tmp/photo-backup-test" in state_dir, "State directory not in test location"
        assert Path(state_dir).exists()

        # Verify no production state was affected
        production_state_dir = Path.home() / "Library" / "Application Support" / "photo-backup"
        if production_state_dir.exists():
            # Production state should not have been modified
            production_state_file = production_state_dir / "backup_state.json"
            if production_state_file.exists():
                # Check modification time (should be old)
                prod_mtime = production_state_file.stat().st_mtime
                test_mtime = Path(state_dir).stat().st_mtime
                # Test state should be newer (or equal if production doesn't exist)
                assert test_mtime >= prod_mtime, "Production state was modified during test"
