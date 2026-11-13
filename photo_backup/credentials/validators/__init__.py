"""
Credential validators for the photo backup system.
"""

from .base import CredentialValidator
from .rclone import RcloneCredentialValidator

__all__ = [
    "CredentialValidator",
    "RcloneCredentialValidator",
]
