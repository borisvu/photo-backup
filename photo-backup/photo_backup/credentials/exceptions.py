"""
Credential-related exceptions for the photo backup system.
"""


class CredentialError(Exception):
    """Exception raised for credential-related errors."""

    def __init__(self, message: str, suggestion: str = "", details: str = ""):
        """Initialize credential error.

        Args:
            message: Primary error message
            suggestion: Suggested fix or action
            details: Additional error details
        """
        self.message = message
        self.suggestion = suggestion
        self.details = details
        if suggestion:
            super().__init__(f"{message}. {suggestion}")
        else:
            super().__init__(message)
