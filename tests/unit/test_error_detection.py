"""
Unit tests for error detection functionality in backup.py

Tests the ErrorDetector class and related BackupError components.
"""

from photo_backup.backup import BackupError, ErrorDetector, ErrorType


class TestErrorType:
    """Test ErrorType enum."""

    def test_error_type_values(self):
        """Test that all error types have expected values."""
        assert ErrorType.PERMISSION_ERROR.value == "permission_error"
        assert ErrorType.NETWORK_ERROR.value == "network_error"
        assert ErrorType.AUTHENTICATION_ERROR.value == "authentication_error"
        assert ErrorType.STORAGE_ERROR.value == "storage_error"
        assert ErrorType.FILE_ERROR.value == "file_error"
        assert ErrorType.CONFIGURATION_ERROR.value == "configuration_error"
        assert ErrorType.TIMEOUT_ERROR.value == "timeout_error"
        assert ErrorType.UNKNOWN_ERROR.value == "unknown_error"

    def test_error_type_count(self):
        """Test that we have the expected number of error types."""
        error_types = list(ErrorType)
        assert len(error_types) == 8


class TestBackupError:
    """Test BackupError dataclass."""

    def test_backup_error_creation(self):
        """Test creating BackupError with all fields."""
        error = BackupError(
            error_type=ErrorType.PERMISSION_ERROR,
            message="Access denied",
            file_path="/path/to/file.jpg",
            line_number=42,
            raw_output="ERROR : /path/to/file.jpg : access denied",
            suggestion="Check file permissions",
        )

        assert error.error_type == ErrorType.PERMISSION_ERROR
        assert error.message == "Access denied"
        assert error.file_path == "/path/to/file.jpg"
        assert error.line_number == 42
        assert error.raw_output == "ERROR : /path/to/file.jpg : access denied"
        assert error.suggestion == "Check file permissions"

    def test_backup_error_minimal(self):
        """Test creating BackupError with minimal fields."""
        error = BackupError(error_type=ErrorType.NETWORK_ERROR, message="Connection refused")

        assert error.error_type == ErrorType.NETWORK_ERROR
        assert error.message == "Connection refused"
        assert error.file_path == ""
        assert error.line_number == 0
        assert error.raw_output == ""
        assert error.suggestion == ""


