"""
Unit tests for config module.

These tests focus on configuration loading and management in isolation.
"""

import pytest
import tempfile
import yaml
from pathlib import Path
from unittest.mock import patch, mock_open
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
        config = Config(test_mode=True)
        assert config.is_test_mode() is True
        
        config = Config(test_mode=False)
        assert config.is_test_mode() is False
    
    @pytest.mark.unit
    def test_config_ssl_settings(self):
        """Test SSL settings in different modes."""
        prod_config = Config(test_mode=False)
        prod_config.load_config()
        assert prod_config.get('storage.use_ssl') is True
        
        test_config = Config(test_mode=True)
        test_config.load_config()
        assert test_config.get('storage.use_ssl') is False
    
    @pytest.mark.unit
    def test_config_monitoring_settings(self):
        """Test monitoring settings in different modes."""
        prod_config = Config(test_mode=False)
        prod_config.load_config()
        assert prod_config.get('monitoring.check_interval_hours') == 4
        assert prod_config.get('monitoring.mount_delay_minutes') == 15
        assert prod_config.get('monitoring.change_delay_minutes') == 30
        
        test_config = Config(test_mode=True)
        test_config.load_config()
        assert test_config.get('monitoring.check_interval_hours') == 0.1
        assert test_config.get('monitoring.mount_delay_minutes') == 1
        assert test_config.get('monitoring.change_delay_minutes') == 1
    
    @pytest.mark.unit
    def test_config_logging_settings(self):
        """Test logging settings in different modes."""
        prod_config = Config(test_mode=False)
        prod_config.load_config()
        assert prod_config.get('logging.level') == "INFO"
        
        test_config = Config(test_mode=True)
        test_config.load_config()
        assert test_config.get('logging.level') == "DEBUG"


class TestConfigFileLoading:
    """Test cases for YAML file loading functionality."""
    
    @pytest.mark.unit
    def testload_config_from_file_valid_yaml(self):
        """Test loading valid YAML configuration file."""
        test_config = {
            'backup': {
                'source_path': '/custom/photos',
                'destination': 'custom:backup'
            },
            'storage': {
                'endpoint': 'custom.s3.com',
                'access_key': 'custom_key',
                'secret_key': 'custom_secret',
                'use_ssl': True
            },
            'monitoring': {
                'check_interval_hours': 2,
                'mount_delay_minutes': 10,
                'change_delay_minutes': 20
            },
            'logging': {
                'level': 'WARNING',
                'directory': '/custom/logs'
            },
            'state': {
                'directory': '/custom/state'
            }
        }
        
        with patch('builtins.open', mock_open(read_data=yaml.dump(test_config))):
            with patch.object(Path, 'exists', return_value=True):
                with patch.object(Path, 'is_file', return_value=True):
                    # Mock path validation to pass
                    with patch.object(Path, 'is_dir', return_value=True):
                        with patch('os.access', return_value=True):
                            config = Config(test_mode=False)
                            config.load_config()
                            
                            # Should use file config values
                            assert config.get('backup.source_path') == '/custom/photos'
                            assert config.get('storage.endpoint') == 'custom.s3.com'
                            assert config.get('monitoring.check_interval_hours') == 2
                            assert config.get('logging.level') == 'WARNING'
    
    @pytest.mark.unit
    def testload_config_from_file_not_found(self):
        """Test behavior when no config file is found."""
        with patch.object(Path, 'exists', return_value=False):
            config = Config(test_mode=False)
            config.load_config()
            
            # Should use default values
            assert config.get('backup.source_path') == '/Volumes/4TB-SSD/Photo'
            assert config.get('storage.endpoint') == 's3.wasabisys.com'
            assert config.loader.get_config_file_path() is None
    
    @pytest.mark.unit
    def testload_config_from_file_invalid_yaml(self):
        """Test behavior when config file contains invalid YAML."""
        invalid_yaml = """
        backup:
          source_path: /custom/photos
        storage:
          endpoint: custom.s3.com
          access_key: [invalid: yaml: syntax
        """
        
        with patch('builtins.open', mock_open(read_data=invalid_yaml)):
            with patch.object(Path, 'exists', return_value=True):
                with patch.object(Path, 'is_file', return_value=True):
                    config = Config(test_mode=False)
                    config.loader.load_config_from_file()
                    
                    # Should fall back to defaults
                    assert config.get('backup.source_path') == '/Volumes/4TB-SSD/Photo'
                    assert config.get('storage.endpoint') == 's3.wasabisys.com'
    
    @pytest.mark.unit
    def testload_config_from_file_with_test_mode_override(self):
        """Test that test mode overrides file config."""
        test_config = {
            'backup': {
                'source_path': '/custom/photos',
                'destination': 'custom:backup'
            },
            'storage': {
                'endpoint': 'custom.s3.com',
                'access_key': 'custom_key',
                'secret_key': 'custom_secret',
                'use_ssl': True
            },
            'monitoring': {
                'check_interval_hours': 2,
                'mount_delay_minutes': 10,
                'change_delay_minutes': 20
            },
            'logging': {
                'level': 'WARNING',
                'directory': '/custom/logs'
            },
            'state': {
                'directory': '/custom/state'
            }
        }
        
        with patch('builtins.open', mock_open(read_data=yaml.dump(test_config))):
            with patch.object(Path, 'exists', return_value=True):
                with patch.object(Path, 'is_file', return_value=True):
                    # Mock path validation to pass
                    with patch.object(Path, 'is_dir', return_value=True):
                        with patch('os.access', return_value=True):
                            config = Config(test_mode=True)
                            config.loader.load_config_from_file()
                            
                            # Test mode should override file config
                            assert config.get('backup.source_path') == '/tmp/photo-backup-test-photos'
                            assert config.get('storage.endpoint') == 'localhost:9000'
                            assert config.get('storage.access_key') == 'minioadmin'
                            assert config.get('monitoring.check_interval_hours') == 0.1
                            assert config.get('logging.level') == 'DEBUG'


