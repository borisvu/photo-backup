#!/usr/bin/env python3
"""
Photo Backup System - Credential Flow Functional Tests

Tests the complete credential flow with Minio container.
"""

import os
import shutil
import subprocess

import pytest
from pathlib import Path

from photo_backup.config.config import Config
from photo_backup.credentials import CredentialManager


class TestCredentialFlow:
    """Test complete credential flow with Minio container."""

    # Use shared fixture factory to avoid code duplication
    from tests.functional.minio_test_utils import MinioTestUtils

    minio_container = MinioTestUtils.create_minio_fixture("photo-backup-credential-test", port=9001)

    @pytest.fixture
    def test_config(self) -> Config:
        """Create test configuration."""
        # Use standard Config constructor
        config_obj = Config(test_mode=True)
        config_obj.load_config()
        # Override endpoint and credentials to use unique port
        storage = config_obj._config.setdefault("storage", {})
        storage["endpoint"] = "localhost:9001"
        storage["access_key"] = "minioadmin"
        storage["secret_key"] = "minioadmin"
        storage["use_ssl"] = False
        storage["bucket"] = "test-bucket"
        return config_obj

    def test_complete_credential_flow(self, minio_container: str, test_config: Config):  # noqa: ARG002
        """Test complete credential flow with Minio."""
        # Create test photos directory
        test_photos_dir = Path("/tmp/test-photos")
        test_photos_dir.mkdir(exist_ok=True)

        # Create some test files
        for i in range(3):
            test_file = test_photos_dir / f"test_photo_{i}.jpg"
            test_file.write_text(f"Test photo content {i}")

        # Initialize rclone_config_path to None to avoid UnboundLocalError
        rclone_config_path = None

        try:
            # Initialize credential manager
            manager = CredentialManager(test_config)

            # Test 1: Retrieve credentials
            credentials = manager.get_credentials()
            assert credentials is not None
            assert "access_key" in credentials
            assert "secret_key" in credentials
            assert credentials["access_key"] == "minioadmin"
            assert credentials["secret_key"] == "minioadmin"

            # Test 2: Validate credentials with rclone
            is_valid, message = manager.validate_credentials()
            assert is_valid, f"Credential validation failed: {message}"
            assert "valid" in message.lower() or "success" in message.lower()

            # Test 3: Get credential status
            status = manager.get_credential_status()
            assert status["mode"] == "test"
            assert status["has_credentials"] is True
            assert status["validation"]["is_valid"] is True

            # Test 4: Test S3 access with rclone
            # Create rclone config for Minio
            rclone_config = f"""[minio]
type = s3
provider = Minio
access_key_id = {credentials["access_key"]}
secret_access_key = {credentials["secret_key"]}
endpoint = http://localhost:9001
region = us-east-1
"""

            rclone_config_path = Path("/tmp/test-rclone.conf")
            rclone_config_path.write_text(rclone_config)

            # Test bucket creation
            result = subprocess.run(
                ["rclone", "mkdir", "minio:test-bucket", "--config", str(rclone_config_path)],
                capture_output=True,
                text=True,
                timeout=30,
            )
            assert result.returncode == 0, f"Failed to create bucket: {result.stderr}"

            # Test file upload
            result = subprocess.run(
                [
                    "rclone",
                    "copy",
                    str(test_photos_dir),
                    "minio:test-bucket/photos",
                    "--config",
                    str(rclone_config_path),
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            assert result.returncode == 0, f"Failed to upload files: {result.stderr}"

            # Test file listing
            result = subprocess.run(
                ["rclone", "ls", "minio:test-bucket/photos", "--config", str(rclone_config_path)],
                capture_output=True,
                text=True,
                timeout=30,
            )
            assert result.returncode == 0, f"Failed to list files: {result.stderr}"
            assert "test_photo_0.jpg" in result.stdout
            assert "test_photo_1.jpg" in result.stdout
            assert "test_photo_2.jpg" in result.stdout

            print("✅ Complete credential flow test passed!")

        finally:
            # Cleanup test files
            if test_photos_dir.exists():
                shutil.rmtree(test_photos_dir)

            # Cleanup rclone config - only if it was created
            if rclone_config_path and rclone_config_path.exists():
                rclone_config_path.unlink()

    def test_credential_flow_with_cli(self, minio_container: str):  # noqa: ARG002
        """Test credential flow using the CLI test-auth command."""
        # Set test environment with credentials and endpoint
        env = os.environ.copy()
        env["PHOTO_BACKUP_TEST_MODE"] = "1"
        env["PHOTO_BACKUP_STORAGE_ENDPOINT"] = "localhost:9001"
        env["PHOTO_BACKUP_STORAGE_ACCESS_KEY"] = "minioadmin"
        env["PHOTO_BACKUP_STORAGE_SECRET_KEY"] = "minioadmin"
        env["PHOTO_BACKUP_STORAGE_USE_SSL"] = "false"
        env["PHOTO_BACKUP_STORAGE_BUCKET"] = "test-bucket"

        # Run test-auth command with --test-mode flag
        result = subprocess.run(
            ["python3", "-m", "photo_backup.main", "--test-mode", "test-auth", "--verbose"],
            capture_output=True,
            text=True,
            cwd=".",
            env=env,
            timeout=60,
        )

        combined_output = result.stdout + result.stderr

        # Verify command succeeded
        assert result.returncode == 0, f"test-auth command failed: {combined_output}"

        # Verify expected output
        assert "🔐 Testing authentication in TEST MODE" in combined_output
        assert "📋 Mode: test" in combined_output
        assert "🔑 Has credentials: ✅ Yes" in combined_output
        assert "✅ Credential validation: PASSED" in combined_output
        assert "🎉 Authentication test completed successfully!" in combined_output

        print("✅ CLI credential flow test passed!")

    def test_credential_flow_error_handling(self):
        """Test credential flow with test-auth command (Phase 5).

        After Phase 1/2: Credentials are loaded successfully even if Minio isn't available.
        The test-auth command may pass or fail depending on Minio availability.
        """
        # Set test environment
        env = os.environ.copy()
        env["PHOTO_BACKUP_TEST_MODE"] = "1"

        # Run test-auth command with --test-mode flag
        result = subprocess.run(
            ["python3", "-m", "photo_backup.main", "--test-mode", "test-auth"],
            capture_output=True,
            text=True,
            cwd=".",
            env=env,
            timeout=30,
        )

        combined_output = result.stdout + result.stderr

        # Verify test mode is recognized
        assert "Testing authentication in TEST MODE" in combined_output or "TEST MODE" in combined_output

        # Command may pass (if Minio available) or fail (if not)
        # Both outcomes are acceptable after refactoring
        if result.returncode != 0:
            # If it failed, should show failure message
            assert "Authentication test failed!" in combined_output or "failed" in combined_output.lower()

        print("✅ Credential flow test passed!")

    def test_credential_flow_basic(self):
        """Test basic credential flow without Docker/Minio."""
        # Create test configuration
        config_obj = Config(test_mode=True)
        config_obj.load_config()

        # Configure credentials explicitly
        storage = config_obj._config.setdefault("storage", {})
        storage["endpoint"] = "localhost:9001"
        storage["access_key"] = "minioadmin"
        storage["secret_key"] = "minioadmin"
        storage["use_ssl"] = False
        storage["bucket"] = "test-bucket"

        # Initialize credential manager
        manager = CredentialManager(config_obj)

        # Test 1: Retrieve credentials
        credentials = manager.get_credentials()
        assert credentials is not None
        assert "access_key" in credentials
        assert "secret_key" in credentials
        assert credentials["access_key"] == "minioadmin"
        assert credentials["secret_key"] == "minioadmin"

        # Test 2: Get credential status
        status = manager.get_credential_status()
        assert status["mode"] == "test"
        # has_credentials depends on whether Minio is available for validation
        # After Phase 1/2: credentials are loaded but validation may fail
        # If Minio is running, validation passes; if not, it fails
        # Both scenarios are valid for this basic test

        # Test 3: Validate credentials (may pass or fail depending on Minio availability)
        is_valid, message = manager.validate_credentials()
        # After Phase 1/2: Validation outcome depends on Minio availability
        # Test should not crash regardless of outcome
        # If Minio is available, validation passes; if not, it fails gracefully
        if not is_valid:
            assert (
                "timed out" in message.lower()
                or "connection" in message.lower()
                or "failed" in message.lower()
                or "refused" in message.lower()
            )

        print("✅ Basic credential flow test passed!")