class TestErrorDetector:
    """Test ErrorDetector class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.detector = ErrorDetector()

    def test_error_detector_initialization(self):
        """Test ErrorDetector initialization."""
        detector = ErrorDetector()
        assert detector.logger is not None

    def test_is_error_line(self):
        """Test error line detection."""
        # Test error indicators
        assert self.detector._is_error_line("ERROR: something went wrong")
        assert self.detector._is_error_line("CRITICAL: critical failure")
        assert self.detector._is_error_line("FATAL: fatal error")
        assert self.detector._is_error_line("Failed to complete")

        # Test non-error lines
        assert not self.detector._is_error_line("INFO: everything is fine")
        assert not self.detector._is_error_line("DEBUG: debug message")
        assert not self.detector._is_error_line("Transferred 5 files")
        assert not self.detector._is_error_line("")

    def test_extract_file_path(self):
        """Test file path extraction from error lines."""
        # Test standard rclone error format
        assert self.detector._extract_file_path("ERROR : /path/to/file.jpg : access denied") == "/path/to/file.jpg"

        # Test quoted paths
        assert (
            self.detector._extract_file_path('ERROR: "/path/to/file with spaces.jpg" not found')
            == "/path/to/file with spaces.jpg"
        )
        assert self.detector._extract_file_path("ERROR: '/path/to/file.jpg' permission denied") == "/path/to/file.jpg"

        # Test no path present
        assert self.detector._extract_file_path("ERROR: general error message") == ""

        # Test Windows paths
        assert (
            self.detector._extract_file_path("ERROR : C:\\path\\to\\file.jpg : access denied")
            == "C:\\path\\to\\file.jpg"
        )

    def test_categorize_permission_errors(self):
        """Test categorization of permission errors."""
        error_type, suggestion = self.detector._categorize_error("ERROR: permission denied")
        assert error_type == ErrorType.PERMISSION_ERROR
        assert "permission" in suggestion.lower()

        error_type, suggestion = self.detector._categorize_error("ERROR: access denied")
        assert error_type == ErrorType.PERMISSION_ERROR
        assert "access denied" in suggestion.lower()

    def test_categorize_network_errors(self):
        """Test categorization of network errors."""
        error_type, suggestion = self.detector._categorize_error("ERROR: connection refused")
        assert error_type == ErrorType.NETWORK_ERROR
        assert "connection" in suggestion.lower()

        error_type, suggestion = self.detector._categorize_error("ERROR: network unreachable")
        assert error_type == ErrorType.NETWORK_ERROR
        assert "network" in suggestion.lower()

    def test_categorize_authentication_errors(self):
        """Test categorization of authentication errors."""
        error_type, suggestion = self.detector._categorize_error("ERROR: authentication failed")
        assert error_type == ErrorType.AUTHENTICATION_ERROR
        assert "credentials" in suggestion.lower()

        error_type, suggestion = self.detector._categorize_error("ERROR: invalid credentials")
        assert error_type == ErrorType.AUTHENTICATION_ERROR
        assert "credentials" in suggestion.lower()

        error_type, suggestion = self.detector._categorize_error("ERROR: 401 unauthorized")
        assert error_type == ErrorType.AUTHENTICATION_ERROR
        assert "credentials" in suggestion.lower()

    def test_categorize_storage_errors(self):
        """Test categorization of storage errors."""
        error_type, suggestion = self.detector._categorize_error("ERROR: bucket not found")
        assert error_type == ErrorType.STORAGE_ERROR
        assert "bucket" in suggestion.lower()

        error_type, suggestion = self.detector._categorize_error("ERROR: no space left on device")
        assert error_type == ErrorType.STORAGE_ERROR
        assert "space" in suggestion.lower()

        error_type, suggestion = self.detector._categorize_error("ERROR: quota exceeded")
        assert error_type == ErrorType.STORAGE_ERROR
        assert "quota" in suggestion.lower()

    def test_categorize_file_errors(self):
        """Test categorization of file errors."""
        error_type, suggestion = self.detector._categorize_error("ERROR: no such file")
        assert error_type == ErrorType.FILE_ERROR
        assert "file" in suggestion.lower()

        error_type, suggestion = self.detector._categorize_error("ERROR: file corrupt")
        assert error_type == ErrorType.FILE_ERROR
        assert "corrupt" in suggestion.lower()

        error_type, suggestion = self.detector._categorize_error("ERROR: checksum mismatch")
        assert error_type == ErrorType.FILE_ERROR
        assert "checksum" in suggestion.lower()

    def test_categorize_configuration_errors(self):
        """Test categorization of configuration errors."""
        error_type, suggestion = self.detector._categorize_error("ERROR: config not found")
        assert error_type == ErrorType.CONFIGURATION_ERROR
        assert "config" in suggestion.lower()

        error_type, suggestion = self.detector._categorize_error("ERROR: unknown flag")
        assert error_type == ErrorType.CONFIGURATION_ERROR
        assert "configuration" in suggestion.lower()

    def test_categorize_timeout_errors(self):
        """Test categorization of timeout errors."""
        error_type, suggestion = self.detector._categorize_error("ERROR: operation timeout")
        assert error_type == ErrorType.TIMEOUT_ERROR
        assert "timeout" in suggestion.lower()

    def test_categorize_unknown_errors(self):
        """Test categorization of unknown errors."""
        error_type, suggestion = self.detector._categorize_error("ERROR: mysterious error")
        assert error_type == ErrorType.UNKNOWN_ERROR
        assert "documentation" in suggestion.lower()

    def test_parse_errors_no_errors(self):
        """Test parsing output with no errors."""
        output = """
        INFO: Starting sync
        Transferred 5 files
        INFO: Sync completed successfully
        """

        errors = self.detector.parse_errors(output)
        assert len(errors) == 0

    def test_parse_errors_single_error(self):
        """Test parsing output with single error."""
        output = """
        INFO: Starting sync
        ERROR : /path/to/file.jpg : permission denied
        Transferred 4 files
        """

        errors = self.detector.parse_errors(output)
        assert len(errors) == 1

        error = errors[0]
        assert error.error_type == ErrorType.PERMISSION_ERROR
        assert "permission denied" in error.message
        assert error.file_path == "/path/to/file.jpg"
        assert error.line_number == 3  # Line number in split output

    def test_parse_errors_multiple_errors(self):
        """Test parsing output with multiple errors."""
        output = """
        INFO: Starting sync
        ERROR : /path/file1.jpg : permission denied
        ERROR: connection refused to server
        ERROR : /path/file2.jpg : no such file
        Transferred 2 files
        """

        errors = self.detector.parse_errors(output)
        assert len(errors) == 3

        # Check error types
        error_types = [error.error_type for error in errors]
        assert ErrorType.PERMISSION_ERROR in error_types
        assert ErrorType.NETWORK_ERROR in error_types
        assert ErrorType.FILE_ERROR in error_types

    def test_parse_errors_with_file_paths(self):
        """Test parsing errors and extracting file paths."""
        output = """
        ERROR : /photos/IMG_001.jpg : checksum mismatch
        ERROR : /photos/IMG_002.jpg : file corrupt
        ERROR: general network error
        """

        errors = self.detector.parse_errors(output)
        assert len(errors) == 3

        # Check file paths
        assert errors[0].file_path == "/photos/IMG_001.jpg"
        assert errors[1].file_path == "/photos/IMG_002.jpg"
        assert errors[2].file_path == ""  # No file path in general error

    def test_get_error_summary_empty(self):
        """Test error summary with no errors."""
        summary = self.detector.get_error_summary([])

        assert summary["total_errors"] == 0
        assert summary["error_types"] == {}

    def test_get_error_summary_single_type(self):
        """Test error summary with single error type."""
        errors = [
            BackupError(ErrorType.PERMISSION_ERROR, "Error 1"),
            BackupError(ErrorType.PERMISSION_ERROR, "Error 2"),
            BackupError(ErrorType.PERMISSION_ERROR, "Error 3"),
        ]

        summary = self.detector.get_error_summary(errors)

        assert summary["total_errors"] == 3
        assert summary["error_types"]["permission_error"] == 3
        assert summary["most_common_type"] == "permission_error"
        assert summary["has_permission_errors"] is True
        assert summary["has_network_errors"] is False
        assert summary["unique_files_with_errors"] == 0  # No file paths

    def test_get_error_summary_multiple_types(self):
        """Test error summary with multiple error types."""
        errors = [
            BackupError(ErrorType.PERMISSION_ERROR, "Error 1", "/file1.jpg"),
            BackupError(ErrorType.PERMISSION_ERROR, "Error 2", "/file2.jpg"),
            BackupError(ErrorType.NETWORK_ERROR, "Error 3"),
            BackupError(ErrorType.FILE_ERROR, "Error 4", "/file3.jpg"),
            BackupError(ErrorType.FILE_ERROR, "Error 5", "/file1.jpg"),  # Same file
        ]

        summary = self.detector.get_error_summary(errors)

        assert summary["total_errors"] == 5
        assert summary["error_types"]["permission_error"] == 2
        assert summary["error_types"]["network_error"] == 1
        assert summary["error_types"]["file_error"] == 2
        assert summary["most_common_type"] in ["permission_error", "file_error"]  # Tied
        assert summary["has_permission_errors"] is True
        assert summary["has_network_errors"] is True
        assert summary["has_authentication_errors"] is False
        assert summary["unique_files_with_errors"] == 3  # /file1.jpg, /file2.jpg, /file3.jpg


class TestErrorDetectorIntegration:
    """Integration tests for ErrorDetector with realistic rclone output."""

    def setup_method(self):
        """Set up test fixtures."""
        self.detector = ErrorDetector()

    def test_realistic_rclone_output_with_errors(self):
        """Test with realistic rclone output containing various errors."""
        realistic_output = """
