"""
Error handling for backup operations.

This module provides error detection, categorization, and reporting
functionality for the backup system.
"""

import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, ClassVar


class ErrorType(Enum):
    """Categories of backup errors for better error handling and reporting."""

    PERMISSION_ERROR = "permission_error"
    NETWORK_ERROR = "network_error"
    AUTHENTICATION_ERROR = "authentication_error"
    STORAGE_ERROR = "storage_error"
    FILE_ERROR = "file_error"
    CONFIGURATION_ERROR = "configuration_error"
    TIMEOUT_ERROR = "timeout_error"
    UNKNOWN_ERROR = "unknown_error"


@dataclass
class BackupError:
    """Detailed backup error information."""

    error_type: ErrorType
    message: str
    file_path: str = ""
    line_number: int = 0
    raw_output: str = ""
    suggestion: str = ""


class ErrorDetector:
    """Parses rclone output to detect and categorize errors."""

    # Error pattern matching rules
    ERROR_PATTERNS: ClassVar = [
        # Permission errors
        (
            re.compile(r"ERROR.*permission denied", re.IGNORECASE),
            ErrorType.PERMISSION_ERROR,
            "Check file permissions and ensure rclone has access",
        ),
        (
            re.compile(r"ERROR.*access denied", re.IGNORECASE),
            ErrorType.PERMISSION_ERROR,
            "Access denied - check credentials and permissions",
        ),
        # Network errors
        (
            re.compile(r"ERROR.*connection refused", re.IGNORECASE),
            ErrorType.NETWORK_ERROR,
            "Connection refused - check network connectivity and endpoint",
        ),
        (
            re.compile(r"ERROR.*network.*unreachable", re.IGNORECASE),
            ErrorType.NETWORK_ERROR,
            "Network unreachable - check internet connection",
        ),
        (
            re.compile(r"ERROR.*timeout", re.IGNORECASE),
            ErrorType.TIMEOUT_ERROR,
            "Operation timed out - try again or increase timeout settings",
        ),
        # Authentication errors
        (
            re.compile(r"ERROR.*authentication.*fail", re.IGNORECASE),
            ErrorType.AUTHENTICATION_ERROR,
            "Authentication failed - check credentials",
        ),
        (
            re.compile(r"ERROR.*invalid.*credentials", re.IGNORECASE),
            ErrorType.AUTHENTICATION_ERROR,
            "Invalid credentials - verify access key and secret key",
        ),
        (
            re.compile(r"ERROR.*401.*unauthorized", re.IGNORECASE),
            ErrorType.AUTHENTICATION_ERROR,
            "Unauthorized - check credentials and permissions",
        ),
        # Storage errors
        (
            re.compile(r"ERROR.*bucket.*not.*found", re.IGNORECASE),
            ErrorType.STORAGE_ERROR,
            "Bucket not found - verify bucket name and region",
        ),
        (
            re.compile(r"ERROR.*no space left", re.IGNORECASE),
            ErrorType.STORAGE_ERROR,
            "No space left on device - free up storage space",
        ),
        (
            re.compile(r"ERROR.*quota.*exceeded", re.IGNORECASE),
            ErrorType.STORAGE_ERROR,
            "Storage quota exceeded - check account limits",
        ),
        # File errors
        (
            re.compile(r"ERROR.*no such file", re.IGNORECASE),
            ErrorType.FILE_ERROR,
            "File not found - ensure source path exists",
        ),
        (
            re.compile(r"ERROR.*file.*corrupt", re.IGNORECASE),
            ErrorType.FILE_ERROR,
            "File corrupted - check file integrity",
        ),
        (
            re.compile(r"ERROR.*checksum.*mismatch", re.IGNORECASE),
            ErrorType.FILE_ERROR,
            "Checksum mismatch - file may be corrupted during transfer",
        ),
        # Configuration errors
        (
            re.compile(r"ERROR.*config.*not.*found", re.IGNORECASE),
            ErrorType.CONFIGURATION_ERROR,
            "Configuration error - check rclone config",
        ),
        (
            re.compile(r"ERROR.*unknown.*flag", re.IGNORECASE),
            ErrorType.CONFIGURATION_ERROR,
            "Invalid configuration - check rclone command options",
        ),
    ]

    def __init__(self, logger: logging.Logger | None = None):
        """Initialize error detector.

        Args:
            logger: Optional logger for error detection logging
        """
        self.logger = logger or logging.getLogger(__name__)

    def parse_errors(self, output: str) -> list[BackupError]:
        """Parse rclone output and extract categorized errors.

        Args:
            output: Complete rclone output text

        Returns:
            List of BackupError objects with categorized error information
        """
        errors = []
        lines = output.split("\n")

        for line_num, line in enumerate(lines, 1):
            line = line.strip()
            if not line or not self._is_error_line(line):
                continue

            # Extract file path from error line if present
            file_path = self._extract_file_path(line)

            # Categorize the error
            error_type, suggestion = self._categorize_error(line)

            # Create error object
            error = BackupError(
                error_type=error_type,
                message=line,
                file_path=file_path,
                line_number=line_num,
                raw_output=line,
                suggestion=suggestion,
            )

            errors.append(error)
            self.logger.debug(f"Detected {error_type.value} error: {line}")

        return errors

    def _is_error_line(self, line: str) -> bool:
        """Check if a line contains an error message.

        Args:
            line: Text line to check

        Returns:
            True if line contains error indicators
        """
        error_indicators = ["ERROR", "CRITICAL", "FATAL", "Failed"]
        return any(indicator in line for indicator in error_indicators)

    def _extract_file_path(self, line: str) -> str:
        """Extract file path from error line if present.

        Args:
            line: Error line text

        Returns:
            Extracted file path or empty string
        """
        # Common patterns for file paths in rclone errors
        path_patterns = [
            r"ERROR\s+:\s+([^:]+(?::[^:]+)?)\s*:",  # "ERROR : /path/file.jpg :" or "ERROR : C:\path\file.jpg :"
            r'"([^"]+)"',  # "path/file.jpg" in quotes
            r"'([^']+)'",  # 'path/file.jpg' in quotes
        ]

        for pattern in path_patterns:
            match = re.search(pattern, line)
            if match:
                path = match.group(1).strip()
                # Validate that it looks like a file path
                if "/" in path or "\\" in path or "." in path:
                    return path

        return ""

    def _categorize_error(self, line: str) -> tuple[ErrorType, str]:
        """Categorize error based on message content.

        Args:
            line: Error message line

        Returns:
            Tuple of (ErrorType, suggestion_text)
        """
        for pattern, error_type, suggestion in self.ERROR_PATTERNS:
            if pattern.search(line):
                return error_type, suggestion

        return ErrorType.UNKNOWN_ERROR, "Check rclone documentation for error details"

    def get_error_summary(self, errors: list[BackupError]) -> dict[str, Any]:
        """Generate summary statistics for detected errors.

        Args:
            errors: List of BackupError objects

        Returns:
            Dictionary with error summary statistics
        """
        if not errors:
            return {"total_errors": 0, "error_types": {}}

        # Count errors by type
        error_counts: dict[str, int] = {}
        for error in errors:
            error_type = error.error_type.value
            error_counts[error_type] = error_counts.get(error_type, 0) + 1

        # Find most common error type
        most_common_type = max(error_counts.keys(), key=lambda k: error_counts[k])

        return {
            "total_errors": len(errors),
            "error_types": error_counts,
            "most_common_type": most_common_type,
            "has_permission_errors": ErrorType.PERMISSION_ERROR.value in error_counts,
            "has_network_errors": ErrorType.NETWORK_ERROR.value in error_counts,
            "has_authentication_errors": ErrorType.AUTHENTICATION_ERROR.value in error_counts,
            "unique_files_with_errors": len({e.file_path for e in errors if e.file_path}),
        }
