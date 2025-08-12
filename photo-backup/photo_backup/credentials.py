"""
Credential management for photo backup system.

This module handles credential retrieval, validation, and management
for S3-compatible storage services, with support for 1Password integration
and test mode using Minio.
"""

import logging
import os
from typing import Any, Dict, Optional

from .config.config import Config


class CredentialManager:
    """Manages credentials for S3-compatible storage services."""

    def __init__(self, config: Config):
        """Initialize credential manager.

        Args:
            config: Configuration object containing storage settings
        """
        self.config = config
        self.logger = logging.getLogger("photo_backup.credentials")
        self._credentials: Optional[Dict[str, Any]] = None

    def get_credentials(self) -> Dict[str, Any]:
        """Get credentials for storage access.

        Returns:
            Dictionary containing credentials with keys:
            - access_key: Storage access key
            - secret_key: Storage secret key
            - endpoint: Storage endpoint URL
            - region: Storage region
            - use_ssl: Whether to use SSL/TLS
            - bucket: Storage bucket name
        """
        if self._credentials is None:
            self._credentials = self._load_credentials()

        return self._credentials.copy()

    def _load_credentials(self) -> Dict[str, Any]:
        """Load credentials based on configuration and mode.

        Returns:
            Dictionary containing storage credentials
        """
        if self.config.is_test_mode():
            return self._get_test_credentials()
        else:
            return self._get_production_credentials()

    def _get_test_credentials(self) -> Dict[str, Any]:
        """Get test mode credentials (Minio).

        Returns:
            Dictionary containing Minio test credentials
        """
        self.logger.debug("Loading test mode credentials (Minio)")
        
        config_data = self.config.load_config()
        storage_config = config_data.get("storage", {})
        
        credentials = {
            "access_key": storage_config.get("access_key", "minioadmin"),
            "secret_key": storage_config.get("secret_key", "minioadmin"),
            "endpoint": storage_config.get("endpoint", "localhost:9000"),
            "region": storage_config.get("region", "us-east-1"),
            "use_ssl": storage_config.get("use_ssl", False),
            "bucket": storage_config.get("bucket", "test-bucket"),
            "timeout_seconds": storage_config.get("timeout_seconds", 30),
            "retry_attempts": storage_config.get("retry_attempts", 1),
        }
        
        self.logger.debug(f"Test credentials loaded: endpoint={credentials['endpoint']}, bucket={credentials['bucket']}")
        return credentials

    def _get_production_credentials(self) -> Dict[str, Any]:
        """Get production credentials (Wasabi via 1Password).

        Returns:
            Dictionary containing production credentials
        """
        self.logger.debug("Loading production credentials")
        
        config_data = self.config.load_config()
        storage_config = config_data.get("storage", {})
        
        # For now, return None values - will be implemented in Task 46
        credentials = {
            "access_key": storage_config.get("access_key"),  # Will be retrieved from 1Password
            "secret_key": storage_config.get("secret_key"),  # Will be retrieved from 1Password
            "endpoint": storage_config.get("endpoint", "s3.wasabisys.com"),
            "region": storage_config.get("region", "us-east-1"),
            "use_ssl": storage_config.get("use_ssl", True),
            "bucket": storage_config.get("bucket", "my-photo-backup-bucket"),
            "timeout_seconds": storage_config.get("timeout_seconds", 300),
            "retry_attempts": storage_config.get("retry_attempts", 3),
        }
        
        self.logger.debug(f"Production credentials loaded: endpoint={credentials['endpoint']}, bucket={credentials['bucket']}")
        return credentials

    def validate_credentials(self) -> tuple[bool, str]:
        """Validate that credentials are available and complete.

        Returns:
            Tuple of (is_valid, error_message)
        """
        credentials = self.get_credentials()
        
        # Check required fields (except access_key and secret_key which may be None in production)
        required_fields = ["endpoint", "bucket"]
        for field in required_fields:
            if not credentials.get(field):
                return False, f"Missing required credential field: {field}"
        
        # Test mode specific validation
        if self.config.is_test_mode():
            return self._validate_test_credentials(credentials)
        else:
            return self._validate_production_credentials(credentials)

    def _validate_test_credentials(self, credentials: Dict[str, Any]) -> tuple[bool, str]:
        """Validate test mode credentials.

        Args:
            credentials: Credentials dictionary

        Returns:
            Tuple of (is_valid, error_message)
        """
        # For test mode, just check that credentials are present
        # Actual Minio connectivity will be tested in Task 48
        if credentials["access_key"] == "minioadmin" and credentials["secret_key"] == "minioadmin":
            return True, "Test credentials are valid"
        else:
            return False, "Invalid test credentials - expected minioadmin/minioadmin"

    def _validate_production_credentials(self, credentials: Dict[str, Any]) -> tuple[bool, str]:
        """Validate production credentials.

        Args:
            credentials: Credentials dictionary

        Returns:
            Tuple of (is_valid, error_message)
        """
        # For now, just check that credentials are present
        # 1Password integration will be implemented in Task 46
        if credentials["access_key"] is None or credentials["secret_key"] is None:
            return False, "Production credentials not available - 1Password integration not yet implemented"
        
        return True, "Production credentials are valid"

    def get_credential_info(self) -> Dict[str, Any]:
        """Get information about current credentials.

        Returns:
            Dictionary containing credential information
        """
        credentials = self.get_credentials()
        
        info = {
            "mode": "test" if self.config.is_test_mode() else "production",
            "endpoint": credentials["endpoint"],
            "bucket": credentials["bucket"],
            "region": credentials["region"],
            "use_ssl": credentials["use_ssl"],
            "has_access_key": credentials["access_key"] is not None,
            "has_secret_key": credentials["secret_key"] is not None,
            "timeout_seconds": credentials["timeout_seconds"],
            "retry_attempts": credentials["retry_attempts"],
        }
        
        # Mask sensitive information
        if credentials["access_key"]:
            info["access_key_preview"] = f"{credentials['access_key'][:4]}...{credentials['access_key'][-4:]}"
        else:
            info["access_key_preview"] = "None"
            
        return info