2024/01/01 12:00:00 INFO  : S3 bucket my-photo-backup-bucket-test: Waiting for checks to finish
2024/01/01 12:00:01 INFO  : S3 bucket my-photo-backup-bucket-test: Waiting for transfers to finish
2024/01/01 12:00:01 ERROR : photos/2023/IMG_001.jpg: permission denied
2024/01/01 12:00:02 INFO  : Transferred:        2 / 5 files, 1.5 MiB / 5.2 MiB, 40% complete, 512 KiB/s
2024/01/01 12:00:03 ERROR : photos/2023/IMG_002.jpg: checksum mismatch
2024/01/01 12:00:04 ERROR : connection refused to endpoint
2024/01/01 12:00:05 INFO  : Transferred:        3 / 5 files, 3.1 MiB / 5.2 MiB, 60% complete, 256 KiB/s
2024/01/01 12:00:06 ERROR : photos/2024/IMG_003.jpg: no such file
2024/01/01 12:00:07 INFO  : Transferred:        4 / 5 files, 4.8 MiB / 5.2 MiB, 92% complete, 128 KiB/s
2024/01/01 12:00:08 INFO  :
Transferred:        4 / 5 files, 4.8 MiB / 5.2 MiB, 92% complete, 300 KiB/s
Errors:             4 files not copied
        """

        errors = self.detector.parse_errors(realistic_output)

        # Should detect 4 errors
        assert len(errors) == 4

        # Check error types are correctly categorized
        error_types = [error.error_type for error in errors]
        assert ErrorType.PERMISSION_ERROR in error_types
        assert ErrorType.FILE_ERROR in error_types  # checksum mismatch and no such file
        assert ErrorType.NETWORK_ERROR in error_types

        # Check file paths are extracted
        file_paths = [error.file_path for error in errors if error.file_path]
        assert "photos/2023/IMG_001.jpg" in file_paths
        assert "photos/2023/IMG_002.jpg" in file_paths
        assert "photos/2024/IMG_003.jpg" in file_paths

        # Check summary
        summary = self.detector.get_error_summary(errors)
        assert summary["total_errors"] == 4
        assert summary["has_permission_errors"] is True
        assert summary["has_network_errors"] is True
        assert summary["has_authentication_errors"] is False
        assert summary["unique_files_with_errors"] == 3

    def test_successful_rclone_output(self):
        """Test with successful rclone output (no errors)."""
        successful_output = """
2024/01/01 12:00:00 INFO  : S3 bucket my-photo-backup-bucket-test: Waiting for checks to finish
2024/01/01 12:00:01 INFO  : S3 bucket my-photo-backup-bucket-test: Waiting for transfers to finish
2024/01/01 12:00:02 INFO  : Transferred:        1 / 5 files, 1.0 MiB / 5.2 MiB, 20% complete, 1 MiB/s
2024/01/01 12:00:03 INFO  : Transferred:        3 / 5 files, 3.1 MiB / 5.2 MiB, 60% complete, 1.5 MiB/s
2024/01/01 12:00:04 INFO  : Transferred:        5 / 5 files, 5.2 MiB / 5.2 MiB, 100% complete, 1.3 MiB/s
2024/01/01 12:00:05 INFO  :
Transferred:        5 files, 5.2 MiB, 100% complete, 1.04 MiB/s
        """

        errors = self.detector.parse_errors(successful_output)
        assert len(errors) == 0

        summary = self.detector.get_error_summary(errors)
        assert summary["total_errors"] == 0
        assert summary["error_types"] == {}
