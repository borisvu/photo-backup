"""
Unit tests for credential management functionality.
"""

import json
import subprocess
from unittest.mock import Mock, patch

import pytest

from photo_backup.config.config import Config
from photo_backup.credentials import (
    CredentialError,
    CredentialManager,
)


class TestCredentialError:
    """Test the CredentialError exception class."""

    def test_credential_error_basic(self):
        """Test basic CredentialError creation."""
        error = CredentialError("Test error")
        assert error.message == "Test error"
        assert error.suggestion == ""
        assert error.details == ""
        assert str(error) == "Test error"

    def test_credential_error_with_suggestion(self):
        """Test CredentialError with suggestion."""
        error = CredentialError("Test error", "Fix it")
        assert error.message == "Test error"
        assert error.suggestion == "Fix it"
        assert str(error) == "Test error. Fix it"

    def test_credential_error_with_details(self):
        """Test CredentialError with details."""
        error = CredentialError("Test error", "Fix it", "Technical details")
        assert error.message == "Test error"
        assert error.suggestion == "Fix it"
        assert error.details == "Technical details"
        assert str(error) == "Test error. Fix it"


class TestCredentialManagerErrorHandling:
    """Test enhanced error handling in CredentialManager."""

    def test_handle_credential_error_test_mode(self):
        """Test error handling in test mode."""
        config = Config(test_mode=True)
        manager = CredentialManager(config)

        error = CredentialError("Minio not running", "Start container", "Connection refused")
        message = manager.handle_credential_error(error)

        assert "test mode" in message
        assert "Minio not running" in message
        assert "Start container" in message
        assert "docker start minio" in message

    def test_handle_credential_error_production_mode(self):
        """Test error handling in production mode."""
        config = Config(test_mode=False)
        manager = CredentialManager(config)

        error = CredentialError("No credentials", "Set env vars", "Missing keys")
        message = manager.handle_credential_error(error)

        assert "production mode" in message
        assert "No credentials" in message
        assert "Set env vars" in message
        assert "WASABI_ACCESS_KEY" in message

    def test_get_credential_status_success(self):
        """Test credential status when credentials are available."""
        config = Config(test_mode=True)
        manager = CredentialManager(config)

        status = manager.get_credential_status()

        assert status["mode"] == "test"
        assert status["has_credentials"] is True
        assert status["error"] is None
        assert status["credential_info"] is not None
        assert "validation" in status

    def test_get_credential_status_with_error(self):
        """Test credential status when error occurs."""
        config = Config(test_mode=True)
        manager = CredentialManager(config)

        # Mock get_credentials to raise an error
        with patch.object(manager, "get_credentials", side_effect=CredentialError("Test error", "Fix it")):
            status = manager.get_credential_status()

        assert status["mode"] == "test"
        assert status["has_credentials"] is False
        assert status["error"] == "Test error"
        assert status["suggestion"] == "Fix it"
        assert status["validation"]["is_valid"] is False

    def test_get_credential_status_unexpected_error(self):
        """Test credential status with unexpected error."""
        config = Config(test_mode=True)
        manager = CredentialManager(config)

        # Mock get_credentials to raise an unexpected error
        with patch.object(manager, "get_credentials", side_effect=ValueError("Unexpected")):
            status = manager.get_credential_status()

        assert status["mode"] == "test"
        assert status["has_credentials"] is False
        assert "Unexpected error" in status["error"]
        assert status["suggestion"] == "Check configuration and try again"


