"""
Unit tests for credential exceptions.
"""

from photo_backup.credentials.exceptions import CredentialError


class TestCredentialError:
    """Test the CredentialError exception class."""

    def test_credential_error_basic(self):
        """Test basic CredentialError creation."""
        error = CredentialError("Test error")
        assert error.message == "Test error"
        assert error.suggestion == ""
        assert error.details == ""
        assert str(error) == "Test error"

    def test_credential_error_with_suggestion(self):
        """Test CredentialError with suggestion."""
        error = CredentialError("Test error", "Fix it")
        assert error.message == "Test error"
        assert error.suggestion == "Fix it"
        assert str(error) == "Test error. Fix it"

    def test_credential_error_with_details(self):
        """Test CredentialError with details."""
        error = CredentialError("Test error", "Fix it", "Technical details")
        assert error.message == "Test error"
        assert error.suggestion == "Fix it"
        assert error.details == "Technical details"
        assert str(error) == "Test error. Fix it"
