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

        Returns:
            Dictionary containing storage credentials

        Raises:
            CredentialError: If credentials cannot be retrieved
        """
        try:
            config_data = self.config.load_config()
            storage_config = config_data.get("storage", {})

            # Try to get access key and secret key
            access_key, secret_key = self._get_direct_credentials()

            if not access_key or not secret_key:
                raise CredentialError(
                    "No direct credentials available",
                    "Set WASABI_ACCESS_KEY/WASABI_SECRET_KEY environment variables or configure in config file",
                    "Both access_key and secret_key are required",
                )

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
                f"Direct credentials loaded: endpoint={credentials['endpoint']}, bucket={credentials['bucket']}"
            )
            return credentials

        except CredentialError:
            # Re-raise credential errors as-is
            raise
        except Exception as e:
            raise CredentialError(
                "Failed to load direct credentials",
                "Check configuration and ensure credentials are properly configured",
                f"Unexpected error: {e}",
            ) from e

    def _get_direct_credentials(self) -> tuple[str | None, str | None]:
        """Get credentials from environment variables or config file.

        Returns:
            Tuple of (access_key, secret_key) or (None, None) if not found
        """
        try:
            # Try environment variables first (most secure for automation)
            access_key = os.environ.get("WASABI_ACCESS_KEY") or os.environ.get("S3_ACCESS_KEY")
            secret_key = os.environ.get("WASABI_SECRET_KEY") or os.environ.get("S3_SECRET_KEY")

            if access_key and secret_key:
                self.logger.debug("Found credentials in environment variables")
                return access_key, secret_key

            # Try config file as fallback
            config_data = self.config.load_config()
            storage_config = config_data.get("storage", {})

            access_key = storage_config.get("access_key")
            secret_key = storage_config.get("secret_key")

            if access_key and secret_key:
                self.logger.debug("Found credentials in config file")
                return access_key, secret_key

            self.logger.debug("No direct credentials found")
            return None, None
        except Exception as e:
            self.logger.error(f"Error retrieving direct credentials: {e}")
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
