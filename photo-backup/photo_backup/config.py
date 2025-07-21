"""
Configuration management for photo backup system.

This module handles loading and managing configuration settings,
with support for test mode using Minio instead of Wasabi.
"""

import os
import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List

from .config_defaults import DEFAULT_CONFIG, DEFAULT_CONFIG_DOCS, TEST_MODE_DEFAULTS
from .config_validator import ConfigValidator

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
        self.validator = ConfigValidator(test_mode=test_mode)

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
                is_valid, errors = self.validator.validate_config(file_config)
                if is_valid:
                    self._config = self._merge_with_defaults(file_config)
                else:
                    # Fail early with detailed error messages
                    error_msg = "Configuration validation failed:\n" + "\n".join(f"  - {error}" for error in errors)
                    raise ValueError(error_msg)
            else:
                # No config file found, use defaults
                self._config = self._get_default_config()
            
            # Apply test mode overrides if needed
            if self.test_mode:
                self._config = self._apply_test_mode_overrides(self._config)
        
        return self._config
    
    def get_search_paths(self) -> List[Path]:
        """Get the list of search paths for configuration files.
        
        Returns:
            List of paths to search for configuration files in order
        """
        search_paths = []
        
        # Add test mode specific config location first if in test mode
        if self.test_mode:
            test_config_path = Path("/tmp/photo-backup-test/config.yaml")
            search_paths.append(test_config_path)
        
        # Standard search paths
        search_paths.extend([
            Path.cwd() / "config.yaml",  # Current directory
            Path.home() / ".config" / "photo-backup" / "config.yaml",  # User config
            Path("/etc/photo-backup/config.yaml"),  # System config
        ])
        
        return search_paths
    
    def _find_config_file(self) -> Optional[Path]:
        """Find config file in standard locations.
        
        Returns:
            Path to config file if found, None otherwise
        """
        search_paths = self.get_search_paths()
        
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
            logging.info("No configuration file found, using default configuration")
            return None
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                self._config_file_path = config_path
                logging.info(f"Loaded configuration from: {config_path}")
                return config
        except (yaml.YAMLError, OSError) as e:
            logging.error(f"Error loading config file {config_path}: {e}")
            return None

    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration that can be overridden.
        
        Returns:
            Default configuration dictionary with comprehensive settings
        """
        return DEFAULT_CONFIG.copy()
    
    def get_config_documentation(self) -> Dict[str, Any]:
        """Get documentation for all configuration options.
        
        Returns:
            Dictionary mapping config keys to their descriptions
        """
        return DEFAULT_CONFIG_DOCS.copy()
    
    def get_default_value(self, key: str) -> Any:
        """Get the default value for a specific configuration key.
        
        Args:
            key: Configuration key (supports dot notation)
            
        Returns:
            Default value for the key, or None if not found
        """
        keys = key.split('.')
        value = DEFAULT_CONFIG
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return None
    
    def get_default_documentation(self, key: str) -> Optional[str]:
        """Get documentation for a specific configuration key.
        
        Args:
            key: Configuration key (supports dot notation)
            
        Returns:
            Documentation string for the key, or None if not found
        """
        keys = key.split('.')
        value = DEFAULT_CONFIG_DOCS
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return None
    
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
        test_overrides = TEST_MODE_DEFAULTS.copy()
        
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