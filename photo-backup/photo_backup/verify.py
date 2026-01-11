"""
Verification module for photo backup system.

This module provides functionality to verify the integrity of backed up files
by comparing local and remote hashes, and supports repair operations.

Tasks 93-95: Create Verify Module, Hash Calculation, Remote Listing
"""

import hashlib
import json
import logging
import os
import subprocess
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from pathlib import Path

from .config.config import Config
from .credentials.manager import CredentialManager


class VerificationStatus(Enum):
    """Status of a verification operation."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class FileHash:
    """Represents a file with its hash information."""

    path: str
    size: int
    hash_md5: str | None = None
    hash_type: str = "md5"
    modified_time: str | None = None

    def __eq__(self, other: object) -> bool:
        """Compare two FileHash objects by path and hash."""
        if not isinstance(other, FileHash):
            return NotImplemented
        return self.path == other.path and self.hash_md5 == other.hash_md5


@dataclass
class VerificationJob:
    """Represents a single verification operation."""

    source_path: str
    destination: str
    status: VerificationStatus = VerificationStatus.PENDING
    error: str | None = None
    local_files: list[FileHash] = field(default_factory=list)
    remote_files: list[FileHash] = field(default_factory=list)
    mismatches: list[dict[str, Any]] = field(default_factory=list)
    missing_remote: list[str] = field(default_factory=list)
    missing_local: list[str] = field(default_factory=list)

    def __repr__(self) -> str:
        return f"VerificationJob(source='{self.source_path}', dest='{self.destination}', status='{self.status.value}')"


@dataclass
class VerificationResult:
    """Result of a verification operation."""

    success: bool
    total_files: int = 0
    verified_files: int = 0
    mismatched_files: int = 0
    missing_remote: int = 0
    missing_local: int = 0
    errors: list[str] = field(default_factory=list)
    duration_seconds: float = 0.0

    def get_summary(self) -> str:
        """Get a human-readable summary of the verification result."""
        lines = [
            f"Verification {'PASSED' if self.success else 'FAILED'}",
            f"  Total files checked: {self.total_files}",
            f"  Verified (matching): {self.verified_files}",
            f"  Mismatched: {self.mismatched_files}",
            f"  Missing on remote: {self.missing_remote}",
            f"  Missing locally: {self.missing_local}",
            f"  Duration: {self.duration_seconds:.2f}s",
        ]
        if self.errors:
            lines.append(f"  Errors: {len(self.errors)}")
            for error in self.errors[:5]:  # Show first 5 errors
                lines.append(f"    - {error}")
        return "\n".join(lines)


class HashCalculator:
    """Calculates file hashes with support for large files and progress reporting."""

    # Default chunk size for reading files (64KB)
    DEFAULT_CHUNK_SIZE = 64 * 1024

    def __init__(
        self,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        progress_callback: Callable[[int, int], None] | None = None,
    ):
        """Initialize the hash calculator.

        Args:
            chunk_size: Size of chunks to read at a time (in bytes)
            progress_callback: Optional callback(bytes_read, total_bytes) for progress
        """
        self.chunk_size = chunk_size
        self.progress_callback = progress_callback
        self.logger = logging.getLogger(__name__)

    def calculate_md5(self, file_path: str | Path) -> str:
        """Calculate MD5 hash of a file.

        Uses chunked reading to support large files without loading
        entire file into memory.

        Args:
            file_path: Path to the file to hash

        Returns:
            MD5 hash as hexadecimal string

        Raises:
            FileNotFoundError: If file does not exist
            PermissionError: If file cannot be read
            OSError: For other file system errors
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        if not file_path.is_file():
            raise ValueError(f"Not a file: {file_path}")

        total_size = file_path.stat().st_size
        bytes_read = 0

        md5_hash = hashlib.md5()

        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(self.chunk_size)
                if not chunk:
                    break

                md5_hash.update(chunk)
                bytes_read += len(chunk)

                # Report progress if callback provided
                if self.progress_callback:
                    self.progress_callback(bytes_read, total_size)

        return md5_hash.hexdigest()

    def calculate_file_hash(self, file_path: str | Path) -> FileHash:
        """Calculate hash and gather file information.

        Args:
            file_path: Path to the file

        Returns:
            FileHash object with file information and hash
        """
        file_path = Path(file_path)
        stat_info = file_path.stat()

        return FileHash(
            path=str(file_path),
            size=stat_info.st_size,
            hash_md5=self.calculate_md5(file_path),
            hash_type="md5",
            modified_time=str(stat_info.st_mtime),
        )

    def calculate_directory_hashes(
        self,
        directory: str | Path,
        exclude_patterns: list[str] | None = None,
    ) -> list[FileHash]:
        """Calculate hashes for all files in a directory.

        Args:
            directory: Directory to scan
            exclude_patterns: Optional list of glob patterns to exclude

        Returns:
            List of FileHash objects for all files
        """
        directory = Path(directory)
        if not directory.exists():
            raise FileNotFoundError(f"Directory not found: {directory}")

        exclude_patterns = exclude_patterns or [".*", "Thumbs.db", ".DS_Store"]
        file_hashes = []

        for file_path in directory.rglob("*"):
            if not file_path.is_file():
                continue

            # Check exclusions
            should_exclude = False
            for pattern in exclude_patterns:
                if file_path.match(pattern):
                    should_exclude = True
                    break

            if should_exclude:
                self.logger.debug(f"Excluding file: {file_path}")
                continue

            try:
                file_hash = self.calculate_file_hash(file_path)
                # Store relative path from directory
                file_hash.path = str(file_path.relative_to(directory))
                file_hashes.append(file_hash)
            except Exception as e:
                self.logger.warning(f"Failed to hash {file_path}: {e}")

        return file_hashes


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


