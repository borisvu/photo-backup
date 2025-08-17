"""
Unit tests for the backup module.
"""

import subprocess
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from photo_backup.backup import BackupEngine, BackupJob, BackupStats, _is_version_sufficient, check_rclone
from photo_backup.progress_parser import TransferStats


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


class TestSyncWithProgress:
    """Test sync with progress parsing functionality."""

    @patch("photo_backup.backup.subprocess.Popen")
    def test_sync_with_progress_success(self, mock_popen):
        """Test successful sync with progress parsing."""
        # Mock process and output
        mock_process = MagicMock()
        mock_process.stdout.readline.side_effect = [
            "Transferred: 2 / 5 files, 1.0 MiB / 2.5 MiB, 40% complete, 0.5 MiB/s, ETA 3s\n",
            "Transferred: 5 / 5 files, 2.5 MiB / 2.5 MiB, 100% complete\n",
            "",  # End of output
        ]
        mock_process.wait.return_value = 0
        mock_popen.return_value = mock_process

        engine = BackupEngine(test_mode=True)
        job = BackupJob("/source/path", "minio-test:bucket", dry_run=False)

        success, output, sync_info, backup_stats = engine.sync_with_progress(job)

        # Verify success
        assert success is True
        assert "Transferred: 5 / 5 files" in output

        # Verify transfer stats are included
        assert "transfer_stats" in sync_info
        transfer_stats = sync_info["transfer_stats"]
        assert transfer_stats["files_transferred"] == 5
        assert transfer_stats["files_total"] == 5
        assert transfer_stats["percentage"] == 100.0

    @patch("photo_backup.backup.subprocess.Popen")
    def test_sync_with_progress_real_time_parsing(self, mock_popen):
        """Test that progress is parsed in real-time."""
        # Mock process with progressive output
        mock_process = MagicMock()
        output_lines = [
            "Transferred: 1 / 5 files, 0.5 MiB / 2.5 MiB, 20% complete\n",
            "Transferred: 3 / 5 files, 1.5 MiB / 2.5 MiB, 60% complete\n",
            "Transferred: 5 files (2.5 MiB)\n",
            "",  # End of output
        ]
        mock_process.stdout.readline.side_effect = output_lines
        mock_process.wait.return_value = 0
        mock_popen.return_value = mock_process

        engine = BackupEngine(test_mode=True)
        job = BackupJob("/source/path", "minio-test:bucket", dry_run=False)

        # Mock progress callback to verify it's called
        progress_events = []

        def capture_progress(stats):
            progress_events.append((stats.files_transferred, stats.percentage))

        # Execute sync with progress
        success, output, sync_info, backup_stats = engine.sync_with_progress(job)

        # Verify success and that all lines were processed
        assert success is True
        assert "Transferred: 5 files" in output

        # Verify final stats
        transfer_stats = sync_info["transfer_stats"]
        assert transfer_stats["files_transferred"] == 5
        assert transfer_stats["percentage"] == 100.0

    @patch("photo_backup.backup.subprocess.Popen")
    def test_sync_with_progress_timeout(self, mock_popen):
        """Test sync with progress handling timeout."""
        # Mock process that times out
        mock_process = MagicMock()
        mock_process.stdout.readline.side_effect = [
            "Transferred: 1 / 5 files, 0.5 MiB / 2.5 MiB, 20% complete\n",
            "",  # End of output before completion
        ]
        mock_process.wait.side_effect = subprocess.TimeoutExpired("rclone", 300)
        mock_popen.return_value = mock_process

        engine = BackupEngine(test_mode=True)
        job = BackupJob("/source/path", "minio-test:bucket", dry_run=False)

        success, output, sync_info, backup_stats = engine.sync_with_progress(job)

        # Verify timeout handling
        assert success is False
        assert "timed out" in output
        assert sync_info["return_code"] == -1

        # Verify transfer stats are still available
        assert "transfer_stats" in sync_info

        # Verify process was killed
        mock_process.kill.assert_called_once()

    @patch("photo_backup.backup.Path")
    @patch("photo_backup.backup.subprocess.Popen")
    def test_sync_with_progress_file_estimation(self, mock_popen, mock_path):
        """Test file count estimation for progress tracking."""
        # Mock file system
        mock_source_path = MagicMock()
        mock_source_path.exists.return_value = True
        mock_source_path.rglob.return_value = [
            MagicMock(is_file=lambda: True),
            MagicMock(is_file=lambda: True),
            MagicMock(is_file=lambda: True),
        ]
        mock_path.return_value = mock_source_path

        # Mock process
        mock_process = MagicMock()
        mock_process.stdout.readline.side_effect = ["Transferred: 3 files (1.5 MiB)\n", ""]
        mock_process.wait.return_value = 0
        mock_popen.return_value = mock_process

        engine = BackupEngine(test_mode=True)
        job = BackupJob("/source/path", "minio-test:bucket", dry_run=False)

        success, output, sync_info, backup_stats = engine.sync_with_progress(job)

        # Verify success
        assert success is True

        # Verify file estimation was attempted
        mock_source_path.rglob.assert_called_with("*")

    @patch("photo_backup.backup.subprocess.Popen")
    def test_sync_with_progress_error_parsing(self, mock_popen):
        """Test parsing of error messages in progress output."""
        # Mock process with errors
        mock_process = MagicMock()
        mock_process.stdout.readline.side_effect = [
            "Transferred: 1 / 5 files, 0.5 MiB / 2.5 MiB, 20% complete\n",
            "ERROR : file1.jpg: permission denied\n",
            "ERROR : file2.jpg: not found\n",
            "Transferred: 3 files (1.5 MiB)\n",
            "",
        ]
        mock_process.wait.return_value = 0
        mock_popen.return_value = mock_process

        engine = BackupEngine(test_mode=True)
        job = BackupJob("/source/path", "minio-test:bucket", dry_run=False)

        success, output, sync_info, backup_stats = engine.sync_with_progress(job)

        # Verify success (rclone returns 0 even with some errors)
        assert success is True

        # Verify errors were captured in output
        assert "ERROR" in output
        assert "permission denied" in output
        assert "not found" in output

        # Verify transfer stats include error count
        transfer_stats = sync_info["transfer_stats"]
        assert transfer_stats["errors"] == 2