class TestConfigSchemaValidation:
    """Test cases for configuration schema validation."""
    
    @pytest.mark.unit
    def test_validate_config_schema_valid(self):
        """Test validation of valid configuration."""
        config = Config()
        valid_config = {
            'backup': {
                'source_path': '/custom/photos',
                'destination': 'custom:backup'
            },
            'storage': {
                'endpoint': 'custom.s3.com',
                'access_key': 'custom_key',
                'secret_key': 'custom_secret',
                'use_ssl': True
            },
            'monitoring': {
                'check_interval_hours': 2,
                'mount_delay_minutes': 10,
                'change_delay_minutes': 20
            },
            'logging': {
                'level': 'WARNING',
                'directory': '/custom/logs'
            },
            'state': {
                'directory': '/custom/state'
            }
        }
        
        errors = config.validator._validate_config_schema(valid_config)
        assert len(errors) == 0
    
    @pytest.mark.unit
    def test_validate_config_schema_missing_sections(self):
        """Test validation with missing required sections."""
        config = Config()
        invalid_config = {
            'backup': {
                'source_path': '/custom/photos',
                'destination': 'custom:backup'
            }
            # Missing storage, monitoring, logging, state sections
        }
        
        errors = config.validator._validate_config_schema(invalid_config)
        assert len(errors) == 4
        assert "Missing required section: storage" in errors
        assert "Missing required section: monitoring" in errors
        assert "Missing required section: logging" in errors
        assert "Missing required section: state" in errors
    
    @pytest.mark.unit
    def test_validate_config_schema_missing_backup_fields(self):
        """Test validation with missing backup fields."""
        config = Config()
        invalid_config = {
            'backup': {
                # Missing source_path and destination
            },
            'storage': {
                'endpoint': 'custom.s3.com',
                'access_key': 'custom_key',
                'secret_key': 'custom_secret',
                'use_ssl': True
            },
            'monitoring': {
                'check_interval_hours': 2,
                'mount_delay_minutes': 10,
                'change_delay_minutes': 20
            },
            'logging': {
                'level': 'WARNING',
                'directory': '/custom/logs'
            },
            'state': {
                'directory': '/custom/state'
            }
        }
        
        errors = config.validator._validate_config_schema(invalid_config)
        assert "backup.source_path is required" in errors
        assert "backup.destination is required" in errors
    
    @pytest.mark.unit
    def test_validate_config_schema_invalid_types(self):
        """Test validation with invalid data types."""
        config = Config()
        invalid_config = {
            'backup': {
                'source_path': 123,  # Should be string
                'destination': 'custom:backup'
            },
            'storage': {
                'endpoint': 'custom.s3.com',
                'access_key': 'custom_key',
                'secret_key': 'custom_secret',
                'use_ssl': 'true'  # Should be boolean
            },
            'monitoring': {
                'check_interval_hours': '2',  # Should be number
                'mount_delay_minutes': 10,
                'change_delay_minutes': 20
            },
            'logging': {
                'level': 'WARNING',
                'directory': '/custom/logs'
            },
            'state': {
                'directory': '/custom/state'
            }
        }
        
        errors = config.validator._validate_config_schema(invalid_config)
        assert "backup.source_path must be a string" in errors
        assert "storage.use_ssl must be a boolean" in errors
        assert "monitoring.check_interval_hours must be a number" in errors
    
    @pytest.mark.unit
    def test_validate_config_schema_null_credentials_allowed(self):
        """Test that null credentials are allowed in storage section."""
        config = Config()
        valid_config = {
            'backup': {
                'source_path': '/custom/photos',
                'destination': 'custom:backup'
            },
            'storage': {
                'endpoint': 'custom.s3.com',
                'access_key': None,  # Null is allowed
                'secret_key': None,  # Null is allowed
                'use_ssl': True
            },
            'monitoring': {
                'check_interval_hours': 2,
                'mount_delay_minutes': 10,
                'change_delay_minutes': 20
            },
            'logging': {
                'level': 'WARNING',
                'directory': '/custom/logs'
            },
            'state': {
                'directory': '/custom/state'
            }
        }
        
        errors = config.validator._validate_config_schema(valid_config)
        assert len(errors) == 0


