"""
Unit tests for main Config class.

These tests focus on the main configuration orchestration and integration.
"""

import pytest
import tempfile
import yaml
from pathlib import Path
from unittest.mock import patch, mock_open
from photo_backup.config import Config
from photo_backup.config.utils import ConfigUtils
from photo_backup.config.defaults import DEFAULT_CONFIG, TEST_MODE_DEFAULTS


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
        """Test that test mode flag is correctly set."""
        prod_config = Config(test_mode=False)
        test_config = Config(test_mode=True)
        
        assert prod_config.is_test_mode() is False
        assert test_config.is_test_mode() is True
    
    @pytest.mark.unit
    def test_config_ssl_settings(self):
        """Test SSL settings differ between modes."""
        prod_config = Config(test_mode=False)
        test_config = Config(test_mode=True)
        
        prod_config.load_config()
        test_config.load_config()
        
        assert prod_config.get('storage.use_ssl') is True
        assert test_config.get('storage.use_ssl') is False
    
    @pytest.mark.unit
    def test_config_monitoring_settings(self):
        """Test monitoring settings differ between modes."""
        prod_config = Config(test_mode=False)
        test_config = Config(test_mode=True)
        
        prod_config.load_config()
        test_config.load_config()
        
        # Production has longer intervals
        assert prod_config.get('monitoring.check_interval_hours') == 4
        assert test_config.get('monitoring.check_interval_hours') == 0.1
        
        assert prod_config.get('monitoring.mount_delay_minutes') == 15
        assert test_config.get('monitoring.mount_delay_minutes') == 1
    
    @pytest.mark.unit
    def test_config_logging_settings(self):
        """Test logging settings differ between modes."""
        prod_config = Config(test_mode=False)
        test_config = Config(test_mode=True)
        
        prod_config.load_config()
        test_config.load_config()
        
        assert prod_config.get('logging.level') == "INFO"
        assert test_config.get('logging.level') == "DEBUG"


class TestConfigFileLoading:
    """Test cases for config file loading functionality."""
    
    @pytest.mark.unit
    def test_load_config_from_file_valid_yaml(self):
        """Test loading config from valid YAML file."""
        config = Config()
        test_config = {
            'backup': {
                'source_path': '/custom/photos',
                'destination': 'custom:backup'
            },
            'storage': {
                'endpoint': 'custom.s3.com',
                'access_key': 'custom_key',
                'secret_key': 'custom_secret',
                'use_ssl': False
            }
        }
        
        with patch.object(config.loader, '_find_config_file') as mock_find:
            with patch('builtins.open', mock_open(read_data=yaml.dump(test_config))):
                with patch('yaml.safe_load', return_value=test_config):
                    mock_find.return_value = Path("/test/config.yaml")
                    
                    result = config.loader.load_config_from_file()
                    
                    assert result == test_config
                    assert config.loader._config_file_path == Path("/test/config.yaml")
    
    @pytest.mark.unit
    def test_load_config_from_file_not_found(self):
        """Test behavior when no config file is found."""
        config = Config()
        
        with patch.object(config.loader, '_find_config_file', return_value=None):
            with patch('logging.info') as mock_log:
                result = config.loader.load_config_from_file()
                
                assert result is None
                mock_log.assert_called_with("No configuration file found, using default configuration")
    
    @pytest.mark.unit
    def test_load_config_from_file_invalid_yaml(self):
        """Test behavior when config file has invalid YAML."""
        config = Config()
        
        with patch.object(config.loader, '_find_config_file') as mock_find:
            with patch('builtins.open', side_effect=yaml.YAMLError("Invalid YAML")):
                with patch('logging.error') as mock_log:
                    mock_find.return_value = Path("/test/config.yaml")
                    
                    result = config.loader.load_config_from_file()
                    
                    assert result is None
                    mock_log.assert_called_with("Error loading config file /test/config.yaml: Invalid YAML")
    
    @pytest.mark.unit
    def test_load_config_from_file_with_test_mode_override(self):
        """Test that test mode overrides are applied after file loading."""
        config = Config(test_mode=True)
        file_config = {
            'backup': {
                'source_path': '/custom/photos',
                'destination': 'custom:backup'
            }
        }
        
        with patch.object(config.loader, 'load_config_from_file', return_value=file_config):
            with patch.object(config.validator, 'validate_config', return_value=(True, [])):
                result = config.load_config()
                
                # Test mode overrides should be applied
                assert result['backup']['source_path'] == '/tmp/photo-backup-test-photos'
                assert result['storage']['endpoint'] == 'localhost:9000'


