"""
Configuration management for photo backup system.

This module handles loading and managing configuration settings,
with support for test mode using Minio instead of Wasabi.
"""

from typing import Any

from pathlib import Path

from .defaults import DEFAULT_CONFIG, DEFAULT_CONFIG_DOCS, TEST_MODE_DEFAULTS
from .env_override import EnvOverride
from .loader import ConfigLoader
from .utils import ConfigUtils
from .validator import ConfigValidator


class Config:
    """Configuration manager for photo backup system."""

    def __init__(self, test_mode=None, dry_run=None):
        """Initialize configuration.

        Args:
            test_mode: If True, use test configuration with Minio.
                      If None, check environment variable PHOTO_BACKUP_TEST_MODE
            dry_run: If True, enable dry-run mode. If None, use config value
        """
        # Check environment variable for test mode if not explicitly set
        if test_mode is None:
            test_mode = EnvOverride.is_test_mode_enabled()

        self.test_mode = test_mode
        self.dry_run = dry_run
        self._config = None
        self.loader = ConfigLoader(test_mode=test_mode)
        self.validator = ConfigValidator(test_mode=test_mode)
        self.utils = ConfigUtils()

    def load_config(self) -> dict[str, Any]:
        """Load configuration settings.

        Returns:
            dict: Configuration dictionary
        """
        if self._config is None:
            # Step 1: Start with DEFAULT_CONFIG as base
            base_config = self._get_default_config()

            # Step 2: If test mode, apply TEST_MODE_DEFAULTS on top of defaults
            # These override default values but will be overridden by user config
            if self.test_mode:
                base_config = self.utils.merge_dicts(base_config, TEST_MODE_DEFAULTS)

            # Step 3: Try to load user config from file
            file_config = self.loader.load_config_from_file()

            if file_config is not None:
                # Validate loaded config
                is_valid, errors = self.validator.validate_config(file_config)
                if is_valid:
                    # Merge user config on top of base (user config wins)
                    self._config = self.utils.merge_with_defaults(file_config, base_config)
                else:
                    # Fail early with detailed error messages
                    error_msg = "Configuration validation failed:\n" + "\n".join(f"  - {error}" for error in errors)
                    raise ValueError(error_msg)
            else:
                # No config file found, use base config (defaults + test overrides if applicable)
                self._config = base_config

            # Apply environment variable overrides (highest priority)
            self._config = EnvOverride.apply_env_overrides(self._config)

            # Apply dry-run override if explicitly set (highest priority)
            if self.dry_run is not None:
                self._config["backup"]["dry_run"] = self.dry_run

        return self._config

    def _get_default_config(self) -> dict[str, Any]:
        """Get default configuration that can be overridden.

        Returns:
            Default configuration dictionary with comprehensive settings
        """
        import copy

        return copy.deepcopy(DEFAULT_CONFIG)

    def get_config_file_path(self) -> Path | None:
        """Get the path of the loaded config file.

        Returns:
            Path to config file if loaded, None otherwise
        """
        if self._config is None:
            self.load_config()
        return self.loader._config_file_path

    def is_test_mode(self) -> bool:
        """Check if running in test mode.

        Returns:
            bool: True if in test mode
        """
        return self.test_mode

    def is_dry_run(self) -> bool:
        """Check if running in dry-run mode.

        Returns:
            bool: True if in dry-run mode
        """
        if self._config is None:
            self.load_config()
        return self._config.get("backup", {}).get("dry_run", False)

    def _reset_config_cache(self) -> None:
        """Reset the configuration cache (mainly for testing)."""
        self._config = None

    #
    def get(self, key: str, default: Any = None) -> Any:
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

    def get_default_documentation(self, key: str) -> str | dict[str, str] | None:
        """Get documentation for a specific configuration key.

        Args:
            key: Configuration key (supports dot notation)

        Returns:
            Documentation string for the key, dictionary for sections, or None if not found
        """
        result: Any = self.utils.get_nested_value(DEFAULT_CONFIG_DOCS, key, None)
        if isinstance(result, str | dict):
            return result
        else:
            return None

    def get_config_documentation(self) -> dict[str, Any]:
        """Get documentation for all configuration options.

        Returns:
            Dictionary mapping config keys to their descriptions
        """
        return DEFAULT_CONFIG_DOCS.copy()

    def get_env_override_info(self) -> dict[str, Any]:
        """Get information about environment variable overrides.

        Returns:
            Dictionary with override information including test mode status
        """
        return EnvOverride.get_env_override_info()
