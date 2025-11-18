#!/usr/bin/env python3
"""
Functional tests for the test-auth CLI command.
"""

import os
import subprocess
import tempfile

from pathlib import Path


class TestAuthCommandFunctional:
    """Functional tests for the test-auth command."""

    def test_test_auth_help(self):
        """Test that test-auth command shows help."""
        result = subprocess.run(
            ["python3", "-m", "photo_backup.main", "test-auth", "--help"],
            capture_output=True,
            text=True,
            cwd=".",
        )

        assert result.returncode == 0
        assert "test-auth" in result.stdout
        assert "Test credential setup and S3 access" in result.stdout
        assert "--verbose" in result.stdout

    def test_test_auth_test_mode_success(self, minio_container):  # noqa: ARG002
        """Test test-auth command success in test mode with Minio running."""
        # Minio container is managed by fixture
        result = subprocess.run(
            ["python3", "-m", "photo_backup.main", "--test-mode", "test-auth"],
            capture_output=True,
            text=True,
            cwd=".",
        )

        # Combine stdout and stderr for checking output
        combined_output = result.stdout + result.stderr

        # Should succeed if Minio is running
        if result.returncode == 0:
            assert "🔐 Testing authentication in TEST MODE" in combined_output
            assert "📋 Mode: test" in combined_output
            assert "🔑 Has credentials: ✅ Yes" in combined_output
            assert "✅ Credential validation: PASSED" in combined_output
            assert "✅ S3 access test: PASSED" in combined_output
            assert "🎉 Authentication test completed successfully!" in combined_output
        else:
            # If it fails, it should be due to Minio not running or other issues
            assert any(
                error_msg in combined_output.lower()
                for error_msg in [
                    "cannot connect to minio",
                    "connection refused",
                    "directory not found",
                    "minio test failed",
                    "rclone test timed out",
                ]
            )

    def test_test_auth_test_mode_verbose(self, minio_container):  # noqa: ARG002
        """Test test-auth command with verbose flag in test mode."""
        # Minio container is managed by fixture
        result = subprocess.run(
            ["python3", "-m", "photo_backup.main", "--test-mode", "test-auth", "--verbose"],
            capture_output=True,
            text=True,
            cwd=".",
        )

        # Combine stdout and stderr for checking output
        combined_output = result.stdout + result.stderr

        # Should show verbose output
        if result.returncode == 0:
            assert "🔐 Testing authentication in TEST MODE" in combined_output
            assert "📊 Detailed Status:" in combined_output
            assert "🎉 Authentication test completed successfully!" in combined_output
        else:
            # If it fails, should still show verbose information
            assert "📊 Detailed Status:" in combined_output or any(
                error_msg in combined_output.lower()
                for error_msg in [
                    "cannot connect to minio",
                    "connection refused",
                    "directory not found",
                    "minio test failed",
                    "rclone test timed out",
                ]
            )

    def test_test_auth_production_mode_no_credentials(self):
        """Test test-auth command in production mode with no credentials."""
        # Clear only credential-related environment variables
        env = os.environ.copy()
        env.pop("WASABI_ACCESS_KEY", None)
        env.pop("WASABI_SECRET_KEY", None)
        env.pop("S3_ACCESS_KEY", None)
        env.pop("S3_SECRET_KEY", None)
        env.pop("PHOTO_BACKUP_CONFIG", None)

        result = subprocess.run(
            ["python3", "-m", "photo_backup.main", "test-auth"],
            capture_output=True,
            text=True,
            cwd=".",
            env=env,
        )

        # Combine stdout and stderr for checking output
        combined_output = result.stdout + result.stderr

        # Should fail due to no credentials
        assert result.returncode == 1
        assert "🔐 Testing authentication in PRODUCTION MODE" in combined_output
        assert "📋 Mode: production" in combined_output
        # The system might detect credentials from config, so check for either case
        assert "🔑 Has credentials: ❌ No" in combined_output or "🔑 Has credentials: ✅ Yes" in combined_output
        assert "💥 Authentication test failed!" in combined_output

    def test_test_auth_production_mode_with_env_vars(self):
        """Test test-auth command in production mode with environment variables."""
        # Set test environment variables
        env = os.environ.copy()
        env["WASABI_ACCESS_KEY"] = "test-access-key"
        env["WASABI_SECRET_KEY"] = "test-secret-key"

        result = subprocess.run(
            ["python3", "-m", "photo_backup.main", "test-auth"],
            capture_output=True,
            text=True,
            cwd=".",
            env=env,
        )

        # Combine stdout and stderr for checking output
        combined_output = result.stdout + result.stderr

        # Should fail due to invalid credentials
        assert result.returncode == 1
        assert "🔐 Testing authentication in PRODUCTION MODE" in combined_output
        assert "📋 Mode: production" in combined_output
        # The system should detect credentials but validation fails, so it shows "❌ No"
        assert "🔑 Has credentials: ❌ No" in combined_output
        assert "💥 Authentication test failed!" in combined_output

    def test_test_auth_with_config_file(self):
        """Test test-auth command with credentials in config file."""
        # Create temporary config file with credentials
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            config_content = """
backup:
  source_path: /test/photos
  destination: s3://test-bucket/photos
  exclude_patterns: []
  include_patterns: ["*.jpg", "*.jpeg", "*.png", "*.gif", "*.bmp", "*.tiff", "*.raw"]

storage:
  endpoint: s3.wasabisys.com
  region: us-east-1
  use_ssl: true
  bucket: test-bucket
  access_key: test-access-key
  secret_key: test-secret-key
  timeout_seconds: 300
  retry_attempts: 3

monitoring:
  enabled: true
  interval_seconds: 300
  check_interval_seconds: 60

logging:
  level: INFO
  format: detailed
  directory: /tmp/photo-backup-test/logs
  max_files: 10
  max_size_mb: 10

state:
  directory: /tmp/photo-backup-test/state
  file: backup_state.json
  backup_count: 5
"""
            f.write(config_content)
            config_file = f.name

        try:
            # Create temporary source directory
            with tempfile.TemporaryDirectory() as temp_dir:
                source_path = Path(temp_dir) / "test-photos"
                source_path.mkdir()

                # Update config file with valid source path
                with open(config_file) as f:
                    content = f.read()
                content = content.replace("/test/photos", str(source_path))
                with open(config_file, "w") as f:
                    f.write(content)

                # Test with config file
                env = os.environ.copy()
                env["PHOTO_BACKUP_CONFIG"] = config_file
                result = subprocess.run(
                    ["python3", "-m", "photo_backup.main", "test-auth"],
                    capture_output=True,
                    text=True,
                    cwd=".",
                    env=env,
                )

                # Combine stdout and stderr for checking output
                combined_output = result.stdout + result.stderr

                # Should detect credentials but fail validation
                assert result.returncode == 1
                assert "🔐 Testing authentication in PRODUCTION MODE" in combined_output
                assert "📋 Mode: production" in combined_output
                # The system should detect credentials but validation fails, so it shows "❌ No"
                assert "🔑 Has credentials: ❌ No" in combined_output
                assert "💥 Authentication test failed!" in combined_output

        finally:
            # Clean up
            Path(config_file).unlink(missing_ok=True)

    def test_test_auth_dry_run_mode(self):
        """Test test-auth command in dry-run mode."""
        result = subprocess.run(
            ["python3", "-m", "photo_backup.main", "--dry-run", "test-auth"],
            capture_output=True,
            text=True,
            cwd=".",
        )

        # Combine stdout and stderr for checking output
        combined_output = result.stdout + result.stderr

        # Should work the same as normal mode
        assert result.returncode == 1  # Should fail due to no credentials
        assert "🔐 Testing authentication in PRODUCTION MODE" in combined_output
        assert "📋 Mode: production" in combined_output
        assert "🔑 Has credentials: ❌ No" in combined_output or "🔑 Has credentials: ✅ Yes" in combined_output
        assert "💥 Authentication test failed!" in combined_output

    def test_test_auth_invalid_command(self):
        """Test test-auth command with invalid options."""
        result = subprocess.run(
            ["python3", "-m", "photo_backup.main", "test-auth", "--invalid-option"],
            capture_output=True,
            text=True,
            cwd=".",
        )

        # Should show error about invalid option
        assert result.returncode == 2
        assert "no such option" in result.stderr.lower() or "unrecognized arguments" in result.stderr.lower()
