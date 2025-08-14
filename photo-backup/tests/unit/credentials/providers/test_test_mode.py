"""
Unit tests for TestModeCredentialProvider.
"""

from unittest.mock import patch

from photo_backup.config.config import Config
from photo_backup.credentials.providers.test_mode import TestModeCredentialProvider


class TestTestModeCredentialProvider:
    """Test the TestModeCredentialProvider."""

    def test_get_credentials_default_values(self):
        """Test getting credentials with default values."""
        config = Config(test_mode=True)

        mock_config_data = {"storage": {}}

        with patch.object(config, "load_config", return_value=mock_config_data):
            provider = TestModeCredentialProvider(config)
            credentials = provider.get_credentials()

            assert credentials["access_key"] == "minioadmin"
            assert credentials["secret_key"] == "minioadmin"
            assert credentials["endpoint"] == "localhost:9000"
            assert credentials["bucket"] == "test-bucket"
            assert credentials["use_ssl"] is False

    def test_get_credentials_custom_values(self):
        """Test getting credentials with custom values from config."""
        config = Config(test_mode=True)

        mock_config_data = {
            "storage": {
                "access_key": "custom_user",
                "secret_key": "custom_pass",
                "endpoint": "custom:9000",
                "bucket": "custom-bucket",
                "use_ssl": True,
            }
        }

        with patch.object(config, "load_config", return_value=mock_config_data):
            provider = TestModeCredentialProvider(config)
            credentials = provider.get_credentials()

            assert credentials["access_key"] == "custom_user"
            assert credentials["secret_key"] == "custom_pass"
            assert credentials["endpoint"] == "custom:9000"
            assert credentials["bucket"] == "custom-bucket"
            assert credentials["use_ssl"] is True

    def test_get_source_name(self):
        """Test source name is always test_mode."""
        config = Config(test_mode=True)
        provider = TestModeCredentialProvider(config)
        assert provider.get_source_name() == "test_mode"
