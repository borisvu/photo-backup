"""
Abstract base class for credential providers.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ...config.config import Config


class CredentialProvider(ABC):
    """Abstract base class for credential providers."""

    def __init__(self, config: "Config") -> None:
        """Initialize the credential provider.

        Args:
            config: Configuration object containing storage settings
        """
        self.config = config

    @abstractmethod
    def get_credentials(self) -> dict[str, Any]:
        """Get credentials for storage access.

        Returns:
            Dictionary containing credentials with keys:
            - access_key: Storage access key
            - secret_key: Storage secret key
            - endpoint: Storage endpoint URL
            - region: Storage region
            - use_ssl: Whether to use SSL/TLS
            - bucket: Storage bucket name
            - timeout_seconds: Request timeout
            - retry_attempts: Number of retry attempts

        Raises:
            CredentialError: If credentials cannot be retrieved
        """
        pass

    @abstractmethod
    def get_source_name(self) -> str:
        """Get the name of this credential source.

        Returns:
            String describing the credential source
        """
        pass
