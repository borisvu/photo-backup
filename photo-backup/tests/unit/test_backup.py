"""
Unit tests for the backup module.
"""

import subprocess
from unittest.mock import MagicMock, patch

from photo_backup.backup import BackupEngine, BackupJob, _is_version_sufficient, check_rclone


class TestBackupJob:
    """Test BackupJob class."""

    def test_backup_job_initialization(self):
        """Test BackupJob can be initialized correctly."""
        job = BackupJob("/source/path", "dest:bucket")

        assert job.source_path == "/source/path"
        assert job.destination == "dest:bucket"
        assert job.dry_run is False
        assert job.status == "pending"
        assert job.error is None

    def test_backup_job_with_dry_run(self):
        """Test BackupJob with dry run mode."""
        job = BackupJob("/source/path", "dest:bucket", dry_run=True)

        assert job.dry_run is True

    def test_backup_job_repr(self):
        """Test BackupJob string representation."""
        job = BackupJob("/source/path", "dest:bucket")
        expected = "BackupJob(source='/source/path', dest='dest:bucket', status='pending')"

        assert repr(job) == expected


class TestBackupEngine:
    """Test BackupEngine class."""

    def test_backup_engine_initialization_test_mode(self):
        """Test BackupEngine can be instantiated in test mode."""
        engine = BackupEngine(test_mode=True)

        assert engine.test_mode is True
        assert engine.config is not None
        assert engine.credential_manager is not None

    def test_backup_engine_initialization_production_mode(self):
        """Test BackupEngine can be instantiated in production mode."""
        engine = BackupEngine(test_mode=False)

        assert engine.test_mode is False
        assert engine.config is not None
        assert engine.credential_manager is not None

    def test_backup_engine_create_job_test_mode(self):
        """Test creating backup job in test mode."""
        engine = BackupEngine(test_mode=True)
        job = engine.create_backup_job()

        assert isinstance(job, BackupJob)
        assert job.source_path == "/tmp/photo-backup-test-photos"
        assert job.destination == "minio-test:my-photo-backup-bucket-test"

    def test_backup_engine_get_backup_info_test_mode(self):
        """Test getting backup info in test mode."""
        engine = BackupEngine(test_mode=True)
        info = engine.get_backup_info()

        assert info["mode"] == "test"
        assert info["source_path"] == "/tmp/photo-backup-test-photos"
        assert info["destination"] == "minio-test:my-photo-backup-bucket-test"
        assert info["endpoint"] == "localhost:9000"
        assert "dry_run" in info
        assert "credential_status" in info

    def test_backup_engine_get_backup_info_production_mode(self):
        """Test getting backup info in production mode."""
        engine = BackupEngine(test_mode=False)
        info = engine.get_backup_info()

        assert info["mode"] == "production"
        assert info["endpoint"] == "s3.wasabisys.com"

    def test_backup_engine_validate_environment(self):
        """Test environment validation (may fail without Minio)."""
        engine = BackupEngine(test_mode=True)
        is_valid, errors = engine.validate_backup_environment()

        # Environment validation should complete without exceptions
        assert isinstance(is_valid, bool)
        assert isinstance(errors, list)
        # In test environment without Minio, validation may fail - that's expected