class TestCredentialManagerEnhancedErrorHandling:
    """Test enhanced error handling scenarios."""

    def test_load_credentials_test_mode_error(self):
        """Test error handling when loading test credentials fails."""
        config = Config(test_mode=True)
        manager = CredentialManager(config)

        # Mock config.load_config to raise an error
        with patch.object(config, "load_config", side_effect=ValueError("Config error")):
            with pytest.raises(CredentialError) as exc_info:
                manager._load_credentials()

            error = exc_info.value
            assert "Failed to load test mode credentials" in error.message
            assert "Minio container is running" in error.suggestion

    def test_load_credentials_production_mode_error(self):
        """Test error handling when loading production credentials fails."""
        config = Config(test_mode=False)
        manager = CredentialManager(config)

        # Mock config.load_config to raise an error
        with patch.object(config, "load_config", side_effect=ValueError("Config error")):
            with pytest.raises(CredentialError) as exc_info:
                manager._load_credentials()

            error = exc_info.value
            assert "Failed to load production credentials" in error.message
            assert "credentials are properly configured" in error.suggestion

    def test_retrieve_credentials_1password_cli_not_available(self):
        """Test error handling when 1Password CLI is not available."""
        config = Config(test_mode=False)
        manager = CredentialManager(config)

        with patch("photo_backup.credentials.check_op_cli", return_value=(False, "Not installed")):
            with pytest.raises(CredentialError) as exc_info:
                manager._retrieve_credentials_from_1password()

            error = exc_info.value
            assert "1Password CLI not available" in error.message
            assert "Install 1Password CLI" in error.suggestion

    def test_retrieve_credentials_1password_item_not_found(self):
        """Test error handling when 1Password item is not found."""
        config = Config(test_mode=False)
        manager = CredentialManager(config)

        with (
            patch("photo_backup.credentials.check_op_cli", return_value=(True, "Available")),
            patch.object(manager, "_get_session_token", return_value="token"),
            patch("subprocess.run") as mock_run,
        ):
            mock_result = Mock()
            mock_result.returncode = 1
            mock_result.stderr = "Item not found"
            mock_run.return_value = mock_result

            with pytest.raises(CredentialError) as exc_info:
                manager._retrieve_credentials_from_1password()

            error = exc_info.value
            assert "not found" in error.message
            assert "Create a secure note" in error.suggestion

    def test_retrieve_credentials_1password_invalid_json(self):
        """Test error handling when 1Password returns invalid JSON."""
        config = Config(test_mode=False)
        manager = CredentialManager(config)

        with (
            patch("photo_backup.credentials.check_op_cli", return_value=(True, "Available")),
            patch.object(manager, "_get_session_token", return_value="token"),
            patch("subprocess.run") as mock_run,
        ):
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = "invalid json"
            mock_run.return_value = mock_result

            with pytest.raises(CredentialError) as exc_info:
                manager._retrieve_credentials_from_1password()

            error = exc_info.value
            assert "Invalid JSON response" in error.message
            assert "Check 1Password CLI version" in error.suggestion

    def test_retrieve_credentials_1password_missing_fields(self):
        """Test error handling when 1Password item is missing required fields."""
        config = Config(test_mode=False)
        manager = CredentialManager(config)

        with (
            patch("photo_backup.credentials.check_op_cli", return_value=(True, "Available")),
            patch.object(manager, "_get_session_token", return_value="token"),
            patch("subprocess.run") as mock_run,
        ):
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = json.dumps({"fields": []})
            mock_run.return_value = mock_result

            with pytest.raises(CredentialError) as exc_info:
                manager._retrieve_credentials_from_1password()

            error = exc_info.value
            assert "Missing required fields" in error.message
            assert "access_key, secret_key" in error.message

    def test_authenticate_session_timeout(self):
        """Test error handling when 1Password authentication times out."""
        config = Config(test_mode=False)
        manager = CredentialManager(config)

        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired("op", 60)):
            with pytest.raises(CredentialError) as exc_info:
                manager._authenticate_session()

            error = exc_info.value
            assert "authentication timed out" in error.message
            assert "Check network connectivity" in error.suggestion

    def test_authenticate_session_command_failed(self):
        """Test error handling when 1Password signin command fails."""
        config = Config(test_mode=False)
        manager = CredentialManager(config)

        with patch("subprocess.run") as mock_run:
            mock_result = Mock()
            mock_result.returncode = 1
            mock_result.stderr = "Command failed"
            mock_run.return_value = mock_result

            with pytest.raises(CredentialError) as exc_info:
                manager._authenticate_session()

            error = exc_info.value
            assert "authentication failed" in error.message
            assert "Run 'op signin' manually" in error.suggestion

    def test_authenticate_session_no_token_extracted(self):
        """Test error handling when session token cannot be extracted."""
        config = Config(test_mode=False)
        manager = CredentialManager(config)

        with patch("subprocess.run") as mock_run:
            mock_result = Mock()
            mock_result.returncode = 0
            mock_result.stdout = "No token here"
            mock_run.return_value = mock_result

            with pytest.raises(CredentialError) as exc_info:
                manager._authenticate_session()

            error = exc_info.value
            assert "Failed to extract session token" in error.message
            assert "Try running 'op signin' manually" in error.suggestion