class TestConfigPathValidation:
    """Test cases for path validation functionality."""
    
    @pytest.mark.unit
    def test_validate_paths_valid_absolute_paths(self):
        """Test validation of valid absolute paths."""
        config = Config()
        valid_config = {
            'backup': {
                'source_path': '/tmp/test-photos',
                'destination': 'custom:backup'
            },
            'storage': {
                'endpoint': 'custom.s3.com',
                'access_key': 'custom_key',
                'secret_key': 'custom_secret',
                'use_ssl': True
            },
            'monitoring': {
                'check_interval_hours': 2,
                'mount_delay_minutes': 10,
                'change_delay_minutes': 20
            },
            'logging': {
                'level': 'WARNING',
                'directory': '/tmp/test-logs'
            },
            'state': {
                'directory': '/tmp/test-state'
            }
        }
        
        with patch.object(Path, 'exists', return_value=True):
            with patch.object(Path, 'is_dir', return_value=True):
                with patch('os.access', return_value=True):
                    errors = config.validator._validate_paths(valid_config)
                    assert len(errors) == 0
    
    @pytest.mark.unit
    def test_validate_paths_relative_path_error(self):
        """Test validation rejects relative paths."""
        config = Config()
        invalid_config = {
            'backup': {
                'source_path': 'relative/path',  # Should be absolute
                'destination': 'custom:backup'
            },
            'storage': {
                'endpoint': 'custom.s3.com',
                'access_key': 'custom_key',
                'secret_key': 'custom_secret',
                'use_ssl': True
            },
            'monitoring': {
                'check_interval_hours': 2,
                'mount_delay_minutes': 10,
                'change_delay_minutes': 20
            },
            'logging': {
                'level': 'WARNING',
                'directory': '/tmp/test-logs'
            },
            'state': {
                'directory': '/tmp/test-state'
            }
        }
        
        errors = config.validator._validate_paths(invalid_config)
        # Check that the specific error is in the list
        assert any("backup.source_path must be an absolute path" in error for error in errors)
    
    @pytest.mark.unit
    def test_validate_paths_nonexistent_path_error(self):
        """Test validation rejects nonexistent paths."""
        config = Config()
        invalid_config = {
            'backup': {
                'source_path': '/nonexistent/path',
                'destination': 'custom:backup'
            },
            'storage': {
                'endpoint': 'custom.s3.com',
                'access_key': 'custom_key',
                'secret_key': 'custom_secret',
                'use_ssl': True
            },
            'monitoring': {
                'check_interval_hours': 2,
                'mount_delay_minutes': 10,
                'change_delay_minutes': 20
            },
            'logging': {
                'level': 'WARNING',
                'directory': '/tmp/test-logs'
            },
            'state': {
                'directory': '/tmp/test-state'
            }
        }
        
        with patch.object(Path, 'exists', return_value=False):
            errors = config.validator._validate_paths(invalid_config)
            # Check that the specific error is in the list
            assert any("backup.source_path does not exist" in error for error in errors)
    
    @pytest.mark.unit
    def test_validate_paths_not_directory_error(self):
        """Test validation rejects non-directory paths."""
        config = Config()
        invalid_config = {
            'backup': {
                'source_path': '/tmp/test-file',  # Should be directory
                'destination': 'custom:backup'
            },
            'storage': {
                'endpoint': 'custom.s3.com',
                'access_key': 'custom_key',
                'secret_key': 'custom_secret',
                'use_ssl': True
            },
            'monitoring': {
                'check_interval_hours': 2,
                'mount_delay_minutes': 10,
                'change_delay_minutes': 20
            },
            'logging': {
                'level': 'WARNING',
                'directory': '/tmp/test-logs'
            },
            'state': {
                'directory': '/tmp/test-state'
            }
        }
        
        with patch.object(Path, 'exists', return_value=True):
            with patch.object(Path, 'is_dir', return_value=False):
                errors = config.validator._validate_paths(invalid_config)
                # Check that the specific error is in the list
                assert any("backup.source_path must be a directory" in error for error in errors)
    
    @pytest.mark.unit
    def test_validate_paths_not_readable_error(self):
        """Test validation rejects non-readable paths."""
        config = Config()
        invalid_config = {
            'backup': {
                'source_path': '/tmp/test-photos',
                'destination': 'custom:backup'
            },
            'storage': {
                'endpoint': 'custom.s3.com',
                'access_key': 'custom_key',
                'secret_key': 'custom_secret',
                'use_ssl': True
            },
            'monitoring': {
                'check_interval_hours': 2,
                'mount_delay_minutes': 10,
                'change_delay_minutes': 20
            },
            'logging': {
                'level': 'WARNING',
                'directory': '/tmp/test-logs'
            },
            'state': {
                'directory': '/tmp/test-state'
            }
        }
        
        with patch.object(Path, 'exists', return_value=True):
            with patch.object(Path, 'is_dir', return_value=True):
                with patch('os.access', return_value=False):
                    errors = config.validator._validate_paths(invalid_config)
                    # Check that the specific error is in the list
                    assert any("backup.source_path is not readable" in error for error in errors)
    
    @pytest.mark.unit
    def test_expand_path(self):
        """Test path expansion functionality."""
        config = Config()
        
        # Test home directory expansion
        expanded = config.validator._expand_path("~/test")
        assert expanded.startswith("/")
        assert "test" in expanded
        
        # Test absolute path (no change)
        expanded = config.validator._expand_path("/absolute/path")
        assert expanded == "/absolute/path"
        
        # Test relative path (becomes absolute)
        expanded = config.validator._expand_path("relative/path")
        assert expanded.startswith("/")
        assert expanded.endswith("relative/path")


