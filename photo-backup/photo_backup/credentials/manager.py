"""
Credential manager for the photo backup system.

This module orchestrates credential providers and validators to provide
a unified interface for credential management.
"""

import logging
from typing import Any

from .exceptions import CredentialError
from .providers import DirectCredentialProvider, OnePasswordCredentialProvider, TestModeCredentialProvider
from .validators import RcloneCredentialValidator


class CredentialManager:
    """Manages credentials for S3-compatible storage services."""

    def __init__(self, config):
        """Initialize credential manager.

        Args:
            config: Configuration object containing storage settings
        """
        self.config = config
        self.logger = logging.getLogger("photo_backup.credentials")
        self._credentials: dict[str, Any] | None = None

        # Initialize providers
        self._test_provider = TestModeCredentialProvider(config)
        self._direct_provider = DirectCredentialProvider(config)
        self._onepassword_provider = OnePasswordCredentialProvider(config)

        # Initialize validators
        self._rclone_validator = RcloneCredentialValidator(config)

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
        """
        if self._credentials is None:
            try:
                self._credentials = self._load_credentials()
            except CredentialError as e:
                # Log the error and provide helpful context
                self.logger.error(f"Credential error: {e.message}")
                if e.suggestion:
                    self.logger.info(f"Suggestion: {e.suggestion}")
                if e.details:
                    self.logger.debug(f"Details: {e.details}")

                # For test mode, provide specific Minio guidance
                if self.config.is_test_mode():
                    self.logger.error(
                        "Test mode requires Minio container. "
                        "Start with: docker run -d --name minio -p 9000:9000 minio/minio server /data"
                    )

                # Re-raise the error for proper handling
                raise

        return self._credentials.copy()

    def handle_credential_error(self, error: CredentialError) -> str:
        """Handle credential errors and return user-friendly message.

        Args:
            error: The CredentialError that occurred

        Returns:
            User-friendly error message with suggestions
        """
        mode = "test" if self.config.is_test_mode() else "production"

        # Build comprehensive error message
        message_parts = [f"Credential error in {mode} mode: {error.message}"]

        if error.suggestion:
            message_parts.append(f"Fix: {error.suggestion}")

        # Add mode-specific suggestions
        if self.config.is_test_mode():
            message_parts.append("For test mode: Ensure Minio container is running with 'docker start minio'")
        else:
            message_parts.append("For production: Set WASABI_ACCESS_KEY/WASABI_SECRET_KEY environment variables")

        if error.details:
            message_parts.append(f"Technical details: {error.details}")

        return " ".join(message_parts)

    def get_credential_status(self) -> dict[str, Any]:
        """Get comprehensive credential status information.

        Returns:
            Dictionary containing credential status with error information
        """
        status: dict[str, Any] = {
            "mode": "test" if self.config.is_test_mode() else "production",
            "has_credentials": False,
            "error": None,
            "suggestion": None,
            "details": None,
            "credential_info": None,
        }

        try:
            # Test credentials if available
            is_valid, message = self.validate_credentials()
            status["validation"] = {"is_valid": is_valid, "message": message}

            # Only report has_credentials as True if validation passes
            if is_valid:
                status["has_credentials"] = True
                status["credential_info"] = self.get_credential_info()
            else:
                status["has_credentials"] = False
                status["error"] = message
                status["suggestion"] = "Set valid credentials via environment variables or config file"

        except CredentialError as e:
            status["error"] = e.message
            status["suggestion"] = e.suggestion
            status["details"] = e.details
            status["validation"] = {"is_valid": False, "message": f"{e.message}. {e.suggestion}"}
        except Exception as e:
            status["error"] = f"Unexpected error: {e}"
            status["suggestion"] = "Check configuration and try again"
            status["validation"] = {"is_valid": False, "message": f"Unexpected error: {e}"}

        return status

    def _load_credentials(self) -> dict[str, Any]:
        """Load credentials based on configuration and mode.

        Returns:
            Dictionary containing storage credentials
        """
        try:
            if self.config.is_test_mode():
                return self._test_provider.get_credentials()
            else:
                return self._get_production_credentials()
        except CredentialError:
            # Re-raise credential errors as-is
            raise
        except Exception as e:
            # Catch any unexpected errors and provide helpful context
            mode = "test" if self.config.is_test_mode() else "production"
            raise CredentialError(
                f"Failed to load {mode} credentials", "Check configuration and try again", f"Unexpected error: {e}"
            ) from e

    def _get_production_credentials(self) -> dict[str, Any]:
        """Get production credentials with fallback logic.

        Returns:
            Dictionary containing production credentials
        """
        try:
            # Try direct credentials first
            try:
                return self._direct_provider.get_credentials()
            except CredentialError:
                self.logger.debug("Direct credentials not available, trying 1Password")

            # Fallback to 1Password if configured
            config_data = self.config.load_config()
            storage_config = config_data.get("storage", {})

            if storage_config.get("use_1password", False):
                return self._onepassword_provider.get_credentials()
            else:
                raise CredentialError(
                    "No production credentials available",
                    "Set WASABI_ACCESS_KEY/WASABI_SECRET_KEY environment variables, "
                    "configure in config file, or enable 1Password integration",
                    "No direct credentials and 1Password not configured",
                )

        except CredentialError:
            # Re-raise credential errors as-is
            raise
        except Exception as e:
            raise CredentialError(
                "Failed to load production credentials",
                "Check configuration and ensure credentials are properly configured",
                f"Unexpected error: {e}",
            ) from e

    def validate_credentials(self) -> tuple[bool, str]:
        """Validate that credentials are available and complete.

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
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
        except CredentialError as e:
            return False, f"{e.message}. {e.suggestion}"
        except Exception as e:
            return False, f"Validation failed: {e}"

    def test_credentials_with_rclone(self) -> tuple[bool, str]:
        """Test credentials by attempting to connect to S3-compatible storage.

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            credentials = self.get_credentials()
            return self._rclone_validator.validate_credentials(credentials)
        except CredentialError as e:
            return False, f"{e.message}. {e.suggestion}"
        except Exception as e:
            return False, f"Credential testing failed: {e}"

    def _validate_test_credentials(self, credentials: dict[str, Any]) -> tuple[bool, str]:
        """Validate test mode credentials.

        Args:
            credentials: Credentials dictionary

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check that credentials are present
        if credentials["access_key"] == "minioadmin" and credentials["secret_key"] == "minioadmin":
            # Test Minio connectivity with rclone
            return self.test_credentials_with_rclone()
        else:
            return False, (
                "Invalid test credentials - expected minioadmin/minioadmin. "
                "Check test mode configuration or start Minio container"
            )

    def _validate_production_credentials(self, credentials: dict[str, Any]) -> tuple[bool, str]:
        """Validate production credentials.

        Args:
            credentials: Credentials dictionary

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check that credentials are available
        if credentials["access_key"] is None or credentials["secret_key"] is None:
            suggestion = (
                "Set WASABI_ACCESS_KEY and WASABI_SECRET_KEY environment variables, "
                "or configure credentials in config file, or enable 1Password integration"
            )
            return False, f"Production credentials not available. {suggestion}"

        # Test credentials with rclone for validation
        return self.test_credentials_with_rclone()

    def get_credential_info(self) -> dict[str, Any]:
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
            "credential_source": self._get_credential_source(),
        }

        # Mask sensitive information
        if credentials["access_key"]:
            info["access_key_preview"] = f"{credentials['access_key'][:4]}...{credentials['access_key'][-4:]}"
        else:
            info["access_key_preview"] = "None"

        return info

    def _get_credential_source(self) -> str:
        """Get the source of the current credentials.

        Returns:
            String describing the credential source
        """
        if self.config.is_test_mode():
            return self._test_provider.get_source_name()

        # Check direct provider first
        try:
            self._direct_provider.get_credentials()
            return self._direct_provider.get_source_name()
        except CredentialError:
            pass

        # Check if 1Password is configured
        try:
            config_data = self.config.load_config()
            storage_config = config_data.get("storage", {})
            if storage_config.get("use_1password", False):
                return self._onepassword_provider.get_source_name()
        except Exception:
            pass

        return "none"
