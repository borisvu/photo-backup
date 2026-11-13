from typing import Any


class ConfigUtils:
    """Utility functions for configuration operations."""

    @staticmethod
    def merge_dicts(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        """Recursively merge dictionaries."""
        import copy

        result = copy.deepcopy(base)
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = ConfigUtils.merge_dicts(result[key], value)
            else:
                result[key] = copy.deepcopy(value)
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
        """Apply test mode defaults as fallbacks to configuration.

        After Phase 2 refactoring, TEST_MODE_DEFAULTS serve as FALLBACKS, not overrides.
        User config takes precedence over test defaults.

        Args:
            config: User configuration (takes precedence)
            test_defaults: Test mode default values (fallbacks only)

        Returns:
            Configuration with test defaults applied as fallbacks
        """
        return ConfigUtils.merge_dicts(test_defaults, config)