class TestConfigMergeAndOverride:
    """Test cases for config merging and override functionality."""
    
    @pytest.mark.unit
    def test_merge_with_defaults(self):
        """Test merging file config with defaults."""
        config = Config()
        file_config = {
            'backup': {
                'source_path': '/custom/photos'
                # destination not specified, should use default
            },
            'storage': {
                'endpoint': 'custom.s3.com'
                # other fields not specified, should use defaults
            }
        }
        
        merged = config.utils.merge_with_defaults(file_config, DEFAULT_CONFIG)
        
        # File config should override defaults
        assert merged['backup']['source_path'] == '/custom/photos'
        assert merged['storage']['endpoint'] == 'custom.s3.com'
        
        # Defaults should be preserved for unspecified fields
        assert merged['backup']['destination'] == 'wasabi-photo:my-photo-backup-bucket'
        assert merged['storage']['access_key'] is None
        assert merged['storage']['use_ssl'] is True
    
    @pytest.mark.unit
    def test_apply_test_mode_overrides(self):
        """Test applying test mode overrides to config."""
        config = Config()
        base_config = {
            'backup': {
                'source_path': '/custom/photos',
                'destination': 'custom:backup'
            },
            'storage': {
                'endpoint': 'custom.s3.com',
                'access_key': 'custom_key',
                'secret_key': 'custom_secret',
                'use_ssl': True
            }
        }
        
        overridden = config.utils.apply_test_mode_overrides(base_config, TEST_MODE_DEFAULTS)
        
        # Test mode overrides should take precedence
        assert overridden['backup']['source_path'] == '/tmp/photo-backup-test-photos'
        assert overridden['storage']['endpoint'] == 'localhost:9000'
        assert overridden['storage']['access_key'] == 'minioadmin'
        assert overridden['storage']['secret_key'] == 'minioadmin'
        assert overridden['storage']['use_ssl'] is False
    
    @pytest.mark.unit
    def test_get_config_file_path(self):
        """Test getting config file path."""
        config = Config()
        
        # Initially no config file path
        assert config.get_config_file_path() is None
        
        # After loading config, should return the path
        with patch.object(config.loader, 'load_config_from_file', return_value=None):
            config.load_config()
            # Should still be None since no file was loaded
            assert config.get_config_file_path() is None


