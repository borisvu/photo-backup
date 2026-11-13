"""
1Password credential provider for secure credential storage.
"""

import json
import logging
import os
import subprocess
from typing import TYPE_CHECKING, Any

from ..exceptions import CredentialError
from ..session.onepassword import OnePasswordSessionManager
from .base import CredentialProvider

if TYPE_CHECKING:
    from ...config.config import Config


class OnePasswordCredentialProvider(CredentialProvider):
    """Provider for credentials stored in 1Password."""

    def __init__(self, config: "Config") -> None:
        """Initialize the 1Password credential provider.

        Args:
            config: Configuration object containing storage settings
        """
        super().__init__(config)
        self.logger = logging.getLogger("photo_backup.credentials.onepassword")
        self.session_manager = OnePasswordSessionManager()

    def get_credentials(self) -> dict[str, Any]:
        """Get credentials from 1Password.

        Returns:
            Dictionary containing storage credentials

        Raises:
            CredentialError: If credentials cannot be retrieved
        """
        try:
            config_data = self.config.load_config()
            storage_config = config_data.get("storage", {})

            # Retrieve credentials from 1Password
            access_key, secret_key = self._retrieve_credentials_from_1password()

            if not access_key or not secret_key:
                raise CredentialError(
                    "Failed to retrieve credentials from 1Password",
                    "Check 1Password item configuration and ensure item exists",
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
                f"1Password credentials loaded: endpoint={credentials['endpoint']}, bucket={credentials['bucket']}"
            )
            return credentials

        except CredentialError:
            # Re-raise credential errors as-is
            raise
        except Exception as e:
            raise CredentialError(
                "Failed to load 1Password credentials",
                "Check 1Password configuration and ensure item exists",
                f"Unexpected error: {e}",
            ) from e

    def _retrieve_credentials_from_1password(self) -> tuple[str | None, str | None]:
        """Retrieve credentials from 1Password.

        Returns:
            Tuple of (access_key, secret_key) or (None, None) if retrieval fails
        """
        # Check if 1Password CLI is available
        is_available, message = self._check_op_cli()
        if not is_available:
            raise CredentialError(
                "1Password CLI not available", "Install 1Password CLI and ensure 'op' command is in PATH", message
            )

        # Get session token (handles authentication if needed)
        session_token = self.session_manager.get_session_token()

        try:
            # Get the item reference from config or use default
            config_data = self.config.load_config()
            storage_config = config_data.get("storage", {})
            item_ref = storage_config.get("1password_item", "Wasabi S3 Credentials")

            self.logger.debug(f"Retrieving credentials from 1Password item: {item_ref}")

            # Build command with session token if available
            cmd = ["op", "item", "get", item_ref, "--format=json"]
            env = os.environ.copy()

            if session_token:
                env["OP_SESSION_1password"] = session_token

            # Retrieve the item from 1Password
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30.0, env=env)

            if result.returncode != 0:
                error_msg = result.stderr.strip()
                self.logger.error(f"1Password command failed: {error_msg}")

                # Check if it's a session-related error and clear the session
                if "session" in error_msg.lower() or "authentication" in error_msg.lower():
                    self.logger.debug("Clearing invalid session token")
                    self.session_manager.clear_session()
                    raise CredentialError(
                        "1Password authentication failed",
                        "Run 'op signin' manually to authenticate with 1Password",
                        error_msg,
                    )

                # Check for specific error types
                if "not found" in error_msg.lower():
                    raise CredentialError(
                        f"1Password item '{item_ref}' not found",
                        f"Create a secure note in 1Password named '{item_ref}' with access_key and secret_key fields",
                        error_msg,
                    )
                elif "timeout" in error_msg.lower():
                    raise CredentialError(
                        "1Password command timed out", "Check network connectivity and try again", error_msg
                    )
                else:
                    raise CredentialError(
                        "1Password command failed", "Check 1Password CLI installation and authentication", error_msg
                    )

            # Parse the JSON response
            try:
                item_data = json.loads(result.stdout)
            except json.JSONDecodeError as e:
                raise CredentialError(
                    "Invalid JSON response from 1Password",
                    "Check 1Password CLI version and item format",
                    f"JSON parse error: {e}",
                ) from e

            # Extract credentials from the item
            access_key = self._extract_field_from_1password_item(item_data, "access_key")
            secret_key = self._extract_field_from_1password_item(item_data, "secret_key")

            if access_key and secret_key:
                self.logger.debug("Successfully retrieved credentials from 1Password")
                return access_key, secret_key
            else:
                missing_fields = []
                if not access_key:
                    missing_fields.append("access_key")
                if not secret_key:
                    missing_fields.append("secret_key")

                raise CredentialError(
                    f"Missing required fields in 1Password item: {', '.join(missing_fields)}",
                    f"Ensure the 1Password item '{item_ref}' contains fields: {', '.join(missing_fields)}",
                    "Fields can be named 'access_key'/'Access Key' and 'secret_key'/'Secret Key'",
                )

        except CredentialError:
            # Re-raise credential errors as-is
            raise
        except subprocess.TimeoutExpired:
            raise CredentialError(
                "1Password command timed out",
                "Check network connectivity and 1Password service status",
                "Command exceeded 30-second timeout",
            ) from None
        except Exception as e:
            raise CredentialError(
                "Unexpected error retrieving credentials from 1Password",
                "Check 1Password CLI installation and try again",
                f"Error: {e}",
            ) from e

    def _extract_field_from_1password_item(self, item_data: dict[str, Any], field_name: str) -> str | None:
        """Extract a field value from a 1Password item.

        Args:
            item_data: The 1Password item data
            field_name: The name of the field to extract

        Returns:
            The field value or None if not found
        """
        try:
            # 1Password items have a 'fields' array with 'id' and 'value' properties
            fields = item_data.get("fields", [])

            for field in fields:
                if field.get("id") == field_name:
                    value: str | None = field.get("value")
                    return value

            # If not found by ID, try to find by label (case-insensitive)
            for field in fields:
                label = field.get("label", "").lower()
                # Try exact match first
                if label == field_name.lower():
                    exact_value: str | None = field.get("value")
                    return exact_value
                # Try partial match (e.g., "Access Key" matches "access_key")
                if field_name.lower() in label.replace(" ", "_") or field_name.lower() in label.replace(" ", ""):
                    partial_value: str | None = field.get("value")
                    return partial_value

            self.logger.warning(f"Field '{field_name}' not found in 1Password item")
            return None

        except Exception as e:
            self.logger.error(f"Error extracting field '{field_name}' from 1Password item: {e}")
            return None

    def _check_op_cli(self) -> tuple[bool, str]:
        """Check if 1Password CLI is available and compatible.

        Returns:
            Tuple of (is_available, message)
        """
        try:
            # Check if op command exists
            result = subprocess.run(["op", "--version"], capture_output=True, text=True, timeout=10.0)

            if result.returncode == 0:
                version = result.stdout.strip()
                # Basic version check - 1Password CLI v2+ is required
                # Version format can be "2.x.x" or "v2.x.x"
                if (
                    version.startswith("2.")
                    or version.startswith("v2.")
                    or version.startswith("1.")
                    or version.startswith("v1.")
                ):
                    return True, f"1Password CLI available: {version}"
                else:
                    return False, f"1Password CLI version not supported: {version}"
            else:
                return False, f"1Password CLI command failed: {result.stderr.strip()}"

        except subprocess.TimeoutExpired:
            return False, "1Password CLI command timed out"
        except FileNotFoundError:
            return False, "1Password CLI not found in PATH"
        except Exception as e:
            return False, f"Error checking 1Password CLI: {e!s}"

    def get_source_name(self) -> str:
        """Get the name of this credential source.

        Returns:
            String describing the credential source
        """
        return "1password"
