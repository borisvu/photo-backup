"""
Credential manager for the photo backup system.

This module orchestrates credential providers and validators to provide
a unified interface for credential management.
"""

import logging
from typing import Any

from .exceptions import CredentialError
from .providers import DirectCredentialProvider, OnePasswordCredentialProvider
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

        # Add general suggestions (mode-independent after Phase 1 refactoring)
        message_parts.append(
            "Set credentials via: 1) Environment variables (S3_ACCESS_KEY/S3_SECRET_KEY), "
            "2) Config file storage section, or 3) 1Password integration"
        )

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
        """Load credentials using unified credential chain (mode-independent).

        Credential chain order:
        1. Environment variables (via DirectCredentialProvider)
        2. Config file storage section (via DirectCredentialProvider)
        3. 1Password (if configured)

        Returns:
            Dictionary containing storage credentials
        """
        try:
            # Try direct credentials first (env vars + config file)
            try:
                credentials = self._direct_provider.get_credentials()

                # If we got credentials with keys, use them
                if credentials.get("access_key") and credentials.get("secret_key"):
                    return credentials

                # If we got config but no keys, try 1Password as fallback
                self.logger.debug("No access keys in direct credentials, checking 1Password")
                config_data = self.config.load_config()
                storage_config = config_data.get("storage", {})

                if storage_config.get("use_1password", False):
                    onepassword_creds = self._onepassword_provider.get_credentials()
                    # Merge 1Password credentials with storage config
                    credentials["access_key"] = onepassword_creds["access_key"]
                    credentials["secret_key"] = onepassword_creds["secret_key"]
                    return credentials

                # Return credentials even without keys (validation happens later)
                return credentials

            except CredentialError as e:
                # If direct provider fails completely, try 1Password
                self.logger.debug(f"Direct credentials failed: {e.message}, trying 1Password")
                config_data = self.config.load_config()
                storage_config = config_data.get("storage", {})

                if storage_config.get("use_1password", False):
                    return self._onepassword_provider.get_credentials()

                # Re-raise the original error if no 1Password fallback
                raise

        except CredentialError:
            # Re-raise credential errors as-is
            raise
        except Exception as e:
            raise CredentialError(
                "Failed to load credentials",
                "Check configuration and ensure credentials are properly configured",
                f"Unexpected error: {e}",
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

            # Check required fields
            required_fields = ["endpoint", "bucket"]
            for field in required_fields:
                if not credentials.get(field):
                    return False, f"Missing required credential field: {field}"

            # Check that credentials are available (mode-independent after Phase 1)
            if credentials.get("access_key") is None or credentials.get("secret_key") is None:
                return False, (
                    "Credentials not available. Set via environment variables, "
                    "config file storage section, or 1Password integration."
                )

            # Test credentials with rclone (works with any S3-compatible backend)
            return self.test_credentials_with_rclone()
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
        """Get the source of the current credentials (mode-independent).

        Returns:
            String describing the credential source
        """
        # Check direct provider first (env vars or config file)
        try:
            self._direct_provider.get_credentials()
            source = self._direct_provider.get_source_name()
            # If direct provider has credentials, use it
            if source != "none":
                return source
        except CredentialError:
            pass

        # Check if 1Password is configured and in use
        try:
            config_data = self.config.load_config()
            storage_config = config_data.get("storage", {})
            if storage_config.get("use_1password", False):
                return self._onepassword_provider.get_source_name()
        except Exception:
            pass

        return "none"
