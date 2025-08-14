"""
Unit tests for the refactored CredentialManager.
"""

from unittest.mock import patch

from photo_backup.config.config import Config
from photo_backup.credentials.exceptions import CredentialError
from photo_backup.credentials.manager import CredentialManager


class TestCredentialManager:
    """Test the refactored CredentialManager."""

    def test_get_credentials_test_mode(self):
        """Test getting credentials in test mode."""
        config = Config(test_mode=True)

        mock_credentials = {
            "access_key": "minioadmin",
            "secret_key": "minioadmin",
            "endpoint": "localhost:9000",
            "bucket": "test-bucket",
        }

        with patch.object(config, "load_config", return_value={"storage": {}}):
            with patch.object(config, "is_test_mode", return_value=True):
                manager = CredentialManager(config)

                # Mock the test provider
                with patch.object(manager._test_provider, "get_credentials", return_value=mock_credentials):
                    credentials = manager.get_credentials()

                    assert credentials["access_key"] == "minioadmin"
                    assert credentials["secret_key"] == "minioadmin"
                    assert credentials["endpoint"] == "localhost:9000"

    def test_get_credentials_production_mode_direct(self):
        """Test getting credentials in production mode with direct provider."""
        config = Config(test_mode=False)

        mock_credentials = {
            "access_key": "prod_key",
            "secret_key": "prod_secret",
            "endpoint": "s3.wasabisys.com",
            "bucket": "prod-bucket",
        }

        with patch.object(config, "load_config", return_value={"storage": {}}):
            with patch.object(config, "is_test_mode", return_value=False):
                manager = CredentialManager(config)

                # Mock the direct provider to succeed
                with patch.object(manager._direct_provider, "get_credentials", return_value=mock_credentials):
                    credentials = manager.get_credentials()

                    assert credentials["access_key"] == "prod_key"
                    assert credentials["secret_key"] == "prod_secret"

    def test_get_credentials_production_mode_1password_fallback(self):
        """Test getting credentials in production mode with 1Password fallback."""
        config = Config(test_mode=False)

        mock_credentials = {
            "access_key": "1p_key",
            "secret_key": "1p_secret",
            "endpoint": "s3.wasabisys.com",
            "bucket": "prod-bucket",
        }

        mock_config_data = {"storage": {"use_1password": True}}

        with patch.object(config, "load_config", return_value=mock_config_data):
            with patch.object(config, "is_test_mode", return_value=False):
                manager = CredentialManager(config)

                # Mock the direct provider to fail
                with patch.object(
                    manager._direct_provider, "get_credentials", side_effect=CredentialError("No direct credentials")
                ):
                    # Mock the 1Password provider to succeed
                    with patch.object(manager._onepassword_provider, "get_credentials", return_value=mock_credentials):
                        credentials = manager.get_credentials()

                        assert credentials["access_key"] == "1p_key"
                        assert credentials["secret_key"] == "1p_secret"

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

    def test_get_credential_source_test_mode(self):
        """Test credential source detection in test mode."""
        config = Config(test_mode=True)
        manager = CredentialManager(config)

        with patch.object(config, "is_test_mode", return_value=True):
            source = manager._get_credential_source()
            assert source == "test_mode"

    def test_get_credential_source_direct(self):
        """Test credential source detection for direct provider."""
        config = Config(test_mode=False)
        manager = CredentialManager(config)

        with patch.object(config, "is_test_mode", return_value=False):
            with patch.object(manager._direct_provider, "get_credentials", return_value={"access_key": "test"}):
                with patch.object(manager._direct_provider, "get_source_name", return_value="environment_variables"):
                    source = manager._get_credential_source()
                    assert source == "environment_variables"  # Default from direct provider

    def test_get_credential_source_1password(self):
        """Test credential source detection for 1Password provider."""
        config = Config(test_mode=False)
        manager = CredentialManager(config)

        mock_config_data = {"storage": {"use_1password": True}}

        with patch.object(config, "is_test_mode", return_value=False):
            with patch.object(config, "load_config", return_value=mock_config_data):
                with patch.object(
                    manager._direct_provider, "get_credentials", side_effect=CredentialError("No direct")
                ):
                    source = manager._get_credential_source()
                    assert source == "1password"
