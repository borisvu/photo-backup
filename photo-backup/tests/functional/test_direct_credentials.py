"""
Functional tests for direct credential functionality.
"""

import os
from unittest.mock import patch

from photo_backup.config.config import Config
from photo_backup.credentials import CredentialManager


class TestDirectCredentialsFunctional:
    """Functional tests for direct credential management."""

    def test_direct_credentials_from_environment(self):
        """Test that credentials can be loaded from environment variables."""
        # Set environment variables
        env = {"WASABI_ACCESS_KEY": "test_env_access_key", "WASABI_SECRET_KEY": "test_env_secret_key"}

        with patch.dict(os.environ, env):
            config = Config(test_mode=False)
            manager = CredentialManager(config)

            credentials = manager.get_credentials()

            assert credentials["access_key"] == "test_env_access_key"
            assert credentials["secret_key"] == "test_env_secret_key"
            assert credentials["bucket"] == "my-photo-backup-bucket"  # Default from config
            assert credentials["endpoint"] == "s3.wasabisys.com"

    def test_direct_credentials_from_config_file(self, temp_dir):
        """Test that credentials can be loaded from config file."""
        # Create config with credentials
        config_content = """
backup:
  source_path: "/tmp/test-photos"
  destination: "test-config-bucket"
  max_size_mb: 100
  backup_count: 3
  check_interval: 30
  mount_delay: 5

storage:
  access_key: "test_config_access_key"
  secret_key: "test_config_secret_key"
  bucket: "test-config-bucket"
  endpoint: "s3.test.com"
  region: "us-west-2"
  use_ssl: false
  timeout_seconds: 300
  retry_attempts: 3

monitoring:
  enabled: true
  check_interval: 60
  alert_threshold: 0.9

logging:
  level: "INFO"
  format: "detailed"
  file_output: true
  console_output: true

state:
  directory: "/tmp/photo-backup-state"
"""

        # Create test photos directory
        test_photos_dir = temp_dir / "test-photos"
        test_photos_dir.mkdir()

        # Write config to file
        config_file = temp_dir / "config.yaml"
        config_content = config_content.replace("/tmp/test-photos", str(test_photos_dir))
        config_file.write_text(config_content)

        # Clear environment variables and set config file path
        with patch.dict(os.environ, {"PHOTO_BACKUP_CONFIG_FILE": str(config_file)}, clear=True):
            config = Config(test_mode=False)
            manager = CredentialManager(config)

            credentials = manager.get_credentials()

            assert credentials["access_key"] == "test_config_access_key"
            assert credentials["secret_key"] == "test_config_secret_key"
            assert credentials["bucket"] == "test-config-bucket"
            assert credentials["endpoint"] == "s3.test.com"
            assert credentials["region"] == "us-west-2"
            assert credentials["use_ssl"] is False

    def test_credential_source_detection(self):
        """Test that credential source is correctly detected."""
        config = Config(test_mode=False)
        manager = CredentialManager(config)

        # Test environment variables
        with patch.dict(os.environ, {"WASABI_ACCESS_KEY": "test"}):
            info = manager.get_credential_info()
            assert info["credential_source"] == "environment_variables"

        # Test config file
        with patch.dict(os.environ, {}, clear=True), patch.object(config, "load_config") as mock_load:
            mock_load.return_value = {"storage": {"access_key": "test"}}
            info = manager.get_credential_info()
            assert info["credential_source"] == "config_file"

        # Test 1Password
        with patch.dict(os.environ, {}, clear=True), patch.object(config, "load_config") as mock_load:
            mock_load.return_value = {"storage": {"use_1password": True}}
            info = manager.get_credential_info()
            assert info["credential_source"] == "1password"

        # Test no credentials
        with patch.dict(os.environ, {}, clear=True), patch.object(config, "load_config") as mock_load:
            mock_load.return_value = {"storage": {}}
            info = manager.get_credential_info()
            assert info["credential_source"] == "none"

    def test_credential_priority_order(self):
        """Test that environment variables take priority over config file."""
        # Set environment variables (should take priority)
        env = {"WASABI_ACCESS_KEY": "env_access_key", "WASABI_SECRET_KEY": "env_secret_key"}

        with patch.dict(os.environ, env):
            config = Config(test_mode=False)
            manager = CredentialManager(config)

            credentials = manager.get_credentials()

            # Environment variables should take priority for credentials
            assert credentials["access_key"] == "env_access_key"
            assert credentials["secret_key"] == "env_secret_key"
            # Bucket comes from config defaults
            assert credentials["bucket"] == "my-photo-backup-bucket"

    def test_credential_fallback_to_1password(self):
        """Test fallback to 1Password when direct credentials are not available."""
        # Clear environment variables
        with patch.dict(os.environ, {}, clear=True):
            config = Config(test_mode=False)

            # Mock config to enable 1Password
            with patch.object(config, "load_config") as mock_load:
                mock_load.return_value = {"storage": {"use_1password": True, "1password_item": "Test Credentials"}}

                manager = CredentialManager(config)

                # Mock 1Password credential retrieval
                with patch.object(manager, "_retrieve_credentials_from_1password") as mock_1p:
                    mock_1p.return_value = ("1p_access_key", "1p_secret_key")

                    credentials = manager.get_credentials()

                    assert credentials["access_key"] == "1p_access_key"
                    assert credentials["secret_key"] == "1p_secret_key"
                    mock_1p.assert_called_once()

    def test_credential_validation_with_direct_credentials(self):
        """Test credential validation with direct credentials."""
        # Set environment variables
        env = {"WASABI_ACCESS_KEY": "test_access_key", "WASABI_SECRET_KEY": "test_secret_key"}

        with patch.dict(os.environ, env):
            config = Config(test_mode=False)
            manager = CredentialManager(config)

            # Mock rclone validation
            with patch.object(manager, "test_credentials_with_rclone") as mock_validate:
                mock_validate.return_value = (True, "Credentials validated successfully")

                is_valid, message = manager.validate_credentials()

                assert is_valid is True
                assert "validated successfully" in message
                mock_validate.assert_called_once()

    def test_credential_info_masking(self):
        """Test that sensitive credential information is properly masked."""
        # Set environment variables
        env = {
            "WASABI_ACCESS_KEY": "AKIAIOSFODNN7EXAMPLE",
            "WASABI_SECRET_KEY": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        }

        with patch.dict(os.environ, env):
            config = Config(test_mode=False)
            manager = CredentialManager(config)

            info = manager.get_credential_info()

            # Check that sensitive data is masked
            assert info["has_access_key"] is True
            assert info["has_secret_key"] is True
            assert info["access_key_preview"] == "AKIA...MPLE"
            assert "secret_key" not in info  # Secret key should not be exposed
            assert info["credential_source"] == "environment_variables"

    def test_test_mode_credentials_unchanged(self):
        """Test that test mode credentials remain unchanged."""
        # Set environment variables (should be ignored in test mode)
        env = {"WASABI_ACCESS_KEY": "env_access_key", "WASABI_SECRET_KEY": "env_secret_key"}

        with patch.dict(os.environ, env):
            config = Config(test_mode=True)
            manager = CredentialManager(config)

            credentials = manager.get_credentials()

            # Test mode should use Minio credentials regardless of environment
            assert credentials["access_key"] == "minioadmin"
            assert credentials["secret_key"] == "minioadmin"
            assert credentials["endpoint"] == "localhost:9000"
            assert credentials["bucket"] == "test-bucket"
            assert credentials["use_ssl"] is False
