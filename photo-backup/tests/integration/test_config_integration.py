"""
Integration tests for configuration system.

These tests verify that configuration works with other components.
"""

import pytest
import yaml
from pathlib import Path


class TestConfigIntegration:
    """Integration tests for configuration system."""

    @pytest.mark.integration
    def test_config_example_file_exists(self):
        """Test that config example file exists and is valid."""
        config_file = Path(__file__).parent.parent.parent / "config.yaml.example"
        assert config_file.exists()

        with open(config_file) as f:
            config = yaml.safe_load(f)

        assert config is not None
        assert "backup" in config
        assert "test_mode" in config

    @pytest.mark.integration
    def test_config_with_logger_integration(self):
        """Test that config works with logger system."""
        import logging

        from photo_backup.config import Config
        from photo_backup.logger import setup_logger

        # Test production mode
        config = Config(test_mode=False)
        config.load_config()
        logger = setup_logger("integration_test", logging.INFO)

        assert logger.name == "integration_test"
        assert logger.level == logging.INFO
        assert config.get("storage.endpoint") == "s3.wasabisys.com"

        # Test test mode
        test_config = Config(test_mode=True)
        test_config.load_config()
        test_logger = setup_logger("test_integration", logging.DEBUG)

        assert test_logger.name == "test_integration"
        assert test_logger.level == logging.DEBUG
        assert test_config.get("storage.endpoint") == "localhost:9000"

    @pytest.mark.integration
    def test_config_state_directories_different_modes(self):
        """Test that state directories are different between modes."""
        from photo_backup.config import Config

        prod_config = Config(test_mode=False)
        prod_config.load_config()

        test_config = Config(test_mode=True)
        test_config.load_config()

        prod_state = prod_config.get("state.directory")
        test_state = test_config.get("state.directory")

        assert prod_state != test_state
        assert "/tmp/photo-backup-test" in test_state
        assert "Library/Application Support" in prod_state

    @pytest.mark.integration
    def test_config_credentials_isolation(self):
        """Test that credentials are properly isolated between modes."""
        from photo_backup.config import Config

        prod_config = Config(test_mode=False)
        prod_config.load_config()

        test_config = Config(test_mode=True)
        test_config.load_config()

        # Production should use None credentials (retrieved from 1Password)
        assert prod_config.get("storage.access_key") is None
        assert prod_config.get("storage.secret_key") is None

        # Test should use Minio credentials
        assert test_config.get("storage.access_key") == "minioadmin"
        assert test_config.get("storage.secret_key") == "minioadmin"

    @pytest.mark.integration
    def test_config_backup_paths_isolation(self):
        """Test that backup paths are properly isolated between modes."""
        from photo_backup.config import Config

        prod_config = Config(test_mode=False)
        prod_config.load_config()

        test_config = Config(test_mode=True)
        test_config.load_config()

        # Production should use real paths
        assert prod_config.get("backup.source_path") == "/Volumes/4TB-SSD/Photo"
        assert prod_config.get("backup.destination") == "wasabi-photo:my-photo-backup-bucket"

        # Test should use test paths
        assert test_config.get("backup.source_path") == "/tmp/photo-backup-test-photos"
        assert test_config.get("backup.destination") == "minio-test:my-photo-backup-bucket-test"

    @pytest.mark.integration
    def test_config_dot_notation_comprehensive(self):
        """Test comprehensive dot notation access across all config sections."""
        from photo_backup.config import Config

        config = Config(test_mode=True)
        config.load_config()

        # Test all major config paths
        test_paths = [
            "backup.source_path",
            "backup.destination",
            "storage.endpoint",
            "storage.access_key",
            "storage.secret_key",
            "state.directory",
        ]

        for path in test_paths:
            value = config.get(path)
            assert value is not None, f"Config path {path} should not be None"
            assert isinstance(value, str), f"Config path {path} should be a string"

    @pytest.mark.integration
    def test_config_mode_switching(self):
        """Test switching between production and test modes."""
        from photo_backup.config import Config

        # Start with production
        config = Config(test_mode=False)
        config.load_config()
        prod_endpoint = config.get("storage.endpoint")

        # Switch to test mode
        config = Config(test_mode=True)
        config.load_config()
        test_endpoint = config.get("storage.endpoint")

        # Switch back to production
        config = Config(test_mode=False)
        config.load_config()
        prod_endpoint_2 = config.get("storage.endpoint")

        assert prod_endpoint == "s3.wasabisys.com"
        assert test_endpoint == "localhost:9000"
        assert prod_endpoint_2 == "s3.wasabisys.com"
        assert prod_endpoint == prod_endpoint_2

    @pytest.mark.integration
    def test_config_ssl_settings_integration(self):
        """Test SSL settings integration between modes."""
        from photo_backup.config import Config

        prod_config = Config(test_mode=False)
        prod_config.load_config()

        test_config = Config(test_mode=True)
        test_config.load_config()

        # Production should use SSL, test should not
        assert prod_config.get("storage.use_ssl") is True
        assert test_config.get("storage.use_ssl") is False

    @pytest.mark.integration
    def test_config_logging_integration(self):
        """Test logging configuration integration."""
        from photo_backup.config import Config

        prod_config = Config(test_mode=False)
        prod_config.load_config()

        test_config = Config(test_mode=True)
        test_config.load_config()

        # Different log levels and directories
        assert prod_config.get("logging.level") == "INFO"
        assert test_config.get("logging.level") == "DEBUG"
        assert prod_config.get("logging.directory") != test_config.get("logging.directory")
