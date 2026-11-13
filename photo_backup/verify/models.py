"""
Data models for the verification module.

This module contains all dataclasses and enums used by the verification system.
"""

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from pathlib import Path


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

    Hash Comparison support dataclass.
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

    THash Comparison result dataclass.
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

    Repair Function result dataclass.
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

    Verification Report dataclass.
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
