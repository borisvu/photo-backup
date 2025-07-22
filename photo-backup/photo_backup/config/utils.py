from typing import Any


class ConfigUtils:
    """Utility functions for configuration operations."""

    @staticmethod
    def merge_dicts(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        """Recursively merge dictionaries."""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = ConfigUtils.merge_dicts(result[key], value)
            else:
                result[key] = value
        return result

    @staticmethod
    def get_nested_value(data: dict[str, Any], key: str, default: Any = None) -> Any:
        """Get nested value using dot notation."""
        keys = key.split(".")
        value = data

        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default

    @staticmethod
    def merge_with_defaults(file_config: dict[str, Any], defaults: dict[str, Any]) -> dict[str, Any]:
        """Merge file config with defaults.

        Args:
            file_config: Configuration loaded from file

        Returns:
            Merged configuration dictionary
        """

        return ConfigUtils.merge_dicts(defaults, file_config)

    @staticmethod
    def apply_test_mode_overrides(config: dict[str, Any], test_defaults: dict[str, Any]) -> dict[str, Any]:
        """Apply test mode overrides to configuration.

        Args:
            config: Base configuration

        Returns:
            Configuration with test mode overrides applied
        """
        return ConfigUtils.merge_dicts(config, test_defaults)
