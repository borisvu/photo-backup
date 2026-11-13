"""
Functional tests for enhanced credential error handling.
"""

import os
import subprocess
import sys

import pytest
from pathlib import Path

from photo_backup.config.config import Config
from photo_backup.credentials import CredentialError, CredentialManager


class TestCredentialErrorHandlingFunctional:
    """Test enhanced error handling in real scenarios."""

    def test_credential_error_handling_test_mode_minio_not_running(self):
        """Test error handling when Minio container is not running in test mode."""
        # Ensure Minio is not running
        try:
            subprocess.run(["docker", "stop", "photo-backup-minio-test"], capture_output=True, check=False)
            subprocess.run(["docker", "rm", "photo-backup-minio-test"], capture_output=True, check=False)
        except FileNotFoundError:
            pass  # Docker not available, skip

        # Test credential validation in test mode
        result = subprocess.run(
            [sys.executable, "-m", "photo_backup.main", "--test-mode", "validate"],
            capture_output=True,
            text=True,
            cwd=".",
        )

        # Should show helpful error message about Minio
        assert result.returncode != 0
        assert "Cannot reach Minio endpoint" in result.stdout
        assert "localhost:9000" in result.stdout

    def test_credential_error_handling_production_mode_no_credentials(self):
        """Test error handling when no production credentials are available."""
        # Clear any existing environment variables
        env = os.environ.copy()
        env.pop("WASABI_ACCESS_KEY", None)
        env.pop("WASABI_SECRET_KEY", None)
        env.pop("S3_ACCESS_KEY", None)
        env.pop("S3_SECRET_KEY", None)

        # Test credential validation in production mode
        result = subprocess.run(
            [sys.executable, "-m", "photo_backup.main", "validate"],
            capture_output=True,
            text=True,
            cwd=".",
            env=env,
        )

        # Should show validation failure due to missing paths
        assert result.returncode != 0
        assert "Configuration validation failed" in result.stdout
        assert "backup.source_path does not exist" in result.stdout

    def test_credential_error_handling_rclone_not_available(self):
        """Test error handling when rclone is not available."""
        # Mock rclone as not available by temporarily renaming it
        rclone_path = None
        try:
            # Find rclone in PATH
            result = subprocess.run(["which", "rclone"], capture_output=True, text=True)
            if result.returncode == 0:
                rclone_path = Path(result.stdout.strip())
                if rclone_path.exists():
                    # Temporarily rename rclone
                    backup_path = rclone_path.with_suffix(".backup")
                    rclone_path.rename(backup_path)

                    # Test credential validation
                    result = subprocess.run(
                        [sys.executable, "-m", "photo_backup.main", "--test-mode", "validate"],
                        capture_output=True,
                        text=True,
                        cwd=".",
                    )

                    # Should show helpful error message about rclone
                    assert result.returncode != 0
                    assert "rclone not found or not working" in result.stdout

                    # Restore rclone
                    backup_path.rename(rclone_path)
                else:
                    pytest.skip("rclone not found in PATH")
            else:
                pytest.skip("rclone not found in PATH")
        except Exception:
            # Restore rclone if something went wrong
            if rclone_path and rclone_path.with_suffix(".backup").exists():
                backup_path = rclone_path.with_suffix(".backup")
                backup_path.rename(rclone_path)
            raise

    def test_credential_error_handling_invalid_credentials(self):
        """Test error handling with invalid credentials."""
        # Set invalid credentials
        env = os.environ.copy()
        env["WASABI_ACCESS_KEY"] = "invalid_key"
        env["WASABI_SECRET_KEY"] = "invalid_secret"

        # Test credential validation
        result = subprocess.run(
            [sys.executable, "-m", "photo_backup.main", "validate"],
            capture_output=True,
            text=True,
            cwd=".",
            env=env,
        )

        # Should show helpful error message about invalid credentials
        assert result.returncode != 0
        assert "Configuration validation failed" in result.stdout

    def test_credential_error_handling_graceful_fallback(self):
        """Test that error handling provides graceful fallback suggestions."""
        # Test in test mode without Minio
        result = subprocess.run(
            [sys.executable, "-m", "photo_backup.main", "--test-mode", "config"],
            capture_output=True,
            text=True,
            cwd=".",
        )

        # Should show test mode configuration
        assert result.returncode == 0
        assert "test mode" in result.stdout.lower()
        assert "localhost:9000" in result.stdout

    def test_credential_error_handling_detailed_suggestions(self):
        """Test that error handling provides detailed, actionable suggestions."""
        config = Config(test_mode=True)
        manager = CredentialManager(config)

        # Test credential status with error
        status = manager.get_credential_status()

        # Should provide comprehensive error information
        assert "mode" in status
        assert "error" in status or "has_credentials" in status
        assert "suggestion" in status or status["has_credentials"] is True

    def test_credential_error_handling_test_mode_specific_guidance(self):
        """Test that error handling provides generic credential guidance (Phase 7.2).

        After refactoring: Error messages are mode-independent and generic.
        """
        config = Config(test_mode=True)
        manager = CredentialManager(config)

        # Create a test error
        error = CredentialError("Minio connection failed", "Start Minio container", "Connection refused")

        # Test error handling
        message = manager.handle_credential_error(error)

        # Should include mode label and generic credential suggestions
        assert "test mode" in message
        assert "Minio connection failed" in message
        assert "Environment variables" in message or "Config file" in message

    def test_credential_error_handling_production_mode_specific_guidance(self):
        """Test that error handling provides generic credential guidance (Phase 7.2).

        After refactoring: Error messages are mode-independent and generic.
        """
        config = Config(test_mode=False)
        manager = CredentialManager(config)

        # Create a test error
        error = CredentialError("No credentials available", "Set environment variables", "Missing access key")

        # Test error handling
        message = manager.handle_credential_error(error)

        # Should include mode label and generic credential suggestions
        assert "production mode" in message
        assert "No credentials available" in message
        assert "Environment variables" in message or "environment variables" in message
