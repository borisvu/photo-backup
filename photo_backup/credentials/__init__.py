"""
Credential management for photo backup system.

This package handles credential retrieval, validation, and management
for S3-compatible storage services, with support for direct credentials
and optional 1Password integration for test mode using Minio.
"""

from .exceptions import CredentialError
from .manager import CredentialManager

__all__ = ["CredentialError", "CredentialManager"]
