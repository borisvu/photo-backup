"""
Verification module for photo backup system.

This module provides functionality to verify the integrity of backed up files
by comparing local and remote hashes, and supports repair operations.

Tasks 93-95: Create Verify Module, Hash Calculation, Remote Listing
Tasks 96-98: Hash Comparison, Repair Function, Verification Report
"""

import contextlib
import hashlib
import json
import logging
import os
import subprocess
import tempfile
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
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


@dataclass
class FileMismatch:
    """Represents a file with mismatched hashes between local and remote.

    Task 96: Hash Comparison support dataclass.
    """

    path: str
    local_hash: str | None
    remote_hash: str | None
    local_size: int
    remote_size: int
    mismatch_type: str  # "hash", "size", "both"

    def __repr__(self) -> str:
        return f"FileMismatch(path='{self.path}', type='{self.mismatch_type}')"


@dataclass
class ComparisonResult:
    """Result of comparing local and remote file hashes.

    Task 96: Hash Comparison result dataclass.
    """

    # Files that match perfectly
    matched_files: list[str] = field(default_factory=list)

    # Files with hash mismatches
    mismatched_files: list[FileMismatch] = field(default_factory=list)

    # Files present locally but not on remote
    missing_remote: list[FileHash] = field(default_factory=list)

    # Files present on remote but not locally
    missing_local: list[FileHash] = field(default_factory=list)

    # Timing information
    comparison_time_seconds: float = 0.0

    @property
    def total_local_files(self) -> int:
        """Total number of local files checked."""
        return len(self.matched_files) + len(self.mismatched_files) + len(self.missing_remote)

    @property
    def total_remote_files(self) -> int:
        """Total number of remote files checked."""
        return len(self.matched_files) + len(self.mismatched_files) + len(self.missing_local)

    @property
    def has_issues(self) -> bool:
        """Check if there are any verification issues."""
        return bool(self.mismatched_files or self.missing_remote or self.missing_local)

    def get_summary(self) -> str:
        """Get a human-readable summary of the comparison."""
        status = "ISSUES FOUND" if self.has_issues else "ALL MATCHED"
        lines = [
            f"Comparison Result: {status}",
            f"  Matched files: {len(self.matched_files)}",
            f"  Mismatched files: {len(self.mismatched_files)}",
            f"  Missing on remote: {len(self.missing_remote)}",
            f"  Missing locally: {len(self.missing_local)}",
            f"  Comparison time: {self.comparison_time_seconds:.2f}s",
        ]
        return "\n".join(lines)


@dataclass
class RepairResult:
    """Result of a repair operation.

    Task 97: Repair Function result dataclass.
    """

    # Successfully repaired files
    repaired_files: list[str] = field(default_factory=list)

    # Files that failed to repair
    failed_files: list[dict[str, Any]] = field(default_factory=list)

    # Files that were verified after repair
    verified_after_repair: list[str] = field(default_factory=list)

    # Total repair time
    repair_time_seconds: float = 0.0

    @property
    def success(self) -> bool:
        """Check if all repairs were successful."""
        return len(self.failed_files) == 0 and len(self.repaired_files) > 0

    @property
    def all_verified(self) -> bool:
        """Check if all repaired files were verified."""
        return set(self.repaired_files) == set(self.verified_after_repair)

    def get_summary(self) -> str:
        """Get a human-readable summary of the repair operation."""
        status = "SUCCESS" if self.success else "PARTIAL" if self.repaired_files else "FAILED"
        lines = [
            f"Repair Result: {status}",
            f"  Repaired: {len(self.repaired_files)}",
            f"  Failed: {len(self.failed_files)}",
            f"  Verified after repair: {len(self.verified_after_repair)}",
            f"  Repair time: {self.repair_time_seconds:.2f}s",
        ]
        if self.failed_files:
            lines.append("  Failed files:")
            for fail in self.failed_files[:5]:
                lines.append(f"    - {fail.get('path', 'unknown')}: {fail.get('error', 'unknown error')}")
        return "\n".join(lines)