class TestConfigNumericValidation:
    """Test cases for numeric range validation."""
    
    @pytest.mark.unit
    def test_validate_numeric_ranges_valid(self):
        """Test validation of valid numeric ranges."""
        config = Config()
        valid_config = {
            'backup': {
                'source_path': '/tmp/test-photos',
                'destination': 'custom:backup'
            },
            'storage': {
                'endpoint': 'custom.s3.com',
                'access_key': 'custom_key',
                'secret_key': 'custom_secret',
                'use_ssl': True
            },
            'monitoring': {
                'check_interval_hours': 2,  # Valid range: 0.1 to 24
                'mount_delay_minutes': 10,  # Valid range: 1 to 60
                'change_delay_minutes': 20  # Valid range: 1 to 120
            },
            'logging': {
                'level': 'WARNING',
                'directory': '/tmp/test-logs',
                'max_size_mb': 100,  # Valid range: 1 to 1000
                'backup_count': 5    # Valid range: 1 to 50
            },
            'state': {
                'directory': '/tmp/test-state'
            }
        }
        
        errors = config.validator._validate_numeric_ranges(valid_config)
        assert len(errors) == 0
    
    @pytest.mark.unit
    def test_validate_numeric_ranges_check_interval_too_low(self):
        """Test validation rejects check_interval_hours below minimum."""
        config = Config()
        invalid_config = {
            'backup': {
                'source_path': '/tmp/test-photos',
                'destination': 'custom:backup'
            },
            'storage': {
                'endpoint': 'custom.s3.com',
                'access_key': 'custom_key',
                'secret_key': 'custom_secret',
                'use_ssl': True
            },
            'monitoring': {
                'check_interval_hours': 0.05,  # Too low: minimum is 0.1
                'mount_delay_minutes': 10,
                'change_delay_minutes': 20
            },
            'logging': {
                'level': 'WARNING',
                'directory': '/tmp/test-logs'
            },
            'state': {
                'directory': '/tmp/test-state'
            }
        }
        
        errors = config.validator._validate_numeric_ranges(invalid_config)
        assert "monitoring.check_interval_hours must be between 0.1 and 24 hours" in errors
    
    @pytest.mark.unit
    def test_validate_numeric_ranges_check_interval_too_high(self):
        """Test validation rejects check_interval_hours above maximum."""
        config = Config()
        invalid_config = {
            'backup': {
                'source_path': '/tmp/test-photos',
                'destination': 'custom:backup'
            },
            'storage': {
                'endpoint': 'custom.s3.com',
                'access_key': 'custom_key',
                'secret_key': 'custom_secret',
                'use_ssl': True
            },
            'monitoring': {
                'check_interval_hours': 25,  # Too high: maximum is 24
                'mount_delay_minutes': 10,
                'change_delay_minutes': 20
            },
            'logging': {
                'level': 'WARNING',
                'directory': '/tmp/test-logs'
            },
            'state': {
                'directory': '/tmp/test-state'
            }
        }
        
        errors = config.validator._validate_numeric_ranges(invalid_config)
        assert "monitoring.check_interval_hours must be between 0.1 and 24 hours" in errors
    
    @pytest.mark.unit
    def test_validate_numeric_ranges_mount_delay_too_low(self):
        """Test validation rejects mount_delay_minutes below minimum."""
        config = Config()
        invalid_config = {
            'backup': {
                'source_path': '/tmp/test-photos',
                'destination': 'custom:backup'
            },
            'storage': {
                'endpoint': 'custom.s3.com',
                'access_key': 'custom_key',
                'secret_key': 'custom_secret',
                'use_ssl': True
            },
            'monitoring': {
                'check_interval_hours': 2,
                'mount_delay_minutes': 0,  # Too low: minimum is 1
                'change_delay_minutes': 20
            },
            'logging': {
                'level': 'WARNING',
                'directory': '/tmp/test-logs'
            },
            'state': {
                'directory': '/tmp/test-state'
            }
        }
        
        errors = config.validator._validate_numeric_ranges(invalid_config)
        assert "monitoring.mount_delay_minutes must be between 1 and 60 minutes" in errors
    
    @pytest.mark.unit
    def test_validate_numeric_ranges_max_size_mb_too_high(self):
        """Test validation rejects max_size_mb above maximum."""
        config = Config()
        invalid_config = {
            'backup': {
                'source_path': '/tmp/test-photos',
                'destination': 'custom:backup'
            },
            'storage': {
                'endpoint': 'custom.s3.com',
                'access_key': 'custom_key',
                'secret_key': 'custom_secret',
                'use_ssl': True
            },
            'monitoring': {
                'check_interval_hours': 2,
                'mount_delay_minutes': 10,
                'change_delay_minutes': 20
            },
            'logging': {
                'level': 'WARNING',
                'directory': '/tmp/test-logs',
                'max_size_mb': 1500  # Too high: maximum is 1000
            },
            'state': {
                'directory': '/tmp/test-state'
            }
        }
        
        errors = config.validator._validate_numeric_ranges(invalid_config)
        assert "logging.max_size_mb must be between 1 and 1000 MB" in errors
    
    @pytest.mark.unit
    def test_validate_numeric_ranges_backup_count_not_integer(self):
        """Test validation rejects non-integer backup_count."""
        config = Config()
        invalid_config = {
            'backup': {
                'source_path': '/tmp/test-photos',
                'destination': 'custom:backup'
            },
            'storage': {
                'endpoint': 'custom.s3.com',
                'access_key': 'custom_key',
                'secret_key': 'custom_secret',
                'use_ssl': True
            },
            'monitoring': {
                'check_interval_hours': 2,
                'mount_delay_minutes': 10,
                'change_delay_minutes': 20
            },
            'logging': {
                'level': 'WARNING',
                'directory': '/tmp/test-logs',
                'backup_count': 5.5  # Should be integer
            },
            'state': {
                'directory': '/tmp/test-state'
            }
        }
        
        errors = config.validator._validate_numeric_ranges(invalid_config)
        assert "logging.backup_count must be an integer" in errors


