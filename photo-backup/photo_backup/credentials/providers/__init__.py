"""
Credential providers for the photo backup system.
"""

from .base import CredentialProvider
from .direct import DirectCredentialProvider
from .onepassword import OnePasswordCredentialProvider

# TestModeCredentialProvider is deprecated - DirectCredentialProvider now handles all modes
# from .test_mode import TestModeCredentialProvider

__all__ = [
    "CredentialProvider",
    "DirectCredentialProvider",
    "OnePasswordCredentialProvider",
]
