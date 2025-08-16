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


class TestRcloneCommandBuilding:
    """Test rclone command building functionality."""

    def test_build_sync_command_test_mode(self):
        """Test building rclone sync command in test mode."""
        engine = BackupEngine(test_mode=True)
        job = BackupJob("/source/path", "minio-test:bucket", dry_run=False)

        cmd = engine.build_sync_command(job)

        # Verify basic command structure
        assert cmd[0] == "rclone"
        assert cmd[1] == "sync"
        assert cmd[2] == "/source/path"
        assert cmd[3] == "test:bucket"  # Should use 'test' remote name

        # Verify key options are present
        assert "--transfers" in cmd
        assert "--checkers" in cmd
        assert "--progress" in cmd
        assert "--checksum" in cmd
        assert "--config" in cmd
        assert "RCLONE_CONFIG_PATH" in cmd

        # Verify test mode specific options
        assert "--verbose" in cmd

        # Verify dry-run is NOT present when dry_run=False
        assert "--dry-run" not in cmd

    def test_build_sync_command_with_dry_run(self):
        """Test building rclone sync command with dry-run enabled."""
        engine = BackupEngine(test_mode=True)
        job = BackupJob("/source/path", "minio-test:bucket", dry_run=True)

        cmd = engine.build_sync_command(job)

        # Verify dry-run flag is present
        assert "--dry-run" in cmd

    @patch("photo_backup.backup.CredentialManager")
    def test_build_sync_command_production_mode(self, _mock_credential_manager):
        """Test building rclone sync command in production mode."""
        # Mock credential manager to avoid real credential lookup
        mock_creds = {
            "access_key": "test_key",
            "secret_key": "test_secret",
            "endpoint": "s3.wasabisys.com",
            "region": "us-east-1",
            "use_ssl": True,
            "bucket": "test-bucket",
        }

        engine = BackupEngine(test_mode=False)
        engine.credential_manager.get_credentials = MagicMock(return_value=mock_creds)
        job = BackupJob("/source/path", "wasabi:bucket", dry_run=False)

        cmd = engine.build_sync_command(job)

        # Verify basic command structure
        assert cmd[0] == "rclone"
        assert cmd[1] == "sync"
        assert cmd[2] == "/source/path"
        assert cmd[3] == "test:bucket"  # Still uses 'test' but with production destination

        # Verify production mode specific options
        assert "--quiet" in cmd
        assert "--verbose" not in cmd

    def test_build_sync_command_with_config_options(self):
        """Test that command includes configuration-based options."""
        engine = BackupEngine(test_mode=True)
        job = BackupJob("/source/path", "minio-test:bucket")

        cmd = engine.build_sync_command(job)

        # Check that config values are used (with defaults)
        transfers_idx = cmd.index("--transfers")
        assert cmd[transfers_idx + 1] == "8"  # Default value

        checkers_idx = cmd.index("--checkers")
        assert cmd[checkers_idx + 1] == "16"  # Default value

        chunk_size_idx = cmd.index("--s3-chunk-size")
        assert cmd[chunk_size_idx + 1] == "10M"  # Default value

    def test_build_sync_command_destination_parsing(self):
        """Test destination parsing for different formats."""
        engine = BackupEngine(test_mode=True)

        # Test with colon-separated destination
        job1 = BackupJob("/source", "minio-test:bucket/path", dry_run=False)
        cmd1 = engine.build_sync_command(job1)
        assert "test:bucket/path" in cmd1

        # Test with simple destination (no colon)
        job2 = BackupJob("/source", "bucket", dry_run=False)
        cmd2 = engine.build_sync_command(job2)
        assert "test:bucket" in cmd2

    def test_build_sync_command_excludes_hidden_files(self):
        """Test that command excludes common unwanted files."""
        engine = BackupEngine(test_mode=True)
        job = BackupJob("/source/path", "minio-test:bucket")

        cmd = engine.build_sync_command(job)

        # Verify exclude patterns
        assert "--exclude" in cmd
        exclude_indices = [i for i, x in enumerate(cmd) if x == "--exclude"]
        exclude_patterns = [cmd[i + 1] for i in exclude_indices]

        assert ".*" in exclude_patterns  # Hidden files
        assert "Thumbs.db" in exclude_patterns  # Windows thumbnails
        assert ".DS_Store" in exclude_patterns  # macOS metadata

    def test_build_rclone_config_test_mode(self):
        """Test building rclone config in test mode."""
        engine = BackupEngine(test_mode=True)

        config = engine._build_rclone_config()

        # Verify config structure
        assert "[test]" in config
        assert "type = s3" in config
        assert "provider = Other" in config
        assert "access_key_id = minioadmin" in config
        assert "secret_access_key = minioadmin" in config
        assert "endpoint = http://localhost:9000" in config
        assert "use_ssl = false" in config

    def test_build_rclone_config_with_ssl(self):
        """Test rclone config building with SSL enabled."""
        # Mock credentials with SSL enabled
        engine = BackupEngine(test_mode=False)
        engine.credential_manager.get_credentials = MagicMock(
            return_value={
                "access_key": "test_key",
                "secret_key": "test_secret",
                "endpoint": "s3.wasabisys.com",
                "region": "us-east-1",
                "use_ssl": True,
                "bucket": "test-bucket",
            }
        )

        config = engine._build_rclone_config()

        # Verify HTTPS endpoint
        assert "endpoint = https://s3.wasabisys.com" in config
        assert "use_ssl = true" in config

    def test_build_sync_command_logging(self):
        """Test that command building includes appropriate logging."""
        engine = BackupEngine(test_mode=True)
        job = BackupJob("/source/path", "minio-test:bucket", dry_run=True)

        with patch.object(engine.logger, "info") as mock_log:
            engine.build_sync_command(job)

            # Verify logging calls
            assert mock_log.call_count >= 2
            log_calls = [call.args[0] for call in mock_log.call_args_list]

            # Check for command building log
            assert any("Built rclone command" in call for call in log_calls)


