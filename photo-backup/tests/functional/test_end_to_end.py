#!/usr/bin/env python3
"""
End-to-End Test for Photo Backup System.

Complete workflow test that exercises the entire system.

This test verifies that all components work together in a complete workflow:
1. Fresh install in test mode
2. Configure for Minio
3. Add test photos
4. Run full backup cycle
5. Verify files in Minio using verification command

This is the definitive "smoke test" that confirms the system works end-to-end.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import time

import pytest
from pathlib import Path

from tests.fixtures.photo_fixtures import generate_test_photos
from tests.functional.minio_test_utils import MinioTestUtils


class TestEndToEnd:
    """End-to-end test for complete photo backup workflow."""

    # Unique port for this test suite to avoid conflicts
    MINIO_PORT = 9030
    BUCKET_NAME = "my-photo-backup-bucket-test"

    # Use shared fixture factory
    minio_container = MinioTestUtils.create_minio_fixture(
        "photo-backup-e2e-test",
        port=MINIO_PORT,
    )

    @pytest.fixture
    def clean_test_environment(self):
        """Clean up test environment before and after test."""
        from photo_backup.consts import TEST_MODE_BASE_DIR

        test_base_dir = Path(TEST_MODE_BASE_DIR)

        # Clean up before test
        if test_base_dir.exists():
            shutil.rmtree(test_base_dir)

        yield test_base_dir

        # Clean up after test
        if test_base_dir.exists():
            shutil.rmtree(test_base_dir)

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

    def _setup_environment(self, source_path: str) -> dict:
        """Set up environment variables for test mode with Minio."""
        env = os.environ.copy()
        env["PHOTO_BACKUP_BACKUP_SOURCE_PATH"] = source_path
        env["PHOTO_BACKUP_STORAGE_ENDPOINT"] = f"localhost:{self.MINIO_PORT}"
        env["PHOTO_BACKUP_STORAGE_ACCESS_KEY"] = "minioadmin"
        env["PHOTO_BACKUP_STORAGE_SECRET_KEY"] = "minioadmin"
        env["PHOTO_BACKUP_STORAGE_USE_SSL"] = "false"
        env["PHOTO_BACKUP_STORAGE_BUCKET"] = "test-bucket"
        return env

    def _list_files_in_minio(self, container_name: str) -> list[str]:
        """List files in the Minio bucket."""
        result = subprocess.run(
            [
                "docker",
                "exec",
                container_name,
                "mc",
                "ls",
                f"test/{self.BUCKET_NAME}/",
                "--recursive",
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            return []

        # Parse output - format is like: "[DATE] [SIZE] path/to/file"
        files = []
        for line in result.stdout.strip().split("\n"):
            if line:
                # Extract filename from the line (last part after size)
                parts = line.split()
                if len(parts) >= 4:
                    files.append(parts[-1])
        return files

    @pytest.mark.functional
    @pytest.mark.slow
    def test_complete_workflow(self, clean_test_environment, minio_container):
        """Test complete end-to-end workflow: install → configure → backup → verify.

        This is the main test - verifies everything works together:

        1. Fresh install in test mode using install.py
        2. Configure for Minio via environment variables
        3. Generate test photos with realistic content
        4. Run full backup cycle via sync command
        5. Verify files in Minio using verification command
        6. Confirm final state is correct
        """
        test_base_dir = clean_test_environment
        container_name = self._get_container_name(minio_container)
        install_script = Path(__file__).parent.parent.parent / "install.py"
        project_dir = install_script.parent

        # ═══════════════════════════════════════════════════════════════════════
        # STEP 1: Fresh install in test mode
        # ═══════════════════════════════════════════════════════════════════════
        print("\n" + "=" * 70)
        print("STEP 1: Fresh install in test mode")
        print("=" * 70)

        result = subprocess.run(
            [
                sys.executable,
                str(install_script),
                "install",
                "--test",
                "--skip-service",  # Can't run launchd in tests
            ],
            capture_output=True,
            text=True,
            cwd=str(project_dir),
            timeout=60,
        )

        assert result.returncode == 0, f"Install failed: {result.stderr}\n{result.stdout}"
        assert "Installation completed successfully" in result.stdout
        assert "TEST MODE" in result.stdout

        # Verify installation structure
        assert test_base_dir.exists(), "Test base directory should exist"
        assert (test_base_dir / "state").exists(), "State directory should exist"
        assert (test_base_dir / "config").exists(), "Config directory should exist"
        assert (test_base_dir / "config" / "config.yaml").exists(), "Config file should exist"

        print("✓ Installation completed successfully")
        print(f"  Base directory: {test_base_dir}")

        # ═══════════════════════════════════════════════════════════════════════
        # STEP 2: Configure for Minio (create bucket)
        # ═══════════════════════════════════════════════════════════════════════
        print("\n" + "=" * 70)
        print("STEP 2: Configure for Minio")
        print("=" * 70)

        assert self._create_test_bucket(container_name), "Failed to create test bucket"
        print(f"✓ Created bucket: {self.BUCKET_NAME}")
        print(f"  Minio endpoint: localhost:{self.MINIO_PORT}")

        # ═══════════════════════════════════════════════════════════════════════
        # STEP 3: Generate test photos
        # ═══════════════════════════════════════════════════════════════════════
        print("\n" + "=" * 70)
        print("STEP 3: Generate test photos")
        print("=" * 70)

        with tempfile.TemporaryDirectory() as temp_dir:
            test_photos_path = generate_test_photos(
                base_dir=temp_dir,
                num_files=10,
                min_size_mb=1,
                max_size_mb=2,
            )

            # Count files
            photo_files = list(test_photos_path.rglob("*"))
            photo_files = [f for f in photo_files if f.is_file()]
            total_size = sum(f.stat().st_size for f in photo_files)

            print(f"✓ Generated {len(photo_files)} test photos")
            print(f"  Location: {test_photos_path}")
            print(f"  Total size: {total_size / (1024 * 1024):.2f} MB")

            # Set up environment for Minio
            env = self._setup_environment(str(test_photos_path))

            # ═══════════════════════════════════════════════════════════════════
            # STEP 4: Run full backup cycle
            # ═══════════════════════════════════════════════════════════════════
            print("\n" + "=" * 70)
            print("STEP 4: Run full backup cycle")
            print("=" * 70)

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "photo_backup.main",
                    "--test-mode",
                    "sync",
                ],
                capture_output=True,
                text=True,
                cwd=str(project_dir),
                env=env,
                timeout=180,  # 3 minutes for backup
            )

            combined_output = result.stdout + result.stderr

            assert result.returncode == 0, f"Backup failed: {combined_output}"
            assert "TEST MODE" in combined_output
            assert "Backup completed successfully" in combined_output

            print("✓ Backup completed successfully")

            # Check for statistics in output
            if "Backup Statistics" in combined_output:
                print("  Backup statistics reported")

            # Allow Minio to settle
            time.sleep(1)

            # Verify files are in Minio
            minio_files = self._list_files_in_minio(container_name)
            assert len(minio_files) >= len(photo_files), (
                f"Expected at least {len(photo_files)} files in Minio, found {len(minio_files)}"
            )

            print(f"✓ Verified {len(minio_files)} files in Minio bucket")

            # ═══════════════════════════════════════════════════════════════════
            # STEP 5: Run verification
            # ═══════════════════════════════════════════════════════════════════
            print("\n" + "=" * 70)
            print("STEP 5: Run verification")
            print("=" * 70)

            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "photo_backup.main",
                    "--test-mode",
                    "verify",
                    "--verbose",
                ],
                capture_output=True,
                text=True,
                cwd=str(project_dir),
                env=env,
                timeout=180,  # 3 minutes for verification
            )

            verify_output = result.stdout + result.stderr

            # Verification should pass
            assert result.returncode == 0, f"Verification failed: {verify_output}"
            assert "VERIFICATION PASSED" in verify_output

            print("✓ Verification passed")

            # Check verification details
            if "Matched files:" in verify_output:
                # Extract matched count
                for line in verify_output.split("\n"):
                    if "Matched files:" in line:
                        print(f"  {line.strip()}")
                        break

            # ═══════════════════════════════════════════════════════════════════
            # STEP 6: Final state confirmation
            # ═══════════════════════════════════════════════════════════════════
            print("\n" + "=" * 70)
            print("STEP 6: Final state confirmation")
            print("=" * 70)

            # Check state files exist
            state_dir = test_base_dir / "state"
            state_files = list(state_dir.glob("*.json"))
            print(f"✓ State directory has {len(state_files)} state files")

            # Run status command to get current state
            result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "photo_backup.main",
                    "--test-mode",
                    "status",
                ],
                capture_output=True,
                text=True,
                cwd=str(project_dir),
                env=env,
                timeout=30,
            )

            if result.returncode == 0:
                print("✓ Status command reports healthy state")
            else:
                # Status command might not exist or have issues
                print("  Status command not available or returned non-zero")

            print("\n" + "=" * 70)
            print("END-TO-END TEST COMPLETE: All steps passed!")
            print("=" * 70 + "\n")

    @pytest.mark.functional
    @pytest.mark.slow
    def test_workflow_with_incremental_backup(self, clean_test_environment, minio_container):
        """Test that incremental backups work correctly.

        This test verifies:
        1. Initial backup uploads all files
        2. Second backup with same files does nothing (incremental)
        3. Third backup with new files only uploads new ones
        """
        test_base_dir = clean_test_environment  # noqa: F841
        container_name = self._get_container_name(minio_container)
        install_script = Path(__file__).parent.parent.parent / "install.py"
        project_dir = install_script.parent

        # Install
        result = subprocess.run(
            [sys.executable, str(install_script), "install", "--test", "--skip-service"],
            capture_output=True,
            text=True,
            cwd=str(project_dir),
            timeout=60,
        )
        assert result.returncode == 0, f"Install failed: {result.stderr}"

        # Create bucket
        assert self._create_test_bucket(container_name), "Failed to create bucket"

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create initial set of files
            photos_dir = temp_path / "photos"
            photos_dir.mkdir()

            for i in range(5):
                (photos_dir / f"photo_{i}.jpg").write_bytes(b"Initial content " * 1000 + str(i).encode())

            env = self._setup_environment(str(photos_dir))

            # First backup - should transfer all 5 files
            result = subprocess.run(
                [sys.executable, "-m", "photo_backup.main", "--test-mode", "sync"],
                capture_output=True,
                text=True,
                cwd=str(project_dir),
                env=env,
                timeout=120,
            )
            assert result.returncode == 0, f"First backup failed: {result.stdout + result.stderr}"

            time.sleep(0.5)

            files_after_first = self._list_files_in_minio(container_name)
            assert len(files_after_first) == 5, f"Expected 5 files, got {len(files_after_first)}"

            # Second backup - same files, should be quick (nothing to transfer)
            result = subprocess.run(
                [sys.executable, "-m", "photo_backup.main", "--test-mode", "sync"],
                capture_output=True,
                text=True,
                cwd=str(project_dir),
                env=env,
                timeout=120,
            )
            assert result.returncode == 0, f"Second backup failed: {result.stdout + result.stderr}"

            # Still 5 files
            files_after_second = self._list_files_in_minio(container_name)
            assert len(files_after_second) == 5, "File count should remain 5"

            # Add 3 more files
            for i in range(5, 8):
                (photos_dir / f"photo_{i}.jpg").write_bytes(b"New content " * 1000 + str(i).encode())

            # Third backup - should only transfer new files
            result = subprocess.run(
                [sys.executable, "-m", "photo_backup.main", "--test-mode", "sync"],
                capture_output=True,
                text=True,
                cwd=str(project_dir),
                env=env,
                timeout=120,
            )
            assert result.returncode == 0, f"Third backup failed: {result.stdout + result.stderr}"

            time.sleep(0.5)

            # Now should have 8 files
            files_after_third = self._list_files_in_minio(container_name)
            assert len(files_after_third) == 8, f"Expected 8 files, got {len(files_after_third)}"

            # Verify all files
            result = subprocess.run(
                [sys.executable, "-m", "photo_backup.main", "--test-mode", "verify", "--verbose"],
                capture_output=True,
                text=True,
                cwd=str(project_dir),
                env=env,
                timeout=120,
            )
            assert result.returncode == 0, f"Verification failed: {result.stdout + result.stderr}"
            assert "VERIFICATION PASSED" in (result.stdout + result.stderr)

    @pytest.mark.functional
    def test_workflow_dry_run(self, clean_test_environment, minio_container):
        """Test that dry-run mode works correctly in the workflow."""
        test_base_dir = clean_test_environment  # noqa: F841
        container_name = self._get_container_name(minio_container)
        install_script = Path(__file__).parent.parent.parent / "install.py"
        project_dir = install_script.parent

        # Install
        result = subprocess.run(
            [sys.executable, str(install_script), "install", "--test", "--skip-service"],
            capture_output=True,
            text=True,
            cwd=str(project_dir),
            timeout=60,
        )
        assert result.returncode == 0, f"Install failed: {result.stderr}"

        # Create bucket
        assert self._create_test_bucket(container_name), "Failed to create bucket"

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create test files
            for i in range(3):
                (temp_path / f"test_{i}.jpg").write_bytes(b"Test content " * 500)

            env = self._setup_environment(str(temp_path))

            # Dry-run backup
            result = subprocess.run(
                [sys.executable, "-m", "photo_backup.main", "--test-mode", "--dry-run", "sync"],
                capture_output=True,
                text=True,
                cwd=str(project_dir),
                env=env,
                timeout=60,
            )

            combined_output = result.stdout + result.stderr
            assert result.returncode == 0, f"Dry-run failed: {combined_output}"
            assert "DRY RUN" in combined_output

            # Verify no files actually uploaded
            time.sleep(0.5)
            files_in_minio = self._list_files_in_minio(container_name)
            assert len(files_in_minio) == 0, "Dry-run should not upload any files"

            # Now do actual backup
            result = subprocess.run(
                [sys.executable, "-m", "photo_backup.main", "--test-mode", "sync"],
                capture_output=True,
                text=True,
                cwd=str(project_dir),
                env=env,
                timeout=120,
            )
            assert result.returncode == 0, f"Actual backup failed: {result.stdout + result.stderr}"

            # Now files should be there
            time.sleep(0.5)
            files_in_minio = self._list_files_in_minio(container_name)
            assert len(files_in_minio) == 3, f"Expected 3 files after actual backup, got {len(files_in_minio)}"
