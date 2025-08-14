"""
Test mode credential provider for Minio.
"""

import logging
from typing import Any

from ..exceptions import CredentialError
from .base import CredentialProvider


class TestModeCredentialProvider(CredentialProvider):
    """Provider for test mode credentials (Minio)."""

    def __init__(self, config):
        """Initialize the test mode credential provider.

        Args:
            config: Configuration object containing storage settings
        """
        super().__init__(config)
        self.logger = logging.getLogger("photo_backup.credentials.test_mode")

    def get_credentials(self) -> dict[str, Any]:
        """Get test mode credentials (Minio).

        Returns:
            Dictionary containing Minio test credentials

        Raises:
            CredentialError: If credentials cannot be retrieved
        """
        try:
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

            self.logger.debug(
                f"Test credentials loaded: endpoint={credentials['endpoint']}, bucket={credentials['bucket']}"
            )
            return credentials
        except Exception as e:
            raise CredentialError(
                "Failed to load test mode credentials",
                "Check test configuration and ensure Minio container is running",
                f"Configuration error: {e}",
            ) from e

    def get_source_name(self) -> str:
        """Get the name of this credential source.

        Returns:
            String describing the credential source
        """
        return "test_mode"
