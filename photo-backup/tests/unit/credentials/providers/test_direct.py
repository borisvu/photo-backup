"""
Unit tests for DirectCredentialProvider.
"""

import os
from unittest.mock import patch

from photo_backup.config.config import Config
from photo_backup.credentials.providers.direct import DirectCredentialProvider


class TestDirectCredentialProvider:
    """Test the DirectCredentialProvider."""

    def test_get_credentials_from_environment(self):
        """Test getting credentials from environment variables."""
        config = Config(test_mode=False)

        with patch.dict(os.environ, {"WASABI_ACCESS_KEY": "test_access_key", "WASABI_SECRET_KEY": "test_secret_key"}):
            provider = DirectCredentialProvider(config)
            credentials = provider.get_credentials()

            assert credentials["access_key"] == "test_access_key"
            assert credentials["secret_key"] == "test_secret_key"
            assert credentials["endpoint"] == "s3.wasabisys.com"
            assert credentials["bucket"] == "my-photo-backup-bucket"

    def test_get_credentials_from_config_file(self):
        """Test getting credentials from config file."""
        config = Config(test_mode=False)

        # Mock config to return credentials
        mock_config_data = {
            "storage": {
                "access_key": "config_access_key",
                "secret_key": "config_secret_key",
                "endpoint": "custom.endpoint.com",
                "bucket": "custom-bucket",
            }
        }

        with patch.object(config, "load_config", return_value=mock_config_data):
            with patch.dict(os.environ, {}, clear=True):
                provider = DirectCredentialProvider(config)
                credentials = provider.get_credentials()

                assert credentials["access_key"] == "config_access_key"
                assert credentials["secret_key"] == "config_secret_key"
                assert credentials["endpoint"] == "custom.endpoint.com"
                assert credentials["bucket"] == "custom-bucket"

    def test_get_credentials_no_credentials_available(self):
        """Test that credentials are returned even when keys are not available.

        After Phase 1 refactoring, DirectCredentialProvider returns credentials
        with None values instead of raising an error. Validation happens at a
        higher level in the credential manager.
        """
        config = Config(test_mode=False)

        mock_config_data = {"storage": {}}

        with patch.object(config, "load_config", return_value=mock_config_data):
            with patch.dict(os.environ, {}, clear=True):
                provider = DirectCredentialProvider(config)
                credentials = provider.get_credentials()

                # Credentials should be returned but keys should be None
                assert credentials["access_key"] is None
                assert credentials["secret_key"] is None
                # Other fields should have defaults
                assert credentials["endpoint"] == "s3.wasabisys.com"
                assert credentials["bucket"] == "my-photo-backup-bucket"

    def test_get_source_name_environment_variables(self):
        """Test source name when credentials come from environment."""
        config = Config(test_mode=False)

        with patch.dict(os.environ, {"WASABI_ACCESS_KEY": "test"}):
            provider = DirectCredentialProvider(config)
            assert provider.get_source_name() == "environment_variables"

    def test_get_source_name_config_file(self):
        """Test source name when credentials come from config file."""
        config = Config(test_mode=False)

        mock_config_data = {"storage": {"access_key": "test"}}

        with patch.object(config, "load_config", return_value=mock_config_data):
            with patch.dict(os.environ, {}, clear=True):
                provider = DirectCredentialProvider(config)
                assert provider.get_source_name() == "config_file"

    def test_get_source_name_none(self):
        """Test source name when no credentials are available."""
        config = Config(test_mode=False)

        mock_config_data = {"storage": {}}

        with patch.object(config, "load_config", return_value=mock_config_data):
            with patch.dict(os.environ, {}, clear=True):
                provider = DirectCredentialProvider(config)
                assert provider.get_source_name() == "none"