@dataclass
class VerificationReport:
    """Detailed verification report with all issues and statistics.

    Task 98: Verification Report dataclass.
    """

    # Report metadata
    report_id: str = ""
    timestamp: str = ""
    source_path: str = ""
    destination: str = ""
    mode: str = "test"

    # Comparison results
    comparison_result: ComparisonResult | None = None

    # Repair results (if repair was performed)
    repair_result: RepairResult | None = None

    # Overall statistics
    total_files_checked: int = 0
    total_bytes_checked: int = 0
    verification_passed: bool = False

    # Timing
    total_duration_seconds: float = 0.0

    # Errors encountered
    errors: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Initialize report ID and timestamp if not set."""
        if not self.report_id:
            # Use time_ns for higher precision unique IDs
            self.report_id = f"verify-{time.time_ns()}"
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> dict[str, Any]:
        """Convert report to dictionary format."""
        result: dict[str, Any] = {
            "report_id": self.report_id,
            "timestamp": self.timestamp,
            "source_path": self.source_path,
            "destination": self.destination,
            "mode": self.mode,
            "verification_passed": self.verification_passed,
            "total_files_checked": self.total_files_checked,
            "total_bytes_checked": self.total_bytes_checked,
            "total_duration_seconds": self.total_duration_seconds,
            "errors": self.errors,
        }

        if self.comparison_result:
            result["comparison"] = {
                "matched_files": len(self.comparison_result.matched_files),
                "mismatched_files": [
                    {
                        "path": m.path,
                        "local_hash": m.local_hash,
                        "remote_hash": m.remote_hash,
                        "local_size": m.local_size,
                        "remote_size": m.remote_size,
                        "mismatch_type": m.mismatch_type,
                    }
                    for m in self.comparison_result.mismatched_files
                ],
                "missing_remote": [f.path for f in self.comparison_result.missing_remote],
                "missing_local": [f.path for f in self.comparison_result.missing_local],
                "comparison_time_seconds": self.comparison_result.comparison_time_seconds,
            }

        if self.repair_result:
            result["repair"] = {
                "repaired_files": self.repair_result.repaired_files,
                "failed_files": self.repair_result.failed_files,
                "verified_after_repair": self.repair_result.verified_after_repair,
                "repair_time_seconds": self.repair_result.repair_time_seconds,
            }

        return result

    def to_json(self, indent: int = 2) -> str:
        """Convert report to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    def to_text(self) -> str:
        """Generate human-readable text report."""
        lines = [
            "=" * 60,
            "VERIFICATION REPORT",
            "=" * 60,
            f"Report ID: {self.report_id}",
            f"Timestamp: {self.timestamp}",
            f"Mode: {self.mode}",
            f"Source: {self.source_path}",
            f"Destination: {self.destination}",
            "",
            "-" * 60,
            "SUMMARY",
            "-" * 60,
            f"Status: {'PASSED' if self.verification_passed else 'FAILED'}",
            f"Total files checked: {self.total_files_checked}",
            f"Total bytes checked: {self._format_bytes(self.total_bytes_checked)}",
            f"Total duration: {self.total_duration_seconds:.2f}s",
            "",
        ]

        if self.comparison_result:
            lines.extend(
                [
                    "-" * 60,
                    "COMPARISON RESULTS",
                    "-" * 60,
                    f"Matched files: {len(self.comparison_result.matched_files)}",
                    f"Mismatched files: {len(self.comparison_result.mismatched_files)}",
                    f"Missing on remote: {len(self.comparison_result.missing_remote)}",
                    f"Missing locally: {len(self.comparison_result.missing_local)}",
                    "",
                ]
            )

            if self.comparison_result.mismatched_files:
                lines.append("Mismatched Files:")
                for mismatch in self.comparison_result.mismatched_files[:10]:
                    lines.append(f"  - {mismatch.path}")
                    lines.append(f"    Local hash:  {mismatch.local_hash}")
                    lines.append(f"    Remote hash: {mismatch.remote_hash}")
                if len(self.comparison_result.mismatched_files) > 10:
                    lines.append(f"  ... and {len(self.comparison_result.mismatched_files) - 10} more")
                lines.append("")

            if self.comparison_result.missing_remote:
                lines.append("Missing on Remote:")
                for fh in self.comparison_result.missing_remote[:10]:
                    lines.append(f"  - {fh.path}")
                if len(self.comparison_result.missing_remote) > 10:
                    lines.append(f"  ... and {len(self.comparison_result.missing_remote) - 10} more")
                lines.append("")

            if self.comparison_result.missing_local:
                lines.append("Missing Locally:")
                for fh in self.comparison_result.missing_local[:10]:
                    lines.append(f"  - {fh.path}")
                if len(self.comparison_result.missing_local) > 10:
                    lines.append(f"  ... and {len(self.comparison_result.missing_local) - 10} more")
                lines.append("")

        if self.repair_result:
            lines.extend(
                [
                    "-" * 60,
                    "REPAIR RESULTS",
                    "-" * 60,
                    f"Repaired: {len(self.repair_result.repaired_files)}",
                    f"Failed: {len(self.repair_result.failed_files)}",
                    f"Verified: {len(self.repair_result.verified_after_repair)}",
                    "",
                ]
            )

        if self.errors:
            lines.extend(
                [
                    "-" * 60,
                    "ERRORS",
                    "-" * 60,
                ]
            )
            for error in self.errors[:10]:
                lines.append(f"  - {error}")
            if len(self.errors) > 10:
                lines.append(f"  ... and {len(self.errors) - 10} more")
            lines.append("")

        lines.append("=" * 60)
        return "\n".join(lines)

    def save_to_file(self, file_path: str | Path, format: str = "json") -> bool:
        """Save report to file.

        Args:
            file_path: Path to save the report
            format: Output format ('json' or 'text')

        Returns:
            True if saved successfully, False otherwise
        """
        file_path = Path(file_path)

        try:
            # Ensure parent directory exists
            file_path.parent.mkdir(parents=True, exist_ok=True)

            content = self.to_json() if format == "json" else self.to_text()

            with open(file_path, "w") as f:
                f.write(content)

            return True
        except Exception:
            return False

    @staticmethod
    def _format_bytes(bytes_count: int) -> str:
        """Format byte count as human-readable string."""
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if bytes_count < 1024:
                return f"{bytes_count:.1f} {unit}"
            bytes_count = bytes_count // 1024
        return f"{bytes_count:.1f} PB"


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

    # ==========================================================================
    # Task 96: Hash Comparison
    # ==========================================================================

    def compare_hashes(
        self,
        local_files: list[FileHash],
        remote_files: list[FileHash],
    ) -> ComparisonResult:
        """Compare local and remote file hashes to find differences.

        Task 96: Hash Comparison implementation.

        This method matches files by their relative paths and compares their
        MD5 hashes to identify:
        - Files that match perfectly
        - Files with hash mismatches (possibly corrupted)
        - Files present locally but missing on remote
        - Files present on remote but missing locally

        Args:
            local_files: List of FileHash objects from local storage
            remote_files: List of FileHash objects from remote storage

        Returns:
            ComparisonResult with detailed comparison information
        """
        start_time = time.time()
        self.logger.info(f"Comparing {len(local_files)} local files with {len(remote_files)} remote files")

        # Build lookup dictionaries for O(1) access
        local_by_path: dict[str, FileHash] = {fh.path: fh for fh in local_files}
        remote_by_path: dict[str, FileHash] = {fh.path: fh for fh in remote_files}

        # Track results
        matched_files: list[str] = []
        mismatched_files: list[FileMismatch] = []
        missing_remote: list[FileHash] = []
        missing_local: list[FileHash] = []

        # Compare local files against remote
        for path, local_fh in local_by_path.items():
            if path in remote_by_path:
                remote_fh = remote_by_path[path]

                # Compare hashes
                if local_fh.hash_md5 and remote_fh.hash_md5:
                    if local_fh.hash_md5 == remote_fh.hash_md5:
                        matched_files.append(path)
                    else:
                        # Determine mismatch type
                        hash_mismatch = local_fh.hash_md5 != remote_fh.hash_md5
                        size_mismatch = local_fh.size != remote_fh.size

                        if hash_mismatch and size_mismatch:
                            mismatch_type = "both"
                        elif hash_mismatch:
                            mismatch_type = "hash"
                        else:
                            mismatch_type = "size"

                        mismatched_files.append(
                            FileMismatch(
                                path=path,
                                local_hash=local_fh.hash_md5,
                                remote_hash=remote_fh.hash_md5,
                                local_size=local_fh.size,
                                remote_size=remote_fh.size,
                                mismatch_type=mismatch_type,
                            )
                        )
                else:
                    # Can't compare if hash is missing - assume match for now
                    self.logger.warning(f"Missing hash for comparison: {path}")
                    matched_files.append(path)
            else:
                # File exists locally but not on remote
                missing_remote.append(local_fh)

        # Find files that exist on remote but not locally
        for path, remote_fh in remote_by_path.items():
            if path not in local_by_path:
                missing_local.append(remote_fh)

        # Calculate comparison time
        comparison_time = time.time() - start_time

        result = ComparisonResult(
            matched_files=matched_files,
            mismatched_files=mismatched_files,
            missing_remote=missing_remote,
            missing_local=missing_local,
            comparison_time_seconds=comparison_time,
        )

        self.logger.info(result.get_summary())
        return result

    # ==========================================================================
    # Task 97: Repair Function
    # ==========================================================================

    def repair_files(
        self,
        comparison_result: ComparisonResult,
        source_path: str | None = None,
        verify_after_repair: bool = True,
    ) -> RepairResult:
        """Re-upload files that have mismatches or are missing on remote.

        Task 97: Repair Function implementation.

        This method:
        1. Re-uploads files that have hash mismatches
        2. Uploads files that are missing on remote
        3. Optionally verifies files after upload

        Args:
            comparison_result: Result from compare_hashes() with files to repair
            source_path: Local source path (uses config if None)
            verify_after_repair: Whether to verify files after uploading

        Returns:
            RepairResult with repair operation details
        """
        start_time = time.time()

        if source_path is None:
            source_path = self.config.get("backup.source_path")

        if not source_path:
            raise ValueError("No source path configured")

        # Collect files that need repair
        files_to_repair: list[str] = []

        # Add mismatched files
        for mismatch in comparison_result.mismatched_files:
            files_to_repair.append(mismatch.path)

        # Add files missing on remote
        for fh in comparison_result.missing_remote:
            files_to_repair.append(fh.path)

        if not files_to_repair:
            self.logger.info("No files need repair")
            return RepairResult(repair_time_seconds=time.time() - start_time)

        self.logger.info(f"Repairing {len(files_to_repair)} files")

        repaired_files: list[str] = []
        failed_files: list[dict[str, Any]] = []
        verified_after_repair: list[str] = []

        # Repair each file
        for file_path in files_to_repair:
            try:
                success = self._repair_single_file(source_path, file_path)
                if success:
                    repaired_files.append(file_path)
                    self.logger.info(f"Repaired: {file_path}")
                else:
                    failed_files.append({"path": file_path, "error": "Upload failed"})
                    self.logger.error(f"Failed to repair: {file_path}")
            except Exception as e:
                failed_files.append({"path": file_path, "error": str(e)})
                self.logger.error(f"Error repairing {file_path}: {e}")

        # Verify after repair if requested
        if verify_after_repair and repaired_files:
            self.logger.info("Verifying repaired files...")
            for file_path in repaired_files:
                try:
                    if self._verify_repaired_file(source_path, file_path):
                        verified_after_repair.append(file_path)
                    else:
                        self.logger.warning(f"Verification failed after repair: {file_path}")
                except Exception as e:
                    self.logger.warning(f"Error verifying {file_path}: {e}")

        repair_time = time.time() - start_time

        result = RepairResult(
            repaired_files=repaired_files,
            failed_files=failed_files,
            verified_after_repair=verified_after_repair,
            repair_time_seconds=repair_time,
        )

        self.logger.info(result.get_summary())
        return result

    def _repair_single_file(self, source_path: str, file_path: str) -> bool:
        """Upload a single file to repair it on remote.

        Args:
            source_path: Base local source path
            file_path: Relative path of file to repair

        Returns:
            True if upload succeeded, False otherwise
        """
        # Build full local path
        full_local_path = Path(source_path) / file_path

        if not full_local_path.exists():
            self.logger.error(f"Local file not found: {full_local_path}")
            return False

        # Get destination
        destination = self.config.get("backup.destination")
        if not destination:
            raise ValueError("No destination configured")

        # Extract bucket/path from destination
        remote_path = destination.split(":", 1)[1] if ":" in destination else destination

        # Build rclone copy command for single file
        # rclone copyto source test:bucket/path --config config.conf
        cmd = [
            "rclone",
            "copyto",
            str(full_local_path),
            f"test:{remote_path}/{file_path}",
            "--checksum",
        ]

        # Create temporary config file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".conf", delete=False) as config_file:
            config_content = self.remote_lister._build_rclone_config()
            config_file.write(config_content)
            config_file.flush()
            config_path = config_file.name

        try:
            cmd.extend(["--config", config_path])

            self.logger.debug(f"Repair command: {' '.join(cmd[:4])}...")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120.0,  # 2 minute timeout per file
            )

            if result.returncode != 0:
                self.logger.error(f"rclone copyto failed: {result.stderr}")
                return False

            return True

        except subprocess.TimeoutExpired:
            self.logger.error(f"Timeout uploading {file_path}")
            return False
        except Exception as e:
            self.logger.error(f"Error uploading {file_path}: {e}")
            return False
        finally:
            with contextlib.suppress(Exception):
                os.unlink(config_path)

    def _verify_repaired_file(self, source_path: str, file_path: str) -> bool:
        """Verify a single file after repair by comparing hashes.

        Args:
            source_path: Base local source path
            file_path: Relative path of file to verify

        Returns:
            True if local and remote hashes match, False otherwise
        """
        # Calculate local hash
        full_local_path = Path(source_path) / file_path
        local_hash = self.hash_calculator.calculate_md5(full_local_path)

        # Get remote hash for this specific file
        destination = self.config.get("backup.destination")
        remote_path = destination.split(":", 1)[1] if ":" in destination else destination

        # Use rclone to get hash of specific remote file
        cmd = [
            "rclone",
            "md5sum",
            f"test:{remote_path}/{file_path}",
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".conf", delete=False) as config_file:
            config_content = self.remote_lister._build_rclone_config()
            config_file.write(config_content)
            config_file.flush()
            config_path = config_file.name

        try:
            cmd.extend(["--config", config_path])

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60.0,
            )

            if result.returncode != 0:
                self.logger.warning(f"Failed to get remote hash for {file_path}")
                return False

            # Parse md5sum output (format: "hash  filename")
            output = result.stdout.strip()
            if output:
                remote_hash = output.split()[0]
                return local_hash == remote_hash

            return False

        except Exception as e:
            self.logger.warning(f"Error verifying {file_path}: {e}")
            return False
        finally:
            with contextlib.suppress(Exception):
                os.unlink(config_path)

    # ==========================================================================
    # Task 98: Verification Report
    # ==========================================================================

    def generate_report(
        self,
        comparison_result: ComparisonResult,
        repair_result: RepairResult | None = None,
        local_files: list[FileHash] | None = None,
    ) -> VerificationReport:
        """Generate a detailed verification report.

        Task 98: Verification Report implementation.

        Args:
            comparison_result: Result from compare_hashes()
            repair_result: Optional result from repair_files()
            local_files: Optional list of local files for byte count

        Returns:
            VerificationReport with comprehensive verification details
        """
        # Calculate total bytes if local_files provided
        total_bytes = 0
        if local_files:
            total_bytes = sum(fh.size for fh in local_files)

        # Determine if verification passed
        verification_passed = not comparison_result.has_issues

        # If repair was performed, check if all repairs succeeded
        if repair_result:
            verification_passed = repair_result.success and repair_result.all_verified

        # Calculate total duration
        total_duration = comparison_result.comparison_time_seconds
        if repair_result:
            total_duration += repair_result.repair_time_seconds

        report = VerificationReport(
            source_path=self.config.get("backup.source_path", ""),
            destination=self.config.get("backup.destination", ""),
            mode="test" if self.test_mode else "production",
            comparison_result=comparison_result,
            repair_result=repair_result,
            total_files_checked=comparison_result.total_local_files,
            total_bytes_checked=total_bytes,
            verification_passed=verification_passed,
            total_duration_seconds=total_duration,
        )

        self.logger.info(f"Generated verification report: {report.report_id}")
        return report

    def run_full_verification(
        self,
        repair: bool = False,
        save_report: bool = False,
        report_path: str | None = None,
    ) -> VerificationReport:
        """Run a complete verification workflow.

        This is a convenience method that:
        1. Calculates local hashes
        2. Lists remote files
        3. Compares hashes
        4. Optionally repairs mismatches
        5. Generates and optionally saves a report

        Args:
            repair: Whether to repair any found issues
            save_report: Whether to save the report to file
            report_path: Custom path for the report file

        Returns:
            VerificationReport with all verification details
        """
        self.logger.info("Starting full verification...")
        start_time = time.time()

        errors: list[str] = []

        # Step 1: Calculate local hashes
        try:
            self.logger.info("Calculating local file hashes...")
            local_files = self.calculate_local_hashes()
            self.logger.info(f"Found {len(local_files)} local files")
        except Exception as e:
            errors.append(f"Failed to calculate local hashes: {e}")
            self.logger.error(errors[-1])
            # Return error report
            return VerificationReport(
                source_path=self.config.get("backup.source_path", ""),
                destination=self.config.get("backup.destination", ""),
                mode="test" if self.test_mode else "production",
                verification_passed=False,
                errors=errors,
                total_duration_seconds=time.time() - start_time,
            )

        # Step 2: List remote files
        try:
            self.logger.info("Listing remote files...")
            remote_files = self.list_remote_files()
            self.logger.info(f"Found {len(remote_files)} remote files")
        except Exception as e:
            errors.append(f"Failed to list remote files: {e}")
            self.logger.error(errors[-1])
            return VerificationReport(
                source_path=self.config.get("backup.source_path", ""),
                destination=self.config.get("backup.destination", ""),
                mode="test" if self.test_mode else "production",
                verification_passed=False,
                errors=errors,
                total_duration_seconds=time.time() - start_time,
            )

        # Step 3: Compare hashes
        self.logger.info("Comparing file hashes...")
        comparison_result = self.compare_hashes(local_files, remote_files)

        # Step 4: Optionally repair
        repair_result = None
        if repair and comparison_result.has_issues:
            self.logger.info("Repairing issues...")
            try:
                repair_result = self.repair_files(comparison_result)
            except Exception as e:
                errors.append(f"Repair failed: {e}")
                self.logger.error(errors[-1])

        # Step 5: Generate report
        report = self.generate_report(comparison_result, repair_result, local_files)
        report.errors = errors
        report.total_duration_seconds = time.time() - start_time

        # Step 6: Optionally save report
        if save_report:
            if report_path is None:
                # Default to state directory
                state_dir = Path.home() / ".photo-backup"
                if self.test_mode:
                    state_dir = state_dir / "test"
                report_path = str(state_dir / "reports" / f"{report.report_id}.json")

            if report.save_to_file(report_path, format="json"):
                self.logger.info(f"Report saved to: {report_path}")
            else:
                self.logger.warning(f"Failed to save report to: {report_path}")

        return report
