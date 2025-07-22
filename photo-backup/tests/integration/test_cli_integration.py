"""
Integration tests for CLI functionality.

These tests verify that CLI components work together correctly.
"""

import re

import pytest


class TestCLIIntegration:
    """Integration tests for CLI commands and options."""

    @pytest.mark.integration
    def test_cli_version_command(self, cli_runner):
        """Test CLI version command."""
        result = cli_runner(["--version"])

        assert result.returncode == 0
        assert result.stdout.strip() == "Photo Backup v0.1.0"

    @pytest.mark.integration
    def test_cli_help_command(self, cli_runner):
        """Test CLI help command."""
        result = cli_runner(["--help"])

        assert result.returncode == 0
        assert "--test-mode" in result.stdout
        assert "--version" in result.stdout
        assert "Photo Backup System" in result.stdout

    @pytest.mark.integration
    def test_cli_production_mode_default(self, cli_runner):
        """Test CLI runs in production mode by default."""
        result = cli_runner([])

        assert result.returncode == 0
        assert "Photo Backup v0.1.0" in result.stdout
        assert "PRODUCTION MODE" in result.stdout
        assert "s3.wasabisys.com" in result.stdout
        assert "INFO" in result.stdout

    @pytest.mark.integration
    def test_cli_test_mode_flag(self, cli_runner):
        """Test CLI test mode flag."""
        result = cli_runner(["--test-mode"])

        assert result.returncode == 0
        assert "Photo Backup v0.1.0" in result.stdout
        assert "TEST MODE" in result.stdout
        assert "localhost:9000" in result.stdout
        assert "minioadmin" in result.stdout
        assert "DEBUG" in result.stdout

    @pytest.mark.integration
    def test_version_flag_priority(self, cli_runner):
        """Test that --version takes priority over other flags."""
        result = cli_runner(["--test-mode", "--version"])

        assert result.returncode == 0
        assert result.stdout.strip() == "Photo Backup v0.1.0"
        # Should not show test mode output when --version is used
        assert "TEST MODE" not in result.stdout

    @pytest.mark.integration
    def test_logging_timestamps_present(self, cli_runner):
        """Test that log output includes proper timestamps."""
        result = cli_runner(["--test-mode"])

        assert result.returncode == 0

        # Check for timestamp pattern (YYYY-MM-DD HH:MM:SS)
        timestamp_pattern = r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}"
        assert re.search(timestamp_pattern, result.stdout) is not None

    @pytest.mark.integration
    def test_initialization_completion_logged(self, cli_runner):
        """Test that initialization completion is logged."""
        result = cli_runner([])

        assert result.returncode == 0
        assert "CLI initialization completed successfully" in result.stdout

    @pytest.mark.integration
    def test_config_integration_production(self, cli_runner):
        """Test config integration in production mode."""
        result = cli_runner([])

        assert result.returncode == 0
        assert "PRODUCTION MODE" in result.stdout
        assert "Source: /Volumes/4TB-SSD/Photo" in result.stdout
        assert "Destination: wasabi-photo:my-photo-backup-bucket" in result.stdout
        assert "Endpoint: s3.wasabisys.com" in result.stdout

    @pytest.mark.integration
    def test_config_integration_test_mode(self, cli_runner):
        """Test config integration in test mode."""
        result = cli_runner(["--test-mode"])

        assert result.returncode == 0
        assert "TEST MODE" in result.stdout
        assert "Source: /tmp/photo-backup-test-photos" in result.stdout
        assert "Destination: minio-test:my-photo-backup-bucket-test" in result.stdout
        assert "Endpoint: localhost:9000" in result.stdout
        assert "Credentials: minioadmin/minioadmin" in result.stdout

    @pytest.mark.integration
    def test_logger_integration_production(self, cli_runner):
        """Test logger integration in production mode."""
        result = cli_runner([])

        assert result.returncode == 0
        assert "starting in PRODUCTION MODE" in result.stdout
        assert "INFO" in result.stdout
        # Should not have DEBUG messages in production
        assert result.stdout.count("DEBUG") == 0

    @pytest.mark.integration
    def test_logger_integration_test_mode(self, cli_runner):
        """Test logger integration in test mode."""
        result = cli_runner(["--test-mode"])

        assert result.returncode == 0
        assert "starting in TEST MODE" in result.stdout
        assert "DEBUG" in result.stdout
        # Should have debug messages in test mode
        assert "Initializing test mode configuration" in result.stdout

    @pytest.mark.integration
    def test_cli_ready_message(self, cli_runner):
        """Test that CLI shows ready message."""
        result = cli_runner([])

        assert result.returncode == 0
        assert "CLI interface ready" in result.stdout
        assert "photo-backup --help" in result.stdout
