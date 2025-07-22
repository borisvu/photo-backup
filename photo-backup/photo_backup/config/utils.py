from typing import Dict, Any, Optional

class ConfigUtils:
    """Utility functions for configuration operations."""
    
    def merge_dicts(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively merge dictionaries."""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = ConfigUtils.merge_dicts(result[key], value)
            else:
                result[key] = value
        return result
    
    @staticmethod
    def get_nested_value(data: Dict[str, Any], key: str, default: Any = None) -> Any:
        """Get nested value using dot notation."""
        keys = key.split('.')
        value = data

        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
    
    @staticmethod
    def merge_with_defaults(file_config: Dict[str, Any], defaults: Dict[str, Any]) -> Dict[str, Any]:
        """Merge file config with defaults.
        
        Args:
            file_config: Configuration loaded from file
            
        Returns:
            Merged configuration dictionary
        """
        
        return ConfigUtils.merge_dicts(defaults, file_config)
    
    @staticmethod
    def apply_test_mode_overrides(config: Dict[str, Any], test_defaults: Dict[str, Any]) -> Dict[str, Any]:
        """Apply test mode overrides to configuration.
        
        Args:
            config: Base configuration
            
        Returns:
            Configuration with test mode overrides applied
        """
        return ConfigUtils.merge_dicts(config, test_defaults)
    