class TestConfigValidationIntegration:
    """Test cases for config validation integration."""
    
    @pytest.mark.unit
    def test_validate_config_comprehensive_valid(self):
        """Test comprehensive valid configuration."""
        config = Config()
        valid_config = {
            'backup': {
                'source_path': '/Volumes/4TB-SSD/Photo',
                'destination': 'wasabi-photo:my-photo-backup-bucket'
            },
            'storage': {
                'endpoint': 's3.wasabisys.com',
                'access_key': None,
                'secret_key': None,
                'use_ssl': True
            },
            'monitoring': {
                'check_interval_hours': 4,
                'mount_delay_minutes': 15,
                'change_delay_minutes': 30
            },
            'logging': {
                'level': 'INFO',
                'directory': '~/Library/Logs/photo-backup',
                'max_size_mb': 100,
                'backup_count': 5
            },
            'state': {
                'directory': '~/Library/Application Support/photo-backup'
            }
        }
        
        # Mock path validation to avoid filesystem dependencies
        with patch.object(config.validator, '_validate_paths', return_value=[]):
            is_valid, errors = config.validator.validate_config(valid_config)
            assert is_valid is True
            assert len(errors) == 0
    
    @pytest.mark.unit
    def test_validate_config_comprehensive_invalid(self):
        """Test comprehensive invalid configuration."""
        config = Config()
        invalid_config = {
            'backup': {
                'source_path': 'relative/path',  # Should be absolute
                'destination': 'wasabi-photo:my-photo-backup-bucket'
            },
            'storage': {
                'endpoint': 's3.wasabisys.com',
                'access_key': None,
                'secret_key': None,
                'use_ssl': True
            },
            'monitoring': {
                'check_interval_hours': 25,  # Too high
                'mount_delay_minutes': 0,    # Too low
                'change_delay_minutes': 30
            },
            'logging': {
                'level': 'INFO',
                'directory': '~/Library/Logs/photo-backup',
                'max_size_mb': 2000,  # Too high
                'backup_count': 5
            },
            'state': {
                'directory': '~/Library/Application Support/photo-backup'
            }
        }
        
        is_valid, errors = config.validator.validate_config(invalid_config)
        assert is_valid is False
        assert len(errors) > 0
        
        # Check that specific errors are present
        error_messages = [error.lower() for error in errors]
        assert any('backup.source_path must be an absolute path' in error for error in error_messages)
        assert any('check_interval_hours must be between' in error for error in error_messages)
        assert any('mount_delay_minutes must be between' in error for error in error_messages)
        assert any('max_size_mb must be between' in error for error in error_messages)
    
    @pytest.mark.unit
    def test_load_config_fails_early_on_validation_error(self):
        """Test that load_config fails early on validation errors."""
        config = Config()
        invalid_config = {
            'backup': {
                'source_path': 'relative/path'  # Invalid - should be absolute
            }
        }
        
        with patch.object(config.loader, 'load_config_from_file', return_value=invalid_config):
            with pytest.raises(ValueError) as exc_info:
                config.load_config()
            
            error_message = str(exc_info.value)
            assert "Configuration validation failed:" in error_message
            assert "backup.source_path must be an absolute path" in error_message


