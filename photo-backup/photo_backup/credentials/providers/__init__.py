"""
Credential providers for the photo backup system.
"""

from .base import CredentialProvider
from .direct import DirectCredentialProvider
from .onepassword import OnePasswordCredentialProvider
from .test_mode import TestModeCredentialProvider

__all__ = [
    "CredentialProvider",
    "DirectCredentialProvider",
    "OnePasswordCredentialProvider",
    "TestModeCredentialProvider",
]
