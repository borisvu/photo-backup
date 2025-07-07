"""
Configuration management for photo backup system.

This module handles loading and managing configuration settings,
with support for test mode using Minio instead of Wasabi.
"""


class Config:
    """Configuration manager for photo backup system."""
    
    def __init__(self, test_mode=False):
        """Initialize configuration.
        
        Args:
            test_mode: If True, use test configuration with Minio
        """
        self.test_mode = test_mode
        self._config = None
    
    def load_config(self):
        """Load configuration settings.
        
        Returns:
            dict: Configuration dictionary
        """
        if self._config is None:
            if self.test_mode:
                self._config = self._get_test_config()
            else:
                self._config = self._get_production_config()
        
        return self._config
    
    def _get_test_config(self):
        """Get test mode configuration using Minio.
        
        Returns:
            dict: Test configuration with Minio settings
        """
        return {
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
    
    def _get_production_config(self):
        """Get production configuration for Wasabi.
        
        Returns:
            dict: Production configuration with Wasabi settings
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