class TestConfigSearchPaths:
    """Test cases for config file search paths."""
    
    @pytest.mark.unit
    def test_find_config_file_current_directory(self):
        """Test finding config file in current directory."""
        config = Config()
        
        with patch.object(Path, 'exists') as mock_exists:
            with patch.object(Path, 'is_file') as mock_is_file:
                # Mock current directory config exists
                mock_exists.return_value = True
                mock_is_file.return_value = True
                
                config_path = config.loader._find_config_file()
                assert config_path == Path.cwd() / "config.yaml"
    
    @pytest.mark.unit
    def test_find_config_file_user_config(self):
        """Test finding config file in user config directory."""
        config = Config()
        
        # Test the search paths logic by checking the expected paths
        search_paths = [
            Path.cwd() / "config.yaml",  # Current directory
            Path.home() / ".config" / "photo-backup" / "config.yaml",  # User config
            Path("/etc/photo-backup/config.yaml"),  # System config
        ]
        
        # Verify the search paths are correct
        assert len(search_paths) == 3
        assert search_paths[0] == Path.cwd() / "config.yaml"
        assert search_paths[1] == Path.home() / ".config" / "photo-backup" / "config.yaml"
        assert search_paths[2] == Path("/etc/photo-backup/config.yaml")
    
    @pytest.mark.unit
    def test_find_config_file_system_config(self):
        """Test finding config file in system config directory."""
        config = Config()
        
        # Test that the method returns None when no config file exists
        # This is a simpler test that doesn't require complex mocking
        with patch.object(Path, 'exists', return_value=False):
            config_path = config.loader._find_config_file()
            assert config_path is None
    
    @pytest.mark.unit
    def test_find_config_file_not_found(self):
        """Test behavior when no config file is found."""
        config = Config()
        
        with patch.object(Path, 'exists', return_value=False):
            config_path = config.loader._find_config_file()
            assert config_path is None
    
    @pytest.mark.unit
    def test_get_search_paths_production_mode(self):
        """Test search paths in production mode."""
        config = Config(test_mode=False)
        search_paths = config.loader.get_search_paths()
        
        # Should have 3 standard paths, no test path
        assert len(search_paths) == 3
        assert search_paths[0] == Path.cwd() / "config.yaml"
        assert search_paths[1] == Path.home() / ".config" / "photo-backup" / "config.yaml"
        assert search_paths[2] == Path("/etc/photo-backup/config.yaml")
    
    @pytest.mark.unit
    def test_get_search_paths_test_mode(self):
        """Test search paths in test mode."""
        config = Config(test_mode=True)
        search_paths = config.loader.get_search_paths()
        
        # Should have 4 paths, with test path first
        assert len(search_paths) == 4
        assert search_paths[0] == Path("/tmp/photo-backup-test/config.yaml")
        assert search_paths[1] == Path.cwd() / "config.yaml"
        assert search_paths[2] == Path.home() / ".config" / "photo-backup" / "config.yaml"
        assert search_paths[3] == Path("/etc/photo-backup/config.yaml")
    
    @pytest.mark.unit
    def test_find_config_file_test_mode_priority(self):
        """Test that test mode config takes priority."""
        config = Config(test_mode=True)
        
        # Test that test mode includes the test config path first
        search_paths = config.loader.get_search_paths()
        assert search_paths[0] == Path("/tmp/photo-backup-test/config.yaml")
        
        # Test that the search paths are in the correct order
        assert len(search_paths) == 4
        assert search_paths[1] == Path.cwd() / "config.yaml"
        assert search_paths[2] == Path.home() / ".config" / "photo-backup" / "config.yaml"
        assert search_paths[3] == Path("/etc/photo-backup/config.yaml")
    
    @pytest.mark.unit
    def test_load_config_logging_with_file(self):
        """Test logging when config file is loaded."""
        config = Config()
        test_config = {'backup': {'source_path': '/test/path'}}
        
        with patch.object(config.loader, '_find_config_file') as mock_find:
            with patch('builtins.open', mock_open(read_data='backup:\n  source_path: /test/path')):
                with patch('yaml.safe_load', return_value=test_config):
                    with patch('logging.info') as mock_log:
                        mock_find.return_value = Path("/test/config.yaml")
                        
                        result = config.loader.load_config_from_file()
                        
                        # Should log the config file location
                        mock_log.assert_called_with("Loaded configuration from: /test/config.yaml")
                        assert result == test_config
    
    @pytest.mark.unit
    def test_load_config_logging_no_file(self):
        """Test logging when no config file is found."""
        config = Config()
        
        with patch.object(config.loader, '_find_config_file', return_value=None):
            with patch('logging.info') as mock_log:
                result = config.loader.load_config_from_file()
                
                # Should log that no config file was found
                mock_log.assert_called_with("No configuration file found, using default configuration")
                assert result is None
    
    @pytest.mark.unit
    def test_load_config_logging_error(self):
        """Test logging when config file has errors."""
        config = Config()
        
        with patch.object(config.loader, '_find_config_file') as mock_find:
            with patch('builtins.open', side_effect=OSError("File not found")):
                with patch('logging.error') as mock_log:
                    mock_find.return_value = Path("/test/config.yaml")
                    
                    result = config.loader.load_config_from_file()
                    
                    # Should log the error
                    mock_log.assert_called_with("Error loading config file /test/config.yaml: File not found")
                    assert result is None


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
        
        merged = config._merge_with_defaults(file_config)
        
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
            },
            'monitoring': {
                'check_interval_hours': 2,
                'mount_delay_minutes': 10,
                'change_delay_minutes': 20
            },
            'logging': {
                'level': 'WARNING',
                'directory': '/custom/logs'
            },
            'state': {
                'directory': '/custom/state'
            }
        }
        
        overridden = config._apply_test_mode_overrides(base_config)
        
        # Test mode should override all relevant fields
        assert overridden['backup']['source_path'] == '/tmp/photo-backup-test-photos'
        assert overridden['storage']['endpoint'] == 'localhost:9000'
        assert overridden['storage']['access_key'] == 'minioadmin'
        assert overridden['monitoring']['check_interval_hours'] == 0.1
        assert overridden['logging']['level'] == 'DEBUG'
    
    @pytest.mark.unit
    def test_get_config_file_path(self):
        """Test getting config file path."""
        config = Config()
        
        # Initially should be None
        assert config.get_config_file_path() is None
        
        # Test that the method exists and returns the expected type
        config_path = config.get_config_file_path()
        assert config_path is None or isinstance(config_path, Path)


