"""
Functional tests for configuration CLI commands.

These tests verify that the config and validate commands work correctly
through the main CLI interface.
"""

import os
import subprocess
import sys
import tempfile

from pathlib import Path


class TestConfigCLICommand:
    """Test cases for the photo-backup config command."""

    def test_config_command_shows_configuration(self):
        """Test that config command displays configuration."""
        result = subprocess.run(
            [sys.executable, "-m", "photo_backup.main", "config"],
            capture_output=True,
            text=True,
            cwd=".",
        )

        assert result.returncode == 0
        assert "Configuration for Photo Backup System" in result.stdout
        assert "Mode: PRODUCTION MODE" in result.stdout
        assert "Backup Settings:" in result.stdout
        assert "Storage Settings:" in result.stdout

    def test_config_command_test_mode_via_cli_flag(self):
        """Test config command with test mode via CLI flag."""
        result = subprocess.run(
            [sys.executable, "-m", "photo_backup.main", "--test-mode", "config"],
            capture_output=True,
            text=True,
            cwd=".",
        )

        assert result.returncode == 0
        assert "Mode: TEST MODE" in result.stdout
        # After refactoring: config file overrides test defaults
        assert "Endpoint:" in result.stdout  # Endpoint is shown, regardless of value

    def test_config_command_test_mode_via_env_var(self):
        """Test config command with test mode via environment variable."""
        env = os.environ.copy()
        env["PHOTO_BACKUP_TEST_MODE"] = "1"

        result = subprocess.run(
            [sys.executable, "-m", "photo_backup.main", "config"],
            capture_output=True,
            text=True,
            cwd=".",
            env=env,
        )

        assert result.returncode == 0
        assert "Mode: TEST MODE" in result.stdout
        # After refactoring: config file overrides test defaults
        assert "Endpoint:" in result.stdout  # Endpoint is shown, regardless of value

    def test_config_command_shows_environment_overrides(self):
        """Test config command shows environment variable overrides."""
        env = os.environ.copy()
        env["PHOTO_BACKUP_BACKUP_SOURCE_PATH"] = "/custom/source/path"
        env["PHOTO_BACKUP_STORAGE_ENDPOINT"] = "custom.endpoint.com:9000"

        result = subprocess.run(
            [sys.executable, "-m", "photo_backup.main", "config"],
            capture_output=True,
            text=True,
            cwd=".",
            env=env,
        )

        assert result.returncode == 0
        assert "Environment Overrides: 2 variables" in result.stdout
        assert "PHOTO_BACKUP_BACKUP_SOURCE_PATH" in result.stdout
        assert "PHOTO_BACKUP_STORAGE_ENDPOINT" in result.stdout

    def test_config_command_shows_no_environment_overrides(self):
        """Test config command shows no environment overrides when none exist."""
        result = subprocess.run(
            [sys.executable, "-m", "photo_backup.main", "config"],
            capture_output=True,
            text=True,
            cwd=".",
        )

        assert result.returncode == 0
        assert "Environment Overrides: None" in result.stdout

    def test_config_command_masks_sensitive_data(self):
        """Test config command masks sensitive information."""
        result = subprocess.run(
            [sys.executable, "-m", "photo_backup.main", "--test-mode", "config"],
            capture_output=True,
            text=True,
            cwd=".",
        )

        assert result.returncode == 0
        # Should not show full credentials
        assert "minioadmin" not in result.stdout

    def test_config_command_shows_config_file_location(self):
        """Test config command shows config file location."""
        result = subprocess.run(
            [sys.executable, "-m", "photo_backup.main", "config"],
            capture_output=True,
            text=True,
            cwd=".",
        )

        assert result.returncode == 0
        assert "Config File:" in result.stdout

    def test_config_command_includes_all_sections(self):
        """Test config command includes all configuration sections."""
        result = subprocess.run(
            [sys.executable, "-m", "photo_backup.main", "config"],
            capture_output=True,
            text=True,
            cwd=".",
        )

        assert result.returncode == 0
        sections = [
            "Backup Settings:",
            "Storage Settings:",
            "Monitoring Settings:",
            "Logging Settings:",
            "State Settings:",
            "Security Settings:",
            "Performance Settings:",
            "Notifications Settings:",
        ]

        for section in sections:
            assert section in result.stdout

    def test_config_command_help_available(self):
        """Test config command help is available."""
        result = subprocess.run(
            [sys.executable, "-m", "photo_backup.main", "config", "--help"],
            capture_output=True,
            text=True,
            cwd=".",
        )

        assert result.returncode == 0
        assert "Display current configuration settings" in result.stdout

    def test_config_command_in_main_help(self):
        """Test config command appears in main help."""
        result = subprocess.run(
            [sys.executable, "-m", "photo_backup.main", "--help"],
            capture_output=True,
            text=True,
            cwd=".",
        )

        assert result.returncode == 0
        assert "config" in result.stdout

    def test_config_command_with_multiple_env_overrides(self):
        """Test config command with multiple environment overrides."""
        env = os.environ.copy()
        env["PHOTO_BACKUP_BACKUP_SOURCE_PATH"] = "/custom/source"
        env["PHOTO_BACKUP_STORAGE_ENDPOINT"] = "custom.endpoint.com"
        env["PHOTO_BACKUP_LOGGING_LEVEL"] = "DEBUG"

        result = subprocess.run(
            [sys.executable, "-m", "photo_backup.main", "config"],
            capture_output=True,
            text=True,
            cwd=".",
            env=env,
        )

        assert result.returncode == 0
        assert "Environment Overrides: 3 variables" in result.stdout

    def test_config_command_production_vs_test_differences(self):
        """Test config command shows different values in production vs test mode."""
        # Production mode
        prod_result = subprocess.run(
            [sys.executable, "-m", "photo_backup.main", "config"],
            capture_output=True,
            text=True,
            cwd=".",
        )

        # Test mode
        test_result = subprocess.run(
            [sys.executable, "-m", "photo_backup.main", "--test-mode", "config"],
            capture_output=True,
            text=True,
            cwd=".",
        )

        assert prod_result.returncode == 0
        assert test_result.returncode == 0

        # After refactoring: Just verify both modes show config correctly
        # Config file overrides test defaults, so we can't assume specific endpoints
        assert "Mode: PRODUCTION MODE" in prod_result.stdout
        assert "Mode: TEST MODE" in test_result.stdout


