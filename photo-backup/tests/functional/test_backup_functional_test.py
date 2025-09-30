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

This is Task 62: Backup Functional Test - the final test for Phase 6.
"""

import contextlib
import os
import subprocess
import time

import docker
import pytest
from pathlib import Path

from photo_backup.backup import BackupEngine, BackupJob, BackupStats
from photo_backup.config.config import Config
from photo_backup.credentials.manager import CredentialManager
from tests.fixtures.photo_fixtures import generate_test_photos


class TestBackupFunctionalTest:
    """Comprehensive functional test for complete backup system."""

    @pytest.fixture
    def minio_container_management(self):
        """Manage Minio container lifecycle for functional testing."""
        client = docker.from_env()
        container_name = "photo-backup-functional-test"

        # Check if container already exists and is running
        try:
            existing_container = client.containers.get(container_name)
            if existing_container.status == "running":
                yield existing_container
                return
            else:
                existing_container.remove()
        except docker.errors.NotFound:
            pass

        # Start new container
        try:
            container = client.containers.run(
                "minio/minio:latest",
                command="server /data --console-address :9001",
                ports={"9000/tcp": 9000, "9001/tcp": 9001},
                environment={"MINIO_ROOT_USER": "minioadmin", "MINIO_ROOT_PASSWORD": "minioadmin"},
                name=container_name,
                detach=True,
                remove=True,
            )

            # Wait for Minio to be ready
            max_attempts = 30
            for _attempt in range(max_attempts):
                try:
                    # Test connection by checking if we can list buckets
                    result = subprocess.run(
                        [
                            "docker",
                            "exec",
                            container_name,
                            "mc",
                            "alias",
                            "set",
                            "test",
                            "http://localhost:9000",
                            "minioadmin",
                            "minioadmin",
                        ],
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    if result.returncode == 0:
                        break
                except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
                    pass
                time.sleep(2)
            else:
                pytest.fail("Minio container failed to start within timeout")

            yield container

        except docker.errors.DockerException as e:
            pytest.skip(f"Docker not available or Minio image not found: {e}")
        finally:
            # Cleanup
            try:
                container = client.containers.get(container_name)
                container.stop(timeout=5)
            except docker.errors.NotFound:
                pass

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

        credential_manager = CredentialManager(config=config)
        credential_status = credential_manager.get_credential_status()

        assert credential_status["available"], f"Credentials not available: {credential_status.get('error')}"
        assert credential_status["source"] == "test_mode"

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

        # Step 9: Verify files in Minio bucket (using rclone)
        verify_result = subprocess.run(
            ["rclone", "ls", "test:my-photo-backup-bucket-test", "--config", sync_info["config_file"]],
            capture_output=True,
            text=True,
            timeout=30,
        )

        assert verify_result.returncode == 0, f"Failed to verify files in bucket: {verify_result.stderr}"
        assert len(verify_result.stdout.strip().split("\n")) > 0, "No files found in bucket"

        # Step 10: Verify state summary
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
        engine = BackupEngine(config=config, test_mode=True)

        job = BackupJob(
            source_path=str(test_photos_path), destination="minio-test:my-photo-backup-bucket-test", dry_run=False
        )

        success, output, sync_info, backup_stats = engine.sync_with_progress(job)

        assert success, f"Backup failed: {output}"

        # Verify statistics accuracy
        assert backup_stats.files_transferred == file_count
        assert backup_stats.bytes_transferred == total_size
        assert backup_stats.files_total == file_count
        assert backup_stats.bytes_total == total_size
        assert backup_stats.percentage == 100.0

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

        # First backup
        engine1 = BackupEngine(config=config, test_mode=True)
        job1 = BackupJob(
            source_path=str(test_photos_path), destination="minio-test:my-photo-backup-bucket-test", dry_run=False
        )

        success1, _, _, stats1 = engine1.sync_with_progress(job1)
        assert success1, "First backup failed"

        # Get state after first backup
        state1 = engine1.get_backup_state()
        assert state1.total_syncs == 1
        assert state1.successful_syncs == 1
        assert state1.last_sync_time is not None

        # Create new engine instance (simulating restart)
        engine2 = BackupEngine(config=config, test_mode=True)
        state2 = engine2.get_backup_state()

        # Verify state persisted
        assert state2.total_syncs == state1.total_syncs
        assert state2.successful_syncs == state1.successful_syncs
        assert state2.last_sync_time == state1.last_sync_time
        assert state2.total_files_transferred == state1.total_files_transferred
        assert state2.total_bytes_transferred == state1.total_bytes_transferred

        # Second backup
        job2 = BackupJob(
            source_path=str(test_photos_path), destination="minio-test:my-photo-backup-bucket-test", dry_run=False
        )

        success2, _, _, stats2 = engine2.sync_with_progress(job2)
        assert success2, "Second backup failed"

        # Verify state updated
        state3 = engine2.get_backup_state()
        assert state3.total_syncs == 2
        assert state3.successful_syncs == 2
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
        engine = BackupEngine(config=config, test_mode=True)

        job = BackupJob(
            source_path=str(test_photos_path), destination="minio-test:my-photo-backup-bucket-test", dry_run=False
        )

        # Track progress events
        progress_events = []

        def progress_callback(stats):
            progress_events.append(stats)

        # Execute sync with progress callback
        success, output, sync_info, backup_stats = engine.sync_with_progress(job, progress_callback=progress_callback)

        assert success, f"Progress monitoring backup failed: {output}"

        # Verify progress events were captured
        assert len(progress_events) > 0, "No progress events captured"

        # Verify progress events have expected structure
        for event in progress_events:
            assert "files_transferred" in event
            assert "bytes_transferred" in event
            assert "percentage" in event
            assert event["files_transferred"] >= 0
            assert event["bytes_transferred"] >= 0
            assert 0 <= event["percentage"] <= 100

        # Verify final progress matches backup stats
        if progress_events:
            final_event = progress_events[-1]
            assert final_event["files_transferred"] == backup_stats.files_transferred
            assert final_event["bytes_transferred"] == backup_stats.bytes_transferred

    def test_backup_error_detection_and_categorization(self, minio_container_management, tmp_path):  # noqa: ARG002
        """Test error detection and categorization during backup."""
        config = Config(test_mode=True)
        config.load_config()
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
            # Should detect permission or file errors
            assert any(error_type in ["permission", "file", "unknown"] for error_type in error_types)

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
        backup_info = engine.get_backup_info()
        state_dir = backup_info.get("state_directory", "")
        assert "/tmp/photo-backup-test" in state_dir, "State directory not in test location"

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
