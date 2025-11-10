"""
Functional tests for error detection in backup operations.

These tests verify that the BackupEngine properly integrates error detection
functionality and handles various error scenarios correctly.
"""

from unittest.mock import Mock, patch

import pytest

from photo_backup.backup import BackupEngine, BackupJob, ErrorType
from photo_backup.config.config import Config


@pytest.mark.functional
class TestBackupErrorDetection:
    """Functional tests for backup error detection integration."""

    def setup_method(self):
        """Set up test fixtures."""
        self.config = Config(test_mode=True)
        self.config.load_config()
        self.engine = BackupEngine(self.config, test_mode=True)

    def test_backup_engine_has_error_detector(self):
        """Test that BackupEngine initializes with ErrorDetector."""
        assert self.engine.error_detector is not None
        assert hasattr(self.engine.error_detector, "parse_errors")
        assert hasattr(self.engine.error_detector, "get_error_summary")

    @patch("photo_backup.backup.engine.subprocess.Popen")
    def test_sync_with_permission_errors(self, mock_popen):
        """Test sync operation with permission errors in output."""
        # Mock rclone output with permission errors
        rclone_output = """
2024/01/01 12:00:00 INFO  : Starting sync
2024/01/01 12:00:01 ERROR : /test/photo1.jpg : permission denied
2024/01/01 12:00:02 ERROR : /test/photo2.jpg : access denied
2024/01/01 12:00:03 INFO  : Transferred: 3 files, 1.5 MiB
"""

        # Mock the subprocess
        mock_process = Mock()
        mock_process.stdout.readline.side_effect = [*rclone_output.strip().split("\n"), ""]
        mock_process.wait.return_value = 1  # Non-zero return code for errors
        mock_popen.return_value = mock_process

        # Create test job
        job = BackupJob("/tmp/test-photos", "test-bucket", dry_run=False)

        # Run sync with progress (includes error detection)
        success, output, sync_info, backup_stats = self.engine.sync_with_progress(job)

        # Verify basic operation
        assert success is False  # Should fail due to errors
        assert "permission denied" in output

        # Verify error detection in backup stats
        assert len(backup_stats.detailed_errors) == 2
        assert backup_stats.error_summary["total_errors"] == 2
        assert backup_stats.error_summary["has_permission_errors"] is True

        # Check specific errors (handle both BackupError objects and dict objects)
        permission_errors = []
        for e in backup_stats.detailed_errors:
            if hasattr(e, "error_type") and e.error_type == ErrorType.PERMISSION_ERROR:
                # It's a BackupError object
                permission_errors.append(e)
            elif isinstance(e, dict) and e.get("error_type") == ErrorType.PERMISSION_ERROR.value:
                # It's a dict object
                permission_errors.append(e)

        assert len(permission_errors) == 2

        # Check file paths (handle both object types)
        file_paths = []
        for e in permission_errors:
            if hasattr(e, "file_path"):
                file_paths.append(e.file_path)
            elif isinstance(e, dict):
                file_paths.append(e.get("file_path", ""))

        assert any("/test/photo1.jpg" in path for path in file_paths)
        assert any("/test/photo2.jpg" in path for path in file_paths)

    @patch("photo_backup.backup.engine.subprocess.Popen")
    def test_sync_with_network_errors(self, mock_popen):
        """Test sync operation with network errors in output."""
        # Mock rclone output with network errors
        rclone_output = """
2024/01/01 12:00:00 INFO  : Starting sync
2024/01/01 12:00:01 ERROR : connection refused to endpoint
2024/01/01 12:00:02 ERROR : network unreachable
2024/01/01 12:00:03 INFO  : Retrying...
"""

        # Mock the subprocess
        mock_process = Mock()
        mock_process.stdout.readline.side_effect = [*rclone_output.strip().split("\n"), ""]
        mock_process.wait.return_value = 1  # Non-zero return code for errors
        mock_popen.return_value = mock_process

        # Create test job
        job = BackupJob("/tmp/test-photos", "test-bucket", dry_run=False)

        # Run sync with progress
        success, output, sync_info, backup_stats = self.engine.sync_with_progress(job)

        # Verify error detection
        assert success is False
        assert len(backup_stats.detailed_errors) == 2
        assert backup_stats.error_summary["has_network_errors"] is True

        # Check specific error types
        network_errors = []
        for e in backup_stats.detailed_errors:
            if (hasattr(e, "error_type") and e.error_type == ErrorType.NETWORK_ERROR) or (
                isinstance(e, dict) and e.get("error_type") == ErrorType.NETWORK_ERROR.value
            ):
                network_errors.append(e)
        assert len(network_errors) == 2

    @patch("photo_backup.backup.engine.subprocess.Popen")
    def test_sync_with_mixed_errors(self, mock_popen):
        """Test sync operation with multiple different error types."""
        # Mock rclone output with various errors
        rclone_output = """
2024/01/01 12:00:00 INFO  : Starting sync
2024/01/01 12:00:01 ERROR : /photos/IMG_001.jpg : permission denied
2024/01/01 12:00:02 ERROR : connection refused
2024/01/01 12:00:03 ERROR : /photos/IMG_002.jpg : checksum mismatch
2024/01/01 12:00:04 ERROR : bucket not found
2024/01/01 12:00:05 ERROR : authentication failed
2024/01/01 12:00:06 INFO  : Transferred: 0 files
"""

        # Mock the subprocess
        mock_process = Mock()
        mock_process.stdout.readline.side_effect = [*rclone_output.strip().split("\n"), ""]
        mock_process.wait.return_value = 1  # Non-zero return code for errors
        mock_popen.return_value = mock_process

        # Create test job
        job = BackupJob("/tmp/test-photos", "test-bucket", dry_run=False)

        # Run sync with progress
        success, output, sync_info, backup_stats = self.engine.sync_with_progress(job)

        # Verify comprehensive error detection
        assert success is False
        assert len(backup_stats.detailed_errors) == 5
        assert backup_stats.error_summary["total_errors"] == 5

        # Check that different error types are detected
        assert backup_stats.error_summary["has_permission_errors"] is True
        assert backup_stats.error_summary["has_network_errors"] is True
        assert backup_stats.error_summary["has_authentication_errors"] is True

        # Verify specific error types are present
        error_types = []
        for e in backup_stats.detailed_errors:
            if hasattr(e, "error_type"):
                error_types.append(e.error_type)
            elif isinstance(e, dict):
                error_types.append(e.get("error_type", "unknown_error"))
        assert ErrorType.PERMISSION_ERROR.value in error_types or ErrorType.PERMISSION_ERROR in error_types
        assert ErrorType.NETWORK_ERROR.value in error_types or ErrorType.NETWORK_ERROR in error_types
        assert ErrorType.FILE_ERROR.value in error_types or ErrorType.FILE_ERROR in error_types  # checksum mismatch
        assert (
            ErrorType.STORAGE_ERROR.value in error_types or ErrorType.STORAGE_ERROR in error_types
        )  # bucket not found
        assert ErrorType.AUTHENTICATION_ERROR.value in error_types or ErrorType.AUTHENTICATION_ERROR in error_types

        # Check files with errors
        assert backup_stats.error_summary["unique_files_with_errors"] == 2  # IMG_001.jpg and IMG_002.jpg

    @patch("photo_backup.backup.engine.subprocess.Popen")
    def test_sync_successful_no_errors(self, mock_popen):
        """Test successful sync operation with no errors."""
        # Mock successful rclone output
        rclone_output = """
2024/01/01 12:00:00 INFO  : Starting sync
2024/01/01 12:00:01 INFO  : Transferred: 1 / 5 files, 20% complete
2024/01/01 12:00:02 INFO  : Transferred: 3 / 5 files, 60% complete
2024/01/01 12:00:03 INFO  : Transferred: 5 / 5 files, 100% complete
2024/01/01 12:00:04 INFO  : Transferred: 5 files, 10.5 MiB
"""

        # Mock the subprocess
        mock_process = Mock()
        mock_process.stdout.readline.side_effect = [*rclone_output.strip().split("\n"), ""]
        mock_process.wait.return_value = 0  # Success return code
        mock_popen.return_value = mock_process

        # Create test job
        job = BackupJob("/tmp/test-photos", "test-bucket", dry_run=False)

        # Run sync with progress
        success, output, sync_info, backup_stats = self.engine.sync_with_progress(job)

        # Verify successful operation with no errors
        assert success is True
        assert len(backup_stats.detailed_errors) == 0
        assert backup_stats.error_summary["total_errors"] == 0
        assert backup_stats.error_summary["error_types"] == {}

    @patch("photo_backup.backup.engine.subprocess.Popen")
    def test_sync_timeout_error_detection(self, mock_popen):
        """Test timeout scenario creates proper error detection."""
        # Mock timeout scenario
        from subprocess import TimeoutExpired

        mock_process = Mock()
        mock_process.stdout.readline.side_effect = [""]  # Empty output
        mock_process.wait.side_effect = TimeoutExpired("rclone", 300)
        mock_popen.return_value = mock_process

        # Create test job
        job = BackupJob("/tmp/test-photos", "test-bucket", dry_run=False)

        # Run sync with progress
        success, output, sync_info, backup_stats = self.engine.sync_with_progress(job)

        # Verify timeout error detection
        assert success is False
        assert len(backup_stats.detailed_errors) == 1
        first_error = backup_stats.detailed_errors[0]
        if hasattr(first_error, "error_type"):
            assert first_error.error_type == ErrorType.TIMEOUT_ERROR
        elif isinstance(first_error, dict):
            assert first_error.get("error_type") == ErrorType.TIMEOUT_ERROR.value
        assert backup_stats.error_summary["total_errors"] == 1
        first_error = backup_stats.detailed_errors[0]
        message = first_error.message if hasattr(first_error, "message") else first_error.get("message", "")
        suggestion = first_error.suggestion if hasattr(first_error, "suggestion") else first_error.get("suggestion", "")
        assert "timed out" in message.lower()
        assert "timeout" in suggestion.lower()

    @patch("photo_backup.backup.engine.subprocess.Popen")
    def test_sync_exception_error_detection(self, mock_popen):
        """Test exception scenario creates proper error detection."""
        # Mock exception scenario
        mock_popen.side_effect = Exception("Test exception")

        # Create test job
        job = BackupJob("/tmp/test-photos", "test-bucket", dry_run=False)

        # Run sync with progress
        success, output, sync_info, backup_stats = self.engine.sync_with_progress(job)

        # Verify exception error detection
        assert success is False
        assert len(backup_stats.detailed_errors) == 1
        first_error = backup_stats.detailed_errors[0]
        if hasattr(first_error, "error_type"):
            assert first_error.error_type == ErrorType.UNKNOWN_ERROR
        elif isinstance(first_error, dict):
            assert first_error.get("error_type") == ErrorType.UNKNOWN_ERROR.value
        assert backup_stats.error_summary["total_errors"] == 1
        first_error = backup_stats.detailed_errors[0]
        message = first_error.message if hasattr(first_error, "message") else first_error.get("message", "")
        assert "exception" in message.lower()

    def test_sync_stats_method_includes_errors(self):
        """Test sync_with_stats method includes error detection."""
        # Create test job
        job = BackupJob("/tmp/test-photos", "test-bucket", dry_run=True)

        # Mock successful operation
        with patch("photo_backup.backup.BackupEngine.sync_with_progress") as mock_sync:
            from datetime import datetime

            from photo_backup.backup import BackupError, BackupStats, ErrorType

            # Create mock errors
            test_error = BackupError(
                error_type=ErrorType.FILE_ERROR, message="Test error", suggestion="Test suggestion"
            )

            # Create mock backup stats with errors
            mock_stats = BackupStats(
                start_time=datetime.now(),
                end_time=datetime.now(),
                success=False,
                detailed_errors=[test_error],
                error_summary={"total_errors": 1, "has_file_errors": True},
            )

            mock_sync.return_value = (False, "test output", {}, mock_stats)

            # Call sync_with_stats
            result_stats = self.engine.sync_with_stats(job)

            # Verify error information is preserved
            assert len(result_stats.detailed_errors) == 1
            assert result_stats.error_summary["total_errors"] == 1
            first_error = result_stats.detailed_errors[0]
            if hasattr(first_error, "error_type"):
                assert first_error.error_type == ErrorType.FILE_ERROR
            elif isinstance(first_error, dict):
                assert first_error.get("error_type") == ErrorType.FILE_ERROR.value


