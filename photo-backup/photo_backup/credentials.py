"""
Credential management for photo backup system.

This module handles credential retrieval, validation, and management
for S3-compatible storage services, with support for direct credentials
and optional 1Password integration for test mode using Minio.
"""

import json
import logging
import os
import subprocess
import time
from typing import Any

from .config.config import Config


class CredentialError(Exception):
    """Exception raised for credential-related errors."""

    def __init__(self, message: str, suggestion: str = "", details: str = ""):
        """Initialize credential error.

        Args:
            message: Primary error message
            suggestion: Suggested fix or action
            details: Additional error details
        """
        self.message = message
        self.suggestion = suggestion
        self.details = details
        if suggestion:
            super().__init__(f"{message}. {suggestion}")
        else:
            super().__init__(message)


class CredentialManager:
    """Manages credentials for S3-compatible storage services."""

    def __init__(self, config: Config):
        """Initialize credential manager.

        Args:
            config: Configuration object containing storage settings
        """
        self.config = config
        self.logger = logging.getLogger("photo_backup.credentials")
        self._credentials: dict[str, Any] | None = None
        self._session_token: str | None = None
        self._session_expiry: float | None = None

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
            # Try to get credentials
            self.get_credentials()  # Just test if we can get credentials
            status["has_credentials"] = True
            status["credential_info"] = self.get_credential_info()

            # Test credentials if available
            is_valid, message = self.validate_credentials()
            status["validation"] = {"is_valid": is_valid, "message": message}

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
                return self._get_test_credentials()
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

    def _get_test_credentials(self) -> dict[str, Any]:
        """Get test mode credentials (Minio).

        Returns:
            Dictionary containing Minio test credentials
        """
        self.logger.debug("Loading test mode credentials (Minio)")

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

    def _get_production_credentials(self) -> dict[str, Any]:
        """Get production credentials (Wasabi) with direct credentials as primary method.

        Returns:
            Dictionary containing production credentials
        """
        self.logger.debug("Loading production credentials")

        try:
            config_data = self.config.load_config()
            storage_config = config_data.get("storage", {})

            # Try direct credentials first (environment variables or config file)
            access_key, secret_key = self._get_direct_credentials()

            if access_key and secret_key:
                self.logger.debug("Using direct credentials")
            else:
                # Fallback to 1Password if configured
                if storage_config.get("use_1password", False):
                    self.logger.debug("Direct credentials not available, trying 1Password")
                    access_key, secret_key = self._retrieve_credentials_from_1password()
                else:
                    self.logger.warning("No direct credentials available and 1Password not configured")

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
                f"Production credentials loaded: endpoint={credentials['endpoint']}, bucket={credentials['bucket']}"
            )
            return credentials
        except CredentialError:
            # Re-raise credential errors as-is
            raise
        except Exception as e:
            raise CredentialError(
                "Failed to load production credentials",
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

    def _retrieve_credentials_from_1password(self) -> tuple[str | None, str | None]:
        """Retrieve credentials from 1Password.

        Returns:
            Tuple of (access_key, secret_key) or (None, None) if retrieval fails
        """
        # Check if 1Password CLI is available
        is_available, message = check_op_cli()
        if not is_available:
            raise CredentialError(
                "1Password CLI not available", "Install 1Password CLI and ensure 'op' command is in PATH", message
            )

        # Get session token (handles authentication if needed)
        session_token = self._get_session_token()

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
                    self._clear_session()
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
                    return field.get("value")

            # If not found by ID, try to find by label (case-insensitive)
            for field in fields:
                label = field.get("label", "").lower()
                # Try exact match first
                if label == field_name.lower():
                    return field.get("value")
                # Try partial match (e.g., "Access Key" matches "access_key")
                if field_name.lower() in label.replace(" ", "_") or field_name.lower() in label.replace(" ", ""):
                    return field.get("value")

            self.logger.warning(f"Field '{field_name}' not found in 1Password item")
            return None

        except Exception as e:
            self.logger.error(f"Error extracting field '{field_name}' from 1Password item: {e}")
            return None

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

            # Check if rclone is available
            if not self._check_rclone_available():
                suggestion = "Install rclone from https://rclone.org/install/"
                if self.config.is_test_mode():
                    suggestion += " For test mode, also ensure Minio container is running with 'docker start minio'"
                return False, f"rclone is not available - cannot test credentials. {suggestion}"

            try:
                # Create a temporary rclone config for testing
                config_content = self._build_rclone_config(credentials)

                # Test the connection with a simple ls command
                result = subprocess.run(
                    ["rclone", "ls", f"test-{credentials['bucket']}", "--config", "-"],
                    input=config_content,
                    capture_output=True,
                    text=True,
                    timeout=30.0,
                )

                if result.returncode == 0:
                    return True, "Credentials validated successfully with rclone"
                else:
                    error_msg = result.stderr.strip()

                    # Test mode specific error handling
                    if self.config.is_test_mode():
                        if (
                            "connection refused" in error_msg.lower()
                            or "connect: no route to host" in error_msg.lower()
                        ):
                            return False, (
                                f"Cannot connect to Minio at {credentials['endpoint']}. "
                                "Start Minio container with: docker run -d --name minio -p 9000:9000 "
                                "minio/minio server /data"
                            )
                        elif "no such bucket" in error_msg.lower():
                            return False, (
                                f"Test bucket '{credentials['bucket']}' not found. "
                                "Create bucket in Minio or check bucket name in configuration"
                            )
                        elif "access denied" in error_msg.lower() or "403" in error_msg:
                            return False, (
                                "Access denied to Minio. "
                                "Check that Minio is running and credentials are correct (minioadmin/minioadmin)"
                            )
                        else:
                            return False, f"Minio test failed: {error_msg}"
                    else:
                        # Production mode error handling
                        if "Access Denied" in error_msg or "403" in error_msg:
                            return False, (
                                "Access denied - check credentials and bucket permissions. "
                                "Verify access key and secret key are correct"
                            )
                        elif "No such bucket" in error_msg or "404" in error_msg:
                            return False, (
                                f"Bucket '{credentials['bucket']}' not found. "
                                f"Create bucket in {credentials['endpoint']} or check bucket name"
                            )
                        elif "connection" in error_msg.lower():
                            return False, (
                                f"Cannot connect to {credentials['endpoint']}. "
                                "Check endpoint URL, network connectivity, and SSL settings"
                            )
                        else:
                            return False, f"rclone test failed: {error_msg}"

            except subprocess.TimeoutExpired:
                suggestion = "Check network connectivity"
                if self.config.is_test_mode():
                    suggestion += " and ensure Minio container is running"
                return False, f"rclone test timed out - {suggestion}"
            except Exception as e:
                return False, f"Error testing credentials with rclone: {e}"

        except CredentialError as e:
            return False, f"{e.message}. {e.suggestion}"
        except Exception as e:
            return False, f"Credential testing failed: {e}"

    def _check_rclone_available(self) -> bool:
        """Check if rclone is available in the system.

        Returns:
            True if rclone is available, False otherwise
        """
        try:
            result = subprocess.run(["rclone", "version"], capture_output=True, text=True, timeout=10.0)
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False

    def _build_rclone_config(self, credentials: dict[str, Any]) -> str:
        """Build rclone configuration content for testing.

        Args:
            credentials: Credentials dictionary

        Returns:
            rclone configuration content as string
        """
        config = f"""[test-{credentials["bucket"]}]
type = s3
provider = Other
access_key_id = {credentials["access_key"]}
secret_access_key = {credentials["secret_key"]}
endpoint = {credentials["endpoint"]}
region = {credentials["region"]}
use_ssl = {str(credentials["use_ssl"]).lower()}
"""
        return config

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
            return "test_mode"

        # Check environment variables first
        if os.environ.get("WASABI_ACCESS_KEY") or os.environ.get("S3_ACCESS_KEY"):
            return "environment_variables"

        # Check config file
        config_data = self.config.load_config()
        storage_config = config_data.get("storage", {})
        if storage_config.get("access_key"):
            return "config_file"

        # Check if 1Password is configured
        if storage_config.get("use_1password", False):
            return "1password"

        return "none"

    def _get_session_token(self) -> str | None:
        """Get a valid 1Password session token.

        Returns:
            Session token or None if not available/expired
        """
        # Skip session management in test mode
        if self.config.is_test_mode():
            return None

        # Check if we have a valid cached session
        if self._is_session_valid():
            self.logger.debug("Using cached 1Password session token")
            return self._session_token

        # Get a new session token
        return self._authenticate_session()

    def _is_session_valid(self) -> bool:
        """Check if the current session token is valid.

        Returns:
            True if session is valid, False otherwise
        """
        if not self._session_token or not self._session_expiry:
            return False

        # Check if session has expired (with 5-minute buffer)
        if time.time() > (self._session_expiry - 300):
            self.logger.debug("1Password session token expired")
            return False

        return True

    def _authenticate_session(self) -> str | None:
        """Authenticate with 1Password and get a session token.

        Returns:
            Session token or None if authentication failed
        """
        try:
            self.logger.debug("Authenticating with 1Password")

            # Sign in to 1Password (this will prompt for authentication)
            result = subprocess.run(["op", "signin"], capture_output=True, text=True, timeout=60.0)

            if result.returncode != 0:
                error_msg = result.stderr.strip()
                self.logger.error(f"1Password signin failed: {error_msg}")

                # Provide specific suggestions based on error
                if "timeout" in error_msg.lower():
                    raise CredentialError(
                        "1Password authentication timed out", "Check network connectivity and try again", error_msg
                    )
                elif "not found" in error_msg.lower():
                    raise CredentialError(
                        "1Password CLI not found", "Install 1Password CLI and ensure 'op' command is in PATH", error_msg
                    )
                else:
                    raise CredentialError(
                        "1Password authentication failed", "Run 'op signin' manually to authenticate", error_msg
                    )

            # Extract session token from output
            # 1Password CLI typically outputs the session token on success
            lines = result.stdout.strip().split("\n")
            session_token = None

            for line in lines:
                if line.startswith("export OP_SESSION_"):
                    # Extract token from export command
                    parts = line.split("=")
                    if len(parts) == 2:
                        session_token = parts[1].strip().strip('"')
                        break

            if not session_token:
                raise CredentialError(
                    "Failed to extract session token from 1Password",
                    "Try running 'op signin' manually and check output format",
                    "No session token found in 1Password output",
                )

            # Set session expiry (30 minutes from now)
            self._session_token = session_token
            self._session_expiry = time.time() + 1800  # 30 minutes

            self.logger.debug("Successfully authenticated with 1Password")
            return session_token

        except CredentialError:
            # Re-raise credential errors as-is
            raise
        except subprocess.TimeoutExpired:
            raise CredentialError(
                "1Password authentication timed out",
                "Check network connectivity and try again",
                "Authentication exceeded 60-second timeout",
            ) from None
        except Exception as e:
            raise CredentialError(
                "Unexpected error during 1Password authentication",
                "Check 1Password CLI installation and try again",
                f"Error: {e}",
            ) from e

    def _clear_session(self) -> None:
        """Clear the current session token."""
        self._session_token = None
        self._session_expiry = None
        self.logger.debug("Cleared 1Password session token")


def check_op_cli() -> tuple[bool, str]:
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


def check_op_cli_in_test_mode() -> tuple[bool, str]:
    """Check 1Password CLI availability, skipping in test mode.

    Returns:
        Tuple of (is_available, message)
    """
    # In test mode, we don't need 1Password CLI
    if os.environ.get("PHOTO_BACKUP_TEST_MODE") == "1":
        return True, "1Password CLI check skipped in test mode"

    return check_op_cli()
