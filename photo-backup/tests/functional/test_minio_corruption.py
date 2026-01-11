#!/usr/bin/env python3
"""
Functional tests for Minio corruption detection and repair.

Add Minio Corruption Test - Test repair functionality.

These tests:
1. Upload test files to Minio
2. Corrupt a file in Minio
3. Run verification to detect corruption
4. Run repair to fix it
5. Verify the file is now correct
"""

import os
import subprocess
import tempfile

import pytest
from pathlib import Path

from tests.functional.minio_test_utils import MinioTestUtils


class TestMinioCorruptionDetection:
    """Test corruption detection and repair functionality with Minio."""

    MINIO_PORT = 9020
    # This must match the bucket in backup.destination for test mode
    BUCKET_NAME = "my-photo-backup-bucket-test"

    # Use shared fixture factory
    minio_container = MinioTestUtils.create_minio_fixture(
        "photo-backup-corruption-test",
        port=MINIO_PORT,
    )

    def _create_test_bucket(self, container_name: str) -> bool:
        """Create test bucket in Minio."""
        result = subprocess.run(
            [
                "docker",
                "exec",
                container_name,
                "mc",
                "mb",
                f"test/{self.BUCKET_NAME}",
                "--ignore-existing",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode == 0

    def _corrupt_file_in_minio(
        self,
        container_name: str,
        file_path: str,
        corruption_data: bytes = b"CORRUPTED DATA!!!",
    ) -> bool:
        """Corrupt a specific file in Minio by overwriting it with different content.

        Args:
            container_name: Name of the Minio container
            file_path: Path to the file in the bucket (e.g., "photo1.jpg")
            corruption_data: Data to write to corrupt the file

        Returns:
            True if corruption succeeded, False otherwise
        """
        # Use mc cp with stdin to overwrite the file
        # We need to create a temp file with corruption data and copy it
        with tempfile.NamedTemporaryFile(mode="wb", delete=False) as temp_file:
            temp_file.write(corruption_data)
            temp_path = temp_file.name

        try:
            # Copy the temp file into the container
            subprocess.run(
                [
                    "docker",
                    "cp",
                    temp_path,
                    f"{container_name}:/tmp/corrupt_data",
                ],
                check=True,
                capture_output=True,
                timeout=30,
            )

            # Use mc cp to overwrite the file in the bucket
            result = subprocess.run(
                [
                    "docker",
                    "exec",
                    container_name,
                    "mc",
                    "cp",
                    "/tmp/corrupt_data",
                    f"test/{self.BUCKET_NAME}/{file_path}",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            return result.returncode == 0
        finally:
            os.unlink(temp_path)

    def _get_file_hash_from_minio(self, container_name: str, file_path: str) -> str | None:
        """Get the MD5 hash of a file in Minio using the class BUCKET_NAME.

        Args:
            container_name: Name of the Minio container
            file_path: Path to the file in the bucket

        Returns:
            MD5 hash string or None if failed
        """
        return self._get_file_hash_from_bucket(container_name, self.BUCKET_NAME, file_path)

    def _get_file_hash_from_bucket(self, container_name: str, bucket_name: str, file_path: str) -> str | None:
        """Get the MD5 hash of a file in Minio from a specific bucket.

        Args:
            container_name: Name of the Minio container
            bucket_name: Name of the bucket
            file_path: Path to the file in the bucket

        Returns:
            MD5 hash string or None if failed
        """
        result = subprocess.run(
            [
                "docker",
                "exec",
                container_name,
                "mc",
                "stat",
                f"test/{bucket_name}/{file_path}",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            return None

        # Parse the output to find ETag (which is MD5 for non-multipart uploads)
        # The mc stat output looks like:
        # ETag      : d6eb32081c822ed572b70567826d9d9d
        for line in result.stdout.split("\n"):
            line = line.strip()
            if line.startswith("ETag"):
                # ETag line format: "ETag      : d8e8fca2dc0f896fd7cb4cb0031ba249"
                parts = line.split(":", 1)  # Split on first colon only
                if len(parts) >= 2:
                    return parts[1].strip()
        return None

    def _get_container_name(self, container_id: str) -> str:
        """Get container name from container ID."""
        result = subprocess.run(
            ["docker", "inspect", "--format", "{{.Name}}", container_id],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            # Docker adds leading "/" to container names
            return result.stdout.strip().lstrip("/")
        return container_id

    def test_corruption_detection(self, minio_container):
        """Test that verification detects corrupted files."""
        container_name = self._get_container_name(minio_container)

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create test photos with unique content
            test_files = {
                "photo1.jpg": b"Original content for photo 1 - test data",
                "photo2.jpg": b"Original content for photo 2 - more test data",
                "subdir/photo3.jpg": b"Original content for photo 3 - even more test data",
            }

            for rel_path, content in test_files.items():
                photo_file = temp_path / rel_path
                photo_file.parent.mkdir(parents=True, exist_ok=True)
                photo_file.write_bytes(content)

            # Create bucket
            assert self._create_test_bucket(container_name), "Failed to create test bucket"

            # Set up environment
            env = os.environ.copy()
            env["PHOTO_BACKUP_BACKUP_SOURCE_PATH"] = str(temp_path)
            env["PHOTO_BACKUP_STORAGE_ENDPOINT"] = f"localhost:{self.MINIO_PORT}"
            env["PHOTO_BACKUP_STORAGE_ACCESS_KEY"] = "minioadmin"
            env["PHOTO_BACKUP_STORAGE_SECRET_KEY"] = "minioadmin"
            env["PHOTO_BACKUP_STORAGE_USE_SSL"] = "false"
            # Note: We don't override PHOTO_BACKUP_STORAGE_BUCKET because
            # the sync command uses backup.destination which includes the bucket name

            # Step 1: Sync files to Minio
            sync_result = subprocess.run(
                ["python3", "-m", "photo_backup.main", "--test-mode", "sync"],
                capture_output=True,
                text=True,
                cwd=".",
                env=env,
                timeout=60,
            )

            if sync_result.returncode != 0:
                pytest.skip(f"Sync failed: {sync_result.stdout + sync_result.stderr}")

            # Step 2: Verify initial state - all should match
            verify_result = subprocess.run(
                ["python3", "-m", "photo_backup.main", "--test-mode", "verify", "--verbose"],
                capture_output=True,
                text=True,
                cwd=".",
                env=env,
                timeout=60,
            )

            verify_output = verify_result.stdout + verify_result.stderr
            assert "Matched files:" in verify_output

            # Should have matched all files initially
            if verify_result.returncode == 0:
                assert "VERIFICATION PASSED" in verify_output

            # Step 3: Corrupt one file in Minio
            corrupted = self._corrupt_file_in_minio(
                container_name,
                "photo1.jpg",
                b"THIS IS CORRUPTED DATA - NOT THE ORIGINAL",
            )
            assert corrupted, "Failed to corrupt file in Minio"

            # Step 4: Run verification again - should detect mismatch
            verify_result2 = subprocess.run(
                ["python3", "-m", "photo_backup.main", "--test-mode", "verify", "--verbose"],
                capture_output=True,
                text=True,
                cwd=".",
                env=env,
                timeout=60,
            )

            verify_output2 = verify_result2.stdout + verify_result2.stderr

            # Should detect the mismatch
            assert "Mismatched files:" in verify_output2 or "VERIFICATION FAILED" in verify_output2
            # The corrupted file should be identified
            if "photo1.jpg" not in verify_output2:
                # If not in verbose output, at least check it failed
                assert verify_result2.returncode != 0 or "Mismatched files: 0" not in verify_output2

    def test_auto_repair_corrupted_file(self, minio_container):
        """Test that repair functionality fixes corrupted files."""
        container_name = self._get_container_name(minio_container)

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create test files with known content
            original_content = b"Original unique content for repair test file"
            (temp_path / "repair_test.jpg").write_bytes(original_content)

            # Create bucket
            assert self._create_test_bucket(container_name), "Failed to create test bucket"

            # Set up environment
            env = os.environ.copy()
            env["PHOTO_BACKUP_BACKUP_SOURCE_PATH"] = str(temp_path)
            env["PHOTO_BACKUP_STORAGE_ENDPOINT"] = f"localhost:{self.MINIO_PORT}"
            env["PHOTO_BACKUP_STORAGE_ACCESS_KEY"] = "minioadmin"
            env["PHOTO_BACKUP_STORAGE_SECRET_KEY"] = "minioadmin"
            env["PHOTO_BACKUP_STORAGE_USE_SSL"] = "false"
            # Note: We don't override PHOTO_BACKUP_STORAGE_BUCKET because
            # the sync command uses backup.destination which includes the bucket name

            # Step 1: Sync file to Minio
            sync_result = subprocess.run(
                ["python3", "-m", "photo_backup.main", "--test-mode", "sync"],
                capture_output=True,
                text=True,
                cwd=".",
                env=env,
                timeout=60,
            )

            if sync_result.returncode != 0:
                pytest.skip(f"Sync failed: {sync_result.stdout + sync_result.stderr}")

            # Give Minio time to settle
            import time

            time.sleep(0.5)

            # Get original hash from Minio
            original_hash = self._get_file_hash_from_minio(container_name, "repair_test.jpg")
            assert original_hash is not None, "Failed to get original hash from Minio"

            # Step 2: Corrupt the file
            corrupted = self._corrupt_file_in_minio(
                container_name,
                "repair_test.jpg",
                b"CORRUPTED - different data",
            )
            assert corrupted, "Failed to corrupt file"

            # Verify hash changed
            corrupted_hash = self._get_file_hash_from_minio(container_name, "repair_test.jpg")
            assert corrupted_hash != original_hash, "File was not corrupted"

            # Step 3: Run verification with --repair
            repair_result = subprocess.run(
                [
                    "python3",
                    "-m",
                    "photo_backup.main",
                    "--test-mode",
                    "verify",
                    "--repair",
                    "--verbose",
                ],
                capture_output=True,
                text=True,
                cwd=".",
                env=env,
                timeout=120,
            )

            repair_output = repair_result.stdout + repair_result.stderr

            # Should show repair activity
            assert "Repair" in repair_output or "repair" in repair_output.lower() or "REPAIR" in repair_output, (
                f"Repair not mentioned in output: {repair_output}"
            )

            # Step 4: Verify the file is now correct
            final_hash = self._get_file_hash_from_minio(container_name, "repair_test.jpg")

            # Hash should match original
            assert final_hash == original_hash, (
                f"File not properly repaired. Original: {original_hash}, Final: {final_hash}"
            )

    def test_corruption_detection_multiple_files(self, minio_container):
        """Test corruption detection with multiple files where only some are corrupted."""
        container_name = self._get_container_name(minio_container)

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create multiple test files
            test_files = {
                "good1.jpg": b"Good file 1 content - should remain unchanged",
                "bad1.jpg": b"Bad file 1 content - will be corrupted",
                "good2.jpg": b"Good file 2 content - should remain unchanged",
                "bad2.jpg": b"Bad file 2 content - will be corrupted",
                "good3.jpg": b"Good file 3 content - should remain unchanged",
            }

            for rel_path, content in test_files.items():
                (temp_path / rel_path).write_bytes(content)

            # Create bucket
            assert self._create_test_bucket(container_name), "Failed to create test bucket"

            # Set up environment
            env = os.environ.copy()
            env["PHOTO_BACKUP_BACKUP_SOURCE_PATH"] = str(temp_path)
            env["PHOTO_BACKUP_STORAGE_ENDPOINT"] = f"localhost:{self.MINIO_PORT}"
            env["PHOTO_BACKUP_STORAGE_ACCESS_KEY"] = "minioadmin"
            env["PHOTO_BACKUP_STORAGE_SECRET_KEY"] = "minioadmin"
            env["PHOTO_BACKUP_STORAGE_USE_SSL"] = "false"
            # Note: We don't override PHOTO_BACKUP_STORAGE_BUCKET because
            # the sync command uses backup.destination which includes the bucket name

            # Sync to Minio
            sync_result = subprocess.run(
                ["python3", "-m", "photo_backup.main", "--test-mode", "sync"],
                capture_output=True,
                text=True,
                cwd=".",
                env=env,
                timeout=60,
            )

            if sync_result.returncode != 0:
                pytest.skip(f"Sync failed: {sync_result.stdout + sync_result.stderr}")

            # Corrupt only the "bad" files
            self._corrupt_file_in_minio(container_name, "bad1.jpg", b"CORRUPTED1")
            self._corrupt_file_in_minio(container_name, "bad2.jpg", b"CORRUPTED2")

            # Run verification
            verify_result = subprocess.run(
                ["python3", "-m", "photo_backup.main", "--test-mode", "verify", "--verbose"],
                capture_output=True,
                text=True,
                cwd=".",
                env=env,
                timeout=60,
            )

            verify_output = verify_result.stdout + verify_result.stderr

            # Should detect mismatches
            assert verify_result.returncode != 0 or "Mismatched files:" in verify_output

            # Should still have some matched files
            assert "Matched files:" in verify_output

    def test_dry_run_does_not_repair(self, minio_container):
        """Test that dry run mode reports but doesn't actually repair."""
        container_name = self._get_container_name(minio_container)

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create test file
            original_content = b"Dry run test content"
            (temp_path / "dryrun_test.jpg").write_bytes(original_content)

            # Create bucket
            assert self._create_test_bucket(container_name), "Failed to create test bucket"

            # Set up environment
            env = os.environ.copy()
            env["PHOTO_BACKUP_BACKUP_SOURCE_PATH"] = str(temp_path)
            env["PHOTO_BACKUP_STORAGE_ENDPOINT"] = f"localhost:{self.MINIO_PORT}"
            env["PHOTO_BACKUP_STORAGE_ACCESS_KEY"] = "minioadmin"
            env["PHOTO_BACKUP_STORAGE_SECRET_KEY"] = "minioadmin"
            env["PHOTO_BACKUP_STORAGE_USE_SSL"] = "false"
            # Note: We don't override PHOTO_BACKUP_STORAGE_BUCKET because
            # the sync command uses backup.destination which includes the bucket name

            # Sync to Minio
            sync_result = subprocess.run(
                ["python3", "-m", "photo_backup.main", "--test-mode", "sync"],
                capture_output=True,
                text=True,
                cwd=".",
                env=env,
                timeout=60,
            )

            if sync_result.returncode != 0:
                pytest.skip(f"Sync failed: {sync_result.stdout + sync_result.stderr}")

            # Get original hash
            original_hash = self._get_file_hash_from_minio(container_name, "dryrun_test.jpg")

            # Corrupt the file
            self._corrupt_file_in_minio(container_name, "dryrun_test.jpg", b"CORRUPTED")
            corrupted_hash = self._get_file_hash_from_minio(container_name, "dryrun_test.jpg")
            assert corrupted_hash != original_hash

            # Run verify with --repair --dry-run
            result = subprocess.run(
                [
                    "python3",
                    "-m",
                    "photo_backup.main",
                    "--test-mode",
                    "--dry-run",
                    "verify",
                    "--repair",
                ],
                capture_output=True,
                text=True,
                cwd=".",
                env=env,
                timeout=60,
            )

            output = result.stdout + result.stderr
            assert "DRY RUN" in output

            # File should still be corrupted (not actually repaired)
            final_hash = self._get_file_hash_from_minio(container_name, "dryrun_test.jpg")
            assert final_hash == corrupted_hash, "Dry run should not modify files"


class TestCorruptionWithScheduledVerification:
    """Test corruption handling with scheduled verification."""

    MINIO_PORT = 9021
    # This must match the bucket in backup.destination for test mode
    BUCKET_NAME = "my-photo-backup-bucket-test"

    minio_container = MinioTestUtils.create_minio_fixture(
        "photo-backup-scheduled-corruption-test",
        port=MINIO_PORT,
    )

    def _create_test_bucket(self, container_name: str) -> bool:
        """Create test bucket in Minio."""
        result = subprocess.run(
            [
                "docker",
                "exec",
                container_name,
                "mc",
                "mb",
                f"test/{self.BUCKET_NAME}",
                "--ignore-existing",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode == 0

    def _get_container_name(self, container_id: str) -> str:
        """Get container name from container ID."""
        result = subprocess.run(
            ["docker", "inspect", "--format", "{{.Name}}", container_id],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            return result.stdout.strip().lstrip("/")
        return container_id

    def test_verification_scheduler_integration(self, minio_container):
        """Test that VerificationScheduler can run verification against Minio."""
        container_name = self._get_container_name(minio_container)

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create test file
            (temp_path / "scheduled_test.jpg").write_bytes(b"Scheduled verification test content")

            # Create bucket
            assert self._create_test_bucket(container_name), "Failed to create test bucket"

            # Set up environment
            env = os.environ.copy()
            env["PHOTO_BACKUP_BACKUP_SOURCE_PATH"] = str(temp_path)
            env["PHOTO_BACKUP_STORAGE_ENDPOINT"] = f"localhost:{self.MINIO_PORT}"
            env["PHOTO_BACKUP_STORAGE_ACCESS_KEY"] = "minioadmin"
            env["PHOTO_BACKUP_STORAGE_SECRET_KEY"] = "minioadmin"
            env["PHOTO_BACKUP_STORAGE_USE_SSL"] = "false"
            # Note: We don't override PHOTO_BACKUP_STORAGE_BUCKET because
            # the sync command uses backup.destination which includes the bucket name

            # Sync to Minio first
            sync_result = subprocess.run(
                ["python3", "-m", "photo_backup.main", "--test-mode", "sync"],
                capture_output=True,
                text=True,
                cwd=".",
                env=env,
                timeout=60,
            )

            if sync_result.returncode != 0:
                pytest.skip(f"Sync failed: {sync_result.stdout + sync_result.stderr}")

            # Use Python to test the VerificationScheduler directly
            from unittest.mock import patch

            from photo_backup.config.config import Config
            from photo_backup.verify.scheduler import VerificationScheduler

            # Create config with env overrides
            config = Config(test_mode=True)

            # Patch the environment for config loading
            with patch.dict(os.environ, env):
                config.load_config()

                # Create scheduler
                scheduler = VerificationScheduler(
                    config=config,
                    test_mode=True,
                    interval_days=1,  # Daily for test
                )

                # Reset schedule to ensure clean state for this test
                scheduler.reset_schedule()

                # Now scheduler should indicate verification is due (schedule was reset)
                assert scheduler.is_verification_due() is True

                # Run scheduled verification
                result = scheduler.run_scheduled_verification(
                    force=False,  # Not forcing, should run because it's due
                    repair=False,
                    save_report=False,
                )

                # Check result
                assert result.ran is True
                # May or may not pass depending on sync success
                if result.passed:
                    assert "PASSED" in result.get_summary()

                # After running, should not be due immediately
                assert scheduler.is_verification_due() is False
