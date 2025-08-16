"""
Rclone-based credential validator for S3-compatible storage.
"""

import logging
import subprocess
import tempfile
from contextlib import suppress
from typing import Any

from pathlib import Path

from .base import CredentialValidator


class RcloneCredentialValidator(CredentialValidator):
    """Validator that uses rclone to test S3-compatible storage credentials."""

    def __init__(self, config):
        """Initialize the rclone credential validator.

        Args:
            config: Configuration object containing storage settings
        """
        super().__init__(config)
        self.logger = logging.getLogger("photo_backup.credentials.validators.rclone")

    def validate_credentials(self, credentials: dict[str, Any]) -> tuple[bool, str]:
        """Validate credentials by attempting to connect to S3-compatible storage.

        Args:
            credentials: Dictionary containing credentials to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Check if rclone is available
            if not self._check_rclone_available():
                suggestion = "Install rclone from https://rclone.org/install/"
                if self.config.is_test_mode():
                    suggestion += " For test mode, also ensure Minio container is running with 'docker start minio'"
                return False, f"rclone is not available - cannot test credentials. {suggestion}"

            try:
                # Create a temporary rclone config for testing
                config_content = self._build_rclone_config(credentials)

                # Write config to temporary file
                with tempfile.NamedTemporaryFile(mode="w", suffix=".conf", delete=False) as temp_config:
                    temp_config.write(config_content)
                    temp_config_path = temp_config.name

                try:
                    # Test the connection with a simple lsd command (lists buckets)
                    # Use shorter timeout for test mode
                    timeout_seconds = 10.0 if self.config.is_test_mode() else 30.0
                    result = subprocess.run(
                        ["rclone", "lsd", "test:", "--config", temp_config_path],
                        capture_output=True,
                        text=True,
                        timeout=timeout_seconds,
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

                finally:
                    # Clean up temporary config file
                    with suppress(Exception):
                        Path(temp_config_path).unlink()

            except subprocess.TimeoutExpired:
                suggestion = "Check network connectivity"
                if self.config.is_test_mode():
                    suggestion += " and ensure Minio container is running"
                return False, f"rclone test timed out - {suggestion}"
            except Exception as e:
                return False, f"Error testing credentials with rclone: {e}"

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
        # Ensure endpoint has proper scheme
        endpoint = credentials["endpoint"]
        if not endpoint.startswith(("http://", "https://")):
            endpoint = f"https://{endpoint}" if credentials["use_ssl"] else f"http://{endpoint}"

        config = f"""[test]
type = s3
provider = Other
access_key_id = {credentials["access_key"]}
secret_access_key = {credentials["secret_key"]}
endpoint = {endpoint}
region = {credentials["region"]}
use_ssl = {str(credentials["use_ssl"]).lower()}
"""
        return config

    def get_validator_name(self) -> str:
        """Get the name of this validator.

        Returns:
            String describing the validator
        """
        return "rclone"
