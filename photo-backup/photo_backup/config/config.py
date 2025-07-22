"""
Configuration management for photo backup system.

This module handles loading and managing configuration settings,
with support for test mode using Minio instead of Wasabi.
"""

from pathlib import Path
from typing import Dict, Any, Optional

from .defaults import DEFAULT_CONFIG, DEFAULT_CONFIG_DOCS, TEST_MODE_DEFAULTS
from .validator import ConfigValidator
from .loader import ConfigLoader
from .utils import ConfigUtils

class Config:
    """Configuration manager for photo backup system."""
    
    def __init__(self, test_mode=False):
        """Initialize configuration.
        
        Args:
            test_mode: If True, use test configuration with Minio
        """
        self.test_mode = test_mode
        self._config = None
        self.loader = ConfigLoader(test_mode=test_mode)
        self.validator = ConfigValidator(test_mode=test_mode)
        self.utils = ConfigUtils()

    def load_config(self):
        """Load configuration settings.
        
        Returns:
            dict: Configuration dictionary
        """
        if self._config is None:
            # Try to load from file first
            file_config = self.loader.load_config_from_file()
            
            if file_config is not None:
                # Validate loaded config
                is_valid, errors = self.validator.validate_config(file_config)
                if is_valid:
                    self._config = self.utils.merge_with_defaults(file_config, DEFAULT_CONFIG)
                else:
                    # Fail early with detailed error messages
                    error_msg = "Configuration validation failed:\n" + "\n".join(f"  - {error}" for error in errors)
                    raise ValueError(error_msg)
            else:
                # No config file found, use defaults
                self._config = self._get_default_config()
            
            # Apply test mode overrides if needed
            if self.test_mode:
                self._config = self.utils.apply_test_mode_overrides(self._config, TEST_MODE_DEFAULTS)
        
        return self._config
    
    def _get_default_config(self) -> Dict[str, Any]:
        """Get default configuration that can be overridden.
        
        Returns:
            Default configuration dictionary with comprehensive settings
        """
        return DEFAULT_CONFIG.copy()
    
    def get_config_file_path(self) -> Optional[Path]:
        """Get the path of the loaded config file.
        
        Returns:
            Path to config file if loaded, None otherwise
        """
        if self._config is None:
            self.load_config()
        return self.loader._config_file_path
    
    def is_test_mode(self):
        """Check if running in test mode.
        
        Returns:
            bool: True if in test mode
        """
        return self.test_mode
    
    #
    def get(self, key, default=None):
        """Get configuration value by key.
        
        Args:
            key: Configuration key (supports dot notation like 'backup.source_path')
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        return self.utils.get_nested_value(self.load_config(), key, default)
    
    def get_default_value(self, key: str) -> Any:
        """Get the default value for a specific configuration key.
        
        Args:
            key: Configuration key (supports dot notation)
            
        Returns:
            Default value for the key, or None if not found
        """
        return self.utils.get_nested_value(DEFAULT_CONFIG, key, None)
    
    def get_default_documentation(self, key: str) -> Optional[str]:
        """Get documentation for a specific configuration key.
        
        Args:
            key: Configuration key (supports dot notation)
            
        Returns:
            Documentation string for the key, or None if not found
        """
        return self.utils.get_nested_value(DEFAULT_CONFIG_DOCS, key, None)
       
    def get_config_documentation(self) -> Dict[str, Any]:
        """Get documentation for all configuration options.
        
        Returns:
            Dictionary mapping config keys to their descriptions
        """
        return DEFAULT_CONFIG_DOCS.copy()