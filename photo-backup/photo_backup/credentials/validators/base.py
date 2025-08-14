"""
Abstract base class for credential validators.
"""

from abc import ABC, abstractmethod
from typing import Any


class CredentialValidator(ABC):
    """Abstract base class for credential validators."""

    def __init__(self, config):
        """Initialize the credential validator.

        Args:
            config: Configuration object containing storage settings
        """
        self.config = config

    @abstractmethod
    def validate_credentials(self, credentials: dict[str, Any]) -> tuple[bool, str]:
        """Validate that credentials are available and complete.

        Args:
            credentials: Dictionary containing credentials to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        pass

    @abstractmethod
    def get_validator_name(self) -> str:
        """Get the name of this validator.

        Returns:
            String describing the validator
        """
        pass
