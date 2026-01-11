"""
Remote file lister for S3-compatible storage.

This module provides functionality to list files from remote storage
using rclone, including their hashes for verification.
"""

import json
import logging
import os
import subprocess
import tempfile

from ..config.config import Config
from ..credentials.manager import CredentialManager
from .models import FileHash


class RemoteLister:
    """Lists files from remote S3-compatible storage using rclone."""

    def __init__(self, config: Config, credential_manager: CredentialManager):
        """Initialize the remote lister.

        Args:
            config: Configuration object
            credential_manager: Credential manager for storage access
        """
        self.config = config
        self.credential_manager = credential_manager
        self.logger = logging.getLogger(__name__)

    def _build_rclone_config(self) -> str:
        """Build rclone configuration content.

        Returns:
            rclone configuration content as string
        """
        credentials = self.credential_manager.get_credentials()

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

    def list_remote_files(self, remote_path: str) -> list[FileHash]:
        """List files in remote storage with their hashes.

        Uses rclone lsjson with --hash flag to get file information
        including MD5 hashes.

        Args:
            remote_path: Remote path (e.g., 'bucket/prefix')

        Returns:
            List of FileHash objects for remote files

        Raises:
            RuntimeError: If rclone command fails
        """
        # Build rclone command
        # Format: rclone lsjson --hash test:bucket/path --config config.conf
        cmd = [
            "rclone",
            "lsjson",
            "--hash",
            "--recursive",
            f"test:{remote_path}",
        ]

        # Create temporary config file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".conf", delete=False) as config_file:
            config_content = self._build_rclone_config()
            config_file.write(config_content)
            config_file.flush()
            config_path = config_file.name

        try:
            # Add config file to command
            cmd.extend(["--config", config_path])

            self.logger.info(f"Listing remote files: rclone lsjson test:{remote_path}")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300.0,  # 5 minute timeout
            )

            if result.returncode != 0:
                error_msg = result.stderr.strip() if result.stderr else "Unknown error"
                # Handle empty bucket case gracefully
                if "directory not found" in error_msg.lower():
                    self.logger.info(f"Remote path is empty or does not exist: {remote_path}")
                    return []
                raise RuntimeError(f"rclone lsjson failed: {error_msg}")

            # Parse JSON output
            return self._parse_lsjson_output(result.stdout)

        except subprocess.TimeoutExpired as e:
            raise RuntimeError("rclone lsjson timed out after 5 minutes") from e
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Failed to parse rclone output as JSON: {e}") from e
        finally:
            # Clean up temp config file
            try:
                os.unlink(config_path)
            except Exception as e:
                self.logger.warning(f"Failed to clean up config file: {e}")

    def _parse_lsjson_output(self, output: str) -> list[FileHash]:
        """Parse rclone lsjson output into FileHash objects.

        Args:
            output: JSON output from rclone lsjson

        Returns:
            List of FileHash objects
        """
        if not output.strip():
            return []

        try:
            items = json.loads(output)
        except json.JSONDecodeError:
            self.logger.error(f"Invalid JSON output: {output[:200]}...")
            return []

        file_hashes = []

        for item in items:
            # Skip directories
            if item.get("IsDir", False):
                continue

            # Extract hash - rclone returns hashes in "Hashes" dict
            hashes = item.get("Hashes", {})
            md5_hash = hashes.get("MD5") or hashes.get("md5")

            file_hash = FileHash(
                path=item.get("Path", ""),
                size=item.get("Size", 0),
                hash_md5=md5_hash,
                hash_type="md5",
                modified_time=item.get("ModTime"),
            )
            file_hashes.append(file_hash)

        self.logger.info(f"Found {len(file_hashes)} files in remote storage")
        return file_hashes
