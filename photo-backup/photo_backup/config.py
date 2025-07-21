"""
Configuration management for photo backup system.

This module handles loading and managing configuration settings,
with support for test mode using Minio instead of Wasabi.
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List


# Module-level default configuration constants
DEFAULT_CONFIG = {
    "backup": {
        "source_path": "/Volumes/4TB-SSD/Photo",
        "destination": "wasabi-photo:my-photo-backup-bucket",
        "strategy": "incremental",
        "compression": True,
        "encryption": False,
        "verify_after_backup": True,
        "max_concurrent_backups": 1
    },
    "storage": {
        "endpoint": "s3.wasabisys.com",
        "access_key": None,  # Retrieved from 1Password
        "secret_key": None,  # Retrieved from 1Password
        "use_ssl": True,
        "region": "us-east-1",
        "bucket": "my-photo-backup-bucket",
        "timeout_seconds": 300,
        "retry_attempts": 3
    },
    "monitoring": {
        "check_interval_hours": 4,
        "mount_delay_minutes": 15,
        "change_delay_minutes": 30,
        "max_retries": 3,
        "retry_delay_minutes": 5,
        "health_check_enabled": True,
        "health_check_interval_minutes": 60
    },
    "logging": {
        "level": "INFO",
        "directory": "~/Library/Logs/photo-backup",
        "max_size_mb": 100,
        "backup_count": 5,
        "format": "detailed",
        "console_output": True,
        "file_output": True,
        "include_timestamps": True
    },
    "state": {
        "directory": "~/Library/Application Support/photo-backup",
        "auto_cleanup": True,
        "cleanup_days": 30,
        "backup_state_file": "backup_state.json",
        "lock_file": "backup.lock"
    },
    "security": {
        "encrypt_backups": False,
        "encryption_key": None,
        "verify_checksums": True,
        "checksum_algorithm": "sha256",
        "secure_erase": False
    },
    "performance": {
        "buffer_size_mb": 10,
        "max_memory_usage_mb": 512,
        "parallel_uploads": 1,
        "chunk_size_mb": 5,
        "enable_caching": True
    },
    "notifications": {
        "enabled": False,
        "email": {
            "smtp_server": None,
            "smtp_port": 587,
            "username": None,
            "password": None,
            "from_address": None,
            "to_addresses": []
        },
        "webhook": {
            "url": None,
            "timeout_seconds": 30
        }
    }
}

# Documentation for all configuration options
DEFAULT_CONFIG_DOCS = {
    "backup": {
        "source_path": "Absolute path to the photo source directory to be backed up",
        "destination": "Rclone remote:path specification for backup destination",
        "strategy": "Backup strategy: 'incremental' (default), 'full', or 'differential'",
        "compression": "Enable compression for backup files to reduce storage usage",
        "encryption": "Enable encryption for backup files (requires encryption_key)",
        "verify_after_backup": "Verify backup integrity after completion",
        "max_concurrent_backups": "Maximum number of concurrent backup operations"
    },
    "storage": {
        "endpoint": "S3-compatible storage endpoint URL",
        "access_key": "Storage access key (None to retrieve from 1Password)",
        "secret_key": "Storage secret key (None to retrieve from 1Password)",
        "use_ssl": "Use SSL/TLS encryption for storage connections",
        "region": "Storage region for S3-compatible services",
        "bucket": "Storage bucket name for backup files",
        "timeout_seconds": "Connection timeout in seconds",
        "retry_attempts": "Number of retry attempts for failed operations"
    },
    "monitoring": {
        "check_interval_hours": "Interval between backup checks in hours (0.1-24)",
        "mount_delay_minutes": "Delay after mount detection before backup (1-60)",
        "change_delay_minutes": "Delay after file changes before backup (1-120)",
        "max_retries": "Maximum number of retry attempts for failed operations",
        "retry_delay_minutes": "Delay between retry attempts in minutes",
        "health_check_enabled": "Enable periodic health checks of the backup system",
        "health_check_interval_minutes": "Interval between health checks in minutes"
    },
    "logging": {
        "level": "Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL",
        "directory": "Directory for log file storage",
        "max_size_mb": "Maximum log file size in MB before rotation (1-1000)",
        "backup_count": "Number of log files to keep during rotation (1-50)",
        "format": "Log format: 'simple', 'detailed', or 'json'",
        "console_output": "Output logs to console/terminal",
        "file_output": "Output logs to files",
        "include_timestamps": "Include timestamps in log messages"
    },
    "state": {
        "directory": "Directory for storing backup state and metadata",
        "auto_cleanup": "Automatically clean up old state files",
        "cleanup_days": "Number of days to keep state files before cleanup",
        "backup_state_file": "Filename for backup state information",
        "lock_file": "Filename for backup lock file to prevent concurrent runs"
    },
    "security": {
        "encrypt_backups": "Enable encryption for backup files",
        "encryption_key": "Encryption key for backup files (None for auto-generation)",
        "verify_checksums": "Verify file integrity using checksums",
        "checksum_algorithm": "Checksum algorithm: 'md5', 'sha1', 'sha256', 'sha512'",
        "secure_erase": "Securely erase temporary files after backup"
    },
    "performance": {
        "buffer_size_mb": "Buffer size for file operations in MB",
        "max_memory_usage_mb": "Maximum memory usage for backup operations in MB",
        "parallel_uploads": "Number of parallel upload operations",
        "chunk_size_mb": "Chunk size for large file uploads in MB",
        "enable_caching": "Enable caching for improved performance"
    },
    "notifications": {
        "enabled": "Enable notification system for backup events",
        "email": {
            "smtp_server": "SMTP server for email notifications",
            "smtp_port": "SMTP server port",
            "username": "SMTP username for authentication",
            "password": "SMTP password for authentication",
            "from_address": "From email address for notifications",
            "to_addresses": "List of email addresses to receive notifications"
        },
        "webhook": {
            "url": "Webhook URL for notifications",
            "timeout_seconds": "Webhook request timeout in seconds"
        }
    }
}

# Test mode specific defaults
TEST_MODE_DEFAULTS = {
    "backup": {
        "source_path": "/tmp/photo-backup-test-photos",
        "destination": "minio-test:my-photo-backup-bucket-test",
        "strategy": "incremental",
        "compression": False,  # Faster for testing
        "encryption": False,
        "verify_after_backup": False,  # Skip verification for speed
        "max_concurrent_backups": 1
    },
    "storage": {
        "endpoint": "localhost:9000",
        "access_key": "minioadmin",
        "secret_key": "minioadmin",
        "use_ssl": False,
        "region": "us-east-1",
        "bucket": "test-bucket",
        "timeout_seconds": 30,  # Shorter timeout for testing
        "retry_attempts": 1  # Fewer retries for testing
    },
    "monitoring": {
        "check_interval_hours": 0.1,  # 6 minutes for testing
        "mount_delay_minutes": 1,
        "change_delay_minutes": 1,
        "max_retries": 1,
        "retry_delay_minutes": 1,
        "health_check_enabled": False,  # Disable for testing
        "health_check_interval_minutes": 60
    },
    "logging": {
        "level": "DEBUG",
        "directory": "/tmp/photo-backup-test/logs",
        "max_size_mb": 10,  # Smaller for testing
        "backup_count": 3,  # Fewer for testing
        "format": "detailed",
        "console_output": True,
        "file_output": True,
        "include_timestamps": True
    },
    "state": {
        "directory": "/tmp/photo-backup-test/state",
        "auto_cleanup": True,
        "cleanup_days": 1,  # Shorter retention for testing
        "backup_state_file": "backup_state.json",
        "lock_file": "backup.lock"
    },
    "security": {
        "encrypt_backups": False,
        "encryption_key": None,
        "verify_checksums": False,  # Skip for testing speed
        "checksum_algorithm": "sha256",
        "secure_erase": False
    },
    "performance": {
        "buffer_size_mb": 1,  # Smaller for testing
        "max_memory_usage_mb": 64,  # Lower for testing
        "parallel_uploads": 1,
        "chunk_size_mb": 1,  # Smaller for testing
        "enable_caching": False  # Disable for testing
    },
    "notifications": {
        "enabled": False,
        "email": {
            "smtp_server": None,
            "smtp_port": 587,
            "username": None,
            "password": None,
            "from_address": None,
            "to_addresses": []
        },
        "webhook": {
            "url": None,
            "timeout_seconds": 30
        }
    }
}


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
                is_valid, errors = self.validate_config(file_config)
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
    
    def _expand_path(self, path: str) -> str:
        """Expand relative paths and environment variables.
        
        Args:
            path: Path string to expand
            
        Returns:
            Expanded absolute path
        """
        # Expand environment variables
        expanded = os.path.expandvars(path)
        # Expand user home directory
        expanded = os.path.expanduser(expanded)
        # Convert to absolute path
        return os.path.abspath(expanded)
    
    def _validate_config_schema(self, config: Dict[str, Any]) -> List[str]:
        """Basic schema validation for loaded config.
        
        Args:
            config: Configuration dictionary to validate
            
        Returns:
            List of validation errors
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
        
        return errors
    
    def _validate_paths(self, config: Dict[str, Any]) -> List[str]:
        """Validate that paths are absolute and accessible.
        
        Args:
            config: Configuration dictionary to validate
            
        Returns:
            List of validation errors
        """
        errors = []
        
        # Validate backup source path
        if 'backup' in config and isinstance(config['backup'], dict):
            backup = config['backup']
            if 'source_path' in backup and isinstance(backup['source_path'], str):
                source_path = backup['source_path']
                
                # Check if original path is absolute (before expansion)
                if not os.path.isabs(source_path):
                    errors.append("backup.source_path must be an absolute path")
                else:
                    # Expand the path
                    expanded_path = self._expand_path(source_path)
                    
                    # Check if path exists and is accessible
                    try:
                        path_obj = Path(expanded_path)
                        if not path_obj.exists():
                            errors.append(f"backup.source_path does not exist: {expanded_path}")
                        elif not path_obj.is_dir():
                            errors.append(f"backup.source_path must be a directory: {expanded_path}")
                        elif not os.access(expanded_path, os.R_OK):
                            errors.append(f"backup.source_path is not readable: {expanded_path}")
                    except Exception as e:
                        errors.append(f"backup.source_path validation error: {e}")
        
        # Validate logging directory
        if 'logging' in config and isinstance(config['logging'], dict):
            logging_config = config['logging']
            if 'directory' in logging_config and isinstance(logging_config['directory'], str):
                log_dir = logging_config['directory']
                expanded_path = self._expand_path(log_dir)
                
                # For logging directory, we'll create it if it doesn't exist
                # But we need to check if the parent directory is writable
                try:
                    path_obj = Path(expanded_path)
                    if path_obj.exists() and not path_obj.is_dir():
                        errors.append(f"logging.directory must be a directory: {expanded_path}")
                    elif path_obj.exists() and not os.access(expanded_path, os.W_OK):
                        errors.append(f"logging.directory is not writable: {expanded_path}")
                    elif not path_obj.exists():
                        # Check if parent directory is writable
                        parent = path_obj.parent
                        if not parent.exists():
                            errors.append(f"logging.directory parent does not exist: {parent}")
                        elif not os.access(parent, os.W_OK):
                            errors.append(f"logging.directory parent is not writable: {parent}")
                except Exception as e:
                    errors.append(f"logging.directory validation error: {e}")
        
        # Validate state directory
        if 'state' in config and isinstance(config['state'], dict):
            state = config['state']
            if 'directory' in state and isinstance(state['directory'], str):
                state_dir = state['directory']
                expanded_path = self._expand_path(state_dir)
                
                # For state directory, we'll create it if it doesn't exist
                # But we need to check if the parent directory is writable
                try:
                    path_obj = Path(expanded_path)
                    if path_obj.exists() and not path_obj.is_dir():
                        errors.append(f"state.directory must be a directory: {expanded_path}")
                    elif path_obj.exists() and not os.access(expanded_path, os.W_OK):
                        errors.append(f"state.directory is not writable: {expanded_path}")
                    elif not path_obj.exists():
                        # Check if parent directory is writable
                        parent = path_obj.parent
                        if not parent.exists():
                            errors.append(f"state.directory parent does not exist: {parent}")
                        elif not os.access(parent, os.W_OK):
                            errors.append(f"state.directory parent is not writable: {parent}")
                except Exception as e:
                    errors.append(f"state.directory validation error: {e}")
        
        return errors
    
    def _validate_numeric_ranges(self, config: Dict[str, Any]) -> List[str]:
        """Validate numeric values are within acceptable ranges.
        
        Args:
            config: Configuration dictionary to validate
            
        Returns:
            List of validation errors
        """
        errors = []
        
        # Validate monitoring section
        if 'monitoring' in config and isinstance(config['monitoring'], dict):
            monitoring = config['monitoring']
            
            # Check interval hours: 0.1 to 24
            if 'check_interval_hours' in monitoring:
                value = monitoring['check_interval_hours']
                if isinstance(value, (int, float)):
                    if value < 0.1 or value > 24:
                        errors.append("monitoring.check_interval_hours must be between 0.1 and 24 hours")
                else:
                    errors.append("monitoring.check_interval_hours must be a number")
            
            # Mount delay minutes: 1 to 60
            if 'mount_delay_minutes' in monitoring:
                value = monitoring['mount_delay_minutes']
                if isinstance(value, (int, float)):
                    if value < 1 or value > 60:
                        errors.append("monitoring.mount_delay_minutes must be between 1 and 60 minutes")
                else:
                    errors.append("monitoring.mount_delay_minutes must be a number")
            
            # Change delay minutes: 1 to 120
            if 'change_delay_minutes' in monitoring:
                value = monitoring['change_delay_minutes']
                if isinstance(value, (int, float)):
                    if value < 1 or value > 120:
                        errors.append("monitoring.change_delay_minutes must be between 1 and 120 minutes")
                else:
                    errors.append("monitoring.change_delay_minutes must be a number")
        
        # Validate logging section
        if 'logging' in config and isinstance(config['logging'], dict):
            logging_config = config['logging']
            
            # Max size MB: 1 to 1000
            if 'max_size_mb' in logging_config:
                value = logging_config['max_size_mb']
                if isinstance(value, (int, float)):
                    if value < 1 or value > 1000:
                        errors.append("logging.max_size_mb must be between 1 and 1000 MB")
                else:
                    errors.append("logging.max_size_mb must be a number")
            
            # Backup count: 1 to 50
            if 'backup_count' in logging_config:
                value = logging_config['backup_count']
                if isinstance(value, int):
                    if value < 1 or value > 50:
                        errors.append("logging.backup_count must be between 1 and 50")
                else:
                    errors.append("logging.backup_count must be an integer")
        
        return errors
    
    def _validate_test_mode_paths(self, config: Dict[str, Any]) -> List[str]:
        """Validate paths are appropriate for test mode.
        
        Args:
            config: Configuration dictionary to validate
            
        Returns:
            List of validation errors
        """
        errors = []
        
        # In test mode, we're more lenient with paths
        # Allow any path, but warn about non-test paths
        if 'backup' in config and isinstance(config['backup'], dict):
            backup = config['backup']
            if 'source_path' in backup and isinstance(backup['source_path'], str):
                source_path = backup['source_path']
                expanded_path = self._expand_path(source_path)
                
                # In test mode, we allow any path but prefer test directories
                if not any(test_dir in expanded_path for test_dir in ['/tmp', 'test', 'temp']):
                    # This is just a warning, not an error in test mode
                    pass  # Could add a warning here if desired
        
        return errors
    
    def validate_config(self, config: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Comprehensive configuration validation.
        
        Args:
            config: Configuration dictionary to validate
            
        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []
        
        # Basic schema validation
        errors.extend(self._validate_config_schema(config))
        
        # Path validation (collect all path errors)
        errors.extend(self._validate_paths(config))
        
        # Numeric range validation (collect all numeric errors)
        errors.extend(self._validate_numeric_ranges(config))
        
        # Test mode specific validation
        if self.test_mode:
            errors.extend(self._validate_test_mode_paths(config))
        
        return len(errors) == 0, errors
    
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