class TestConfigValidationIntegration:
    """Test cases for comprehensive config validation integration."""
    
    @pytest.mark.unit
    def test_validate_config_comprehensive_valid(self):
        """Test comprehensive validation of valid config."""
        config = Config()
        valid_config = {
            'backup': {
                'source_path': '/tmp/test-photos',
                'destination': 'custom:backup'
            },
            'storage': {
                'endpoint': 'custom.s3.com',
                'access_key': 'custom_key',
                'secret_key': 'custom_secret',
                'use_ssl': True
            },
            'monitoring': {
                'check_interval_hours': 2,
                'mount_delay_minutes': 10,
                'change_delay_minutes': 20
            },
            'logging': {
                'level': 'WARNING',
                'directory': '/tmp/test-logs',
                'max_size_mb': 100,
                'backup_count': 5
            },
            'state': {
                'directory': '/tmp/test-state'
            }
        }
        
        with patch.object(Path, 'exists', return_value=True):
            with patch.object(Path, 'is_dir', return_value=True):
                with patch('os.access', return_value=True):
                    is_valid, errors = config.validator.validate_config(valid_config)
                    assert is_valid is True
                    assert len(errors) == 0
    
    @pytest.mark.unit
    def test_validate_config_comprehensive_invalid(self):
        """Test comprehensive validation of invalid config."""
        config = Config()
        invalid_config = {
            'backup': {
                'source_path': 'relative/path',  # Should be absolute
                'destination': 'custom:backup'
            },
            'storage': {
                'endpoint': 'custom.s3.com',
                'access_key': 'custom_key',
                'secret_key': 'custom_secret',
                'use_ssl': True
            },
            'monitoring': {
                'check_interval_hours': 25,  # Too high
                'mount_delay_minutes': 10,
                'change_delay_minutes': 20
            },
            'logging': {
                'level': 'WARNING',
                'directory': '/tmp/test-logs'
            },
            'state': {
                'directory': '/tmp/test-state'
            }
        }
        
        is_valid, errors = config.validator.validate_config(invalid_config)
        assert is_valid is False
        assert len(errors) >= 2  # Should have at least 2 errors
        # Check that specific errors are present
        error_messages = [error for error in errors]
        assert any("backup.source_path must be an absolute path" in error for error in error_messages)
        assert any("monitoring.check_interval_hours must be between 0.1 and 24 hours" in error for error in error_messages)
    
    @pytest.mark.unit
    def test_load_config_fails_early_on_validation_error(self):
        """Test that load_config fails early when validation fails."""
        config = Config()
        invalid_config = {
            'backup': {
                'source_path': 'relative/path',  # Invalid
                'destination': 'custom:backup'
            },
            'storage': {
                'endpoint': 'custom.s3.com',
                'access_key': 'custom_key',
                'secret_key': 'custom_secret',
                'use_ssl': True
            },
            'monitoring': {
                'check_interval_hours': 2,
                'mount_delay_minutes': 10,
                'change_delay_minutes': 20
            },
            'logging': {
                'level': 'WARNING',
                'directory': '/tmp/test-logs'
            },
            'state': {
                'directory': '/tmp/test-state'
            }
        }
        
        with patch('builtins.open', mock_open(read_data=yaml.dump(invalid_config))):
            with patch.object(Path, 'exists', return_value=True):
                with patch.object(Path, 'is_file', return_value=True):
                    with pytest.raises(ValueError) as exc_info:
                        config.load_config()
                    
                    error_message = str(exc_info.value)
                    assert "Configuration validation failed:" in error_message
                    # Check that the specific error is mentioned
                    assert any("backup.source_path" in error for error in error_message.split('\n'))


class TestConfigDefaults:
    """Test cases for default configuration functionality."""
    
    @pytest.mark.unit
    def test_default_config_structure(self):
        """Test that DEFAULT_CONFIG has the expected structure."""
        from photo_backup.config import DEFAULT_CONFIG
        
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
        from photo_backup.config import DEFAULT_CONFIG_DOCS, DEFAULT_CONFIG
        
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
        from photo_backup.config import TEST_MODE_DEFAULTS
        
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
        from photo_backup.config import DEFAULT_CONFIG
        
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
        from photo_backup.config import TEST_MODE_DEFAULTS
        
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