class TestConfigDefaults:
    """Test cases for default configuration functionality."""
    
    @pytest.mark.unit
    def test_default_config_structure(self):
        """Test that DEFAULT_CONFIG has the expected structure."""
        from photo_backup.config.defaults import DEFAULT_CONFIG
        
        # Check that all required sections exist
        required_sections = ['backup', 'storage', 'monitoring', 'logging', 'state']
        for section in required_sections:
            assert section in DEFAULT_CONFIG
            assert isinstance(DEFAULT_CONFIG[section], dict)
        
        # Check that backup section has required fields
        backup = DEFAULT_CONFIG['backup']
        assert 'source_path' in backup
        assert 'destination' in backup
        assert 'strategy' in backup
        assert backup['strategy'] == 'incremental'
        
        # Check that storage section has required fields
        storage = DEFAULT_CONFIG['storage']
        assert 'endpoint' in storage
        assert 'access_key' in storage
        assert 'secret_key' in storage
        assert storage['endpoint'] == 's3.wasabisys.com'
        
        # Check that monitoring section has required fields
        monitoring = DEFAULT_CONFIG['monitoring']
        assert 'check_interval_hours' in monitoring
        assert 'mount_delay_minutes' in monitoring
        assert 'change_delay_minutes' in monitoring
    
    @pytest.mark.unit
    def test_default_config_documentation(self):
        """Test that DEFAULT_CONFIG_DOCS has documentation for all settings."""
        from photo_backup.config.defaults import DEFAULT_CONFIG_DOCS, DEFAULT_CONFIG
        
        # Check that all sections in DEFAULT_CONFIG have documentation
        for section in DEFAULT_CONFIG:
            assert section in DEFAULT_CONFIG_DOCS
            assert isinstance(DEFAULT_CONFIG_DOCS[section], dict)
            
            # Check that all fields in each section have documentation
            for field in DEFAULT_CONFIG[section]:
                if isinstance(DEFAULT_CONFIG[section][field], dict):
                    # For nested dictionaries, check if the field itself has documentation
                    if field in DEFAULT_CONFIG_DOCS[section]:
                        assert isinstance(DEFAULT_CONFIG_DOCS[section][field], dict)
                else:
                    # For simple fields, check that documentation exists
                    assert field in DEFAULT_CONFIG_DOCS[section]
                    assert isinstance(DEFAULT_CONFIG_DOCS[section][field], str)
                    assert len(DEFAULT_CONFIG_DOCS[section][field]) > 0
    
    @pytest.mark.unit
    def test_test_mode_defaults(self):
        """Test that TEST_MODE_DEFAULTS has appropriate test settings."""
        from photo_backup.config.defaults import TEST_MODE_DEFAULTS
        
        # Check that test mode has faster intervals
        monitoring = TEST_MODE_DEFAULTS['monitoring']
        assert monitoring['check_interval_hours'] == 0.1  # 6 minutes
        assert monitoring['mount_delay_minutes'] == 1
        assert monitoring['change_delay_minutes'] == 1
        
        # Check that test mode uses local storage
        storage = TEST_MODE_DEFAULTS['storage']
        assert storage['endpoint'] == 'localhost:9000'
        assert storage['access_key'] == 'minioadmin'
        assert storage['secret_key'] == 'minioadmin'
        assert storage['use_ssl'] is False
        
        # Check that test mode uses debug logging
        logging = TEST_MODE_DEFAULTS['logging']
        assert logging['level'] == 'DEBUG'
        assert '/tmp/photo-backup-test' in logging['directory']
    
    @pytest.mark.unit
    def test_get_config_documentation(self):
        """Test get_config_documentation method."""
        config = Config()
        docs = config.get_config_documentation()
        
        # Check that documentation is returned
        assert isinstance(docs, dict)
        assert 'backup' in docs
        assert 'storage' in docs
        assert 'monitoring' in docs
        assert 'logging' in docs
        assert 'state' in docs
        
        # Check that it's a copy, not the original
        assert docs is not config.get_config_documentation()
    
    @pytest.mark.unit
    def test_get_default_value(self):
        """Test get_default_value method."""
        config = Config()
        
        # Test simple key
        value = config.get_default_value('backup.source_path')
        assert value == '/Volumes/4TB-SSD/Photo'
        
        # Test nested key
        value = config.get_default_value('storage.endpoint')
        assert value == 's3.wasabisys.com'
        
        # Test non-existent key
        value = config.get_default_value('nonexistent.key')
        assert value is None
        
        # Test section key
        value = config.get_default_value('backup')
        assert isinstance(value, dict)
        assert 'source_path' in value
    
    @pytest.mark.unit
    def test_get_default_documentation(self):
        """Test get_default_documentation method."""
        config = Config()
        
        # Test simple key documentation
        doc = config.get_default_documentation('backup.source_path')
        assert isinstance(doc, str)
        assert 'Absolute path' in doc
        
        # Test nested key documentation
        doc = config.get_default_documentation('storage.endpoint')
        assert isinstance(doc, str)
        assert 'S3-compatible' in doc
        
        # Test non-existent key
        doc = config.get_default_documentation('nonexistent.key')
        assert doc is None
        
        # Test section documentation (returns dict of field docs)
        doc = config.get_default_documentation('backup')
        assert isinstance(doc, dict)
        assert 'source_path' in doc
        assert isinstance(doc['source_path'], str)
    
    @pytest.mark.unit
    def test_get_default_config_returns_copy(self):
        """Test that _get_default_config returns a copy, not the original."""
        config = Config()
        default1 = config._get_default_config()
        default2 = config._get_default_config()
        
        # Should be different objects
        assert default1 is not default2
        
        # But should have the same content
        assert default1 == default2
    
    @pytest.mark.unit
    def test_default_config_has_new_sections(self):
        """Test that DEFAULT_CONFIG includes new sections."""
        from photo_backup.config.defaults import DEFAULT_CONFIG
        
        # Check for new sections
        assert 'security' in DEFAULT_CONFIG
        assert 'performance' in DEFAULT_CONFIG
        assert 'notifications' in DEFAULT_CONFIG
        
        # Check security section
        security = DEFAULT_CONFIG['security']
        assert 'encrypt_backups' in security
        assert 'verify_checksums' in security
        assert 'checksum_algorithm' in security
        
        # Check performance section
        performance = DEFAULT_CONFIG['performance']
        assert 'buffer_size_mb' in performance
        assert 'max_memory_usage_mb' in performance
        assert 'parallel_uploads' in performance
        
        # Check notifications section
        notifications = DEFAULT_CONFIG['notifications']
        assert 'enabled' in notifications
        assert 'email' in notifications
        assert 'webhook' in notifications
    
    @pytest.mark.unit
    def test_test_mode_defaults_optimized_for_testing(self):
        """Test that test mode defaults are optimized for testing."""
        from photo_backup.config.defaults import TEST_MODE_DEFAULTS
        
        # Check performance settings are reduced for testing
        performance = TEST_MODE_DEFAULTS['performance']
        assert performance['buffer_size_mb'] == 1  # Smaller buffer
        assert performance['max_memory_usage_mb'] == 64  # Lower memory
        assert performance['chunk_size_mb'] == 1  # Smaller chunks
        assert performance['enable_caching'] is False  # No caching
        
        # Check security settings are relaxed for testing
        security = TEST_MODE_DEFAULTS['security']
        assert security['verify_checksums'] is False  # Skip verification
        assert security['encrypt_backups'] is False  # No encryption
        
        # Check backup settings are optimized for testing
        backup = TEST_MODE_DEFAULTS['backup']
        assert backup['compression'] is False  # No compression
        assert backup['verify_after_backup'] is False  # Skip verification
    
    @pytest.mark.unit
    def test_default_config_backward_compatibility(self):
        """Test that default config maintains backward compatibility."""
        config = Config()
        default_config = config._get_default_config()
        
        # Check that original fields still exist with same values
        assert default_config['backup']['source_path'] == '/Volumes/4TB-SSD/Photo'
        assert default_config['backup']['destination'] == 'wasabi-photo:my-photo-backup-bucket'
        assert default_config['storage']['endpoint'] == 's3.wasabisys.com'
        assert default_config['storage']['access_key'] is None
        assert default_config['storage']['secret_key'] is None
        assert default_config['storage']['use_ssl'] is True
        assert default_config['monitoring']['check_interval_hours'] == 4
        assert default_config['monitoring']['mount_delay_minutes'] == 15
        assert default_config['monitoring']['change_delay_minutes'] == 30
        assert default_config['logging']['level'] == 'INFO'
        assert default_config['logging']['directory'] == '~/Library/Logs/photo-backup'
        assert default_config['state']['directory'] == '~/Library/Application Support/photo-backup'
    
    @pytest.mark.unit
    def test_config_works_without_file(self):
        """Test that config works without a config file using defaults."""
        config = Config(test_mode=False)
        
        # Should load defaults when no file exists
        settings = config.load_config()
        
        # Should have all default values
        assert settings['backup']['source_path'] == '/Volumes/4TB-SSD/Photo'
        assert settings['storage']['endpoint'] == 's3.wasabisys.com'
        assert settings['monitoring']['check_interval_hours'] == 4
        assert settings['logging']['level'] == 'INFO'
        
        # Should have new sections
        assert 'security' in settings
        assert 'performance' in settings
        assert 'notifications' in settings
        
        # Should indicate no config file was loaded
        assert config.get_config_file_path() is None 