class TestBackupStats:
    """Test BackupStats class."""

    def test_backup_stats_initialization(self):
        """Test BackupStats can be initialized correctly."""
        start_time = datetime.now()
        end_time = start_time + timedelta(seconds=30)

        stats = BackupStats(
            start_time=start_time,
            end_time=end_time,
            duration_seconds=30.0,
            files_transferred=100,
            files_total=120,
            bytes_transferred=1048576,  # 1 MB
            bytes_total=1258291,  # ~1.2 MB
            source_path="/test/source",
            destination="test:bucket",
            dry_run=False,
            test_mode=True,
            success=True,
        )

        assert stats.start_time == start_time
        assert stats.end_time == end_time
        assert stats.duration_seconds == 30.0
        assert stats.files_transferred == 100
        assert stats.files_total == 120
        assert stats.bytes_transferred == 1048576
        assert stats.bytes_total == 1258291
        assert stats.source_path == "/test/source"
        assert stats.destination == "test:bucket"
        assert stats.dry_run is False
        assert stats.test_mode is True
        assert stats.success is True
        assert stats.error_message is None

    def test_backup_stats_from_transfer_stats(self):
        """Test creating BackupStats from TransferStats."""
        # Create mock transfer stats
        transfer_stats = TransferStats(
            files_transferred=50,
            files_total=60,
            bytes_transferred=524288,  # 512 KB
            bytes_total=629145,  # ~615 KB
            transfer_rate_mbps=2.5,
            errors=1,
        )

        start_time = datetime.now()
        end_time = start_time + timedelta(seconds=15)

        backup_stats = BackupStats.from_transfer_stats(
            transfer_stats=transfer_stats,
            start_time=start_time,
            end_time=end_time,
            source_path="/test/photos",
            destination="minio:test-bucket",
            dry_run=True,
            test_mode=True,
            success=True,
        )

        assert backup_stats.files_transferred == 50
        assert backup_stats.files_total == 60
        assert backup_stats.bytes_transferred == 524288
        assert backup_stats.bytes_total == 629145
        assert backup_stats.errors == 1
        assert backup_stats.duration_seconds == 15.0
        assert backup_stats.source_path == "/test/photos"
        assert backup_stats.destination == "minio:test-bucket"
        assert backup_stats.dry_run is True
        assert backup_stats.test_mode is True
        assert backup_stats.success is True

        # Verify calculated rates
        assert backup_stats.transfer_rate_mbps > 0  # Should be calculated from bytes/duration
        assert backup_stats.files_rate_per_second > 0  # Should be calculated from files/duration

    def test_backup_stats_percentages(self):
        """Test percentage calculations."""
        stats = BackupStats(
            start_time=datetime.now(),
            files_transferred=75,
            files_total=100,
            bytes_transferred=750000,
            bytes_total=1000000,
        )

        assert stats.files_percentage == 75.0
        assert stats.bytes_percentage == 75.0

        # Test edge cases
        stats_empty = BackupStats(
            start_time=datetime.now(),
            files_transferred=0,
            files_total=0,
            bytes_transferred=0,
            bytes_total=0,
        )

        assert stats_empty.files_percentage == 0.0
        assert stats_empty.bytes_percentage == 0.0

    def test_backup_stats_formatted_bytes(self):
        """Test byte formatting."""
        stats = BackupStats(
            start_time=datetime.now(),
            bytes_transferred=1024,
            bytes_total=1048576,
        )

        assert stats.formatted_bytes_transferred == "1.0 KB"
        assert stats.formatted_bytes_total == "1.0 MB"

        # Test different sizes
        stats.bytes_transferred = 512
        assert stats._format_bytes(512) == "512 B"

        stats.bytes_transferred = 1536
        assert stats._format_bytes(1536) == "1.5 KB"

        stats.bytes_transferred = 1073741824
        assert stats._format_bytes(1073741824) == "1.0 GB"

    def test_backup_stats_formatted_duration(self):
        """Test duration formatting."""
        # Test seconds
        stats = BackupStats(
            start_time=datetime.now(),
            duration_seconds=45.5,
        )
        assert stats.formatted_duration == "45.5s"

        # Test minutes
        stats.duration_seconds = 125.0  # 2m 5s
        assert stats.formatted_duration == "2m 5s"

        # Test hours
        stats.duration_seconds = 3665.0  # 1h 1m
        assert stats.formatted_duration == "1h 1m"

    def test_backup_stats_summary(self):
        """Test summary generation."""
        stats = BackupStats(
            start_time=datetime.now(),
            end_time=datetime.now() + timedelta(seconds=60),
            duration_seconds=60.0,
            files_transferred=100,
            files_total=100,
            bytes_transferred=1048576,  # 1 MB
            bytes_total=1048576,
            transfer_rate_mbps=1.0,
            files_rate_per_second=1.67,
            source_path="/test/source",
            destination="test:bucket",
            dry_run=False,
            test_mode=True,
            success=True,
            errors=0,
        )

        summary = stats.get_summary()

        assert "SUCCESS" in summary
        assert "TEST MODE" in summary
        assert "1m 0s" in summary
        assert "100/100 (100.0%)" in summary
        assert "1.0 MB/1.0 MB (100.0%)" in summary
        assert "1.0 MB/s" in summary
        assert "1.7 files/s" in summary

    def test_backup_stats_summary_with_errors(self):
        """Test summary with errors and failure."""
        stats = BackupStats(
            start_time=datetime.now(),
            duration_seconds=30.0,
            files_transferred=50,
            files_total=100,
            bytes_transferred=500000,
            bytes_total=1000000,
            errors=3,
            dry_run=True,
            test_mode=False,
            success=False,
            error_message="Connection timeout",
        )

        summary = stats.get_summary()

        assert "FAILED" in summary
        assert "DRY RUN PRODUCTION" in summary
        assert "Errors: 3" in summary
        assert "Error: Connection timeout" in summary

    def test_backup_stats_to_dict(self):
        """Test dictionary conversion."""
        start_time = datetime.now()
        end_time = start_time + timedelta(seconds=45)

        stats = BackupStats(
            start_time=start_time,
            end_time=end_time,
            duration_seconds=45.0,
            files_transferred=25,
            files_total=30,
            bytes_transferred=262144,  # 256 KB
            bytes_total=314572,  # ~307 KB
            transfer_rate_mbps=0.5,
            files_rate_per_second=0.56,
            source_path="/test/src",
            destination="s3:my-bucket",
            dry_run=False,
            test_mode=False,
            success=True,
        )

        data = stats.to_dict()

        assert data["start_time"] == start_time.isoformat()
        assert data["end_time"] == end_time.isoformat()
        assert data["duration_seconds"] == 45.0
        assert data["files_transferred"] == 25
        assert data["files_total"] == 30
        assert data["bytes_transferred"] == 262144
        assert data["bytes_total"] == 314572
        assert data["transfer_rate_mbps"] == 0.5
        assert data["files_rate_per_second"] == 0.56
        assert data["files_percentage"] == stats.files_percentage
        assert data["bytes_percentage"] == stats.bytes_percentage
        assert data["source_path"] == "/test/src"
        assert data["destination"] == "s3:my-bucket"
        assert data["dry_run"] is False
        assert data["test_mode"] is False
        assert data["success"] is True
        assert data["error_message"] is None
        assert data["formatted_bytes_transferred"] == "256.0 KB"
        assert data["formatted_bytes_total"] == "307.2 KB"
        assert data["formatted_duration"] == "45.0s"

    def test_backup_stats_rate_calculations(self):
        """Test rate calculations in from_transfer_stats."""
        transfer_stats = TransferStats(
            files_transferred=60,
            bytes_transferred=6291456,  # 6 MB
        )

        start_time = datetime.now()
        end_time = start_time + timedelta(seconds=30)  # 30 seconds

        backup_stats = BackupStats.from_transfer_stats(
            transfer_stats=transfer_stats,
            start_time=start_time,
            end_time=end_time,
            source_path="/test",
            destination="test:bucket",
            dry_run=False,
            test_mode=True,
            success=True,
        )

        # Verify rate calculations
        expected_mb_rate = 6.0 / 30.0  # 6 MB in 30 seconds = 0.2 MB/s
        expected_files_rate = 60.0 / 30.0  # 60 files in 30 seconds = 2.0 files/s

        assert abs(backup_stats.transfer_rate_mbps - expected_mb_rate) < 0.01
        assert abs(backup_stats.files_rate_per_second - expected_files_rate) < 0.01

    def test_backup_stats_zero_duration(self):
        """Test behavior with zero duration."""
        transfer_stats = TransferStats(
            files_transferred=10,
            bytes_transferred=1024,
        )

        start_time = datetime.now()
        end_time = start_time  # Same time = zero duration

        backup_stats = BackupStats.from_transfer_stats(
            transfer_stats=transfer_stats,
            start_time=start_time,
            end_time=end_time,
            source_path="/test",
            destination="test:bucket",
            dry_run=False,
            test_mode=True,
            success=True,
        )

        # Rates should be 0 when duration is 0
        assert backup_stats.transfer_rate_mbps == 0.0
        assert backup_stats.files_rate_per_second == 0.0
        assert backup_stats.duration_seconds == 0.0