class Verifier:
    """Core verifier for photo backup integrity checking."""

    def __init__(self, config: Config | None = None, test_mode: bool = False):
        """Initialize the verifier.

        Args:
            config: Configuration object. If None, creates a new one
            test_mode: Whether to run in test mode (uses Minio)
        """
        self.config = config or Config(test_mode=test_mode)
        self.test_mode = test_mode or self.config.is_test_mode()
        self.logger = logging.getLogger(__name__)
        self.credential_manager = CredentialManager(self.config)
        self.hash_calculator = HashCalculator()
        self.remote_lister = RemoteLister(self.config, self.credential_manager)

        # Load configuration
        self.config.load_config()

        self.logger.info(f"Verifier initialized in {'test' if self.test_mode else 'production'} mode")

    def create_verification_job(self) -> VerificationJob:
        """Create a verification job from current configuration.

        Returns:
            VerificationJob: Configured verification job
        """
        source_path = self.config.get("backup.source_path")
        destination = self.config.get("backup.destination")

        job = VerificationJob(source_path=source_path, destination=destination)

        self.logger.info(f"Created verification job: {job}")
        return job

    def get_verification_info(self) -> dict[str, Any]:
        """Get current verification configuration information.

        Returns:
            Dict containing verification configuration details
        """
        return {
            "mode": "test" if self.test_mode else "production",
            "source_path": self.config.get("backup.source_path"),
            "destination": self.config.get("backup.destination"),
            "endpoint": self.config.get("storage.endpoint"),
            "credential_status": self.credential_manager.get_credential_status(),
        }

    def calculate_local_hashes(
        self,
        source_path: str | None = None,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> list[FileHash]:
        """Calculate hashes for all local files.

        Args:
            source_path: Path to local directory (uses config if None)
            progress_callback: Optional callback for progress reporting

        Returns:
            List of FileHash objects for local files
        """
        if source_path is None:
            source_path = self.config.get("backup.source_path")

        if not source_path:
            raise ValueError("No source path configured")

        # Set progress callback if provided
        if progress_callback:
            self.hash_calculator.progress_callback = progress_callback

        self.logger.info(f"Calculating hashes for local files in: {source_path}")
        return self.hash_calculator.calculate_directory_hashes(source_path)

    def list_remote_files(self, remote_path: str | None = None) -> list[FileHash]:
        """List files in remote storage.

        Args:
            remote_path: Remote path (uses config destination if None)

        Returns:
            List of FileHash objects for remote files
        """
        if remote_path is None:
            destination = self.config.get("backup.destination")
            # Extract bucket/path from destination
            remote_path = destination.split(":", 1)[1] if ":" in destination else destination

        if not remote_path:
            raise ValueError("No remote path configured")

        self.logger.info(f"Listing remote files in: {remote_path}")
        return self.remote_lister.list_remote_files(remote_path)

    def set_progress_callback(self, callback: Callable[[int, int], None]) -> None:
        """Set progress callback for hash calculations.

        Args:
            callback: Callback function(bytes_processed, total_bytes)
        """
        self.hash_calculator.progress_callback = callback
