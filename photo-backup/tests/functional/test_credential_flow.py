#!/usr/bin/env python3
"""
Photo Backup System - Credential Flow Functional Tests

Task 52: Credential Functional Test
Tests the complete credential flow with Minio container.
"""

import os
import shutil
import subprocess
import time
from collections.abc import Generator

import docker
import pytest
from pathlib import Path

from photo_backup.config.config import Config
from photo_backup.credentials import CredentialManager


class TestCredentialFlow:
    """Test complete credential flow with Minio container."""

    @pytest.fixture
    def minio_container(self) -> Generator[str]:
        """Start Minio container and yield container ID."""
        client = None
        try:
            # Try to get the Docker Desktop socket path programmatically
            result = subprocess.run(["docker", "context", "ls"], capture_output=True, text=True)
            if result.returncode == 0:
                lines = result.stdout.split("\n")
                socket_path = None

                # Find the active context (marked with *)
                for line in lines:
                    if "*" in line and "desktop" in line.lower():
                        parts = line.split()
                        for part in parts:
                            if part.startswith("unix://"):
                                socket_path = part.replace("unix://", "")
                                break
                        if socket_path:
                            break

                if socket_path:
                    client = docker.DockerClient(base_url=f"unix://{socket_path}") if socket_path else docker.from_env()
                else:
                    client = docker.from_env()
            else:
                client = docker.from_env()

        except Exception as e:
            print(f"Error connecting to Docker: {e}")
            pytest.skip("Docker not available or not running")

        if client is None:
            pytest.skip("Docker not available or not running")

        # Start Minio container
        assert client is not None  # Type guard for mypy
        container = client.containers.run(
            "minio/minio:latest",
            command="server /data --console-address :9001",
            ports={"9000/tcp": 9000, "9001/tcp": 9001},
            environment={"MINIO_ROOT_USER": "minioadmin", "MINIO_ROOT_PASSWORD": "minioadmin"},
            detach=True,
            remove=True,
        )

        container_id = container.id

        # Wait for Minio to be ready
        max_attempts = 30
        for _attempt in range(max_attempts):
            try:
                result = subprocess.run(
                    ["curl", "-f", "http://localhost:9000/minio/health/live"], capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    break
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass

            time.sleep(1)
        else:
            # Clean up on failure
            try:
                container.stop(timeout=5)
                container.remove()
            except Exception:
                pass
            pytest.fail("Minio container failed to start within 30 seconds")

        yield container_id

        # Cleanup
        try:
            if client is not None:  # Type guard for mypy
                container = client.containers.get(container_id)
                container.stop(timeout=5)
                container.remove()
        except Exception:
            pass

    @pytest.fixture
    def test_config(self) -> Config:
        """Create test configuration."""
        # Use standard Config constructor
        config_obj = Config(test_mode=True)
        config_obj.load_config()
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
endpoint = http://localhost:9000
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
        # Set test environment
        env = os.environ.copy()
        env["PHOTO_BACKUP_TEST_MODE"] = "1"

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
        """Test credential flow error handling when Minio is not available."""
        # Set test environment but don't start Minio
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

        # Verify command failed as expected
        assert result.returncode == 1, f"test-auth should have failed: {combined_output}"

        # Verify error handling - should show test mode but fail due to no Minio
        assert "🔐 Testing authentication in TEST MODE" in combined_output
        assert "💥 Authentication test failed!" in combined_output

        print("✅ Credential flow error handling test passed!")

    def test_credential_flow_basic(self):
        """Test basic credential flow without Docker/Minio."""
        # Create test configuration
        config_obj = Config(test_mode=True)
        config_obj.load_config()

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
        # has_credentials will be False because validation fails without Minio
        assert status["has_credentials"] is False
        assert status["validation"]["is_valid"] is False

        # Test 3: Validate credentials (this will fail without Minio, but should handle gracefully)
        is_valid, message = manager.validate_credentials()
        # In test mode without Minio, this should fail but not crash
        assert not is_valid
        assert "timed out" in message.lower() or "connection" in message.lower() or "failed" in message.lower()

        print("✅ Basic credential flow test passed!")