class TestSyncWithStats:
    """Test BackupEngine sync_with_stats method."""

    @patch("photo_backup.backup.subprocess.Popen")
    @patch("photo_backup.backup.Path")
    def test_sync_with_stats_success(self, mock_path, mock_popen):
        """Test sync_with_stats returns BackupStats."""
        # Setup mocks
        mock_path.return_value.rglob.return_value = ["file1.jpg", "file2.jpg"]

        mock_process = MagicMock()
        mock_process.stdout.readline.side_effect = [
            "Transferred:   2 / 2, 100%\n",
            "",  # End of output
        ]
        mock_process.wait.return_value = 0
        mock_popen.return_value = mock_process

        # Create engine and job
        engine = BackupEngine(test_mode=True)
        job = BackupJob("/test/source", "test:bucket", dry_run=False)

        # Mock credential manager
        with patch.object(engine.credential_manager, "get_credentials") as mock_creds:
            mock_creds.return_value = {
                "access_key": "test_key",
                "secret_key": "test_secret",
                "endpoint": "localhost:9000",
                "region": "us-east-1",
                "use_ssl": False,
            }

            # Execute sync_with_stats
            backup_stats = engine.sync_with_stats(job)

            # Verify BackupStats object
            assert isinstance(backup_stats, BackupStats)
            assert backup_stats.source_path == "/test/source"
            assert backup_stats.destination == "test:bucket"
            assert backup_stats.dry_run is False
            assert backup_stats.test_mode is True
            assert backup_stats.success is True
            assert backup_stats.duration_seconds > 0
            assert backup_stats.start_time is not None
            assert backup_stats.end_time is not None
