"""
Unit tests for EnvOverride class.

These tests focus on environment variable override functionality.
"""

import pytest
import os
from unittest.mock import patch
from photo_backup.config.env_override import EnvOverride
from photo_backup.config import Config


class TestEnvOverride:
    """Test cases for EnvOverride class."""
    
    @pytest.mark.unit
    def test_is_test_mode_enabled_true(self):
        """Test that test mode is enabled with truthy values."""
        truthy_values = ['1', 'true', 'TRUE', 'True', 'yes', 'YES', 'on', 'ON']
        
        for value in truthy_values:
            with patch.dict(os.environ, {'PHOTO_BACKUP_TEST_MODE': value}):
                assert EnvOverride.is_test_mode_enabled() is True
    
    @pytest.mark.unit
    def test_is_test_mode_enabled_false(self):
        """Test that test mode is disabled with falsy values."""
        falsy_values = ['0', 'false', 'FALSE', 'False', 'no', 'NO', 'off', 'OFF', '', 'anything']
        
        for value in falsy_values:
            with patch.dict(os.environ, {'PHOTO_BACKUP_TEST_MODE': value}):
                assert EnvOverride.is_test_mode_enabled() is False
    
    @pytest.mark.unit
    def test_is_test_mode_enabled_not_set(self):
        """Test that test mode is disabled when env var is not set."""
        with patch.dict(os.environ, {}, clear=True):
            assert EnvOverride.is_test_mode_enabled() is False
    
    @pytest.mark.unit
    def test_env_key_to_config_key_valid(self):
        """Test converting valid environment variable keys to config keys."""
        test_cases = [
            ('PHOTO_BACKUP_BACKUP_SOURCE_PATH', 'backup.source_path'),
            ('PHOTO_BACKUP_STORAGE_ENDPOINT', 'storage.endpoint'),
            ('PHOTO_BACKUP_MONITORING_CHECK_INTERVAL_HOURS', 'monitoring.check_interval_hours'),
            ('PHOTO_BACKUP_LOGGING_LEVEL', 'logging.level'),
            ('PHOTO_BACKUP_STATE_DIRECTORY', 'state.directory'),
        ]
        
        for env_key, expected_config_key in test_cases:
            result = EnvOverride._env_key_to_config_key(env_key)
            assert result == expected_config_key
    
    @pytest.mark.unit
    def test_env_key_to_config_key_invalid(self):
        """Test that invalid environment variable keys return None."""
        invalid_keys = [
            'PHOTO_BACKUP_TEST_MODE',  # Special case, handled separately
            'PHOTO_BACKUP_',  # No section
            'PHOTO_BACKUP_BACKUP',  # No key after section
            'NOT_PHOTO_BACKUP_SOMETHING',  # Wrong prefix
            'PHOTO_BACKUP',  # Just prefix
            'SOMETHING_ELSE',  # Completely different
        ]
        
        for env_key in invalid_keys:
            result = EnvOverride._env_key_to_config_key(env_key)
            assert result is None
    
    @pytest.mark.unit
    def test_convert_env_value_string(self):
        """Test converting environment values to strings."""
        test_cases = [
            ('backup.source_path', '/custom/path', '/custom/path'),
            ('storage.endpoint', 'custom.s3.com', 'custom.s3.com'),
            ('logging.level', 'DEBUG', 'DEBUG'),
        ]
        
        for config_key, env_value, expected in test_cases:
            result = EnvOverride._convert_env_value(config_key, env_value)
            assert result == expected
            assert isinstance(result, str)
    
    @pytest.mark.unit
    def test_convert_env_value_int(self):
        """Test converting environment values to integers."""
        test_cases = [
            ('monitoring.mount_delay_minutes', '15', 15),
            ('logging.max_size_mb', '100', 100),
            ('logging.backup_count', '5', 5),
        ]
        
        for config_key, env_value, expected in test_cases:
            result = EnvOverride._convert_env_value(config_key, env_value)
            assert result == expected
            assert isinstance(result, int)
    
    @pytest.mark.unit
    def test_convert_env_value_float(self):
        """Test converting environment values to floats."""
        test_cases = [
            ('monitoring.check_interval_hours', '4.5', 4.5),
            ('monitoring.check_interval_hours', '0.1', 0.1),
        ]
        
        for config_key, env_value, expected in test_cases:
            result = EnvOverride._convert_env_value(config_key, env_value)
            assert result == expected
            assert isinstance(result, float)
    
    @pytest.mark.unit
    def test_convert_env_value_bool(self):
        """Test converting environment values to booleans."""
        # True values
        true_values = ['true', 'TRUE', 'True', '1', 'yes', 'YES', 'on', 'ON']
        for value in true_values:
            result = EnvOverride._convert_env_value('storage.use_ssl', value)
            assert result is True
            assert isinstance(result, bool)
        
        # False values
        false_values = ['false', 'FALSE', 'False', '0', 'no', 'NO', 'off', 'OFF']
        for value in false_values:
            result = EnvOverride._convert_env_value('storage.use_ssl', value)
            assert result is False
            assert isinstance(result, bool)
    
    @pytest.mark.unit
    def test_convert_env_value_fallback_to_string(self):
        """Test that invalid conversions fall back to string."""
        # Invalid int
        result = EnvOverride._convert_env_value('logging.max_size_mb', 'not_a_number')
        assert result == 'not_a_number'
        assert isinstance(result, str)
        
        # Invalid float
        result = EnvOverride._convert_env_value('monitoring.check_interval_hours', 'not_a_float')
        assert result == 'not_a_float'
        assert isinstance(result, str)
    
    @pytest.mark.unit
    def test_get_env_overrides_empty(self):
        """Test getting environment overrides when none are set."""
        with patch.dict(os.environ, {}, clear=True):
            overrides = EnvOverride.get_env_overrides()
            assert overrides == {}
    
    @pytest.mark.unit
    def test_get_env_overrides_single(self):
        """Test getting a single environment override."""
        env_vars = {
            'PHOTO_BACKUP_BACKUP_SOURCE_PATH': '/custom/photos'
        }
        
        with patch.dict(os.environ, env_vars):
            overrides = EnvOverride.get_env_overrides()
            assert overrides == {'backup': {'source_path': '/custom/photos'}}
    
    @pytest.mark.unit
    def test_get_env_overrides_multiple(self):
        """Test getting multiple environment overrides."""
        env_vars = {
            'PHOTO_BACKUP_BACKUP_SOURCE_PATH': '/custom/photos',
            'PHOTO_BACKUP_STORAGE_ENDPOINT': 'custom.s3.com',
            'PHOTO_BACKUP_STORAGE_USE_SSL': 'false',
            'PHOTO_BACKUP_MONITORING_CHECK_INTERVAL_HOURS': '2.5',
        }
        
        with patch.dict(os.environ, env_vars):
            overrides = EnvOverride.get_env_overrides()
            expected = {
                'backup': {'source_path': '/custom/photos'},
                'storage': {
                    'endpoint': 'custom.s3.com',
                    'use_ssl': False
                },
                'monitoring': {'check_interval_hours': 2.5}
            }
            assert overrides == expected
    
    @pytest.mark.unit
    def test_get_env_overrides_ignores_invalid(self):
        """Test that invalid environment variables are ignored."""
        env_vars = {
            'PHOTO_BACKUP_BACKUP_SOURCE_PATH': '/custom/photos',  # Valid
            'PHOTO_BACKUP_TEST_MODE': '1',  # Special case, should be ignored
            'PHOTO_BACKUP_': 'something',  # Invalid, should be ignored
            'NOT_PHOTO_BACKUP_SOMETHING': 'value',  # Wrong prefix, should be ignored
        }
        
        with patch.dict(os.environ, env_vars):
            overrides = EnvOverride.get_env_overrides()
            assert overrides == {'backup': {'source_path': '/custom/photos'}}
    
    @pytest.mark.unit
    def test_apply_env_overrides_empty(self):
        """Test applying empty environment overrides."""
        config = {
            'backup': {'source_path': '/default/path'},
            'storage': {'endpoint': 'default.s3.com'}
        }
        
        with patch.dict(os.environ, {}, clear=True):
            result = EnvOverride.apply_env_overrides(config)
            assert result == config
    
    @pytest.mark.unit
    def test_apply_env_overrides_single(self):
        """Test applying a single environment override."""
        config = {
            'backup': {'source_path': '/default/path'},
            'storage': {'endpoint': 'default.s3.com'}
        }
        
        env_vars = {
            'PHOTO_BACKUP_BACKUP_SOURCE_PATH': '/custom/photos'
        }
        
        with patch.dict(os.environ, env_vars):
            result = EnvOverride.apply_env_overrides(config)
            expected = {
                'backup': {'source_path': '/custom/photos'},  # Overridden
                'storage': {'endpoint': 'default.s3.com'}  # Unchanged
            }
            assert result == expected
    
    @pytest.mark.unit
    def test_apply_env_overrides_multiple(self):
        """Test applying multiple environment overrides."""
        config = {
            'backup': {'source_path': '/default/path'},
            'storage': {'endpoint': 'default.s3.com', 'use_ssl': True},
            'monitoring': {'check_interval_hours': 4}
        }
        
        env_vars = {
            'PHOTO_BACKUP_BACKUP_SOURCE_PATH': '/custom/photos',
            'PHOTO_BACKUP_STORAGE_USE_SSL': 'false',
            'PHOTO_BACKUP_MONITORING_CHECK_INTERVAL_HOURS': '2.5',
        }
        
        with patch.dict(os.environ, env_vars):
            result = EnvOverride.apply_env_overrides(config)
            expected = {
                'backup': {'source_path': '/custom/photos'},  # Overridden
                'storage': {
                    'endpoint': 'default.s3.com',  # Unchanged
                    'use_ssl': False  # Overridden
                },
                'monitoring': {'check_interval_hours': 2.5}  # Overridden
            }
            assert result == expected
    
    @pytest.mark.unit
    def test_get_env_override_info(self):
        """Test getting environment override information."""
        env_vars = {
            'PHOTO_BACKUP_TEST_MODE': '1',
            'PHOTO_BACKUP_BACKUP_SOURCE_PATH': '/custom/photos',
            'PHOTO_BACKUP_STORAGE_ENDPOINT': 'custom.s3.com',
        }
        
        with patch.dict(os.environ, env_vars):
            info = EnvOverride.get_env_override_info()
            
            assert info['test_mode_enabled'] is True
            assert info['override_count'] == 2
            assert 'backup' in info['overrides']
            assert 'storage' in info['overrides']
            assert info['overrides']['backup']['source_path'] == '/custom/photos'
            assert info['overrides']['storage']['endpoint'] == 'custom.s3.com'
            assert 'PHOTO_BACKUP_BACKUP_SOURCE_PATH' in info['env_vars_used']
            assert 'PHOTO_BACKUP_STORAGE_ENDPOINT' in info['env_vars_used']
    
    @pytest.mark.unit
    def test_set_nested_value(self):
        """Test setting nested values in a dictionary."""
        data = {}
        
        # Set simple nested value
        EnvOverride._set_nested_value(data, 'backup.source_path', '/custom/path')
        assert data == {'backup': {'source_path': '/custom/path'}}
        
        # Set another value in same section
        EnvOverride._set_nested_value(data, 'backup.destination', 'custom:backup')
        assert data == {
            'backup': {
                'source_path': '/custom/path',
                'destination': 'custom:backup'
            }
        }
        
        # Set value in different section
        EnvOverride._set_nested_value(data, 'storage.endpoint', 'custom.s3.com')
        assert data == {
            'backup': {
                'source_path': '/custom/path',
                'destination': 'custom:backup'
            },
            'storage': {
                'endpoint': 'custom.s3.com'
            }
        }
    
    @pytest.mark.unit
    def test_get_expected_type(self):
        """Test getting expected types for configuration keys."""
        # Test string types
        assert EnvOverride._get_expected_type('backup.source_path') == str
        assert EnvOverride._get_expected_type('storage.endpoint') == str
        assert EnvOverride._get_expected_type('logging.level') == str
        
        # Test int types
        assert EnvOverride._get_expected_type('monitoring.mount_delay_minutes') == int
        assert EnvOverride._get_expected_type('logging.max_size_mb') == int
        assert EnvOverride._get_expected_type('logging.backup_count') == int
        
        # Test float types
        assert EnvOverride._get_expected_type('monitoring.check_interval_hours') == float
        
        # Test bool types
        assert EnvOverride._get_expected_type('storage.use_ssl') == bool
        assert EnvOverride._get_expected_type('security.encrypt_backups') == bool
        assert EnvOverride._get_expected_type('performance.enable_caching') == bool
        
        # Test unknown keys default to string
        assert EnvOverride._get_expected_type('unknown.key') == str