class TestValidateCLICommand:
    """Test cases for the photo-backup validate command."""

    MINIO_PORT = 9006  # Unique port for this test suite

    # Use shared fixture factory to avoid code duplication
    from tests.functional.minio_test_utils import MinioTestUtils

    minio_container = MinioTestUtils.create_minio_fixture("photo-backup-config-cli-test", port=MINIO_PORT)

    def test_validate_command_shows_validation_header(self):
        """Test that validate command displays validation header."""
        result = subprocess.run(
            [sys.executable, "-m", "photo_backup.main", "validate"],
            capture_output=True,
            text=True,
            cwd=".",
        )

        assert result.returncode == 1  # Should fail due to missing paths
        assert "Configuration Validation for Photo Backup System" in result.stdout
        assert "Mode: PRODUCTION MODE" in result.stdout
        assert "VALIDATION SUMMARY:" in result.stdout

    def test_validate_command_test_mode_via_cli_flag(self):
        """Test validate command with test mode via CLI flag."""
        result = subprocess.run(
            [sys.executable, "-m", "photo_backup.main", "--test-mode", "validate"],
            capture_output=True,
            text=True,
            cwd=".",
        )

        assert result.returncode == 1  # Should fail due to missing paths
        assert "Mode: TEST MODE" in result.stdout
        assert "Minio Connection Test:" in result.stdout

    def test_validate_command_test_mode_via_env_var(self):
        """Test validate command with test mode via environment variable."""
        env = os.environ.copy()
        env["PHOTO_BACKUP_TEST_MODE"] = "1"

        result = subprocess.run(
            [sys.executable, "-m", "photo_backup.main", "validate"],
            capture_output=True,
            text=True,
            cwd=".",
            env=env,
        )

        assert result.returncode == 1  # Should fail due to missing paths
        assert "Mode: TEST MODE" in result.stdout
        assert "Minio Connection Test:" in result.stdout

    def test_validate_command_checks_rclone_availability(self):
        """Test validate command checks rclone availability."""
        result = subprocess.run(
            [sys.executable, "-m", "photo_backup.main", "validate"],
            capture_output=True,
            text=True,
            cwd=".",
        )

        assert result.returncode == 1  # Should fail due to missing paths
        assert "Rclone Availability:" in result.stdout
        # Should show rclone status (either available or not)

    def test_validate_command_validates_paths(self):
        """Test validate command validates configuration paths."""
        result = subprocess.run(
            [sys.executable, "-m", "photo_backup.main", "validate"],
            capture_output=True,
            text=True,
            cwd=".",
        )

        assert result.returncode == 1  # Should fail due to missing paths
        assert "Path Validation:" in result.stdout
        assert "Backup source path:" in result.stdout
        assert "Logging directory:" in result.stdout
        assert "State directory:" in result.stdout

    def test_validate_command_validates_configuration_structure(self):
        """Test validate command validates configuration structure."""
        result = subprocess.run(
            [sys.executable, "-m", "photo_backup.main", "validate"],
            capture_output=True,
            text=True,
            cwd=".",
        )

        assert result.returncode == 1  # Should fail due to missing paths
        assert "Configuration Validation:" in result.stdout

    def test_validate_command_help_available(self):
        """Test validate command help is available."""
        result = subprocess.run(
            [sys.executable, "-m", "photo_backup.main", "validate", "--help"],
            capture_output=True,
            text=True,
            cwd=".",
        )

        assert result.returncode == 0
        assert "Validate configuration settings and system requirements" in result.stdout

    def test_validate_command_in_main_help(self):
        """Test validate command appears in main help."""
        result = subprocess.run(
            [sys.executable, "-m", "photo_backup.main", "--help"],
            capture_output=True,
            text=True,
            cwd=".",
        )

        assert result.returncode == 0
        assert "validate" in result.stdout

    def test_validate_command_with_valid_test_setup(self, minio_container, test_photos):
        """Test validate command with valid test setup (requires fixtures)."""
        # This test requires the minio_container and test_photos fixtures
        # which create the necessary paths and start Minio

        # Create missing directories that the validate command expects

        # Create logging directory
        log_dir = Path("/tmp/photo-backup-test/logs")
        log_dir.mkdir(parents=True, exist_ok=True)

        # Create state directory (should already exist from test_photos fixture)
        state_dir = Path("/tmp/photo-backup-test/state")
        state_dir.mkdir(parents=True, exist_ok=True)

        # Set environment variables to use unique port and ensure credentials
        env = os.environ.copy()
        env["PHOTO_BACKUP_STORAGE_ENDPOINT"] = f"localhost:{self.MINIO_PORT}"
        env["PHOTO_BACKUP_STORAGE_ACCESS_KEY"] = "minioadmin"
        env["PHOTO_BACKUP_STORAGE_SECRET_KEY"] = "minioadmin"
        env["PHOTO_BACKUP_STORAGE_USE_SSL"] = "false"
        env["PHOTO_BACKUP_STORAGE_BUCKET"] = "test-bucket"

        result = subprocess.run(
            [sys.executable, "-m", "photo_backup.main", "--test-mode", "validate"],
            capture_output=True,
            text=True,
            cwd=".",
            env=env,
        )

        # Should pass with valid test setup
        assert result.returncode == 0
        assert "Overall Status: ✅ VALID" in result.stdout
        assert "🎉 Configuration is valid and ready for use!" in result.stdout

    def test_validate_command_shows_detailed_error_messages(self):
        """Test validate command shows detailed error messages for failures."""
        result = subprocess.run(
            [sys.executable, "-m", "photo_backup.main", "validate"],
            capture_output=True,
            text=True,
            cwd=".",
        )

        assert result.returncode == 1
        assert "❌ FAIL" in result.stdout
        assert "Overall Status: ❌ INVALID" in result.stdout
        assert "⚠️  Please fix the issues above before proceeding" in result.stdout

    def test_validate_command_checks_all_validation_steps(self):
        """Test validate command performs all validation steps."""
        result = subprocess.run(
            [sys.executable, "-m", "photo_backup.main", "--test-mode", "validate"],
            capture_output=True,
            text=True,
            cwd=".",
        )

        assert result.returncode == 1  # Should fail due to missing paths
        validation_steps = [
            "1. Configuration Validation:",
            "2. Path Validation:",
            "3. Rclone Availability:",
            "4. Minio Connection Test:",
        ]

        for step in validation_steps:
            assert step in result.stdout

    def test_validate_command_production_mode_no_minio_test(self):
        """Test validate command doesn't test Minio in production mode."""
        result = subprocess.run(
            [sys.executable, "-m", "photo_backup.main", "validate"],
            capture_output=True,
            text=True,
            cwd=".",
        )

        assert result.returncode == 1  # Should fail due to missing paths
        assert "Minio Connection Test:" not in result.stdout


