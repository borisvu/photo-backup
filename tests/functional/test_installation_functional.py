#!/usr/bin/env python3
"""
Installation Functional Test.

This test verifies the complete installation flow:
- Fresh test install using install.py
- Configure for Minio
- Run sync command to verify operation
- Verify the installed system works end-to-end

This is the integration point that validates the installer produces a working system.
"""

import os
import shutil
import subprocess
import sys

import pytest
from pathlib import Path

from tests.functional.minio_test_utils import MinioTestUtils


class TestInstallationFunctional:
    """Comprehensive functional test for complete install flow."""

    MINIO_PORT = 9010  # Unique port for this test suite

    # Use shared fixture factory to avoid code duplication
    minio_container = MinioTestUtils.create_minio_fixture("photo-backup-install-functional-test", port=MINIO_PORT)

    @pytest.fixture
    def clean_test_installation(self):
        """Clean up any existing test installation before and after test."""
        from photo_backup.consts import TEST_MODE_BASE_DIR

        test_base_dir = Path(TEST_MODE_BASE_DIR)

        # Clean up before test
        if test_base_dir.exists():
            shutil.rmtree(test_base_dir)

        yield test_base_dir

        # Clean up after test
        if test_base_dir.exists():
            shutil.rmtree(test_base_dir)

    @pytest.fixture
    def test_photos_dir(self, tmp_path):
        """Create a directory with test photos."""
        photos_dir = tmp_path / "test_photos"
        photos_dir.mkdir()

        # Create test photo files
        for i in range(3):
            photo_file = photos_dir / f"photo_{i}.jpg"
            # Write some content to make them non-empty
            photo_file.write_bytes(b"FAKE_JPEG_DATA" * 100)

        yield photos_dir

        # Cleanup handled by tmp_path fixture

    @pytest.mark.functional
    @pytest.mark.slow
    def test_complete_installation_flow(
        self,
        clean_test_installation,
        minio_container,
        test_photos_dir,
    ):
        """Test complete installation flow from fresh install to working sync.

        This is the main test - verifies:
        1. Fresh test install creates proper structure
        2. Configuration is ready for Minio
        3. Sync command runs successfully with Minio
        4. The installed system is fully operational
        """
        test_base_dir = clean_test_installation
        install_script = Path(__file__).parent.parent.parent / "install.py"

        # Step 1: Fresh test install
        # Skip service installation since we can't run launchd in tests
        result = subprocess.run(
            [
                sys.executable,
                str(install_script),
                "install",
                "--test",
                "--skip-service",
            ],
            capture_output=True,
            text=True,
            cwd=str(install_script.parent),
        )

        assert result.returncode == 0, f"Install failed: {result.stderr}\n{result.stdout}"
        assert "Installation completed successfully" in result.stdout
        assert "TEST MODE" in result.stdout

        # Verify installation created proper structure
        assert test_base_dir.exists(), "Test base directory should exist"
        assert (test_base_dir / "state").exists(), "State directory should exist"
        assert (test_base_dir / "config").exists(), "Config directory should exist"
        config_file = test_base_dir / "config" / "config.yaml"
        assert config_file.exists(), "Config file should exist"

        # Step 2: Configure environment for Minio
        env = os.environ.copy()
        env["PHOTO_BACKUP_BACKUP_SOURCE_PATH"] = str(test_photos_dir)
        env["PHOTO_BACKUP_STORAGE_ENDPOINT"] = f"localhost:{self.MINIO_PORT}"
        env["PHOTO_BACKUP_STORAGE_ACCESS_KEY"] = "minioadmin"
        env["PHOTO_BACKUP_STORAGE_SECRET_KEY"] = "minioadmin"
        env["PHOTO_BACKUP_STORAGE_USE_SSL"] = "false"
        env["PHOTO_BACKUP_STORAGE_BUCKET"] = "test-bucket"

        # Step 3: Run sync command with dry-run first to validate environment
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "photo_backup.main",
                "--test-mode",
                "--dry-run",
                "sync",
            ],
            capture_output=True,
            text=True,
            cwd=str(install_script.parent),
            env=env,
        )

        combined_output = result.stdout + result.stderr

        assert result.returncode == 0, f"Sync dry-run failed: {combined_output}"
        assert "TEST MODE (DRY RUN)" in combined_output
        assert "Backup completed successfully" in combined_output

        # Step 4: Run actual sync to verify full operation
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
            cwd=str(install_script.parent),
            env=env,
        )

        combined_output = result.stdout + result.stderr

        assert result.returncode == 0, f"Sync failed: {combined_output}"
        assert "TEST MODE" in combined_output
        assert "Backup completed successfully" in combined_output

        # Verify files were transferred (check stats output)
        # The sync should have transferred 3 files
        assert "Backup Statistics" in combined_output

    @pytest.mark.functional
    def test_installation_validates_correctly(self, clean_test_installation):
        """Test that validate command works after installation."""
        install_script = Path(__file__).parent.parent.parent / "install.py"

        # First, install
        result = subprocess.run(
            [
                sys.executable,
                str(install_script),
                "install",
                "--test",
                "--skip-service",
            ],
            capture_output=True,
            text=True,
            cwd=str(install_script.parent),
        )

        assert result.returncode == 0, f"Install failed: {result.stderr}"

        # Then validate
        result = subprocess.run(
            [
                sys.executable,
                str(install_script),
                "validate",
                "--test",
            ],
            capture_output=True,
            text=True,
            cwd=str(install_script.parent),
        )

        combined_output = result.stdout + result.stderr

        # Validation should check core components
        # Note: Minio check might fail if not running, but core checks should pass
        assert "Base directory" in combined_output
        assert "State directory" in combined_output
        assert "Config file" in combined_output

    @pytest.mark.functional
    def test_installation_uninstall_cleans_up(self, clean_test_installation):
        """Test that uninstall properly cleans up after installation."""
        test_base_dir = clean_test_installation
        install_script = Path(__file__).parent.parent.parent / "install.py"

        # First, install
        result = subprocess.run(
            [
                sys.executable,
                str(install_script),
                "install",
                "--test",
                "--skip-service",
            ],
            capture_output=True,
            text=True,
            cwd=str(install_script.parent),
        )

        assert result.returncode == 0, f"Install failed: {result.stderr}"
        assert test_base_dir.exists(), "Installation should create directories"

        # Then uninstall with --remove-data
        result = subprocess.run(
            [
                sys.executable,
                str(install_script),
                "uninstall",
                "--test",
                "--remove-data",
                "--yes",
            ],
            capture_output=True,
            text=True,
            cwd=str(install_script.parent),
        )

        assert result.returncode == 0, f"Uninstall failed: {result.stderr}"
        assert "Uninstall completed" in result.stdout

        # Verify cleanup
        assert not test_base_dir.exists(), "Uninstall should remove test directories"

    @pytest.mark.functional
    @pytest.mark.launchd
    def test_installation_upgrade_preserves_config(self, clean_test_installation):
        """Test that upgrade preserves existing configuration."""
        test_base_dir = clean_test_installation
        install_script = Path(__file__).parent.parent.parent / "install.py"

        # First, install
        result = subprocess.run(
            [
                sys.executable,
                str(install_script),
                "install",
                "--test",
                "--skip-service",
            ],
            capture_output=True,
            text=True,
            cwd=str(install_script.parent),
        )

        assert result.returncode == 0, f"Install failed: {result.stderr}"

        # Modify config to have custom content
        config_file = test_base_dir / "config" / "config.yaml"
        original_content = config_file.read_text()
        custom_marker = "# CUSTOM_TEST_MARKER"
        config_file.write_text(original_content + f"\n{custom_marker}\n")

        # Upgrade (should preserve config)
        result = subprocess.run(
            [
                sys.executable,
                str(install_script),
                "upgrade",
                "--test",
                "--yes",
                "--force",  # Force even if service not installed
            ],
            capture_output=True,
            text=True,
            cwd=str(install_script.parent),
        )

        assert result.returncode == 0, f"Upgrade failed: {result.stderr}"

        # Verify config was preserved
        new_content = config_file.read_text()
        assert custom_marker in new_content, "Config should be preserved during upgrade"

    @pytest.mark.functional
    @pytest.mark.slow
    def test_full_install_configure_sync_verify_flow(
        self,
        clean_test_installation,
        minio_container,
        test_photos_dir,
    ):
        """Test the complete flow: install -> configure -> sync -> verify in Minio.

        This is the most comprehensive test - verifies files actually end up in Minio.
        """
        import tempfile

        install_script = Path(__file__).parent.parent.parent / "install.py"

        # Step 1: Fresh install
        result = subprocess.run(
            [
                sys.executable,
                str(install_script),
                "install",
                "--test",
                "--skip-service",
            ],
            capture_output=True,
            text=True,
            cwd=str(install_script.parent),
        )
        assert result.returncode == 0, f"Install failed: {result.stderr}"

        # Step 2: Create rclone config for bucket creation and verification
        rclone_config = f"""[minio]
type = s3
provider = Minio
access_key_id = minioadmin
secret_access_key = minioadmin
endpoint = http://localhost:{self.MINIO_PORT}
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".conf", delete=False) as f:
            f.write(rclone_config)
            rclone_config_path = f.name

        # The backup destination bucket is 'my-photo-backup-bucket-test' (from backup.destination config)
        backup_bucket = "my-photo-backup-bucket-test"

        try:
            # Create the bucket first (required for S3-compatible storage)
            result = subprocess.run(
                [
                    "rclone",
                    "mkdir",
                    f"minio:{backup_bucket}",
                    "--config",
                    rclone_config_path,
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            assert result.returncode == 0, f"Bucket creation failed: {result.stderr}"

            # Step 3: Configure environment and sync
            env = os.environ.copy()
            env["PHOTO_BACKUP_BACKUP_SOURCE_PATH"] = str(test_photos_dir)
            env["PHOTO_BACKUP_STORAGE_ENDPOINT"] = f"localhost:{self.MINIO_PORT}"
            env["PHOTO_BACKUP_STORAGE_ACCESS_KEY"] = "minioadmin"
            env["PHOTO_BACKUP_STORAGE_SECRET_KEY"] = "minioadmin"
            env["PHOTO_BACKUP_STORAGE_USE_SSL"] = "false"
            env["PHOTO_BACKUP_STORAGE_BUCKET"] = "test-bucket"

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
                cwd=str(install_script.parent),
                env=env,
            )

            combined_output = result.stdout + result.stderr
            assert result.returncode == 0, f"Sync failed: {combined_output}"

            # Step 4: Verify files are in Minio using rclone
            verify_result = subprocess.run(
                [
                    "rclone",
                    "ls",
                    f"minio:{backup_bucket}/",
                    "--config",
                    rclone_config_path,
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )

            # Should have our 3 test photos
            assert verify_result.returncode == 0, f"Minio verify failed: {verify_result.stderr}"
            output_lines = [line for line in verify_result.stdout.strip().split("\n") if line]
            assert len(output_lines) >= 3, f"Expected at least 3 files in Minio, got: {output_lines}"

            # Verify the photo files are there
            for i in range(3):
                assert any(f"photo_{i}.jpg" in line for line in output_lines), f"photo_{i}.jpg should be in Minio"
        finally:
            Path(rclone_config_path).unlink(missing_ok=True)