class TestConfigEnvOverride:
    """Test cases for Config class with environment variable overrides."""
    
    @pytest.mark.unit
    def test_config_test_mode_from_env(self):
        """Test that config detects test mode from environment variable."""
        with patch.dict(os.environ, {'PHOTO_BACKUP_TEST_MODE': '1'}):
            config = Config()  # test_mode=None, should check env var
            assert config.is_test_mode() is True
            
            settings = config.load_config()
            assert settings['storage']['endpoint'] == 'localhost:9000'
            assert settings['storage']['access_key'] == 'minioadmin'
    
    @pytest.mark.unit
    def test_config_env_override_priority(self):
        """Test that environment variables override file config."""
        file_config = {
            'backup': {
                'source_path': '/file/photos',
                'destination': 'file:backup'
            },
            'storage': {
                'endpoint': 'file.s3.com',
                'use_ssl': True
            }
        }
        
        env_vars = {
            'PHOTO_BACKUP_BACKUP_SOURCE_PATH': '/env/photos',
            'PHOTO_BACKUP_STORAGE_USE_SSL': 'false',
        }
        
        with patch.dict(os.environ, env_vars):
            config = Config(test_mode=False)
            
            with patch.object(config.loader, 'load_config_from_file', return_value=file_config):
                with patch.object(config.validator, 'validate_config', return_value=(True, [])):
                    settings = config.load_config()
                    
                    # Environment variables should override file config
                    assert settings['backup']['source_path'] == '/env/photos'  # From env
                    assert settings['backup']['destination'] == 'file:backup'  # From file
                    assert settings['storage']['endpoint'] == 'file.s3.com'  # From file
                    assert settings['storage']['use_ssl'] is False  # From env
    
    @pytest.mark.unit
    def test_config_env_override_with_defaults(self):
        """Test that environment variables override defaults."""
        env_vars = {
            'PHOTO_BACKUP_BACKUP_SOURCE_PATH': '/env/photos',
            'PHOTO_BACKUP_STORAGE_ENDPOINT': 'env.s3.com',
            'PHOTO_BACKUP_MONITORING_CHECK_INTERVAL_HOURS': '2.5',
        }
        
        with patch.dict(os.environ, env_vars):
            config = Config(test_mode=False)
            
            with patch.object(config.loader, 'load_config_from_file', return_value=None):
                settings = config.load_config()
                
                # Environment variables should override defaults
                assert settings['backup']['source_path'] == '/env/photos'  # From env
                assert settings['backup']['destination'] == 'wasabi-photo:my-photo-backup-bucket'  # Default
                assert settings['storage']['endpoint'] == 'env.s3.com'  # From env
                assert settings['storage']['access_key'] is None  # Default
                assert settings['monitoring']['check_interval_hours'] == 2.5  # From env
                assert settings['monitoring']['mount_delay_minutes'] == 15  # Default
    
    @pytest.mark.unit
    def test_config_env_override_type_conversion(self):
        """Test that environment variables are converted to correct types."""
        env_vars = {
            'PHOTO_BACKUP_STORAGE_USE_SSL': 'false',
            'PHOTO_BACKUP_MONITORING_MOUNT_DELAY_MINUTES': '30',
            'PHOTO_BACKUP_MONITORING_CHECK_INTERVAL_HOURS': '1.5',
            'PHOTO_BACKUP_LOGGING_MAX_SIZE_MB': '200',
        }
        
        with patch.dict(os.environ, env_vars):
            config = Config(test_mode=False)
            
            with patch.object(config.loader, 'load_config_from_file', return_value=None):
                settings = config.load_config()
                
                # Check type conversions
                assert isinstance(settings['storage']['use_ssl'], bool)
                assert settings['storage']['use_ssl'] is False
                
                assert isinstance(settings['monitoring']['mount_delay_minutes'], int)
                assert settings['monitoring']['mount_delay_minutes'] == 30
                
                assert isinstance(settings['monitoring']['check_interval_hours'], float)
                assert settings['monitoring']['check_interval_hours'] == 1.5
                
                assert isinstance(settings['logging']['max_size_mb'], int)
                assert settings['logging']['max_size_mb'] == 200
    
    @pytest.mark.unit
    def test_config_get_env_override_info(self):
        """Test getting environment override information."""
        env_vars = {
            'PHOTO_BACKUP_TEST_MODE': '1',
            'PHOTO_BACKUP_BACKUP_SOURCE_PATH': '/env/photos',
            'PHOTO_BACKUP_STORAGE_ENDPOINT': 'env.s3.com',
        }
        
        with patch.dict(os.environ, env_vars):
            config = Config()
            info = config.get_env_override_info()
            
            assert info['test_mode_enabled'] is True
            assert info['override_count'] == 2
            assert 'backup' in info['overrides']
            assert 'storage' in info['overrides']
            assert info['overrides']['backup']['source_path'] == '/env/photos'
            assert info['overrides']['storage']['endpoint'] == 'env.s3.com'
            assert 'PHOTO_BACKUP_BACKUP_SOURCE_PATH' in info['env_vars_used']
            assert 'PHOTO_BACKUP_STORAGE_ENDPOINT' in info['env_vars_used']
    
    @pytest.mark.unit
    def test_config_env_override_ignores_invalid(self):
        """Test that invalid environment variables are ignored."""
        env_vars = {
            'PHOTO_BACKUP_BACKUP_SOURCE_PATH': '/env/photos',  # Valid
            'PHOTO_BACKUP_TEST_MODE': '1',  # Special case, should be ignored for overrides
            'PHOTO_BACKUP_': 'something',  # Invalid, should be ignored
            'NOT_PHOTO_BACKUP_SOMETHING': 'value',  # Wrong prefix, should be ignored
        }
        
        with patch.dict(os.environ, env_vars):
            config = Config(test_mode=False)
            
            with patch.object(config.loader, 'load_config_from_file', return_value=None):
                settings = config.load_config()
                
                # Only valid environment variable should be applied
                assert settings['backup']['source_path'] == '/env/photos'  # From env
                assert settings['backup']['destination'] == 'wasabi-photo:my-photo-backup-bucket'  # Default 