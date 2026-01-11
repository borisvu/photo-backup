"""
Comprehensive functional tests for the complete config system.

These tests verify the entire config flow: load → override → validate → use with Minio.
"""

import os
import subprocess
import tempfile

import yaml
from pathlib import Path


class TestCompleteConfigFlow:
    """Test complete config system flow."""

    def test_complete_config_flow_with_test_mode(self, minio_container, test_photos):  # noqa: ARG002
        """Test complete config flow: load → override → validate → use with Minio."""
        # This test verifies the entire config system works end-to-end in test mode

        # 1. Create a test config file
        test_config = {
            "backup": {
                "source_path": "/tmp/photo-backup-test-photos",
                "destination": "minio-test:my-photo-backup-bucket-test",
                "strategy": "incremental",
                "compression": False,
                "encryption": False,
                "verify_after_backup": False,
                "max_concurrent_backups": 1,
                "dry_run": False,
            },
            "storage": {
                "endpoint": "localhost:9000",
                "access_key": "minioadmin",
                "secret_key": "minioadmin",
                "use_ssl": False,
                "region": "us-east-1",
                "bucket": "test-bucket",
                "timeout_seconds": 30,
                "retry_attempts": 1,
            },
            "monitoring": {
                "check_interval_hours": 0.1,
                "mount_delay_minutes": 1,
                "change_delay_minutes": 1,
                "max_retries": 1,
                "retry_delay_minutes": 1,
                "health_check_enabled": False,
                "health_check_interval_minutes": 60,
            },
            "logging": {
                "level": "DEBUG",
                "directory": "/tmp/photo-backup-test/logs",
                "max_size_mb": 10,
                "backup_count": 3,
                "format": "detailed",
                "console_output": True,
                "file_output": True,
                "include_timestamps": True,
            },
            "state": {
                "directory": "/tmp/photo-backup-test/state",
                "auto_cleanup": True,
                "cleanup_days": 1,
                "backup_state_file": "backup_state.json",
                "lock_file": "backup.lock",
            },
            "security": {
                "encrypt_backups": False,
                "encryption_key": None,
                "verify_checksums": False,
                "checksum_algorithm": "sha256",
                "secure_erase": False,
            },
            "performance": {
                "buffer_size_mb": 1,
                "max_memory_usage_mb": 64,
                "parallel_uploads": 1,
                "chunk_size_mb": 1,
                "enable_caching": False,
            },
            "notifications": {
                "enabled": False,
                "email": {
                    "smtp_server": None,
                    "smtp_port": 587,
                    "username": None,
                    "password": None,
                    "from_address": None,
                    "to_addresses": [],
                },
                "webhook": {"url": None, "timeout_seconds": 30},
            },
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(test_config, f)
            config_file = f.name

        try:
            # 2. Set environment variable to use our test config
            env = os.environ.copy()
            env["PHOTO_BACKUP_CONFIG_FILE"] = config_file

            # 3. Test config command - should load from file and show test mode settings
            result = subprocess.run(
                ["python", "-m", "photo_backup.main", "--test-mode", "config"],
                capture_output=True,
                text=True,
                env=env,
                cwd=".",
            )

            assert result.returncode == 0
            assert "Mode: TEST MODE" in result.stdout
            assert "localhost:9000" in result.stdout  # Minio endpoint
            assert "/tmp/photo-backup-test-photos" in result.stdout  # Test source path

            # 4. Create necessary directories for validation to pass
            Path("/tmp/photo-backup-test-photos").mkdir(parents=True, exist_ok=True)
            Path("/tmp/photo-backup-test/logs").mkdir(parents=True, exist_ok=True)
            Path("/tmp/photo-backup-test/state").mkdir(parents=True, exist_ok=True)

            # 5. Test validate command - should validate all settings and test Minio connectivity
            result = subprocess.run(
                ["python", "-m", "photo_backup.main", "--test-mode", "validate"],
                capture_output=True,
                text=True,
                env=env,
                cwd=".",
            )

            # Should pass with valid test setup
            assert result.returncode == 0
            assert "Overall Status: ✅ VALID" in result.stdout
            assert "🎉 Configuration is valid and ready for use!" in result.stdout
            assert "Minio Connection Test:" in result.stdout
            assert "✅ Minio endpoint localhost:9000 is reachable" in result.stdout

            # 5. Test that all config sections are present and validated
            validation_steps = [
                "1. Configuration Validation:",
                "2. Path Validation:",
                "3. Rclone Availability:",
                "4. Minio Connection Test:",
            ]

            for step in validation_steps:
                assert step in result.stdout

        finally:
            # Clean up
            os.unlink(config_file)

    def test_complete_config_flow_with_env_overrides(self, minio_container, test_photos):  # noqa: ARG002
        """Test complete config flow with environment variable overrides."""
        # Test that environment overrides work correctly in the complete flow

        env = os.environ.copy()
        env["PHOTO_BACKUP_TEST_MODE"] = "1"
        env["PHOTO_BACKUP_BACKUP_SOURCE_PATH"] = "/custom/test/source"
        env["PHOTO_BACKUP_STORAGE_ENDPOINT"] = "custom.minio.local:9000"
        env["PHOTO_BACKUP_LOGGING_LEVEL"] = "WARNING"

        # Test config command with overrides
        result = subprocess.run(
            ["python", "-m", "photo_backup.main", "config"],
            capture_output=True,
            text=True,
            env=env,
            cwd=".",
        )

        assert result.returncode == 0
        assert "Mode: TEST MODE" in result.stdout
        assert "Environment Overrides: 3 variables" in result.stdout
        assert "/custom/test/source" in result.stdout
        assert "custom.minio.local:9000" in result.stdout
        assert "WARNING" in result.stdout

        # Test validate command with overrides
        result = subprocess.run(
            ["python", "-m", "photo_backup.main", "validate"],
            capture_output=True,
            text=True,
            env=env,
            cwd=".",
        )

        # Should show the overridden values in validation
        assert "custom.minio.local:9000" in result.stdout

    def test_validate_all_config_settings(self):
        """Test that all configuration settings are properly validated."""
        # Test comprehensive validation of all config sections and settings

        result = subprocess.run(
            ["python", "-m", "photo_backup.main", "--test-mode", "validate"],
            capture_output=True,
            text=True,
            cwd=".",
        )

        # Should perform all validation steps
        assert "1. Configuration Validation:" in result.stdout
        assert "2. Path Validation:" in result.stdout
        assert "3. Rclone Availability:" in result.stdout
        assert "4. Minio Connection Test:" in result.stdout

        # Should validate all major config sections
        config_sections = [
            "Backup Settings:",
            "Storage Settings:",
            "Monitoring Settings:",
            "Logging Settings:",
            "State Settings:",
            "Security Settings:",
            "Performance Settings:",
            "Notifications Settings:",
        ]

        # Check that config command shows all sections
        result = subprocess.run(
            ["python", "-m", "photo_backup.main", "--test-mode", "config"],
            capture_output=True,
            text=True,
            cwd=".",
        )

        for section in config_sections:
            assert section in result.stdout

    def test_config_with_minio_endpoint_integration(self, minio_container):  # noqa: ARG002
        """Test config system with actual Minio endpoint connectivity."""
        # Test that the config system properly integrates with Minio

        # Test validate command with Minio running
        result = subprocess.run(
            ["python", "-m", "photo_backup.main", "--test-mode", "validate"],
            capture_output=True,
            text=True,
            cwd=".",
        )

        # Should test Minio connectivity in test mode
        assert "4. Minio Connection Test:" in result.stdout

        # Should show Minio endpoint details
        assert "localhost:9000" in result.stdout
        # Note: validate command doesn't show sensitive data, so we don't check for minioadmin here

        # Test config command shows Minio settings
        result = subprocess.run(
            ["python", "-m", "photo_backup.main", "--test-mode", "config"],
            capture_output=True,
            text=True,
            cwd=".",
        )

        assert "localhost:9000" in result.stdout
        assert "mini******" in result.stdout  # Masked sensitive data
        assert "minio-test:my-photo-backup-bucket-test" in result.stdout

    def test_config_flow_with_invalid_settings(self):
        """Test config flow handles invalid settings gracefully."""
        # Test that the config system properly handles and reports invalid settings

        # Test with invalid config (missing required fields)
        invalid_config = {
            "backup": {
                # Missing source_path and destination
                "strategy": "invalid_strategy",  # Invalid value
            },
            "storage": {
                # Missing endpoint
                "timeout_seconds": "invalid_timeout",  # Should be number
            },
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(invalid_config, f)
            config_file = f.name

        try:
            env = os.environ.copy()
            env["PHOTO_BACKUP_CONFIG_FILE"] = config_file

            # Test validate command with invalid config
            result = subprocess.run(
                ["python", "-m", "photo_backup.main", "--test-mode", "validate"],
                capture_output=True,
                text=True,
                env=env,
                cwd=".",
            )

            # Should fail due to invalid config
            assert result.returncode == 1
            # Check for configuration loading failure
            assert "Configuration validation failed:" in result.stderr
            assert "backup.source_path is required" in result.stderr
            assert "storage.endpoint is required" in result.stderr

        finally:
            os.unlink(config_file)

    def test_config_flow_production_mode(self):
        """Test complete config flow in production mode."""
        # Test that the config system works correctly in production mode

        result = subprocess.run(
            ["python", "-m", "photo_backup.main", "config"],
            capture_output=True,
            text=True,
            cwd=".",
        )

        assert result.returncode == 0
        assert "Mode: PRODUCTION MODE" in result.stdout
        assert "s3.wasabisys.com" in result.stdout  # Production endpoint
        assert "/Volumes/4TB-SSD/Photo" in result.stdout  # Production source path

        # Test validate command in production mode
        result = subprocess.run(
            ["python", "-m", "photo_backup.main", "validate"],
            capture_output=True,
            text=True,
            cwd=".",
        )

        # Should not test Minio in production mode
        assert "Minio Connection Test:" not in result.stdout
        assert "4. Minio Connection Test:" not in result.stdout

    def test_config_flow_with_dry_run_mode(self):
        """Test complete config flow with dry-run mode."""
        # Test that dry-run mode works correctly with the complete config flow

        result = subprocess.run(
            ["python", "-m", "photo_backup.main", "--test-mode", "--dry-run", "config"],
            capture_output=True,
            text=True,
            cwd=".",
        )

        assert result.returncode == 0
        assert "Mode: TEST MODE (DRY RUN)" in result.stdout
        assert "Dry Run: True" in result.stdout

        # Test validate command with dry-run
        result = subprocess.run(
            ["python", "-m", "photo_backup.main", "--test-mode", "--dry-run", "validate"],
            capture_output=True,
            text=True,
            cwd=".",
        )

        assert result.returncode == 1  # Should fail due to missing paths

    def test_config_flow_error_handling(self):
        """Test config flow error handling and recovery."""
        # Test that the config system handles errors gracefully

        # Test with non-existent config file
        env = os.environ.copy()
        env["PHOTO_BACKUP_CONFIG_FILE"] = "/non/existent/config.yaml"

        result = subprocess.run(
            ["python", "-m", "photo_backup.main", "--test-mode", "config"],
            capture_output=True,
            text=True,
            env=env,
            cwd=".",
        )

        # Should fall back to defaults gracefully
        assert result.returncode == 0
        assert "Mode: TEST MODE" in result.stdout
        assert "localhost:9000" in result.stdout  # Should still show test mode defaults

    def test_config_flow_performance(self):
        """Test config flow performance and responsiveness."""
        # Test that the config system is responsive and performs well

        import time

        start_time = time.time()

        result = subprocess.run(
            ["python", "-m", "photo_backup.main", "--test-mode", "config"],
            capture_output=True,
            text=True,
            cwd=".",
        )

        end_time = time.time()
        execution_time = end_time - start_time

        assert result.returncode == 0
        assert execution_time < 5.0  # Should complete within 5 seconds

        # Test validate command performance
        start_time = time.time()

        result = subprocess.run(
            ["python", "-m", "photo_backup.main", "--test-mode", "validate"],
            capture_output=True,
            text=True,
            cwd=".",
        )

        end_time = time.time()
        execution_time = end_time - start_time

        assert execution_time < 10.0  # Should complete within 10 seconds (includes Minio test)
