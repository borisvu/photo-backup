"""
Unit tests for RcloneCredentialValidator.
"""

from unittest.mock import Mock, patch

from photo_backup.config.config import Config
from photo_backup.credentials.validators.rclone import RcloneCredentialValidator


class TestRcloneCredentialValidator:
    """Test the RcloneCredentialValidator."""

    def test_validate_credentials_success(self):
        """Test successful credential validation."""
        config = Config(test_mode=False)
        validator = RcloneCredentialValidator(config)

        credentials = {
            "access_key": "test_key",
            "secret_key": "test_secret",
            "endpoint": "test.endpoint.com",
            "region": "us-east-1",
            "use_ssl": True,
            "bucket": "test-bucket",
        }

        with patch.object(validator, "_check_rclone_available", return_value=True):
            with patch("subprocess.run") as mock_run:
                mock_result = Mock()
                mock_result.returncode = 0
                mock_run.return_value = mock_result

                is_valid, message = validator.validate_credentials(credentials)

                assert is_valid is True
                assert "validated successfully" in message

    def test_validate_credentials_rclone_not_available(self):
        """Test validation when rclone is not available."""
        config = Config(test_mode=False)
        validator = RcloneCredentialValidator(config)

        credentials = {
            "access_key": "test_key",
            "secret_key": "test_secret",
            "endpoint": "test.endpoint.com",
            "region": "us-east-1",
            "use_ssl": True,
            "bucket": "test-bucket",
        }

        with patch.object(validator, "_check_rclone_available", return_value=False):
            is_valid, message = validator.validate_credentials(credentials)

            assert is_valid is False
            assert "rclone is not available" in message
            assert "Install rclone" in message

    def test_validate_credentials_access_denied(self):
        """Test validation with access denied error."""
        config = Config(test_mode=False)
        validator = RcloneCredentialValidator(config)

        credentials = {
            "access_key": "test_key",
            "secret_key": "test_secret",
            "endpoint": "test.endpoint.com",
            "region": "us-east-1",
            "use_ssl": True,
            "bucket": "test-bucket",
        }

        with patch.object(validator, "_check_rclone_available", return_value=True):
            with patch("subprocess.run") as mock_run:
                mock_result = Mock()
                mock_result.returncode = 1
                mock_result.stderr = "Access Denied"
                mock_run.return_value = mock_result

                is_valid, message = validator.validate_credentials(credentials)

                assert is_valid is False
                assert "Access denied" in message

    def test_build_rclone_config(self):
        """Test rclone config building."""
        config = Config(test_mode=False)
        validator = RcloneCredentialValidator(config)

        credentials = {
            "access_key": "test_key",
            "secret_key": "test_secret",
            "endpoint": "test.endpoint.com",
            "region": "us-east-1",
            "use_ssl": True,
            "bucket": "test-bucket",
        }

        config_content = validator._build_rclone_config(credentials)

        assert "test-test-bucket" in config_content
        assert "test_key" in config_content
        assert "test_secret" in config_content
        assert "test.endpoint.com" in config_content
        assert "us-east-1" in config_content
        assert "true" in config_content

    def test_get_validator_name(self):
        """Test validator name."""
        config = Config(test_mode=False)
        validator = RcloneCredentialValidator(config)
        assert validator.get_validator_name() == "rclone"
