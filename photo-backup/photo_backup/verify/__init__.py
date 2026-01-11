"""
Verification module for photo backup system.

This module provides functionality to verify the integrity of backed up files
by comparing local and remote hashes, and supports repair operations.

Usage:
    from photo_backup.verify import Verifier, HashCalculator, RemoteLister
    from photo_backup.verify import FileHash, ComparisonResult, VerificationReport
"""

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

# Main verifier
from .verifier import Verifier

__all__ = [
    "ComparisonResult",
    "FileHash",
    "FileMismatch",
    "HashCalculator",
    "RemoteLister",
    "RepairResult",
    "VerificationJob",
    "VerificationReport",
    "VerificationResult",
    "VerificationStatus",
    "Verifier",
]
