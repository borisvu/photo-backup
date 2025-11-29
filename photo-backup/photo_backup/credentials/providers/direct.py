"""
Direct credential provider for environment variables and config file.
"""

import logging
import os
from typing import Any

from ..exceptions import CredentialError
from .base import CredentialProvider


class DirectCredentialProvider(CredentialProvider):
    """Provider for direct credentials from environment variables or config file."""

    def __init__(self, config):
        """Initialize the direct credential provider.

        Args:
            config: Configuration object containing storage settings
        """
        super().__init__(config)
        self.logger = logging.getLogger("photo_backup.credentials.direct")

    def get_credentials(self) -> dict[str, Any]:
        """Get credentials from environment variables or config file.

        This provider now works in any mode and reads from the storage section
        of the config file. Credentials can be None (for test scenarios), allowing
        the system to work with any S3-compatible backend.

        Returns:
            Dictionary containing storage credentials

        Raises:
            CredentialError: If configuration cannot be loaded
        """
        try:
            config_data = self.config.load_config()
            storage_config = config_data.get("storage", {})

            # Try to get access key and secret key (may be None)
            access_key, secret_key = self._get_direct_credentials()

            # Read all settings from storage config section
            # This allows any S3-compatible backend to be configured
            credentials = {
                "access_key": access_key,
                "secret_key": secret_key,
                "endpoint": storage_config.get("endpoint", "s3.wasabisys.com"),
                "region": storage_config.get("region", "us-east-1"),
                "use_ssl": storage_config.get("use_ssl", True),
                "bucket": storage_config.get("bucket", "my-photo-backup-bucket"),
                "timeout_seconds": storage_config.get("timeout_seconds", 300),
                "retry_attempts": storage_config.get("retry_attempts", 3),
            }

            self.logger.debug(
                f"Credentials loaded from config/env: endpoint={credentials['endpoint']}, "
                f"bucket={credentials['bucket']}, has_keys={access_key is not None}"
            )
            return credentials

        except CredentialError:
            # Re-raise credential errors as-is
            raise
        except Exception as e:
            raise CredentialError(
                "Failed to load credentials",
                "Check configuration and ensure storage section is properly configured",
                f"Unexpected error: {e}",
            ) from e

    def _get_direct_credentials(self) -> tuple[str | None, str | None]:
        """Get credentials from environment variables or config file.

        Implements unified credential chain: Env → Config → None
        Works with any S3-compatible backend (Wasabi, MinIO, AWS, etc.)

        Returns:
            Tuple of (access_key, secret_key) or (None, None) if not found
        """
        try:
            # Try environment variables first (most secure for automation)
            # Support multiple naming conventions for flexibility
            access_key = os.environ.get("WASABI_ACCESS_KEY") or os.environ.get("S3_ACCESS_KEY")
            secret_key = os.environ.get("WASABI_SECRET_KEY") or os.environ.get("S3_SECRET_KEY")

            if access_key and secret_key:
                self.logger.debug("Found credentials in environment variables")
                return access_key, secret_key

            # Try config file storage section as fallback
            config_data = self.config.load_config()
            storage_config = config_data.get("storage", {})

            access_key = storage_config.get("access_key")
            secret_key = storage_config.get("secret_key")

            if access_key and secret_key:
                self.logger.debug("Found credentials in config file storage section")
                return access_key, secret_key

            self.logger.debug("No credentials found - will return None (acceptable for some configurations)")
            return None, None
        except Exception as e:
            self.logger.error(f"Error retrieving credentials: {e}")
            return None, None

    def get_source_name(self) -> str:
        """Get the name of this credential source.

        Returns:
            String describing the credential source
        """
        # Check environment variables first
        if os.environ.get("WASABI_ACCESS_KEY") or os.environ.get("S3_ACCESS_KEY"):
            return "environment_variables"

        # Check config file
        try:
            config_data = self.config.load_config()
            storage_config = config_data.get("storage", {})
            if storage_config.get("access_key"):
                return "config_file"
        except Exception:
            pass

        return "none"
