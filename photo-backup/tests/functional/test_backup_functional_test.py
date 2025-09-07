#!/usr/bin/env python3
"""
Functional test for Task 62: Complete backup cycle test.

This test implements the full backup cycle:
- Start Minio
- Create test photos
- Authenticate
- Run sync
- Verify files in Minio
- Save state
"""

import os
import subprocess
import tempfile

import pytest
from pathlib import Path


class TestBackupFunctionalTest:
    """Functional test for complete backup cycle (Task 62)."""

    def test_complete_backup_cycle_task_62(self):
        """Test complete backup cycle as specified in Task 62.

        This test covers all the steps mentioned in Task 62:
        - Start Minio (use existing container)
        - Create test photos
        - Authenticate
        - Run sync
        - Verify files in Minio
        - Save state
        """
        # Step 1: Start Minio (check if already running)
        try:
            result = subprocess.run(
                ["curl", "-s", "http://localhost:9000/minio/health/live"], capture_output=True, timeout=5
            )
            if result.returncode != 0:
                pytest.skip("Minio container is not running on localhost:9000")
        except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
            pytest.skip("Minio container is not accessible on localhost:9000")

        # Step 2: Create test photos
        with tempfile.TemporaryDirectory() as temp_dir:
            photos_dir = Path(temp_dir) / "test_photos"
            photos_dir.mkdir()

            # Create test photo files with realistic structure
            test_files = [
                "2023/01/IMG_001.jpg",
                "2023/01/IMG_002.jpg",
                "2023/02/IMG_003.jpg",
                "2023/02/vacation/IMG_004.jpg",
                "2023/02/vacation/IMG_005.jpg",
                "2023/03/family/IMG_006.jpg",
                "2023/03/family/IMG_007.jpg",
            ]

            for file_path in test_files:
                full_path = photos_dir / file_path
                full_path.parent.mkdir(parents=True, exist_ok=True)
                # Create files with some content
                full_path.write_text(f"Test photo content for {file_path}")

            # Set up environment variables for test mode
            env = os.environ.copy()
            env.update(
                {
                    "PHOTO_BACKUP_BACKUP_SOURCE_PATH": str(photos_dir),
                    "PHOTO_BACKUP_STORAGE_ACCESS_KEY": "minioadmin",
                    "PHOTO_BACKUP_STORAGE_SECRET_KEY": "minioadmin",
                    "PHOTO_BACKUP_STORAGE_ENDPOINT": "localhost:9000",
                    "PHOTO_BACKUP_BACKUP_DESTINATION": "minio-test:my-photo-backup-bucket-test",
                }
            )

            # Step 3: Authenticate
            auth_result = subprocess.run(
                ["python3", "-m", "photo_backup.main", "--test-mode", "test-auth"],
                capture_output=True,
                text=True,
                cwd=".",
                env=env,
            )
            assert auth_result.returncode == 0, f"Authentication failed: {auth_result.stderr}"
            assert "Authentication test completed successfully" in auth_result.stdout

            # Step 4: Run sync (dry-run first to verify setup)
            dry_run_result = subprocess.run(
                ["python3", "-m", "photo_backup.main", "--test-mode", "--dry-run", "sync"],
                capture_output=True,
                text=True,
                cwd=".",
                env=env,
            )
            assert dry_run_result.returncode == 0, f"Dry run failed: {dry_run_result.stderr}"
            assert "DRY RUN MODE" in dry_run_result.stdout

            # Step 5: Run actual sync
            sync_result = subprocess.run(
                ["python3", "-m", "photo_backup.main", "--test-mode", "sync"],
                capture_output=True,
                text=True,
                cwd=".",
                env=env,
            )
            assert sync_result.returncode == 0, f"Sync failed: {sync_result.stderr}"
            assert "Backup completed successfully" in sync_result.stdout or "Sync completed" in sync_result.stdout

            # Step 6: Verify files in Minio using rclone
            verify_cmd = ["rclone", "ls", "minio-test:my-photo-backup-bucket-test", "--config", "/dev/null"]

            # Set up rclone config for verification
            rclone_config = """[minio-test]
type = s3
provider = Minio
access_key_id = minioadmin
secret_access_key = minioadmin
endpoint = http://localhost:9000
"""

            with tempfile.NamedTemporaryFile(mode="w", suffix=".conf", delete=False) as config_file:
                config_file.write(rclone_config)
                config_file.flush()

                try:
                    verify_result = subprocess.run(
                        [*verify_cmd, "--config", config_file.name], capture_output=True, text=True, timeout=30
                    )

                    assert verify_result.returncode == 0, f"File verification failed: {verify_result.stderr}"

                    # Check that our test files are present
                    file_list = verify_result.stdout
                    expected_files = [
                        "IMG_001.jpg",
                        "IMG_002.jpg",
                        "IMG_003.jpg",
                        "vacation/IMG_004.jpg",
                        "vacation/IMG_005.jpg",
                        "family/IMG_006.jpg",
                        "family/IMG_007.jpg",
                    ]

                    for expected_file in expected_files:
                        assert expected_file in file_list, f"Expected file {expected_file} not found in backup"

                finally:
                    os.unlink(config_file.name)

            # Step 7: Save state (check that state was saved)
            status_result = subprocess.run(
                ["python3", "-m", "photo_backup.main", "--test-mode", "status"],
                capture_output=True,
                text=True,
                cwd=".",
                env=env,
            )
            assert status_result.returncode == 0
            assert "Last Sync:" in status_result.stdout
            assert "Total Syncs:" in status_result.stdout
            assert "Successful:" in status_result.stdout

            # Verify that the backup was recorded in state
            assert "Total Syncs:" in status_result.stdout
            # The sync count should be at least 1 (our test sync)
            import re

            sync_count_match = re.search(r"Total Syncs: (\d+)", status_result.stdout)
            assert sync_count_match is not None, "Could not find Total Syncs count in status output"
            sync_count = int(sync_count_match.group(1))
            assert sync_count >= 1, f"Expected at least 1 sync, but found {sync_count}"
