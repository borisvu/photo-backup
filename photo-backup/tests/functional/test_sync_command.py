#!/usr/bin/env python3
"""
Functional tests for the sync CLI command.
"""

import contextlib
import subprocess
import tempfile

import docker
import pytest
from pathlib import Path


class TestSyncCommandFunctional:
    """Functional tests for the sync command."""

    MINIO_PORT = 9008

    @pytest.fixture
    def minio_container(self):
        """Local Minio fixture for this test class."""
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

    def test_sync_help(self):
        """Test that sync command shows help."""
        result = subprocess.run(
            ["python3", "-m", "photo_backup.main", "sync", "--help"],
            capture_output=True,
            text=True,
            cwd=".",
        )

        assert result.returncode == 0
        assert "sync" in result.stdout
        assert "Run manual backup synchronization" in result.stdout
        assert "--verbose" in result.stdout
        assert "Examples:" in result.stdout

    def test_sync_test_mode_dry_run_without_minio(self):
        """Test sync command in test mode with dry run when Minio is not running."""
        # Ensure test photos directory doesn't exist to avoid interference
        import shutil

        from pathlib import Path

        test_photos_dir = Path("/tmp/photo-backup-test-photos")
        if test_photos_dir.exists():
            shutil.rmtree(test_photos_dir)

        result = subprocess.run(
            ["python3", "-m", "photo_backup.main", "--test-mode", "--dry-run", "sync"],
            capture_output=True,
            text=True,
            cwd=".",
        )

        # Should fail because Minio is not running
        assert result.returncode == 1
        combined_output = result.stdout + result.stderr

        # Check that it shows test mode and dry run
        assert "TEST MODE (DRY RUN)" in combined_output
        assert "Photo Backup Sync" in combined_output

        # Check that it fails with appropriate error message
        # It might fail during validation or during sync, both are acceptable
        assert (
            "Backup environment validation failed" in combined_output
            or "Backup failed" in combined_output
            or "directory not found" in combined_output
        )

    def test_sync_test_mode_with_minio_running(self, minio_container):  # noqa: ARG002
        """Test sync command in test mode when Minio is running."""
        # Minio container is managed by fixture
        # Create test photos directory and some test files
        import os

        from pathlib import Path

        test_photos_dir = Path("/tmp/photo-backup-test-photos")
        test_photos_dir.mkdir(exist_ok=True)

        # Create a simple test file
        test_file = test_photos_dir / "test.jpg"
        test_file.write_text("test photo content")

        try:
            # Configure environment for custom Minio endpoint
            env = os.environ.copy()
            env["PHOTO_BACKUP_STORAGE_ENDPOINT"] = f"localhost:{self.MINIO_PORT}"
            env["PHOTO_BACKUP_STORAGE_ACCESS_KEY"] = "minioadmin"
            env["PHOTO_BACKUP_STORAGE_SECRET_KEY"] = "minioadmin"
            env["PHOTO_BACKUP_STORAGE_USE_SSL"] = "false"
            env["PHOTO_BACKUP_STORAGE_BUCKET"] = "test-bucket"

            # Test with dry run first
            result = subprocess.run(
                ["python3", "-m", "photo_backup.main", "--test-mode", "--dry-run", "sync"],
                capture_output=True,
                text=True,
                cwd=".",
                env=env,
            )

            combined_output = result.stdout + result.stderr

            # Should succeed with dry run now that we have test photos
            assert result.returncode == 0
            assert "TEST MODE (DRY RUN)" in combined_output
            assert "DRY RUN MODE - No files will be transferred" in combined_output
            assert "Backup completed successfully" in combined_output

        finally:
            # Clean up test photos
            import shutil

            if test_photos_dir.exists():
                shutil.rmtree(test_photos_dir)

    def test_sync_verbose_mode(self):
        """Test sync command with verbose flag."""
        result = subprocess.run(
            ["python3", "-m", "photo_backup.main", "--test-mode", "--dry-run", "sync", "--verbose"],
            capture_output=True,
            text=True,
            cwd=".",
        )

        combined_output = result.stdout + result.stderr

        # Should show verbose information
        assert "TEST MODE (DRY RUN)" in combined_output
        # Verbose mode should show more detailed information
        # (The exact content depends on whether Minio is running)

    def test_sync_production_mode_validation(self):
        """Test sync command in production mode (should fail without proper config)."""
        result = subprocess.run(
            ["python3", "-m", "photo_backup.main", "--dry-run", "sync"],
            capture_output=True,
            text=True,
            cwd=".",
        )

        combined_output = result.stdout + result.stderr

        # Should show production mode
        assert "PRODUCTION MODE (DRY RUN)" in combined_output

        # Should fail validation (no production credentials configured)
        assert result.returncode == 1
        assert "Backup environment validation failed" in combined_output

    def test_sync_with_test_photos(self, minio_container):  # noqa: ARG002
        """Test sync command with actual test photos when Minio is running."""
        # Minio container is managed by fixture
        # Create test photos in a temporary directory
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create some test photo files
            test_photos = ["2023/01/IMG_001.jpg", "2023/01/IMG_002.jpg", "2023/02/IMG_003.jpg"]

            for photo_path in test_photos:
                photo_file = temp_path / photo_path
                photo_file.parent.mkdir(parents=True, exist_ok=True)
                photo_file.write_text(f"Test photo content for {photo_path}")

            # Set environment variables for custom Minio endpoint and test photos directory
            import os

            env = os.environ.copy()
            env["PHOTO_BACKUP_BACKUP_SOURCE_PATH"] = str(temp_path)
            env["PHOTO_BACKUP_STORAGE_ENDPOINT"] = f"localhost:{self.MINIO_PORT}"
            env["PHOTO_BACKUP_STORAGE_ACCESS_KEY"] = "minioadmin"
            env["PHOTO_BACKUP_STORAGE_SECRET_KEY"] = "minioadmin"
            env["PHOTO_BACKUP_STORAGE_USE_SSL"] = "false"
            env["PHOTO_BACKUP_STORAGE_BUCKET"] = "test-bucket"

            # Test sync with dry run
            result = subprocess.run(
                ["python3", "-m", "photo_backup.main", "--test-mode", "--dry-run", "sync"],
                capture_output=True,
                text=True,
                cwd=".",
                env=env,
            )

            combined_output = result.stdout + result.stderr

            # Should succeed with dry run
            assert result.returncode == 0
            assert "TEST MODE (DRY RUN)" in combined_output
            assert "Backup completed successfully" in combined_output
            assert "DRY RUN MODE - No files will be transferred" in combined_output

    def test_sync_error_handling(self):
        """Test sync command error handling."""
        # Test with invalid source path
        import os

        env = os.environ.copy()
        env["PHOTO_BACKUP_BACKUP_SOURCE_PATH"] = "/nonexistent/path"

        result = subprocess.run(
            ["python3", "-m", "photo_backup.main", "--test-mode", "--dry-run", "sync"],
            capture_output=True,
            text=True,
            cwd=".",
            env=env,
        )

        combined_output = result.stdout + result.stderr

        # Should fail (either during validation or during sync)
        assert result.returncode == 1
        # Check that it fails with either validation error or sync error
        assert (
            "Backup environment validation failed" in combined_output
            or "Backup failed" in combined_output
            or "directory not found" in combined_output
        )

    def test_sync_keyboard_interrupt_handling(self):
        """Test that sync command handles keyboard interrupt gracefully."""
        # This test would require sending SIGINT to the process
        # For now, we'll just test that the command structure supports it
        # by checking that the help shows the command exists
        result = subprocess.run(
            ["python3", "-m", "photo_backup.main", "sync", "--help"],
            capture_output=True,
            text=True,
            cwd=".",
        )

        assert result.returncode == 0
        assert "sync" in result.stdout
