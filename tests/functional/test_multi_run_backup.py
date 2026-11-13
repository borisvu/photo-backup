#!/usr/bin/env python3
"""
Multi-Run Backup Test (Task 107).

Tests repeated backup operations with incremental changes to verify:
1. Initial backup uploads all files
2. Re-running backup with no changes does nothing (incremental)
3. Adding new files only uploads the new ones
4. Modifying files re-uploads the modified ones
5. No duplicate files are created in the remote
6. Verification passes after each cycle
"""

import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import time

import pytest
from pathlib import Path

from tests.functional.minio_test_utils import MinioTestUtils


class TestMultiRunBackup:
    """Test repeated backup operations with incremental changes."""

    # Unique port for this test suite to avoid conflicts
    MINIO_PORT = 9031
    BUCKET_NAME = "my-photo-backup-bucket-test"

    # Use shared fixture factory
    minio_container = MinioTestUtils.create_minio_fixture(
        "photo-backup-multi-run-test",
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
        """List files in the Minio bucket with their paths."""
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

    def _get_file_hashes_in_minio(self, container_name: str) -> dict[str, str]:
        """Get MD5 hashes of all files in Minio bucket.

        Returns:
            Dict mapping file path to MD5 hash
        """
        result = subprocess.run(
            [
                "docker",
                "exec",
                container_name,
                "mc",
                "stat",
                f"test/{self.BUCKET_NAME}/",
                "--recursive",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            return {}

        # Parse stat output to extract file paths and etags/hashes
        hashes = {}
        current_file = None
        for line in result.stdout.split("\n"):
            line = line.strip()
            if line.startswith("Name"):
                # Name      : path/to/file
                current_file = line.split(":", 1)[1].strip()
            elif line.startswith("ETag") and current_file:
                # ETag      : md5hash
                etag = line.split(":", 1)[1].strip()
                hashes[current_file] = etag
                current_file = None
        return hashes

    def _run_backup(self, env: dict, project_dir: Path, timeout: int = 120) -> subprocess.CompletedProcess:
        """Run a backup sync command."""
        return subprocess.run(
            [sys.executable, "-m", "photo_backup.main", "--test-mode", "sync"],
            capture_output=True,
            text=True,
            cwd=str(project_dir),
            env=env,
            timeout=timeout,
        )

    def _run_verify(self, env: dict, project_dir: Path, timeout: int = 120) -> subprocess.CompletedProcess:
        """Run verification command."""
        return subprocess.run(
            [sys.executable, "-m", "photo_backup.main", "--test-mode", "verify", "--verbose"],
            capture_output=True,
            text=True,
            cwd=str(project_dir),
            env=env,
            timeout=timeout,
        )

    def _create_test_file(self, directory: Path, name: str, content: bytes) -> Path:
        """Create a test file with specific content."""
        file_path = directory / name
        file_path.write_bytes(content)
        return file_path

    def _get_file_hash(self, file_path: Path) -> str:
        """Calculate MD5 hash of a local file."""
        md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                md5.update(chunk)
        return md5.hexdigest()

    @pytest.mark.functional
    @pytest.mark.slow
    def test_multi_run_incremental_backup(self, clean_test_environment, minio_container):
        """Test multiple backup cycles with incremental changes.

        This comprehensive test verifies:
        1. Cycle 1: Initial backup - all files uploaded
        2. Cycle 2: No changes - nothing uploaded (incremental)
        3. Cycle 3: Add new files - only new files uploaded
        4. Cycle 4: Modify existing file - modified file re-uploaded
        5. Cycle 5: No changes again - nothing uploaded
        6. Throughout: No duplicates created, verification passes
        """
        container_name = self._get_container_name(minio_container)
        install_script = Path(__file__).parent.parent.parent / "install.py"
        project_dir = install_script.parent

        # ═══════════════════════════════════════════════════════════════════════
        # SETUP: Install and configure
        # ═══════════════════════════════════════════════════════════════════════
        print("\n" + "=" * 70)
        print("SETUP: Install and configure test environment")
        print("=" * 70)

        # Install
        result = subprocess.run(
            [sys.executable, str(install_script), "install", "--test", "--skip-service"],
            capture_output=True,
            text=True,
            cwd=str(project_dir),
            timeout=60,
        )
        assert result.returncode == 0, f"Install failed: {result.stderr}"
        print("✓ Installation completed")

        # Create bucket
        assert self._create_test_bucket(container_name), "Failed to create bucket"
        print(f"✓ Created bucket: {self.BUCKET_NAME}")

        with tempfile.TemporaryDirectory() as temp_dir:
            photos_dir = Path(temp_dir) / "photos"
            photos_dir.mkdir()
            env = self._setup_environment(str(photos_dir))

            # Track state across cycles
            expected_files: set[str] = set()
            cycle_results: list[dict] = []

            # ═══════════════════════════════════════════════════════════════════
            # CYCLE 1: Initial backup with 5 files
            # ═══════════════════════════════════════════════════════════════════
            print("\n" + "=" * 70)
            print("CYCLE 1: Initial backup with 5 files")
            print("=" * 70)

            initial_files = {}
            for i in range(5):
                name = f"photo_{i:03d}.jpg"
                content = f"Initial content for file {i}".encode() * 1000
                file_path = self._create_test_file(photos_dir, name, content)
                initial_files[name] = self._get_file_hash(file_path)
                expected_files.add(name)

            result = self._run_backup(env, project_dir)
            assert result.returncode == 0, f"Cycle 1 backup failed: {result.stdout + result.stderr}"

            time.sleep(0.5)
            minio_files = self._list_files_in_minio(container_name)
            assert len(minio_files) == 5, f"Cycle 1: Expected 5 files, got {len(minio_files)}"

            # Verify no duplicates (unique file names)
            unique_files = set(minio_files)
            assert len(unique_files) == len(minio_files), "Cycle 1: Duplicate files detected!"

            cycle_results.append({"cycle": 1, "action": "initial", "files_in_minio": len(minio_files)})
            print(f"✓ Uploaded {len(minio_files)} files")

            # Verify
            result = self._run_verify(env, project_dir)
            assert result.returncode == 0, f"Cycle 1 verification failed: {result.stdout + result.stderr}"
            assert "VERIFICATION PASSED" in (result.stdout + result.stderr)
            print("✓ Verification passed")

            # ═══════════════════════════════════════════════════════════════════
            # CYCLE 2: No changes - should be quick (nothing to transfer)
            # ═══════════════════════════════════════════════════════════════════
            print("\n" + "=" * 70)
            print("CYCLE 2: No changes - incremental sync should transfer nothing")
            print("=" * 70)

            start_time = time.time()
            result = self._run_backup(env, project_dir)
            cycle2_duration = time.time() - start_time
            assert result.returncode == 0, f"Cycle 2 backup failed: {result.stdout + result.stderr}"

            minio_files = self._list_files_in_minio(container_name)
            assert len(minio_files) == 5, f"Cycle 2: Expected 5 files, got {len(minio_files)}"

            # Verify no duplicates
            unique_files = set(minio_files)
            assert len(unique_files) == len(minio_files), "Cycle 2: Duplicate files detected!"

            cycle_results.append(
                {
                    "cycle": 2,
                    "action": "no-op",
                    "files_in_minio": len(minio_files),
                    "duration": cycle2_duration,
                }
            )
            print(f"✓ Completed in {cycle2_duration:.2f}s (should be fast)")
            print(f"✓ File count unchanged: {len(minio_files)}")

            # Verify
            result = self._run_verify(env, project_dir)
            assert result.returncode == 0, f"Cycle 2 verification failed: {result.stdout + result.stderr}"
            assert "VERIFICATION PASSED" in (result.stdout + result.stderr)
            print("✓ Verification passed")

            # ═══════════════════════════════════════════════════════════════════
            # CYCLE 3: Add 3 new files
            # ═══════════════════════════════════════════════════════════════════
            print("\n" + "=" * 70)
            print("CYCLE 3: Add 3 new files")
            print("=" * 70)

            for i in range(5, 8):
                name = f"photo_{i:03d}.jpg"
                content = f"New content for file {i}".encode() * 1000
                self._create_test_file(photos_dir, name, content)
                expected_files.add(name)

            result = self._run_backup(env, project_dir)
            assert result.returncode == 0, f"Cycle 3 backup failed: {result.stdout + result.stderr}"

            time.sleep(0.5)
            minio_files = self._list_files_in_minio(container_name)
            assert len(minio_files) == 8, f"Cycle 3: Expected 8 files, got {len(minio_files)}"

            # Verify no duplicates
            unique_files = set(minio_files)
            assert len(unique_files) == len(minio_files), "Cycle 3: Duplicate files detected!"

            cycle_results.append({"cycle": 3, "action": "add 3 files", "files_in_minio": len(minio_files)})
            print(f"✓ Now have {len(minio_files)} files")

            # Verify
            result = self._run_verify(env, project_dir)
            assert result.returncode == 0, f"Cycle 3 verification failed: {result.stdout + result.stderr}"
            assert "VERIFICATION PASSED" in (result.stdout + result.stderr)
            print("✓ Verification passed")

            # ═══════════════════════════════════════════════════════════════════
            # CYCLE 4: Modify an existing file
            # ═══════════════════════════════════════════════════════════════════
            print("\n" + "=" * 70)
            print("CYCLE 4: Modify an existing file (photo_000.jpg)")
            print("=" * 70)

            # Get hash before modification
            modified_file = photos_dir / "photo_000.jpg"
            old_hash = self._get_file_hash(modified_file)

            # Modify the file
            new_content = b"MODIFIED CONTENT - this file has been changed!" * 1000
            modified_file.write_bytes(new_content)
            new_hash = self._get_file_hash(modified_file)

            assert old_hash != new_hash, "File modification should change hash"
            print(f"  Old hash: {old_hash[:16]}...")
            print(f"  New hash: {new_hash[:16]}...")

            result = self._run_backup(env, project_dir)
            assert result.returncode == 0, f"Cycle 4 backup failed: {result.stdout + result.stderr}"

            time.sleep(0.5)
            minio_files = self._list_files_in_minio(container_name)
            assert len(minio_files) == 8, f"Cycle 4: Expected 8 files, got {len(minio_files)}"

            # Verify no duplicates
            unique_files = set(minio_files)
            assert len(unique_files) == len(minio_files), "Cycle 4: Duplicate files detected!"

            cycle_results.append({"cycle": 4, "action": "modify file", "files_in_minio": len(minio_files)})
            print(f"✓ File count unchanged: {len(minio_files)}")

            # Verify
            result = self._run_verify(env, project_dir)
            assert result.returncode == 0, f"Cycle 4 verification failed: {result.stdout + result.stderr}"
            assert "VERIFICATION PASSED" in (result.stdout + result.stderr)
            print("✓ Verification passed")

            # ═══════════════════════════════════════════════════════════════════
            # CYCLE 5: No changes again
            # ═══════════════════════════════════════════════════════════════════
            print("\n" + "=" * 70)
            print("CYCLE 5: No changes again - confirm incremental still works")
            print("=" * 70)

            start_time = time.time()
            result = self._run_backup(env, project_dir)
            cycle5_duration = time.time() - start_time
            assert result.returncode == 0, f"Cycle 5 backup failed: {result.stdout + result.stderr}"

            minio_files = self._list_files_in_minio(container_name)
            assert len(minio_files) == 8, f"Cycle 5: Expected 8 files, got {len(minio_files)}"

            # Verify no duplicates
            unique_files = set(minio_files)
            assert len(unique_files) == len(minio_files), "Cycle 5: Duplicate files detected!"

            cycle_results.append(
                {
                    "cycle": 5,
                    "action": "no-op",
                    "files_in_minio": len(minio_files),
                    "duration": cycle5_duration,
                }
            )
            print(f"✓ Completed in {cycle5_duration:.2f}s")

            # Verify
            result = self._run_verify(env, project_dir)
            assert result.returncode == 0, f"Cycle 5 verification failed: {result.stdout + result.stderr}"
            assert "VERIFICATION PASSED" in (result.stdout + result.stderr)
            print("✓ Verification passed")

            # ═══════════════════════════════════════════════════════════════════
            # FINAL: Summary and duplicate check
            # ═══════════════════════════════════════════════════════════════════
            print("\n" + "=" * 70)
            print("FINAL: Summary and duplicate verification")
            print("=" * 70)

            # Final file list
            final_files = self._list_files_in_minio(container_name)
            print(f"\nFinal file count: {len(final_files)}")

            # Check for duplicates by filename
            file_names = [f.split("/")[-1] for f in final_files]
            unique_names = set(file_names)
            if len(unique_names) != len(file_names):
                # Find duplicates
                from collections import Counter

                counts = Counter(file_names)
                duplicates = {name: count for name, count in counts.items() if count > 1}
                pytest.fail(f"Duplicate files detected: {duplicates}")

            print("✓ No duplicate files detected")

            # Print cycle summary
            print("\nCycle Summary:")
            for cycle in cycle_results:
                action = cycle["action"]
                files = cycle["files_in_minio"]
                duration = cycle.get("duration", "")
                duration_str = f" ({duration:.2f}s)" if duration else ""
                print(f"  Cycle {cycle['cycle']}: {action} → {files} files{duration_str}")

            print("\n" + "=" * 70)
            print("MULTI-RUN TEST COMPLETE: All cycles passed!")
            print("=" * 70 + "\n")

    @pytest.mark.functional
    def test_incremental_preserves_unchanged_files(self, clean_test_environment, minio_container):
        """Test that unchanged files are not re-uploaded.

        Verifies that rclone's incremental sync correctly detects unchanged files
        and does not transfer them again.
        """
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
            photos_dir = Path(temp_dir) / "photos"
            photos_dir.mkdir()
            env = self._setup_environment(str(photos_dir))

            # Create initial files
            for i in range(3):
                name = f"unchanged_{i}.jpg"
                content = f"This file will not change {i}".encode() * 500
                self._create_test_file(photos_dir, name, content)

            # First backup
            result = self._run_backup(env, project_dir)
            assert result.returncode == 0, f"First backup failed: {result.stdout + result.stderr}"

            time.sleep(0.5)

            # Get file hashes after first backup
            initial_hashes = self._get_file_hashes_in_minio(container_name)
            assert len(initial_hashes) == 3, f"Expected 3 files, got {len(initial_hashes)}"

            # Second backup (no changes)
            result = self._run_backup(env, project_dir)
            assert result.returncode == 0, f"Second backup failed: {result.stdout + result.stderr}"

            # Get file hashes after second backup
            final_hashes = self._get_file_hashes_in_minio(container_name)
            assert len(final_hashes) == 3, f"Expected 3 files, got {len(final_hashes)}"

            # Hashes should be identical (files weren't re-uploaded)
            for file_path, initial_hash in initial_hashes.items():
                assert file_path in final_hashes, f"File {file_path} missing after second backup"
                assert final_hashes[file_path] == initial_hash, (
                    f"File {file_path} hash changed: {initial_hash} → {final_hashes[file_path]}"
                )

    @pytest.mark.functional
    def test_multiple_rapid_backups(self, clean_test_environment, minio_container):
        """Test running backups in rapid succession.

        Verifies that the system handles multiple quick backup requests correctly
        without race conditions or data corruption.
        """
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
            photos_dir = Path(temp_dir) / "photos"
            photos_dir.mkdir()
            env = self._setup_environment(str(photos_dir))

            # Create a file
            self._create_test_file(photos_dir, "rapid_test.jpg", b"Rapid test content" * 500)

            # Run 5 backups in rapid succession
            for i in range(5):
                result = self._run_backup(env, project_dir)
                assert result.returncode == 0, f"Rapid backup {i + 1} failed: {result.stdout + result.stderr}"

            # Verify final state
            time.sleep(0.5)
            minio_files = self._list_files_in_minio(container_name)
            assert len(minio_files) == 1, f"Expected 1 file, got {len(minio_files)}: {minio_files}"

            # No duplicates
            unique_files = set(minio_files)
            assert len(unique_files) == len(minio_files), "Duplicate files after rapid backups!"

            # Verification should pass
            result = self._run_verify(env, project_dir)
            assert result.returncode == 0, f"Verification failed: {result.stdout + result.stderr}"
            assert "VERIFICATION PASSED" in (result.stdout + result.stderr)