@pytest.mark.functional
class TestBackupStatsErrorIntegration:
    """Test BackupStats integration with error detection."""

    def test_backup_stats_from_transfer_stats_with_errors(self):
        """Test creating BackupStats with error information."""
        from datetime import datetime

        from photo_backup.backup import BackupError, BackupStats, ErrorType
        from photo_backup.progress_parser import TransferStats

        # Create test errors
        errors = [
            BackupError(
                error_type=ErrorType.PERMISSION_ERROR, message="Permission denied", file_path="/test/file1.jpg"
            ),
            BackupError(error_type=ErrorType.NETWORK_ERROR, message="Connection refused"),
        ]

        # Create error summary
        error_summary = {
            "total_errors": 2,
            "error_types": {"permission_error": 1, "network_error": 1},
            "has_permission_errors": True,
            "has_network_errors": True,
        }

        # Create transfer stats
        transfer_stats = TransferStats()
        transfer_stats.files_transferred = 3
        transfer_stats.files_total = 5
        transfer_stats.bytes_transferred = 1024 * 1024  # 1MB
        transfer_stats.bytes_total = 2 * 1024 * 1024  # 2MB
        transfer_stats.errors = 2

        # Create BackupStats with error information
        start_time = datetime.now()
        end_time = datetime.now()

        backup_stats = BackupStats.from_transfer_stats(
            transfer_stats=transfer_stats,
            start_time=start_time,
            end_time=end_time,
            source_path="/test/source",
            destination="test-bucket",
            dry_run=False,
            test_mode=True,
            success=False,
            error_message="Errors occurred",
            detailed_errors=errors,
            error_summary=error_summary,
        )

        # Verify error information is preserved
        assert len(backup_stats.detailed_errors) == 2
        assert backup_stats.error_summary["total_errors"] == 2
        assert backup_stats.error_summary["has_permission_errors"] is True
        assert backup_stats.error_summary["has_network_errors"] is True

        # Verify other stats are still correct
        assert backup_stats.files_transferred == 3
        assert backup_stats.files_total == 5
        assert backup_stats.bytes_transferred == 1024 * 1024
        assert backup_stats.success is False
        assert backup_stats.error_message == "Errors occurred"

    def test_backup_stats_no_errors(self):
        """Test creating BackupStats with no error information."""
        from datetime import datetime

        from photo_backup.backup import BackupStats
        from photo_backup.progress_parser import TransferStats

        # Create transfer stats
        transfer_stats = TransferStats()
        transfer_stats.files_transferred = 5
        transfer_stats.files_total = 5
        transfer_stats.bytes_transferred = 2 * 1024 * 1024  # 2MB
        transfer_stats.bytes_total = 2 * 1024 * 1024  # 2MB
        transfer_stats.errors = 0

        # Create BackupStats without error information
        start_time = datetime.now()
        end_time = datetime.now()

        backup_stats = BackupStats.from_transfer_stats(
            transfer_stats=transfer_stats,
            start_time=start_time,
            end_time=end_time,
            source_path="/test/source",
            destination="test-bucket",
            dry_run=False,
            test_mode=True,
            success=True,
        )

        # Verify no error information
        assert len(backup_stats.detailed_errors) == 0
        assert backup_stats.error_summary == {}
        assert backup_stats.success is True
        assert backup_stats.error_message is None