class TestSyncExecution:
    """Test sync execution functionality."""

    @patch("photo_backup.backup.subprocess.run")
    def test_sync_success(self, mock_run):
        """Test successful sync operation."""
        # Mock successful subprocess result
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Transferred: 5 files, 10.5 MB"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        engine = BackupEngine(test_mode=True)
        job = BackupJob("/source/path", "minio-test:bucket", dry_run=False)

        success, output, sync_info = engine.sync(job)

        # Verify success
        assert success is True
        assert "STDOUT:" in output
        assert "Transferred: 5 files, 10.5 MB" in output

        # Verify sync info
        assert sync_info["return_code"] == 0
        assert "duration_seconds" in sync_info
        assert sync_info["dry_run"] is False
        assert sync_info["test_mode"] is True
        assert "command" in sync_info

        # Verify job status updated
        assert job.status == "completed"
        assert job.error is None

    @patch("photo_backup.backup.subprocess.run")
    def test_sync_failure(self, mock_run):
        """Test failed sync operation."""
        # Mock failed subprocess result
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "ERROR: Failed to connect to bucket"
        mock_run.return_value = mock_result

        engine = BackupEngine(test_mode=True)
        job = BackupJob("/source/path", "minio-test:bucket", dry_run=False)

        success, output, sync_info = engine.sync(job)

        # Verify failure
        assert success is False
        assert "STDERR:" in output
        assert "Failed to connect to bucket" in output

        # Verify sync info
        assert sync_info["return_code"] == 1
        assert "duration_seconds" in sync_info

        # Verify job status updated
        assert job.status == "error"
        assert job.error == "ERROR: Failed to connect to bucket"

    @patch("photo_backup.backup.subprocess.run")
    def test_sync_timeout(self, mock_run):
        """Test sync operation timeout."""
        # Mock timeout exception
        mock_run.side_effect = subprocess.TimeoutExpired("rclone", 300)

        engine = BackupEngine(test_mode=True)
        job = BackupJob("/source/path", "minio-test:bucket", dry_run=False)

        success, output, sync_info = engine.sync(job)

        # Verify timeout handling
        assert success is False
        assert "timed out" in output

        # Verify sync info
        assert sync_info["return_code"] == -1
        assert sync_info["duration_seconds"] == 300.0
        assert sync_info["error"] == "Timeout"

        # Verify job status updated
        assert job.status == "error"
        assert job.error == "Sync operation timed out"

    @patch("photo_backup.backup.subprocess.run")
    def test_sync_dry_run(self, mock_run):
        """Test sync operation in dry run mode."""
        # Mock successful dry run result
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Would transfer: 5 files"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        engine = BackupEngine(test_mode=True)
        job = BackupJob("/source/path", "minio-test:bucket", dry_run=True)

        success, output, sync_info = engine.sync(job)

        # Verify success
        assert success is True
        assert "Would transfer: 5 files" in output

        # Verify dry run flag in sync info
        assert sync_info["dry_run"] is True

        # Verify dry run was included in command
        command = sync_info["command"]
        assert "--dry-run" in command

    @patch("photo_backup.backup.subprocess.run")
    @patch("photo_backup.backup.os.unlink")
    def test_sync_config_cleanup(self, mock_unlink, mock_run):
        """Test that temporary config files are cleaned up."""
        # Mock successful subprocess result
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Success"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        engine = BackupEngine(test_mode=True)
        job = BackupJob("/source/path", "minio-test:bucket", dry_run=False)

        success, output, sync_info = engine.sync(job)

        # Verify config file cleanup was attempted
        assert mock_unlink.called

        # Verify config file path in sync info
        assert "config_file" in sync_info
        assert sync_info["config_file"].endswith(".conf")

    @patch("photo_backup.backup.subprocess.run")
    def test_sync_with_exception(self, mock_run):
        """Test sync operation with unexpected exception."""
        # Mock exception during subprocess
        mock_run.side_effect = Exception("Unexpected error")

        engine = BackupEngine(test_mode=True)
        job = BackupJob("/source/path", "minio-test:bucket", dry_run=False)

        success, output, sync_info = engine.sync(job)

        # Verify exception handling
        assert success is False
        assert "ERROR: Unexpected error" in output

        # Verify sync info
        assert sync_info["return_code"] == -1
        assert sync_info["error"] == "Unexpected error"

        # Verify job status updated
        assert job.status == "error"
        assert job.error == "Unexpected error"

    @patch("photo_backup.backup.subprocess.run")
    def test_sync_command_execution(self, mock_run):
        """Test that sync executes the correct command."""
        # Mock successful subprocess result
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Success"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        engine = BackupEngine(test_mode=True)
        job = BackupJob("/test/source", "minio-test:mybucket", dry_run=True)

        success, output, sync_info = engine.sync(job)

        # Verify subprocess was called
        assert mock_run.called

        # Get the command that was executed
        executed_command = mock_run.call_args[0][0]

        # Verify key command components
        assert executed_command[0] == "rclone"
        assert executed_command[1] == "sync"
        assert executed_command[2] == "/test/source"
        assert executed_command[3] == "test:mybucket"
        assert "--dry-run" in executed_command
        assert "--config" in executed_command

        # Verify command is recorded in sync info
        assert sync_info["command"] == executed_command
