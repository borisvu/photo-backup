"""
Functional tests for environment variable override functionality.

Tests Task 27: Environment Variable Override functionality including:
- PHOTO_BACKUP_* variables override config values
- PHOTO_BACKUP_TEST_MODE=1 enables test mode
- Environment variables take priority over file config
"""

import os
import subprocess
import sys

from photo_backup.config import Config


class TestEnvironmentVariableOverride:
    """Test environment variable override functionality."""

    def test_phoyo_backup_test_mode_enables_test_mode(self):
        """Test that PHOTO_BACKUP_TEST_MODE=1 enables test mode."""
        # Set up environment
        os.environ["PHOTO_BACKUP_TEST_MODE"] = "1"

        try:
            config = Config()
            assert config.is_test_mode(), "Test mode should be enabled with PHOTO_BACKUP_TEST_MODE=1"
        finally:
            # Clean up
            if "PHOTO_BACKUP_TEST_MODE" in os.environ:
                del os.environ["PHOTO_BACKUP_TEST_MODE"]

    def test_environment_variables_override_config_values(self):
        """Test that environment variables override config values."""
        # Set up environment variables
        os.environ["PHOTO_BACKUP_TEST_MODE"] = "1"
        os.environ["PHOTO_BACKUP_BACKUP_SOURCE_PATH"] = "/custom/test/path"
        os.environ["PHOTO_BACKUP_MONITORING_CHECK_INTERVAL_HOURS"] = "2.5"
        os.environ["PHOTO_BACKUP_LOGGING_LEVEL"] = "DEBUG"

        try:
            config = Config()
            config_data = config.load_config()

            assert config_data["backup"]["source_path"] == "/custom/test/path", (
                f"Expected '/custom/test/path', got {config_data['backup']['source_path']}"
            )
            assert config_data["monitoring"]["check_interval_hours"] == 2.5, (
                f"Expected 2.5, got {config_data['monitoring']['check_interval_hours']}"
            )
            assert config_data["logging"]["level"] == "DEBUG", (
                f"Expected 'DEBUG', got {config_data['logging']['level']}"
            )
        finally:
            # Clean up
            for key in [
                "PHOTO_BACKUP_TEST_MODE",
                "PHOTO_BACKUP_BACKUP_SOURCE_PATH",
                "PHOTO_BACKUP_MONITORING_CHECK_INTERVAL_HOURS",
                "PHOTO_BACKUP_LOGGING_LEVEL",
            ]:
                if key in os.environ:
                    del os.environ[key]

    def test_environment_variable_type_conversion(self):
        """Test that environment variables are converted to appropriate types."""
        # Set up environment variables with different types
        os.environ["PHOTO_BACKUP_TEST_MODE"] = "1"
        os.environ["PHOTO_BACKUP_BACKUP_COMPRESSION"] = "true"
        os.environ["PHOTO_BACKUP_MONITORING_MOUNT_DELAY_MINUTES"] = "30"
        os.environ["PHOTO_BACKUP_LOGGING_MAX_SIZE_MB"] = "100"

        try:
            config = Config()
            config_data = config.load_config()

            # Test boolean conversion
            assert isinstance(config_data["backup"]["compression"], bool), "Compression should be boolean"
            assert config_data["backup"]["compression"] is True, (
                f"Compression should be True, got {config_data['backup']['compression']}"
            )

            # Test integer conversion
            assert isinstance(config_data["monitoring"]["mount_delay_minutes"], int), (
                "mount_delay_minutes should be int"
            )
            assert config_data["monitoring"]["mount_delay_minutes"] == 30, "mount_delay_minutes should be 30"

            # Test integer conversion for logging
            assert isinstance(config_data["logging"]["max_size_mb"], int), "max_size_mb should be int"
            assert config_data["logging"]["max_size_mb"] == 100, "max_size_mb should be 100"
        finally:
            # Clean up
            for key in [
                "PHOTO_BACKUP_TEST_MODE",
                "PHOTO_BACKUP_BACKUP_COMPRESSION",
                "PHOTO_BACKUP_MONITORING_MOUNT_DELAY_MINUTES",
                "PHOTO_BACKUP_LOGGING_MAX_SIZE_MB",
            ]:
                if key in os.environ:
                    del os.environ[key]

    def test_cli_integration_with_environment_variables(self):
        """Test that CLI works correctly with environment variables."""
        # Set up environment
        os.environ["PHOTO_BACKUP_TEST_MODE"] = "1"
        os.environ["PHOTO_BACKUP_BACKUP_SOURCE_PATH"] = "/test/path"

        try:
            result = subprocess.run(
                [sys.executable, "-m", "photo_backup.main", "--version"], capture_output=True, text=True, env=os.environ
            )

            assert result.returncode == 0, f"CLI should succeed, got: {result.stderr}"
            assert "Photo Backup v0.1.0" in result.stdout, f"Expected version output, got: {result.stdout}"
        finally:
            # Clean up
            for key in ["PHOTO_BACKUP_TEST_MODE", "PHOTO_BACKUP_BACKUP_SOURCE_PATH"]:
                if key in os.environ:
                    del os.environ[key]

    def test_environment_override_info_availability(self):
        """Test that environment override information is available."""
        # Set up environment
        os.environ["PHOTO_BACKUP_TEST_MODE"] = "1"
        os.environ["PHOTO_BACKUP_BACKUP_SOURCE_PATH"] = "/test/path"

        try:
            config = Config()
            env_info = config.get_env_override_info()

            assert env_info["test_mode_enabled"] is True, "Test mode should be enabled"
            assert env_info["override_count"] > 0, "Should have environment overrides"
            assert "PHOTO_BACKUP_BACKUP_SOURCE_PATH" in env_info["env_vars_used"], (
                "Should detect used environment variables"
            )
        finally:
            # Clean up
            for key in ["PHOTO_BACKUP_TEST_MODE", "PHOTO_BACKUP_BACKUP_SOURCE_PATH"]:
                if key in os.environ:
                    del os.environ[key]

    def test_environment_variables_priority_over_file_config(self):
        """Test that environment variables take priority over file configuration."""
        # Set up environment variables that should override file config
        os.environ["PHOTO_BACKUP_TEST_MODE"] = "1"
        os.environ["PHOTO_BACKUP_BACKUP_SOURCE_PATH"] = "/env/override/path"
        os.environ["PHOTO_BACKUP_BACKUP_COMPRESSION"] = "true"
        os.environ["PHOTO_BACKUP_MONITORING_CHECK_INTERVAL_HOURS"] = "3.0"
        os.environ["PHOTO_BACKUP_LOGGING_LEVEL"] = "DEBUG"

        try:
            config = Config()
            config_data = config.load_config()

            # Environment variables should take priority
            assert config_data["backup"]["source_path"] == "/env/override/path", (
                "Environment variable should override file config"
            )
            assert config_data["backup"]["compression"] is True, "Environment variable should override file config"
            assert config_data["monitoring"]["check_interval_hours"] == 3.0, (
                "Environment variable should override file config"
            )
            assert config_data["logging"]["level"] == "DEBUG", "Environment variable should override file config"
        finally:
            # Clean up
            for key in [
                "PHOTO_BACKUP_TEST_MODE",
                "PHOTO_BACKUP_BACKUP_SOURCE_PATH",
                "PHOTO_BACKUP_BACKUP_COMPRESSION",
                "PHOTO_BACKUP_MONITORING_CHECK_INTERVAL_HOURS",
                "PHOTO_BACKUP_LOGGING_LEVEL",
            ]:
                if key in os.environ:
                    del os.environ[key]
