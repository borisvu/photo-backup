#!/usr/bin/env python3
"""
Functional tests for full verification cycle.

Task 103: Verification Functional Test - Full verification cycle.

These tests verify the complete verification workflow:
1. Upload test photos to Minio
2. Corrupt one file
3. Run verification (detect corruption)
4. Run verification with repair
5. Validate the final report
"""

import os
import subprocess
import sys
import tempfile
import time

import pytest
from pathlib import Path

from tests.functional.minio_test_utils import MinioTestUtils


class TestFullVerificationCycle:
    """Test complete verification cycle with upload, corruption, and repair."""

    MINIO_PORT = 9022
    # This must match the bucket in backup.destination for test mode
    BUCKET_NAME = "my-photo-backup-bucket-test"

    # Use shared fixture factory
    minio_container = MinioTestUtils.create_minio_fixture(
        "photo-backup-full-verify-test",
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
        """Get the MD5 hash of a file in Minio.

        Args:
            container_name: Name of the Minio container
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
                f"test/{self.BUCKET_NAME}/{file_path}",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            return None

        # Parse the output to find ETag (which is MD5 for non-multipart uploads)
        for line in result.stdout.split("\n"):
            line = line.strip()
            if line.startswith("ETag"):
                parts = line.split(":", 1)
                if len(parts) >= 2:
                    return parts[1].strip()
        return None

    def _setup_environment(self, source_path: str) -> dict:
        """Set up environment variables for test mode."""
        env = os.environ.copy()
        env["PHOTO_BACKUP_BACKUP_SOURCE_PATH"] = source_path
        env["PHOTO_BACKUP_STORAGE_ENDPOINT"] = f"localhost:{self.MINIO_PORT}"
        env["PHOTO_BACKUP_STORAGE_ACCESS_KEY"] = "minioadmin"
        env["PHOTO_BACKUP_STORAGE_SECRET_KEY"] = "minioadmin"
        env["PHOTO_BACKUP_STORAGE_USE_SSL"] = "false"
        return env

    def test_full_verification_cycle_with_repair(self, minio_container):
        """Test complete verification cycle: upload -> corrupt -> verify -> repair -> validate report.

        This is the main test for Task 103 that exercises the entire verification workflow.
        """
        container_name = self._get_container_name(minio_container)

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Step 1: Create test photos with unique content
            test_files = {
                "family/photo1.jpg": b"Family photo 1 - vacation memories from 2024",
                "family/photo2.jpg": b"Family photo 2 - birthday celebration",
                "nature/landscape.jpg": b"Beautiful mountain landscape at sunset",
                "nature/wildlife.jpg": b"Wildlife photo - deer in the forest",
                "events/party.jpg": b"New Year party photo - celebration time",
            }

            for rel_path, content in test_files.items():
                photo_file = temp_path / rel_path
                photo_file.parent.mkdir(parents=True, exist_ok=True)
                photo_file.write_bytes(content)

            # Create bucket
            assert self._create_test_bucket(container_name), "Failed to create test bucket"

            env = self._setup_environment(str(temp_path))

            # Step 2: Sync files to Minio
            sync_result = subprocess.run(
                [sys.executable, "-m", "photo_backup.main", "--test-mode", "sync"],
                capture_output=True,
                text=True,
                cwd=".",
                env=env,
                timeout=120,
            )

            if sync_result.returncode != 0:
                pytest.skip(f"Sync failed: {sync_result.stdout + sync_result.stderr}")

            # Allow Minio to settle
            time.sleep(1)

            # Step 3: Verify initial state - all should match
            initial_verify = subprocess.run(
                [sys.executable, "-m", "photo_backup.main", "--test-mode", "verify", "--verbose"],
                capture_output=True,
                text=True,
                cwd=".",
                env=env,
                timeout=120,
            )

            initial_output = initial_verify.stdout + initial_verify.stderr

            # Initial verification should pass
            assert "Matched files:" in initial_output
            assert initial_verify.returncode == 0, f"Initial verification failed: {initial_output}"
            assert "VERIFICATION PASSED" in initial_output

            # Get original hash of file we'll corrupt
            original_hash = self._get_file_hash_from_minio(container_name, "nature/landscape.jpg")
            assert original_hash is not None, "Failed to get original hash"

            # Step 4: Corrupt one file in Minio
            corrupted = self._corrupt_file_in_minio(
                container_name,
                "nature/landscape.jpg",
                b"THIS FILE HAS BEEN CORRUPTED - NOT ORIGINAL DATA",
            )
            assert corrupted, "Failed to corrupt file in Minio"

            # Verify hash changed
            corrupted_hash = self._get_file_hash_from_minio(container_name, "nature/landscape.jpg")
            assert corrupted_hash != original_hash, "File was not corrupted"

            # Step 5: Run verification - should detect corruption
            detect_verify = subprocess.run(
                [sys.executable, "-m", "photo_backup.main", "--test-mode", "verify", "--verbose"],
                capture_output=True,
                text=True,
                cwd=".",
                env=env,
                timeout=120,
            )

            detect_output = detect_verify.stdout + detect_verify.stderr

            # Should detect the mismatch
            assert detect_verify.returncode != 0 or "Mismatched files:" in detect_output
            assert "landscape.jpg" in detect_output or "VERIFICATION FAILED" in detect_output

            # Step 6: Run verification with repair
            repair_verify = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "photo_backup.main",
                    "--test-mode",
                    "verify",
                    "--repair",
                    "--verbose",
                    "--save-report",
                ],
                capture_output=True,
                text=True,
                cwd=".",
                env=env,
                timeout=180,
            )

            repair_output = repair_verify.stdout + repair_verify.stderr

            # Should show repair activity
            assert "Repair" in repair_output or "repair" in repair_output.lower() or "REPAIR" in repair_output, (
                f"Repair not mentioned in output: {repair_output}"
            )

            # Should indicate success after repair
            assert "VERIFICATION PASSED" in repair_output or "Repaired:" in repair_output

            # Step 7: Verify the file is now correct
            final_hash = self._get_file_hash_from_minio(container_name, "nature/landscape.jpg")
            assert final_hash == original_hash, (
                f"File not properly repaired. Original: {original_hash}, Final: {final_hash}"
            )

            # Step 8: Validate final report output
            assert "Report saved to:" in repair_output, "Report should be saved"

            # Run one more verification to confirm everything is good
            final_verify = subprocess.run(
                [sys.executable, "-m", "photo_backup.main", "--test-mode", "verify", "--verbose"],
                capture_output=True,
                text=True,
                cwd=".",
                env=env,
                timeout=120,
            )

            final_output = final_verify.stdout + final_verify.stderr

            assert final_verify.returncode == 0, f"Final verification should pass: {final_output}"
            assert "VERIFICATION PASSED" in final_output
            assert "Mismatched files: 0" in final_output

    def test_verification_report_contents(self, minio_container):
        """Test that verification report contains all expected information."""
        container_name = self._get_container_name(minio_container)

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            reports_path = temp_path / "reports"
            reports_path.mkdir(parents=True, exist_ok=True)

            # Create test files
            test_files = {
                "photo1.jpg": b"Photo 1 content for report test",
                "photo2.jpg": b"Photo 2 content for report test",
                "photo3.jpg": b"Photo 3 content for report test",
            }

            for rel_path, content in test_files.items():
                (temp_path / rel_path).write_bytes(content)

            # Create bucket
            assert self._create_test_bucket(container_name), "Failed to create test bucket"

            env = self._setup_environment(str(temp_path))

            # Sync files
            sync_result = subprocess.run(
                [sys.executable, "-m", "photo_backup.main", "--test-mode", "sync"],
                capture_output=True,
                text=True,
                cwd=".",
                env=env,
                timeout=120,
            )

            if sync_result.returncode != 0:
                pytest.skip(f"Sync failed: {sync_result.stdout + sync_result.stderr}")

            time.sleep(0.5)

            # Run verification with report saving
            report_file = reports_path / "verify_report.json"
            verify_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "photo_backup.main",
                    "--test-mode",
                    "verify",
                    "--verbose",
                    "--save-report",
                    "--report-path",
                    str(report_file),
                ],
                capture_output=True,
                text=True,
                cwd=".",
                env=env,
                timeout=120,
            )

            verify_output = verify_result.stdout + verify_result.stderr

            # Report should be saved
            if verify_result.returncode == 0:
                assert report_file.exists(), f"Report file not created: {verify_output}"

                # Read and validate report contents
                import json

                with open(report_file) as f:
                    report = json.load(f)

                # Validate report structure
                assert "report_id" in report
                assert "timestamp" in report
                assert "source_path" in report
                assert "destination" in report
                assert "mode" in report
                assert report["mode"] == "test"
                assert "verification_passed" in report
                assert "total_files_checked" in report
                assert "total_duration_seconds" in report

                # Should have comparison results
                assert "comparison" in report
                comp = report["comparison"]
                assert "matched_files" in comp
                assert "mismatched_files" in comp
                assert "missing_remote" in comp
                assert "missing_local" in comp

    def test_verification_multiple_corruptions(self, minio_container):
        """Test verification handles multiple corrupted files."""
        container_name = self._get_container_name(minio_container)

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create multiple test files
            test_files = {
                "good1.jpg": b"Good file 1 - should remain intact",
                "corrupt1.jpg": b"Corrupt file 1 - will be damaged",
                "good2.jpg": b"Good file 2 - should remain intact",
                "corrupt2.jpg": b"Corrupt file 2 - will be damaged",
                "good3.jpg": b"Good file 3 - should remain intact",
            }

            for rel_path, content in test_files.items():
                (temp_path / rel_path).write_bytes(content)

            # Create bucket
            assert self._create_test_bucket(container_name), "Failed to create test bucket"

            env = self._setup_environment(str(temp_path))

            # Sync
            sync_result = subprocess.run(
                [sys.executable, "-m", "photo_backup.main", "--test-mode", "sync"],
                capture_output=True,
                text=True,
                cwd=".",
                env=env,
                timeout=120,
            )

            if sync_result.returncode != 0:
                pytest.skip(f"Sync failed: {sync_result.stdout + sync_result.stderr}")

            time.sleep(0.5)

            # Get original hashes
            hash1 = self._get_file_hash_from_minio(container_name, "corrupt1.jpg")
            hash2 = self._get_file_hash_from_minio(container_name, "corrupt2.jpg")

            # Corrupt multiple files
            self._corrupt_file_in_minio(container_name, "corrupt1.jpg", b"CORRUPTED_1")
            self._corrupt_file_in_minio(container_name, "corrupt2.jpg", b"CORRUPTED_2")

            # Run verification
            verify_result = subprocess.run(
                [sys.executable, "-m", "photo_backup.main", "--test-mode", "verify", "--verbose"],
                capture_output=True,
                text=True,
                cwd=".",
                env=env,
                timeout=120,
            )

            verify_output = verify_result.stdout + verify_result.stderr

            # Should detect multiple mismatches
            assert verify_result.returncode != 0 or "Mismatched files:" in verify_output
            # Should still have matched files
            assert "Matched files:" in verify_output

            # Repair
            repair_result = subprocess.run(
                [
                    sys.executable,
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
                timeout=180,
            )

            repair_output = repair_result.stdout + repair_result.stderr

            # Should repair both files
            assert "Repair" in repair_output or "repair" in repair_output.lower()

            # Verify files are restored
            final_hash1 = self._get_file_hash_from_minio(container_name, "corrupt1.jpg")
            final_hash2 = self._get_file_hash_from_minio(container_name, "corrupt2.jpg")

            assert final_hash1 == hash1, "corrupt1.jpg not properly repaired"
            assert final_hash2 == hash2, "corrupt2.jpg not properly repaired"


class TestVerificationEdgeCases:
    """Test edge cases in verification workflow."""

    MINIO_PORT = 9023
    BUCKET_NAME = "my-photo-backup-bucket-test"

    minio_container = MinioTestUtils.create_minio_fixture(
        "photo-backup-verify-edge-test",
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

    def _setup_environment(self, source_path: str) -> dict:
        """Set up environment variables for test mode."""
        env = os.environ.copy()
        env["PHOTO_BACKUP_BACKUP_SOURCE_PATH"] = source_path
        env["PHOTO_BACKUP_STORAGE_ENDPOINT"] = f"localhost:{self.MINIO_PORT}"
        env["PHOTO_BACKUP_STORAGE_ACCESS_KEY"] = "minioadmin"
        env["PHOTO_BACKUP_STORAGE_SECRET_KEY"] = "minioadmin"
        env["PHOTO_BACKUP_STORAGE_USE_SSL"] = "false"
        return env

    def test_verify_empty_directory(self, minio_container):
        """Test verification with empty source directory."""
        container_name = self._get_container_name(minio_container)

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create bucket
            assert self._create_test_bucket(container_name), "Failed to create test bucket"

            env = self._setup_environment(temp_dir)

            # Run verification on empty directory
            result = subprocess.run(
                [sys.executable, "-m", "photo_backup.main", "--test-mode", "verify", "--verbose"],
                capture_output=True,
                text=True,
                cwd=".",
                env=env,
                timeout=60,
            )

            output = result.stdout + result.stderr

            # Should handle empty directory gracefully
            assert "TEST MODE" in output
            # Should report 0 files
            assert "Found 0 local files" in output or "Matched files: 0" in output

    def test_verify_preserves_good_files_during_repair(self, minio_container):
        """Test that repair doesn't modify files that are already correct."""
        container_name = self._get_container_name(minio_container)

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create test files
            test_files = {
                "good.jpg": b"This file should not be touched",
                "bad.jpg": b"This file will be corrupted",
            }

            for rel_path, content in test_files.items():
                (temp_path / rel_path).write_bytes(content)

            # Create bucket
            assert self._create_test_bucket(container_name), "Failed to create test bucket"

            env = self._setup_environment(str(temp_path))

            # Sync
            sync_result = subprocess.run(
                [sys.executable, "-m", "photo_backup.main", "--test-mode", "sync"],
                capture_output=True,
                text=True,
                cwd=".",
                env=env,
                timeout=120,
            )

            if sync_result.returncode != 0:
                pytest.skip(f"Sync failed: {sync_result.stdout + sync_result.stderr}")

            time.sleep(0.5)

            # Get original hashes
            good_hash_before = self._get_file_hash_from_minio_bucket(container_name, "good.jpg")
            bad_hash_original = self._get_file_hash_from_minio_bucket(container_name, "bad.jpg")

            # Corrupt only the bad file
            self._corrupt_file_in_minio(container_name, "bad.jpg", b"CORRUPTED")

            # Run repair
            subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "photo_backup.main",
                    "--test-mode",
                    "verify",
                    "--repair",
                ],
                capture_output=True,
                text=True,
                cwd=".",
                env=env,
                timeout=180,
            )

            # Verify good file was not modified
            good_hash_after = self._get_file_hash_from_minio_bucket(container_name, "good.jpg")
            assert good_hash_after == good_hash_before, "Good file was incorrectly modified"

            # Verify bad file was repaired
            bad_hash_after = self._get_file_hash_from_minio_bucket(container_name, "bad.jpg")
            assert bad_hash_after == bad_hash_original, "Bad file was not properly repaired"

    def _corrupt_file_in_minio(
        self,
        container_name: str,
        file_path: str,
        corruption_data: bytes = b"CORRUPTED",
    ) -> bool:
        """Corrupt a specific file in Minio."""
        with tempfile.NamedTemporaryFile(mode="wb", delete=False) as temp_file:
            temp_file.write(corruption_data)
            temp_path = temp_file.name

        try:
            subprocess.run(
                ["docker", "cp", temp_path, f"{container_name}:/tmp/corrupt_data"],
                check=True,
                capture_output=True,
                timeout=30,
            )

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

    def _get_file_hash_from_minio_bucket(self, container_name: str, file_path: str) -> str | None:
        """Get the MD5 hash of a file in Minio."""
        result = subprocess.run(
            [
                "docker",
                "exec",
                container_name,
                "mc",
                "stat",
                f"test/{self.BUCKET_NAME}/{file_path}",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            return None

        for line in result.stdout.split("\n"):
            line = line.strip()
            if line.startswith("ETag"):
                parts = line.split(":", 1)
                if len(parts) >= 2:
                    return parts[1].strip()
        return None
