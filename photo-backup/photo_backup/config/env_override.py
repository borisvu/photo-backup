"""
Environment variable override functionality for configuration.

This module handles overriding configuration values with environment variables
using the PHOTO_BACKUP_* prefix convention.
"""

import os
from typing import Any, ClassVar


class EnvOverride:
    """Environment variable override handler."""

    # Prefix for all photo backup environment variables
    ENV_PREFIX = "PHOTO_BACKUP_"

    # Special environment variable for test mode
    TEST_MODE_ENV = "PHOTO_BACKUP_TEST_MODE"

    # Type conversion mappings for environment variables
    TYPE_CONVERTERS: ClassVar[dict[str, Any]] = {
        "int": int,
        "float": float,
        "bool": lambda x: x.lower() in ("true", "1", "yes", "on"),
        "str": str,
    }

    @classmethod
    def is_test_mode_enabled(cls) -> bool:
        """Check if test mode is enabled via environment variable.

        Returns:
            True if PHOTO_BACKUP_TEST_MODE=1 or similar truthy value
        """
        test_mode = os.environ.get(cls.TEST_MODE_ENV, "").lower()
        return test_mode in ("1", "true", "yes", "on")

    @classmethod
    def get_env_overrides(cls) -> dict[str, Any]:
        """Get all environment variable overrides.

        Returns:
            Dictionary of config overrides from environment variables
        """
        overrides: dict[str, Any] = {}

        for key, value in os.environ.items():
            if key.startswith(cls.ENV_PREFIX):
                # Convert environment variable to config key
                config_key = cls._env_key_to_config_key(key)
                if config_key:
                    # Convert value to appropriate type
                    converted_value = cls._convert_env_value(config_key, value)
                    if converted_value is not None:
                        cls._set_nested_value(overrides, config_key, converted_value)

        return overrides

    @classmethod
    def _env_key_to_config_key(cls, env_key: str) -> str | None:
        """Convert environment variable key to config key.

        Args:
            env_key: Environment variable key (e.g., PHOTO_BACKUP_BACKUP_SOURCE_PATH)

        Returns:
            Config key (e.g., backup.source_path) or None if invalid
        """
        if not env_key.startswith(cls.ENV_PREFIX):
            return None

        # Remove prefix and convert to lowercase
        key_part = env_key[len(cls.ENV_PREFIX) :]

        # Skip the test mode variable as it's handled separately
        if key_part == "TEST_MODE":
            return None

        # Convert SNAKE_CASE to dot notation
        # e.g., BACKUP_SOURCE_PATH -> backup.source_path
        parts = key_part.lower().split("_")

        if len(parts) < 2:
            return None

        # First part becomes the section, rest becomes the key
        section = parts[0]
        key = "_".join(parts[1:])

        return f"{section}.{key}"

    @classmethod
    def _convert_env_value(cls, config_key: str, env_value: str) -> Any:
        """Convert environment variable value to appropriate type.

        Args:
            config_key: Configuration key (e.g., 'backup.source_path')
            env_value: Environment variable value as string

        Returns:
            Converted value with appropriate type
        """
        # Determine expected type based on config key
        expected_type = cls._get_expected_type(config_key)

        try:
            if expected_type is bool:
                return env_value.lower() in ("true", "1", "yes", "on")
            elif expected_type is int:
                return int(env_value)
            elif expected_type is float:
                return float(env_value)
            else:
                return env_value
        except (ValueError, TypeError):
            # If conversion fails, return as string
            return env_value

    @classmethod
    def _get_expected_type(cls, config_key: str) -> type:
        """Get expected type for a configuration key.

        Args:
            config_key: Configuration key (e.g., 'backup.source_path')

        Returns:
            Expected Python type for this key
        """
        # Define type mappings for different config sections and keys
        type_mappings = {
            # Backup section
            "backup.source_path": str,
            "backup.destination": str,
            "backup.strategy": str,
            "backup.compression": bool,
            "backup.verify_after_backup": bool,
            # Storage section
            "storage.endpoint": str,
            "storage.access_key": str,
            "storage.secret_key": str,
            "storage.use_ssl": bool,
            "storage.region": str,
            # Monitoring section
            "monitoring.check_interval_hours": float,
            "monitoring.mount_delay_minutes": int,
            "monitoring.change_delay_minutes": int,
            # Logging section
            "logging.level": str,
            "logging.directory": str,
            "logging.max_size_mb": int,
            "logging.backup_count": int,
            # State section
            "state.directory": str,
            # Security section
            "security.encrypt_backups": bool,
            "security.verify_checksums": bool,
            "security.checksum_algorithm": str,
            # Performance section
            "performance.buffer_size_mb": int,
            "performance.max_memory_usage_mb": int,
            "performance.parallel_uploads": int,
            "performance.chunk_size_mb": int,
            "performance.enable_caching": bool,
            # Notifications section
            "notifications.enabled": bool,
            "notifications.email.enabled": bool,
            "notifications.email.smtp_server": str,
            "notifications.email.smtp_port": int,
            "notifications.webhook.enabled": bool,
            "notifications.webhook.url": str,
        }

        return type_mappings.get(config_key, str)

    @classmethod
    def _set_nested_value(cls, data: dict[str, Any], key: str, value: Any) -> None:
        """Set a nested value in a dictionary using dot notation.

        Args:
            data: Dictionary to modify
            key: Dot-notation key (e.g., 'backup.source_path')
            value: Value to set
        """
        keys = key.split(".")
        current = data

        # Navigate to the parent of the target key
        for k in keys[:-1]:
            if k not in current:
                current[k] = {}
            current = current[k]

        # Set the final value
        current[keys[-1]] = value

    @classmethod
    def apply_env_overrides(cls, config: dict[str, Any]) -> dict[str, Any]:
        """Apply environment variable overrides to configuration.

        Args:
            config: Base configuration dictionary

        Returns:
            Configuration with environment variable overrides applied
        """
        env_overrides = cls.get_env_overrides()

        if not env_overrides:
            return config

        # Merge environment overrides with config
        from .utils import ConfigUtils

        return ConfigUtils.merge_dicts(config, env_overrides)

    @classmethod
    def get_env_override_info(cls) -> dict[str, Any]:
        """Get information about current environment variable overrides.

        Returns:
            Dictionary with override information
        """
        overrides = cls.get_env_overrides()
        test_mode = cls.is_test_mode_enabled()

        # Reconstruct the actual environment variable names that were used
        env_vars_used = []
        for key, _value in os.environ.items():
            if key.startswith(cls.ENV_PREFIX) and key != cls.TEST_MODE_ENV:
                config_key = cls._env_key_to_config_key(key)
                if config_key:
                    env_vars_used.append(key)

        return {
            "test_mode_enabled": test_mode,
            "overrides": overrides,
            "override_count": len(overrides),
            "env_vars_used": env_vars_used,
        }
