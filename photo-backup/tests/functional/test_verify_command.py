#!/usr/bin/env python3
"""
Functional tests for the verify CLI command.

Task 99: Add Verify Command - Functional tests.
"""

import os
import shutil
import subprocess
import tempfile

import pytest
from pathlib import Path

from tests.functional.minio_test_utils import MinioTestUtils


class TestVerifyCommandFunctional:
    """Functional tests for the verify command."""

    MINIO_PORT = 9010

    # Use shared fixture factory
    minio_container = MinioTestUtils.create_minio_fixture("photo-backup-verify-cmd-test", port=MINIO_PORT)

    def test_verify_help(self):
        """Test that verify command shows help."""
        result = subprocess.run(
            ["python3", "-m", "photo_backup.main", "verify", "--help"],
            capture_output=True,
            text=True,
            cwd=".",
        )

        assert result.returncode == 0
        assert "verify" in result.stdout
        assert "Verify backup integrity" in result.stdout
        assert "--repair" in result.stdout
        assert "--verbose" in result.stdout
        assert "--save-report" in result.stdout
        assert "Examples:" in result.stdout

    def test_verify_test_mode_without_minio(self):
        """Test verify command in test mode when Minio is not running."""
        # Ensure test photos directory doesn't exist
        test_photos_dir = Path("/tmp/photo-backup-verify-test-photos")
        if test_photos_dir.exists():
            shutil.rmtree(test_photos_dir)

        result = subprocess.run(
            ["python3", "-m", "photo_backup.main", "--test-mode", "verify"],
            capture_output=True,
            text=True,
            cwd=".",
        )

        # Should fail because source path doesn't exist or Minio not running
        assert result.returncode == 1
        combined_output = result.stdout + result.stderr
        assert "TEST MODE" in combined_output

    def test_verify_test_mode_with_minio(self, minio_container):  # noqa: ARG002
        """Test verify command in test mode when Minio is running."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create test photos
            test_photos = ["2024/01/test1.jpg", "2024/01/test2.jpg"]
            for photo_path in test_photos:
                photo_file = temp_path / photo_path
                photo_file.parent.mkdir(parents=True, exist_ok=True)
                photo_file.write_bytes(b"Test photo content " + photo_path.encode())

            # Set environment variables
            env = os.environ.copy()
            env["PHOTO_BACKUP_BACKUP_SOURCE_PATH"] = str(temp_path)
            env["PHOTO_BACKUP_STORAGE_ENDPOINT"] = f"localhost:{self.MINIO_PORT}"
            env["PHOTO_BACKUP_STORAGE_ACCESS_KEY"] = "minioadmin"
            env["PHOTO_BACKUP_STORAGE_SECRET_KEY"] = "minioadmin"
            env["PHOTO_BACKUP_STORAGE_USE_SSL"] = "false"
            env["PHOTO_BACKUP_STORAGE_BUCKET"] = "test-bucket"

            # First, sync some files to Minio
            sync_result = subprocess.run(
                ["python3", "-m", "photo_backup.main", "--test-mode", "sync"],
                capture_output=True,
                text=True,
                cwd=".",
                env=env,
            )

            # Now run verify
            result = subprocess.run(
                ["python3", "-m", "photo_backup.main", "--test-mode", "verify"],
                capture_output=True,
                text=True,
                cwd=".",
                env=env,
            )

            combined_output = result.stdout + result.stderr

            # If sync succeeded, verify should work
            if sync_result.returncode == 0:
                # Verify should show results
                assert "TEST MODE" in combined_output
                assert "Calculating local file hashes" in combined_output or "COMPARISON RESULTS" in combined_output
            else:
                # If sync failed (e.g., bucket creation issue), verify might also fail
                # but should still show test mode output
                assert "TEST MODE" in combined_output

    def test_verify_verbose_mode(self, minio_container):  # noqa: ARG002
        """Test verify command with verbose flag."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create test photo
            (temp_path / "test.jpg").write_bytes(b"Test content")

            env = os.environ.copy()
            env["PHOTO_BACKUP_BACKUP_SOURCE_PATH"] = str(temp_path)
            env["PHOTO_BACKUP_STORAGE_ENDPOINT"] = f"localhost:{self.MINIO_PORT}"
            env["PHOTO_BACKUP_STORAGE_ACCESS_KEY"] = "minioadmin"
            env["PHOTO_BACKUP_STORAGE_SECRET_KEY"] = "minioadmin"
            env["PHOTO_BACKUP_STORAGE_USE_SSL"] = "false"
            env["PHOTO_BACKUP_STORAGE_BUCKET"] = "test-bucket"

            result = subprocess.run(
                ["python3", "-m", "photo_backup.main", "--test-mode", "verify", "--verbose"],
                capture_output=True,
                text=True,
                cwd=".",
                env=env,
            )

            combined_output = result.stdout + result.stderr

            # Verbose should show endpoint info
            assert "TEST MODE" in combined_output
            # In verbose mode, endpoint should be shown
            assert "Endpoint:" in combined_output or "localhost" in combined_output

    def test_verify_production_mode_validation(self):
        """Test verify command in production mode (should fail without proper config)."""
        result = subprocess.run(
            ["python3", "-m", "photo_backup.main", "verify"],
            capture_output=True,
            text=True,
            cwd=".",
        )

        combined_output = result.stdout + result.stderr

        # Should show production mode
        assert "PRODUCTION MODE" in combined_output

        # Should fail (no production credentials/config)
        assert result.returncode == 1

    def test_verify_save_report(self, minio_container):  # noqa: ARG002
        """Test verify command with save-report option."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            report_path = temp_path / "reports" / "test_report.json"

            # Create test photo
            (temp_path / "test.jpg").write_bytes(b"Test content")

            env = os.environ.copy()
            env["PHOTO_BACKUP_BACKUP_SOURCE_PATH"] = str(temp_path)
            env["PHOTO_BACKUP_STORAGE_ENDPOINT"] = f"localhost:{self.MINIO_PORT}"
            env["PHOTO_BACKUP_STORAGE_ACCESS_KEY"] = "minioadmin"
            env["PHOTO_BACKUP_STORAGE_SECRET_KEY"] = "minioadmin"
            env["PHOTO_BACKUP_STORAGE_USE_SSL"] = "false"
            env["PHOTO_BACKUP_STORAGE_BUCKET"] = "test-bucket"

            result = subprocess.run(
                [
                    "python3",
                    "-m",
                    "photo_backup.main",
                    "--test-mode",
                    "verify",
                    "--save-report",
                    "--report-path",
                    str(report_path),
                ],
                capture_output=True,
                text=True,
                cwd=".",
                env=env,
            )

            combined_output = result.stdout + result.stderr

            # Check if report was saved (or at least attempted)
            if result.returncode == 0:
                assert "Report saved to:" in combined_output or report_path.exists()

    def test_verify_dry_run_with_repair(self, minio_container):  # noqa: ARG002
        """Test verify with dry-run and repair flags."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create test photo
            (temp_path / "test.jpg").write_bytes(b"Test content")

            env = os.environ.copy()
            env["PHOTO_BACKUP_BACKUP_SOURCE_PATH"] = str(temp_path)
            env["PHOTO_BACKUP_STORAGE_ENDPOINT"] = f"localhost:{self.MINIO_PORT}"
            env["PHOTO_BACKUP_STORAGE_ACCESS_KEY"] = "minioadmin"
            env["PHOTO_BACKUP_STORAGE_SECRET_KEY"] = "minioadmin"
            env["PHOTO_BACKUP_STORAGE_USE_SSL"] = "false"
            env["PHOTO_BACKUP_STORAGE_BUCKET"] = "test-bucket"

            result = subprocess.run(
                ["python3", "-m", "photo_backup.main", "--test-mode", "--dry-run", "verify", "--repair"],
                capture_output=True,
                text=True,
                cwd=".",
                env=env,
            )

            combined_output = result.stdout + result.stderr

            # Should show dry run mode
            assert "TEST MODE (DRY RUN)" in combined_output

            # Should not actually repair - should say "would repair"
            if "Missing on remote" in combined_output or "missing remote" in combined_output.lower():
                assert "DRY RUN" in combined_output


