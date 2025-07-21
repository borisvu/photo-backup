"""
Configuration management for photo backup system.

This module handles loading and managing configuration settings,
with support for test mode using Minio instead of Wasabi.
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List


class Config:
    """Configuration manager for photo backup system."""
    
    def __init__(self, test_mode=False):
        """Initialize configuration.
        
        Args:
            test_mode: If True, use test configuration with Minio
        """
        self.test_mode = test_mode
        self._config = None
        self._config_file_path = None
    
    def load_config(self):
        """Load configuration settings.
        
        Returns:
            dict: Configuration dictionary
        """
        if self._config is None:
            # Try to load from file first
            file_config = self._load_config_from_file()
            
            if file_config is not None:
                # Validate loaded config
                is_valid, errors = self._validate_config_schema(file_config)
                if is_valid:
                    self._config = self._merge_with_defaults(file_config)
                else:
                    # Log validation errors but continue with defaults
                    print(f"Warning: Config file validation failed: {errors}")
                    self._config = self._get_default_config()
            else:
                # No config file found, use defaults
                self._config = self._get_default_config()
            
            # Apply test mode overrides if needed
            if self.test_mode:
                self._config = self._apply_test_mode_overrides(self._config)
        
        return self._config
    
    def _find_config_file(self) -> Optional[Path]:
        """Find config file in standard locations.
        
        Returns:
            Path to config file if found, None otherwise
        """
        search_paths = [
            Path.cwd() / "config.yaml",  # Current directory
            Path.home() / ".config" / "photo-backup" / "config.yaml",  # User config
            Path("/etc/photo-backup/config.yaml"),  # System config
        ]
        
        for config_path in search_paths:
            if config_path.exists() and config_path.is_file():
                return config_path
        
        return None
    
    def _load_config_from_file(self) -> Optional[Dict[str, Any]]:
        """Load configuration from YAML file.
        
        Returns:
            Loaded configuration dict or None if file not found/invalid
        """
        config_path = self._find_config_file()
        if config_path is None:
            return None
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                self._config_file_path = config_path
                return config
        except (yaml.YAMLError, OSError) as e:
            print(f"Error loading config file {config_path}: {e}")
            return None
    
    def _validate_config_schema(self, config: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Basic schema validation for loaded config.
        
        Args:
            config: Configuration dictionary to validate
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        # Check required top-level sections
        required_sections = ['backup', 'storage', 'monitoring', 'logging', 'state']
        for section in required_sections:
            if section not in config:
                errors.append(f"Missing required section: {section}")
            elif not isinstance(config[section], dict):
                errors.append(f"Section {section} must be a dictionary")
        
        # Validate backup section
        if 'backup' in config and isinstance(config['backup'], dict):
            backup = config['backup']
            if 'source_path' not in backup:
                errors.append("backup.source_path is required")
            elif not isinstance(backup['source_path'], str):
                errors.append("backup.source_path must be a string")
            
            if 'destination' not in backup:
                errors.append("backup.destination is required")
            elif not isinstance(backup['destination'], str):
                errors.append("backup.destination must be a string")
        
        # Validate storage section
        if 'storage' in config and isinstance(config['storage'], dict):
            storage = config['storage']
            if 'endpoint' not in storage:
                errors.append("storage.endpoint is required")
            elif not isinstance(storage['endpoint'], str):
                errors.append("storage.endpoint must be a string")
            
            if 'access_key' in storage and not isinstance(storage['access_key'], (str, type(None))):
                errors.append("storage.access_key must be a string or null")
            
            if 'secret_key' in storage and not isinstance(storage['secret_key'], (str, type(None))):
                errors.append("storage.secret_key must be a string or null")
            
            if 'use_ssl' in storage and not isinstance(storage['use_ssl'], bool):
                errors.append("storage.use_ssl must be a boolean")
        
        # Validate monitoring section
        if 'monitoring' in config and isinstance(config['monitoring'], dict):
            monitoring = config['monitoring']
            for key in ['check_interval_hours', 'mount_delay_minutes', 'change_delay_minutes']:
                if key in monitoring and not isinstance(monitoring[key], (int, float)):
                    errors.append(f"monitoring.{key} must be a number")
        
        # Validate logging section
        if 'logging' in config and isinstance(config['logging'], dict):
            logging_config = config['logging']
            if 'level' in logging_config and not isinstance(logging_config['level'], str):
                errors.append("logging.level must be a string")
            
            if 'directory' in logging_config and not isinstance(logging_config['directory'], str):
                errors.append("logging.directory must be a string")
        
        # Validate state section
        if 'state' in config and isinstance(config['state'], dict):
            state = config['state']
            if 'directory' in state and not isinstance(state['directory'], str):
                errors.append("state.directory must be a string")
        
        return len(errors) == 0, errors
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration that can be overridden.
        
        Returns:
            Default configuration dictionary
        """
        return {
            "backup": {
                "source_path": "/Volumes/4TB-SSD/Photo",
                "destination": "wasabi-photo:my-photo-backup-bucket"
            },
            "storage": {
                "endpoint": "s3.wasabisys.com",
                "access_key": None,  # Retrieved from 1Password
                "secret_key": None,  # Retrieved from 1Password
                "use_ssl": True
            },
            "monitoring": {
                "check_interval_hours": 4,
                "mount_delay_minutes": 15,
                "change_delay_minutes": 30
            },
            "logging": {
                "level": "INFO",
                "directory": "~/Library/Logs/photo-backup"
            },
            "state": {
                "directory": "~/Library/Application Support/photo-backup"
            }
        }
    
    def _merge_with_defaults(self, file_config: Dict[str, Any]) -> Dict[str, Any]:
        """Merge file config with defaults.
        
        Args:
            file_config: Configuration loaded from file
            
        Returns:
            Merged configuration dictionary
        """
        default_config = self._get_default_config()
        
        def merge_dicts(default: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
            """Recursively merge dictionaries."""
            result = default.copy()
            for key, value in override.items():
                if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                    result[key] = merge_dicts(result[key], value)
                else:
                    result[key] = value
            return result
        
        return merge_dicts(default_config, file_config)
    
    def _apply_test_mode_overrides(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Apply test mode overrides to configuration.
        
        Args:
            config: Base configuration
            
        Returns:
            Configuration with test mode overrides applied
        """
        test_overrides = {
            "backup": {
                "source_path": "/tmp/photo-backup-test-photos",
                "destination": "minio-test:my-photo-backup-bucket-test"
            },
            "storage": {
                "endpoint": "localhost:9000",
                "access_key": "minioadmin",
                "secret_key": "minioadmin",
                "use_ssl": False
            },
            "monitoring": {
                "check_interval_hours": 0.1,  # 6 minutes for testing
                "mount_delay_minutes": 1,
                "change_delay_minutes": 1
            },
            "logging": {
                "level": "DEBUG",
                "directory": "/tmp/photo-backup-test/logs"
            },
            "state": {
                "directory": "/tmp/photo-backup-test/state"
            }
        }
        
        def merge_dicts(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
            """Recursively merge dictionaries."""
            result = base.copy()
            for key, value in override.items():
                if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                    result[key] = merge_dicts(result[key], value)
                else:
                    result[key] = value
            return result
        
        return merge_dicts(config, test_overrides)
    
    def get_config_file_path(self) -> Optional[Path]:
        """Get the path of the loaded config file.
        
        Returns:
            Path to config file if loaded, None otherwise
        """
        if self._config is None:
            self.load_config()
        return self._config_file_path
    
    def get(self, key, default=None):
        """Get configuration value by key.
        
        Args:
            key: Configuration key (supports dot notation like 'backup.source_path')
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        config = self.load_config()
        
        # Support dot notation for nested keys
        keys = key.split('.')
        value = config
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    def is_test_mode(self):
        """Check if running in test mode.
        
        Returns:
            bool: True if in test mode
        """
        return self.test_mode