class TestRcloneDetection:
    """Test rclone detection functionality."""

    @patch("photo_backup.backup.subprocess.run")
    def test_check_rclone_success(self, mock_run):
        """Test successful rclone detection with valid version."""
        # Mock successful rclone version output
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "rclone v1.64.2\n- os/version: darwin/arm64"
        mock_run.return_value = mock_result

        is_available, message, version = check_rclone()

        assert is_available is True
        assert "v1.64.2 found (meets minimum requirement v1.50.0)" in message
        assert version == "1.64.2"
        mock_run.assert_called_once_with(["rclone", "version"], capture_output=True, text=True, timeout=10.0)

    @patch("photo_backup.backup.subprocess.run")
    def test_check_rclone_old_version(self, mock_run):
        """Test rclone detection with version too old."""
        # Mock old version output
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "rclone v1.40.2\n- os/version: darwin/arm64"
        mock_run.return_value = mock_result

        is_available, message, version = check_rclone()

        assert is_available is False
        assert "v1.40.2 found but is too old" in message
        assert version == "1.40.2"

    @patch("photo_backup.backup.subprocess.run")
    def test_check_rclone_not_found(self, mock_run):
        """Test rclone not installed."""
        mock_run.side_effect = FileNotFoundError()

        is_available, message, version = check_rclone()

        assert is_available is False
        assert "rclone not found" in message
        assert "https://rclone.org/install/" in message
        assert version is None

    @patch("photo_backup.backup.subprocess.run")
    def test_check_rclone_timeout(self, mock_run):
        """Test rclone command timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired("rclone", 10.0)

        is_available, message, version = check_rclone()

        assert is_available is False
        assert "rclone version check timed out" in message
        assert version is None

    @patch("photo_backup.backup.subprocess.run")
    def test_check_rclone_command_failed(self, mock_run):
        """Test rclone command returns error."""
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "command not found"
        mock_run.return_value = mock_result

        is_available, message, version = check_rclone()

        assert is_available is False
        assert "rclone command failed" in message
        assert version is None

    @patch("photo_backup.backup.subprocess.run")
    def test_check_rclone_version_unparseable(self, mock_run):
        """Test rclone with unparseable version output."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "some unexpected output\nno version here"
        mock_run.return_value = mock_result

        is_available, message, version = check_rclone()

        assert is_available is True
        assert "rclone found but version could not be determined" in message
        assert version is None


class TestVersionComparison:
    """Test version comparison functionality."""

    def test_is_version_sufficient_equal(self):
        """Test version comparison with equal versions."""
        assert _is_version_sufficient("1.50.0", "1.50.0") is True

    def test_is_version_sufficient_newer(self):
        """Test version comparison with newer version."""
        assert _is_version_sufficient("1.64.2", "1.50.0") is True
        assert _is_version_sufficient("2.0.0", "1.50.0") is True
        assert _is_version_sufficient("1.51.0", "1.50.0") is True

    def test_is_version_sufficient_older(self):
        """Test version comparison with older version."""
        assert _is_version_sufficient("1.40.0", "1.50.0") is False
        assert _is_version_sufficient("0.9.0", "1.50.0") is False
        assert _is_version_sufficient("1.49.9", "1.50.0") is False

    def test_is_version_sufficient_different_lengths(self):
        """Test version comparison with different version string lengths."""
        assert _is_version_sufficient("1.50", "1.50.0") is True
        assert _is_version_sufficient("1.50.0", "1.50") is True
        assert _is_version_sufficient("1.50.1", "1.50") is True

    def test_is_version_sufficient_invalid_versions(self):
        """Test version comparison with invalid version strings."""
        # Should return True for unparseable versions (assume sufficient)
        assert _is_version_sufficient("invalid", "1.50.0") is True
        assert _is_version_sufficient("1.50.0", "invalid") is True


class TestBackupEngineWithRclone:
    """Test BackupEngine integration with rclone detection."""

    def test_backup_info_includes_rclone_status(self):
        """Test that backup info includes rclone status."""
        engine = BackupEngine(test_mode=True)
        info = engine.get_backup_info()

        assert "rclone_status" in info
        assert "available" in info["rclone_status"]
        assert "message" in info["rclone_status"]
        assert "version" in info["rclone_status"]

    @patch("photo_backup.backup.check_rclone")
    def test_backup_info_with_rclone_unavailable(self, mock_check_rclone):
        """Test backup info when rclone is not available."""
        mock_check_rclone.return_value = (False, "rclone not found", None)

        engine = BackupEngine(test_mode=True)
        info = engine.get_backup_info()

        assert info["rclone_status"]["available"] is False
        assert info["rclone_status"]["message"] == "rclone not found"
        assert info["rclone_status"]["version"] is None

    @patch("photo_backup.backup.check_rclone")
    def test_validate_environment_with_rclone_failure(self, mock_check_rclone):
        """Test environment validation when rclone check fails."""
        mock_check_rclone.return_value = (False, "rclone not found", None)

        engine = BackupEngine(test_mode=True)
        is_valid, errors = engine.validate_backup_environment()

        assert is_valid is False
        assert any("rclone check failed" in error for error in errors)