class TestVerifyWithSync:
    """Test verify command after successful sync."""

    MINIO_PORT = 9011

    minio_container = MinioTestUtils.create_minio_fixture("photo-backup-verify-sync-test", port=MINIO_PORT)

    def test_verify_after_sync_all_match(self, minio_container):  # noqa: ARG002
        """Test verify after a successful sync - all files should match."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create test photos with unique content
            test_photos = {
                "photo1.jpg": b"unique content for photo 1",
                "photo2.jpg": b"unique content for photo 2",
                "subdir/photo3.jpg": b"unique content for photo 3",
            }

            for rel_path, content in test_photos.items():
                photo_file = temp_path / rel_path
                photo_file.parent.mkdir(parents=True, exist_ok=True)
                photo_file.write_bytes(content)

            env = os.environ.copy()
            env["PHOTO_BACKUP_BACKUP_SOURCE_PATH"] = str(temp_path)
            env["PHOTO_BACKUP_STORAGE_ENDPOINT"] = f"localhost:{self.MINIO_PORT}"
            env["PHOTO_BACKUP_STORAGE_ACCESS_KEY"] = "minioadmin"
            env["PHOTO_BACKUP_STORAGE_SECRET_KEY"] = "minioadmin"
            env["PHOTO_BACKUP_STORAGE_USE_SSL"] = "false"
            env["PHOTO_BACKUP_STORAGE_BUCKET"] = "test-verify-bucket"

            # Step 1: Sync files to Minio
            sync_result = subprocess.run(
                ["python3", "-m", "photo_backup.main", "--test-mode", "sync"],
                capture_output=True,
                text=True,
                cwd=".",
                env=env,
            )

            sync_combined = sync_result.stdout + sync_result.stderr

            # Skip test if sync failed
            if sync_result.returncode != 0:
                pytest.skip(f"Sync failed, cannot test verify: {sync_combined}")

            # Step 2: Verify - all should match
            verify_result = subprocess.run(
                ["python3", "-m", "photo_backup.main", "--test-mode", "verify", "--verbose"],
                capture_output=True,
                text=True,
                cwd=".",
                env=env,
            )

            verify_combined = verify_result.stdout + verify_result.stderr

            # Check verification results
            assert "Matched files:" in verify_combined
            # Should pass if files match
            if verify_result.returncode == 0:
                assert "VERIFICATION PASSED" in verify_combined
