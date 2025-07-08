"""
Unit tests for config module.

These tests focus on configuration loading and management in isolation.
"""

import pytest
from photo_backup.config import Config


class TestConfig:
    """Test cases for Config class."""
    
    @pytest.mark.unit
    def test_config_production_mode(self):
        """Test config in production mode."""
        config = Config(test_mode=False)
        settings = config.load_config()
        
        assert config.get('storage.endpoint') == "s3.wasabisys.com"
        assert config.get('storage.access_key') is None  # Retrieved from 1Password
        assert config.get('storage.secret_key') is None  # Retrieved from 1Password
        assert config.get('backup.source_path') == "/Volumes/4TB-SSD/Photo"
        assert config.get('backup.destination') == "wasabi-photo:my-photo-backup-bucket"
    
    @pytest.mark.unit
    def test_config_test_mode(self):
        """Test config in test mode."""
        config = Config(test_mode=True)
        settings = config.load_config()
        
        assert config.get('storage.endpoint') == "localhost:9000"
        assert config.get('storage.access_key') == "minioadmin"
        assert config.get('storage.secret_key') == "minioadmin"
        assert config.get('backup.source_path') == "/tmp/photo-backup-test-photos"
        assert config.get('backup.destination') == "minio-test:my-photo-backup-bucket-test"
    
    @pytest.mark.unit
    def test_config_dot_notation_access(self):
        """Test accessing config values with dot notation."""
        config = Config(test_mode=True)
        config.load_config()
        
        # Test nested access
        assert config.get('storage.endpoint') == "localhost:9000"
        assert config.get('backup.source_path') == "/tmp/photo-backup-test-photos"
        assert config.get('state.directory') == "/tmp/photo-backup-test/state"
    
    @pytest.mark.unit
    def test_config_missing_key_returns_none(self):
        """Test that missing config keys return None."""
        config = Config(test_mode=True)
        config.load_config()
        
        assert config.get('nonexistent.key') is None
        assert config.get('backup.nonexistent') is None
    
    @pytest.mark.unit
    def test_config_state_directory_differs_by_mode(self):
        """Test that state directories differ between modes."""
        prod_config = Config(test_mode=False)
        prod_config.load_config()
        
        test_config = Config(test_mode=True)
        test_config.load_config()
        
        prod_state = prod_config.get('state.directory')
        test_state = test_config.get('state.directory')
        
        assert prod_state != test_state
        assert "/tmp/photo-backup-test" in test_state
        assert "Library/Application Support" in prod_state
    
    @pytest.mark.parametrize("test_mode,expected_endpoint", [
        (True, "localhost:9000"),
        (False, "s3.wasabisys.com"),
    ])
    @pytest.mark.unit
    def test_config_endpoint_by_mode(self, test_mode, expected_endpoint):
        """Test that endpoint changes based on mode."""
        config = Config(test_mode=test_mode)
        config.load_config()
        
        assert config.get('storage.endpoint') == expected_endpoint
    
    @pytest.mark.parametrize("test_mode,expected_credentials", [
        (True, ("minioadmin", "minioadmin")),
        (False, (None, None)),  # Production uses 1Password
    ])
    @pytest.mark.unit
    def test_config_credentials_by_mode(self, test_mode, expected_credentials):
        """Test that credentials change based on mode."""
        config = Config(test_mode=test_mode)
        config.load_config()
        
        access_key = config.get('storage.access_key')
        secret_key = config.get('storage.secret_key')
        
        assert (access_key, secret_key) == expected_credentials
    
    @pytest.mark.unit
    def test_config_is_test_mode(self):
        """Test is_test_mode method."""
        prod_config = Config(test_mode=False)
        test_config = Config(test_mode=True)
        
        assert prod_config.is_test_mode() is False
        assert test_config.is_test_mode() is True
    
    @pytest.mark.unit
    def test_config_ssl_settings(self):
        """Test SSL settings differ between modes."""
        prod_config = Config(test_mode=False)
        prod_config.load_config()
        
        test_config = Config(test_mode=True)
        test_config.load_config()
        
        assert prod_config.get('storage.use_ssl') is True
        assert test_config.get('storage.use_ssl') is False
    
    @pytest.mark.unit
    def test_config_monitoring_settings(self):
        """Test monitoring settings differ between modes."""
        prod_config = Config(test_mode=False)
        prod_config.load_config()
        
        test_config = Config(test_mode=True)
        test_config.load_config()
        
        # Test mode should have faster intervals
        assert test_config.get('monitoring.check_interval_hours') < prod_config.get('monitoring.check_interval_hours')
        assert test_config.get('monitoring.mount_delay_minutes') < prod_config.get('monitoring.mount_delay_minutes')
        assert test_config.get('monitoring.change_delay_minutes') < prod_config.get('monitoring.change_delay_minutes')
    
    @pytest.mark.unit
    def test_config_logging_settings(self):
        """Test logging settings differ between modes."""
        prod_config = Config(test_mode=False)
        prod_config.load_config()
        
        test_config = Config(test_mode=True)
        test_config.load_config()
        
        assert prod_config.get('logging.level') == "INFO"
        assert test_config.get('logging.level') == "DEBUG"
        
        # Different log directories
        assert prod_config.get('logging.directory') != test_config.get('logging.directory')
        assert "/tmp/photo-backup-test" in test_config.get('logging.directory')