"""
Remote file lister for S3-compatible storage.

This module provides functionality to list files from remote storage
using rclone, including their hashes for verification.
"""

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
provider = Wasabi
access_key_id = {credentials["access_key"]}
secret_access_key = {credentials["secret_key"]}
endpoint = {endpoint}
region = {credentials["region"]}
use_ssl = {str(credentials["use_ssl"]).lower()}
"""
        return config

    # Separator between size and path in `rclone lsf --format sp` output. Size
    # is always the first (numeric) field, so splitting on the FIRST occurrence
    # is safe even if a path itself contains this character.
    _LSF_SEP = "|"

    def list_remote_files(self, remote_path: str) -> list[FileHash]:
        """List files in remote storage with their sizes.

        Uses `rclone lsf --format sp` (size + path only). This deliberately
        avoids `lsjson` and per-object hash/modtime, all of which trigger a
        HEAD request per object on S3/Wasabi and make listing ~200k objects take
        >30 minutes. The plain size+path listing completes in ~30s. Verification
        compares by size + existence (see verifier.compare_hashes); returned
        FileHash objects have hash_md5=None.

        Args:
            remote_path: Remote path (e.g., 'bucket/prefix')

        Returns:
            List of FileHash objects for remote files

        Raises:
            RuntimeError: If rclone command fails
        """
        cmd = [
            "rclone",
            "lsf",
            "--files-only",
            "--recursive",
            # --fast-list collapses the slow directory-style walk into one flat
            # recursive listing, cutting S3 API calls on many-object buckets.
            "--fast-list",
            # "sp" = size then path; nothing that requires per-object metadata.
            "--format",
            "sp",
            "--separator",
            self._LSF_SEP,
            f"test:{remote_path}",
        ]

        # Even the fast listing can grow with bucket size, so the timeout is
        # configurable (default is generous relative to the ~30s typical).
        timeout_seconds = float(self.config.get("verification.remote_list_timeout_seconds", 1800))

        # Create temporary config file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".conf", delete=False) as config_file:
            config_content = self._build_rclone_config()
            config_file.write(config_content)
            config_file.flush()
            config_path = config_file.name

        try:
            # Add config file to command
            cmd.extend(["--config", config_path])

            self.logger.info(f"Listing remote files: rclone lsf test:{remote_path}")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_seconds,
            )

            if result.returncode != 0:
                error_msg = result.stderr.strip() if result.stderr else "Unknown error"
                # Handle empty bucket case gracefully
                if "directory not found" in error_msg.lower():
                    self.logger.info(f"Remote path is empty or does not exist: {remote_path}")
                    return []
                raise RuntimeError(f"rclone lsf failed: {error_msg}")

            return self._parse_lsf_output(result.stdout)

        except subprocess.TimeoutExpired as e:
            raise RuntimeError(
                f"rclone lsf timed out after {timeout_seconds:.0f}s "
                f"(raise verification.remote_list_timeout_seconds if the bucket is very large)"
            ) from e
        finally:
            # Clean up temp config file
            try:
                os.unlink(config_path)
            except Exception as e:
                self.logger.warning(f"Failed to clean up config file: {e}")

    def _parse_lsf_output(self, output: str) -> list[FileHash]:
        """Parse `rclone lsf --format sp` output into FileHash objects.

        Each non-empty line is ``<size><sep><path>``. Split on the first
        separator only, so paths containing the separator are preserved.

        Args:
            output: Text output from rclone lsf

        Returns:
            List of FileHash objects (path + size; hash_md5 is None)
        """
        file_hashes = []

        for line in output.splitlines():
            if not line:
                continue
            size_str, sep, path = line.partition(self._LSF_SEP)
            if not sep or not path:
                self.logger.warning(f"Skipping unparseable lsf line: {line[:120]!r}")
                continue
            try:
                size = int(size_str)
            except ValueError:
                self.logger.warning(f"Skipping lsf line with non-numeric size: {line[:120]!r}")
                continue
            file_hashes.append(FileHash(path=path, size=size, hash_md5=None))

        self.logger.info(f"Found {len(file_hashes)} files in remote storage")
        return file_hashes