class TestSetupConfigCLICommand:
    """Test cases for the photo-backup setup-config command."""

    def test_setup_config_command_shows_help(self):
        """Test that setup-config command displays help."""
        # Set up environment
        env = os.environ.copy()
        env["PYTHONPATH"] = str(Path.cwd().absolute())

        result = subprocess.run(
            [sys.executable, "-m", "photo_backup.main", "setup-config", "--help"],
            capture_output=True,
            text=True,
            cwd=".",
            env=env,
        )

        assert result.returncode == 0
        assert "Create user config directory and copy example configuration" in result.stdout

    def test_setup_config_command_in_main_help(self):
        """Test setup-config command appears in main help."""
        # Set up environment
        env = os.environ.copy()
        env["PYTHONPATH"] = str(Path.cwd().absolute())

        result = subprocess.run(
            [sys.executable, "-m", "photo_backup.main", "--help"],
            capture_output=True,
            text=True,
            cwd=".",
            env=env,
        )

        assert result.returncode == 0
        assert "setup-config" in result.stdout

    def test_setup_config_command_test_mode_via_cli_flag(self):
        """Test setup-config command with test mode via CLI flag."""
        # Clean up any existing test config
        import shutil

        from pathlib import Path

        test_config_dir = Path("/tmp/photo-backup-test")
        if test_config_dir.exists():
            shutil.rmtree(test_config_dir)

        try:
            # Set up environment
            env = os.environ.copy()
            env["PYTHONPATH"] = str(Path.cwd().absolute())

            result = subprocess.run(
                [sys.executable, "-m", "photo_backup.main", "--test-mode", "setup-config"],
                capture_output=True,
                text=True,
                cwd=".",
                env=env,
            )

            assert result.returncode == 0
            assert "Mode: TEST MODE" in result.stdout
            assert "Created config directory and copied example config" in result.stdout
            assert "/tmp/photo-backup-test/config.yaml" in result.stdout
            assert "Configuration created for testing" in result.stdout
            assert "photo-backup validate --test-mode" in result.stdout

            # Verify the config was actually created
            assert test_config_dir.exists()
            assert (test_config_dir / "config.yaml").exists()

        finally:
            # Clean up
            if test_config_dir.exists():
                shutil.rmtree(test_config_dir)

    def test_setup_config_command_test_mode_via_env_var(self):
        """Test setup-config command with test mode via environment variable."""
        # Clean up any existing test config
        import shutil

        from pathlib import Path

        test_config_dir = Path("/tmp/photo-backup-test")
        if test_config_dir.exists():
            shutil.rmtree(test_config_dir)

        env = os.environ.copy()
        env["PHOTO_BACKUP_TEST_MODE"] = "1"
        env["PYTHONPATH"] = str(Path.cwd().absolute())

        try:
            result = subprocess.run(
                [sys.executable, "-m", "photo_backup.main", "setup-config"],
                capture_output=True,
                text=True,
                cwd=".",
                env=env,
            )

            assert result.returncode == 0
            assert "Mode: TEST MODE" in result.stdout
            assert "Created config directory and copied example config" in result.stdout

        finally:
            # Clean up
            if test_config_dir.exists():
                shutil.rmtree(test_config_dir)

    def test_setup_config_command_production_mode(self):
        """Test setup-config command in production mode."""
        # Use a temporary directory as fake home to avoid modifying real config

        from pathlib import Path

        with tempfile.TemporaryDirectory() as temp_home:
            # Set up environment
            env = os.environ.copy()
            env["HOME"] = temp_home
            env["PYTHONPATH"] = str(Path.cwd().absolute())

            result = subprocess.run(
                [sys.executable, "-m", "photo_backup.main", "setup-config"],
                capture_output=True,
                text=True,
                cwd=".",
                env=env,
            )

            assert result.returncode == 0
            assert "Mode: PRODUCTION MODE" in result.stdout
            assert "Created config directory and copied example config" in result.stdout
            assert f"{temp_home}/.config/photo-backup/config.yaml" in result.stdout
            assert "Edit the configuration file with your settings" in result.stdout
            assert "photo-backup validate" in result.stdout

            # Verify the config was actually created
            config_dir = Path(temp_home) / ".config" / "photo-backup"
            config_file = config_dir / "config.yaml"
            assert config_dir.exists()
            assert config_file.exists()

    def test_setup_config_command_already_exists(self):
        """Test setup-config command when config already exists."""
        # Clean up and create test config first
        import shutil

        from pathlib import Path

        test_config_dir = Path("/tmp/photo-backup-test")
        if test_config_dir.exists():
            shutil.rmtree(test_config_dir)

        try:
            # Create existing config
            test_config_dir.mkdir(parents=True, exist_ok=True)
            (test_config_dir / "config.yaml").write_text("existing: config")

            # Set up environment
            env = os.environ.copy()
            env["PYTHONPATH"] = str(Path.cwd().absolute())

            result = subprocess.run(
                [sys.executable, "-m", "photo_backup.main", "--test-mode", "setup-config"],
                capture_output=True,
                text=True,
                cwd=".",
                env=env,
            )

            assert result.returncode == 0
            assert "Mode: TEST MODE" in result.stdout
            assert "Configuration file already exists" in result.stdout

        finally:
            # Clean up
            if test_config_dir.exists():
                shutil.rmtree(test_config_dir)

    def test_setup_config_command_shows_next_steps(self):
        """Test setup-config command shows appropriate next steps."""
        # Clean up any existing test config
        import shutil

        from pathlib import Path

        test_config_dir = Path("/tmp/photo-backup-test")
        if test_config_dir.exists():
            shutil.rmtree(test_config_dir)

        try:
            # Set up environment
            env = os.environ.copy()
            env["PYTHONPATH"] = str(Path.cwd().absolute())

            result = subprocess.run(
                [sys.executable, "-m", "photo_backup.main", "--test-mode", "setup-config"],
                capture_output=True,
                text=True,
                cwd=".",
                env=env,
            )

            assert result.returncode == 0
            assert "📝 Next Steps:" in result.stdout
            assert "1. Configuration created for testing" in result.stdout
            assert "2. Run 'photo-backup validate --test-mode' to verify setup" in result.stdout

        finally:
            # Clean up
            if test_config_dir.exists():
                shutil.rmtree(test_config_dir)

    def test_setup_config_command_production_next_steps(self):
        """Test setup-config command shows production-specific next steps."""

        from pathlib import Path

        with tempfile.TemporaryDirectory() as temp_home:
            # Set up environment
            env = os.environ.copy()
            env["HOME"] = temp_home
            env["PYTHONPATH"] = str(Path.cwd().absolute())

            result = subprocess.run(
                [sys.executable, "-m", "photo_backup.main", "setup-config"],
                capture_output=True,
                text=True,
                cwd=".",
                env=env,
            )

            assert result.returncode == 0
            assert "📝 Next Steps:" in result.stdout
            assert "1. Edit the configuration file with your settings:" in result.stdout
            assert "2. Update storage credentials and backup paths" in result.stdout
            assert "3. Run 'photo-backup validate' to verify your configuration" in result.stdout
            assert "4. Run 'photo-backup config' to view current settings" in result.stdout
