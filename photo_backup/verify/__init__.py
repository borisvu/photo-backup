"""
Verification module for photo backup system.

This module provides functionality to verify the integrity of backed up files
by comparing local and remote hashes, and supports repair operations.

Usage:
    from photo_backup.verify import Verifier, HashCalculator, RemoteLister
    from photo_backup.verify import FileHash, ComparisonResult, VerificationReport
    from photo_backup.verify import HashCache, CacheEntry, get_default_cache_path
    from photo_backup.verify import VerificationScheduler, VerificationScheduleState
"""

# Cache
from .cache import CacheEntry, CacheMetadata, CacheStats, HashCache, get_default_cache_path

# Models (dataclasses and enums)
# Hash calculator
from .hash_calculator import HashCalculator
from .models import (
    ComparisonResult,
    FileHash,
    FileMismatch,
    RepairResult,
    VerificationJob,
    VerificationReport,
    VerificationResult,
    VerificationStatus,
)

# Remote lister
from .remote_lister import RemoteLister

# Scheduler
from .scheduler import (
    ScheduledVerificationResult,
    VerificationScheduler,
    VerificationScheduleState,
)

# Main verifier
from .verifier import Verifier

__all__ = [
    "CacheEntry",
    "CacheMetadata",
    "CacheStats",
    "ComparisonResult",
    "FileHash",
    "FileMismatch",
    "HashCache",
    "HashCalculator",
    "RemoteLister",
    "RepairResult",
    "ScheduledVerificationResult",
    "VerificationJob",
    "VerificationReport",
    "VerificationResult",
    "VerificationScheduleState",
    "VerificationScheduler",
    "VerificationStatus",
    "Verifier",
    "get_default_cache_path",
]
