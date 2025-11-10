"""
Backup module for photo synchronization.

This package provides a comprehensive backup system for synchronizing photos
to S3-compatible storage with progress tracking, error detection, and state
management.

Public API:
    - BackupEngine: Main engine for orchestrating backup operations
    - BackupJob: Representation of a backup task
    - BackupStats: Comprehensive statistics and metrics
    - BackupState: Persistent state tracking
    - BackupError: Detailed error information
    - ErrorType: Error categorization enum
    - check_rclone: Utility to check rclone availability
"""

from .engine import BackupEngine
from .errors import BackupError, ErrorDetector, ErrorType
from .job import BackupJob
from .rclone_utils import check_rclone
from .state import BackupState, StateManager
from .stats import BackupStats

__all__ = [
    "BackupEngine",
    "BackupError",
    "BackupJob",
    "BackupState",
    "BackupStats",
    "ErrorDetector",
    "ErrorType",
    "StateManager",
    "check_rclone",
]
