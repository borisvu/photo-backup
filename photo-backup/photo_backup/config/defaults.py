"""
Default configuration constants for photo backup system.

This module contains all default configuration values, documentation,
and test mode overrides for the photo backup system.
"""

# Module-level default configuration constants
DEFAULT_CONFIG = {
    "backup": {
        "source_path": "/Volumes/4TB-SSD/Photo",
        "destination": "wasabi-photo:my-photo-backup-bucket",
        "strategy": "incremental",
        "compression": True,
        "encryption": False,
        "verify_after_backup": True,
        "max_concurrent_backups": 1,
    },
    "storage": {
        "endpoint": "s3.wasabisys.com",
        "access_key": None,  # Retrieved from 1Password
        "secret_key": None,  # Retrieved from 1Password
        "use_ssl": True,
        "region": "us-east-1",
        "bucket": "my-photo-backup-bucket",
        "timeout_seconds": 300,
        "retry_attempts": 3,
    },
    "monitoring": {
        "check_interval_hours": 4,
        "mount_delay_minutes": 15,
        "change_delay_minutes": 30,
        "max_retries": 3,
        "retry_delay_minutes": 5,
        "health_check_enabled": True,
        "health_check_interval_minutes": 60,
    },
    "logging": {
        "level": "INFO",
        "directory": "~/Library/Logs/photo-backup",
        "max_size_mb": 100,
        "backup_count": 5,
        "format": "detailed",
        "console_output": True,
        "file_output": True,
        "include_timestamps": True,
    },
    "state": {
        "directory": "~/Library/Application Support/photo-backup",
        "auto_cleanup": True,
        "cleanup_days": 30,
        "backup_state_file": "backup_state.json",
        "lock_file": "backup.lock",
    },
    "security": {
        "encrypt_backups": False,
        "encryption_key": None,
        "verify_checksums": True,
        "checksum_algorithm": "sha256",
        "secure_erase": False,
    },
    "performance": {
        "buffer_size_mb": 10,
        "max_memory_usage_mb": 512,
        "parallel_uploads": 1,
        "chunk_size_mb": 5,
        "enable_caching": True,
    },
    "notifications": {
        "enabled": False,
        "email": {
            "smtp_server": None,
            "smtp_port": 587,
            "username": None,
            "password": None,
            "from_address": None,
            "to_addresses": [],
        },
        "webhook": {"url": None, "timeout_seconds": 30},
    },
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
        "max_concurrent_backups": "Maximum number of concurrent backup operations",
    },
    "storage": {
        "endpoint": "S3-compatible storage endpoint URL",
        "access_key": "Storage access key (None to retrieve from 1Password)",
        "secret_key": "Storage secret key (None to retrieve from 1Password)",
        "use_ssl": "Use SSL/TLS encryption for storage connections",
        "region": "Storage region for S3-compatible services",
        "bucket": "Storage bucket name for backup files",
        "timeout_seconds": "Connection timeout in seconds",
        "retry_attempts": "Number of retry attempts for failed operations",
    },
    "monitoring": {
        "check_interval_hours": "Interval between backup checks in hours (0.1-24)",
        "mount_delay_minutes": "Delay after mount detection before backup (1-60)",
        "change_delay_minutes": "Delay after file changes before backup (1-120)",
        "max_retries": "Maximum number of retry attempts for failed operations",
        "retry_delay_minutes": "Delay between retry attempts in minutes",
        "health_check_enabled": "Enable periodic health checks of the backup system",
        "health_check_interval_minutes": "Interval between health checks in minutes",
    },
    "logging": {
        "level": "Logging level: DEBUG, INFO, WARNING, ERROR, CRITICAL",
        "directory": "Directory for log file storage",
        "max_size_mb": "Maximum log file size in MB before rotation (1-1000)",
        "backup_count": "Number of log files to keep during rotation (1-50)",
        "format": "Log format: 'simple', 'detailed', or 'json'",
        "console_output": "Output logs to console/terminal",
        "file_output": "Output logs to files",
        "include_timestamps": "Include timestamps in log messages",
    },
    "state": {
        "directory": "Directory for storing backup state and metadata",
        "auto_cleanup": "Automatically clean up old state files",
        "cleanup_days": "Number of days to keep state files before cleanup",
        "backup_state_file": "Filename for backup state information",
        "lock_file": "Filename for backup lock file to prevent concurrent runs",
    },
    "security": {
        "encrypt_backups": "Enable encryption for backup files",
        "encryption_key": "Encryption key for backup files (None for auto-generation)",
        "verify_checksums": "Verify file integrity using checksums",
        "checksum_algorithm": "Checksum algorithm: 'md5', 'sha1', 'sha256', 'sha512'",
        "secure_erase": "Securely erase temporary files after backup",
    },
    "performance": {
        "buffer_size_mb": "Buffer size for file operations in MB",
        "max_memory_usage_mb": "Maximum memory usage for backup operations in MB",
        "parallel_uploads": "Number of parallel upload operations",
        "chunk_size_mb": "Chunk size for large file uploads in MB",
        "enable_caching": "Enable caching for improved performance",
    },
    "notifications": {
        "enabled": "Enable notification system for backup events",
        "email": {
            "smtp_server": "SMTP server for email notifications",
            "smtp_port": "SMTP server port",
            "username": "SMTP username for authentication",
            "password": "SMTP password for authentication",
            "from_address": "From email address for notifications",
            "to_addresses": "List of email addresses to receive notifications",
        },
        "webhook": {"url": "Webhook URL for notifications", "timeout_seconds": "Webhook request timeout in seconds"},
    },
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
        "max_concurrent_backups": 1,
    },
    "storage": {
        "endpoint": "localhost:9000",
        "access_key": "minioadmin",
        "secret_key": "minioadmin",
        "use_ssl": False,
        "region": "us-east-1",
        "bucket": "test-bucket",
        "timeout_seconds": 30,  # Shorter timeout for testing
        "retry_attempts": 1,  # Fewer retries for testing
    },
    "monitoring": {
        "check_interval_hours": 0.1,  # 6 minutes for testing
        "mount_delay_minutes": 1,
        "change_delay_minutes": 1,
        "max_retries": 1,
        "retry_delay_minutes": 1,
        "health_check_enabled": False,  # Disable for testing
        "health_check_interval_minutes": 60,
    },
    "logging": {
        "level": "DEBUG",
        "directory": "/tmp/photo-backup-test/logs",
        "max_size_mb": 10,  # Smaller for testing
        "backup_count": 3,  # Fewer for testing
        "format": "detailed",
        "console_output": True,
        "file_output": True,
        "include_timestamps": True,
    },
    "state": {
        "directory": "/tmp/photo-backup-test/state",
        "auto_cleanup": True,
        "cleanup_days": 1,  # Shorter retention for testing
        "backup_state_file": "backup_state.json",
        "lock_file": "backup.lock",
    },
    "security": {
        "encrypt_backups": False,
        "encryption_key": None,
        "verify_checksums": False,  # Skip for testing speed
        "checksum_algorithm": "sha256",
        "secure_erase": False,
    },
    "performance": {
        "buffer_size_mb": 1,  # Smaller for testing
        "max_memory_usage_mb": 64,  # Lower for testing
        "parallel_uploads": 1,
        "chunk_size_mb": 1,  # Smaller for testing
        "enable_caching": False,  # Disable for testing
    },
    "notifications": {
        "enabled": False,
        "email": {
            "smtp_server": None,
            "smtp_port": 587,
            "username": None,
            "password": None,
            "from_address": None,
            "to_addresses": [],
        },
        "webhook": {"url": None, "timeout_seconds": 30},
    },
}
