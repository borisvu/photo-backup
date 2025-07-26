"""
Functional tests for config CLI command.

Tests Task 28: Create Config CLI Command functionality including:
- Basic config command output
- Test mode config display
- Environment variable override display
- Config file location display
- Sensitive data masking
- CLI integration
"""

import os
import subprocess
import sys


class TestConfigCLICommand:
    """Test config CLI command functionality."""

    def test_config_command_shows_configuration(self):
        """Test that config command displays configuration settings."""
        result = subprocess.run([sys.executable, "-m", "photo_backup.main", "config"], capture_output=True, text=True)

        assert result.returncode == 0, f"Config command should succeed, got: {result.stderr}"

        # Check for expected output structure
        assert "Configuration for Photo Backup System" in result.stdout
        assert "Mode: PRODUCTION MODE" in result.stdout
        assert "Config File:" in result.stdout
        assert "Environment Overrides:" in result.stdout
        assert "Backup Settings:" in result.stdout
        assert "Storage Settings:" in result.stdout
        assert "Logging Settings:" in result.stdout

    def test_config_command_test_mode_via_cli_flag(self):
        """Test config command with --test-mode flag."""
        result = subprocess.run(
            [sys.executable, "-m", "photo_backup.main", "--test-mode", "config"], capture_output=True, text=True
        )

        assert result.returncode == 0, f"Config command with test mode should succeed, got: {result.stderr}"

        # Check for test mode indicators
        assert "Mode: TEST MODE" in result.stdout
        assert "localhost:9000" in result.stdout  # Minio endpoint
        assert "/tmp/photo-backup-test" in result.stdout  # Test directories

    def test_config_command_test_mode_via_env_var(self):
        """Test config command with PHOTO_BACKUP_TEST_MODE environment variable."""
        env = os.environ.copy()
        env["PHOTO_BACKUP_TEST_MODE"] = "1"

        result = subprocess.run(
            [sys.executable, "-m", "photo_backup.main", "config"], capture_output=True, text=True, env=env
        )

        assert result.returncode == 0, f"Config command with env test mode should succeed, got: {result.stderr}"

        # Check for test mode indicators
        assert "Mode: TEST MODE" in result.stdout
        assert "localhost:9000" in result.stdout  # Minio endpoint

    def test_config_command_shows_environment_overrides(self):
        """Test that config command shows environment variable overrides."""
        env = os.environ.copy()
        env["PHOTO_BACKUP_BACKUP_SOURCE_PATH"] = "/custom/test/path"
        env["PHOTO_BACKUP_LOGGING_LEVEL"] = "DEBUG"

        result = subprocess.run(
            [sys.executable, "-m", "photo_backup.main", "config"], capture_output=True, text=True, env=env
        )

        assert result.returncode == 0, f"Config command with env overrides should succeed, got: {result.stderr}"

        # Check for environment override display
        assert "Environment Overrides: 2 variables" in result.stdout
        assert "PHOTO_BACKUP_BACKUP_SOURCE_PATH" in result.stdout
        assert "PHOTO_BACKUP_LOGGING_LEVEL" in result.stdout
        assert "/custom/test/path" in result.stdout

    def test_config_command_shows_no_environment_overrides(self):
        """Test that config command shows 'None' when no environment overrides."""
        # Clean environment of any PHOTO_BACKUP_* variables
        env = {k: v for k, v in os.environ.items() if not k.startswith("PHOTO_BACKUP_")}

        result = subprocess.run(
            [sys.executable, "-m", "photo_backup.main", "config"], capture_output=True, text=True, env=env
        )

        assert result.returncode == 0, f"Config command should succeed, got: {result.stderr}"

        # Check for no environment overrides
        assert "Environment Overrides: None" in result.stdout

    def test_config_command_masks_sensitive_data(self):
        """Test that config command masks sensitive information."""
        result = subprocess.run(
            [sys.executable, "-m", "photo_backup.main", "--test-mode", "config"], capture_output=True, text=True
        )

        assert result.returncode == 0, f"Config command should succeed, got: {result.stderr}"

        # Check that sensitive data is masked
        assert "Access Key: mini*" in result.stdout or "Access Key: [HIDDEN]" in result.stdout
        assert "Secret Key: mini*" in result.stdout or "Secret Key: [HIDDEN]" in result.stdout

        # Make sure actual sensitive values are not in output
        assert "minioadmin" not in result.stdout

    def test_config_command_shows_config_file_location(self):
        """Test that config command shows config file location or defaults."""
        result = subprocess.run([sys.executable, "-m", "photo_backup.main", "config"], capture_output=True, text=True)

        assert result.returncode == 0, f"Config command should succeed, got: {result.stderr}"

        # Should show either a file path or "Using defaults"
        assert "Config File: Using defaults" in result.stdout or "Config File: /" in result.stdout

    def test_config_command_includes_all_sections(self):
        """Test that config command includes all expected configuration sections."""
        result = subprocess.run([sys.executable, "-m", "photo_backup.main", "config"], capture_output=True, text=True)

        assert result.returncode == 0, f"Config command should succeed, got: {result.stderr}"

        # Check for all expected sections
        expected_sections = [
            "Backup Settings:",
            "Storage Settings:",
            "Monitoring Settings:",
            "Logging Settings:",
            "State Settings:",
            "Security Settings:",
            "Performance Settings:",
            "Notifications Settings:",
        ]

        for section in expected_sections:
            assert section in result.stdout, f"Missing section: {section}"

    def test_config_command_help_available(self):
        """Test that config command help is available."""
        result = subprocess.run(
            [sys.executable, "-m", "photo_backup.main", "config", "--help"], capture_output=True, text=True
        )

        assert result.returncode == 0, f"Config help should succeed, got: {result.stderr}"
        assert "Display current configuration settings" in result.stdout

    def test_config_command_in_main_help(self):
        """Test that config command is listed in main help."""
        result = subprocess.run([sys.executable, "-m", "photo_backup.main", "--help"], capture_output=True, text=True)

        assert result.returncode == 0, f"Main help should succeed, got: {result.stderr}"
        assert "config" in result.stdout
        assert "Display current configuration settings" in result.stdout

    def test_config_command_with_multiple_env_overrides(self):
        """Test config command with multiple environment variable overrides."""
        env = os.environ.copy()
        env.update(
            {
                "PHOTO_BACKUP_TEST_MODE": "1",
                "PHOTO_BACKUP_BACKUP_SOURCE_PATH": "/env/test/path",
                "PHOTO_BACKUP_BACKUP_COMPRESSION": "true",
                "PHOTO_BACKUP_MONITORING_CHECK_INTERVAL_HOURS": "2.5",
                "PHOTO_BACKUP_LOGGING_LEVEL": "INFO",
            }
        )

        result = subprocess.run(
            [sys.executable, "-m", "photo_backup.main", "config"], capture_output=True, text=True, env=env
        )

        assert result.returncode == 0, f"Config command should succeed, got: {result.stderr}"

        # Check that it shows test mode (due to environment variable)
        assert "Mode: TEST MODE" in result.stdout

        # Check that environment overrides are shown (excluding TEST_MODE)
        assert "Environment Overrides: 3 variables" in result.stdout

        # Check that overridden values are displayed
        assert "/env/test/path" in result.stdout
        assert "Compression: True" in result.stdout

    def test_config_command_production_vs_test_differences(self):
        """Test that production and test mode show different configurations."""
        # Production mode
        result_prod = subprocess.run(
            [sys.executable, "-m", "photo_backup.main", "config"], capture_output=True, text=True
        )

        # Test mode
        result_test = subprocess.run(
            [sys.executable, "-m", "photo_backup.main", "--test-mode", "config"], capture_output=True, text=True
        )

        assert result_prod.returncode == 0, "Production config should succeed"
        assert result_test.returncode == 0, "Test config should succeed"

        # Production should show Wasabi settings
        assert "Mode: PRODUCTION MODE" in result_prod.stdout
        assert "s3.wasabisys.com" in result_prod.stdout

        # Test should show Minio settings
        assert "Mode: TEST MODE" in result_test.stdout
        assert "localhost:9000" in result_test.stdout

        # They should be different
        assert result_prod.stdout != result_test.stdout