class TestRcloneErrorHandling:
    """Test rclone-specific error handling."""

    def test_test_credentials_with_rclone_not_available(self):
        """Test error handling when rclone is not available."""
        config = Config(test_mode=True)
        manager = CredentialManager(config)

        with patch.object(manager, "_check_rclone_available", return_value=False):
            is_valid, message = manager.test_credentials_with_rclone()

            assert is_valid is False
            assert "rclone is not available" in message
            assert "Install rclone" in message
            assert "docker start minio" in message

    def test_test_credentials_with_rclone_minio_connection_refused(self):
        """Test error handling when Minio connection is refused."""
        config = Config(test_mode=True)
        manager = CredentialManager(config)

        with (
            patch.object(manager, "_check_rclone_available", return_value=True),
            patch.object(
                manager,
                "get_credentials",
                return_value={
                    "access_key": "minioadmin",
                    "secret_key": "minioadmin",
                    "endpoint": "localhost:9000",
                    "region": "us-east-1",
                    "use_ssl": False,
                    "bucket": "test-bucket",
                },
            ),
            patch("subprocess.run") as mock_run,
        ):
            mock_result = Mock()
            mock_result.returncode = 1
            mock_result.stderr = "connection refused"
            mock_run.return_value = mock_result

            is_valid, message = manager.test_credentials_with_rclone()

            assert is_valid is False
            assert "Cannot connect to Minio" in message
            assert "docker run -d --name minio" in message

    def test_test_credentials_with_rclone_production_access_denied(self):
        """Test error handling when production credentials are denied."""
        config = Config(test_mode=False)
        manager = CredentialManager(config)

        with (
            patch.object(manager, "_check_rclone_available", return_value=True),
            patch.object(
                manager,
                "get_credentials",
                return_value={
                    "access_key": "test",
                    "secret_key": "test",
                    "endpoint": "s3.wasabisys.com",
                    "region": "us-east-1",
                    "use_ssl": True,
                    "bucket": "test-bucket",
                },
            ),
            patch("subprocess.run") as mock_run,
        ):
            mock_result = Mock()
            mock_result.returncode = 1
            mock_result.stderr = "Access Denied"
            mock_run.return_value = mock_result

            is_valid, message = manager.test_credentials_with_rclone()

            assert is_valid is False
            assert "Access denied" in message
            assert "check credentials and bucket permissions" in message

    def test_test_credentials_with_rclone_timeout(self):
        """Test error handling when rclone test times out."""
        config = Config(test_mode=True)
        manager = CredentialManager(config)

        with (
            patch.object(manager, "_check_rclone_available", return_value=True),
            patch.object(
                manager,
                "get_credentials",
                return_value={
                    "access_key": "minioadmin",
                    "secret_key": "minioadmin",
                    "endpoint": "localhost:9000",
                    "region": "us-east-1",
                    "use_ssl": False,
                    "bucket": "test-bucket",
                },
            ),
            patch("subprocess.run", side_effect=subprocess.TimeoutExpired("rclone", 30)),
        ):
            is_valid, message = manager.test_credentials_with_rclone()

            assert is_valid is False
            assert "timed out" in message
            assert "Minio container is running" in message


class TestValidationErrorHandling:
    """Test validation error handling."""

    def test_validate_credentials_with_credential_error(self):
        """Test validation when credential loading fails."""
        config = Config(test_mode=True)
        manager = CredentialManager(config)

        with patch.object(manager, "get_credentials", side_effect=CredentialError("Test error", "Fix it")):
            is_valid, message = manager.validate_credentials()

            assert is_valid is False
            assert "Test error" in message
            assert "Fix it" in message

    def test_validate_test_credentials_invalid(self):
        """Test validation when test credentials are invalid."""
        config = Config(test_mode=True)
        manager = CredentialManager(config)

        with patch.object(
            manager,
            "get_credentials",
            return_value={
                "access_key": "wrong",
                "secret_key": "wrong",
                "endpoint": "localhost:9000",
                "bucket": "test-bucket",
            },
        ):
            is_valid, message = manager._validate_test_credentials(
                {"access_key": "wrong", "secret_key": "wrong", "endpoint": "localhost:9000", "bucket": "test-bucket"}
            )

            assert is_valid is False
            assert "Invalid test credentials" in message
            assert "minioadmin/minioadmin" in message

    def test_validate_production_credentials_missing(self):
        """Test validation when production credentials are missing."""
        config = Config(test_mode=False)
        manager = CredentialManager(config)

        is_valid, message = manager._validate_production_credentials(
            {"access_key": None, "secret_key": None, "endpoint": "s3.wasabisys.com", "bucket": "test-bucket"}
        )

        assert is_valid is False
        assert "Production credentials not available" in message
        assert "WASABI_ACCESS_KEY" in message
