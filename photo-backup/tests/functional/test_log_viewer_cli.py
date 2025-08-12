"""
Functional tests for log viewer CLI integration.

Tests the logs command integration with the main CLI.
"""

import subprocess


class TestLogViewerCLI:
    """Test log viewer CLI integration."""

    def test_logs_command_help_available(self):
        """Test that logs command help is available."""
        result = subprocess.run(
            ["python", "-m", "photo_backup.main", "logs", "--help"],
            capture_output=True,
            text=True,
            cwd=".",
        )

        assert result.returncode == 0
        assert "View and filter photo-backup log files" in result.stdout
        assert "--tail" in result.stdout
        assert "--level" in result.stdout
        assert "--errors" in result.stdout
        assert "--follow" in result.stdout
        assert "--json" in result.stdout

    def test_logs_command_in_main_help(self):
        """Test that logs command appears in main help."""
        result = subprocess.run(
            ["python", "-m", "photo_backup.main", "--help"],
            capture_output=True,
            text=True,
            cwd=".",
        )

        assert result.returncode == 0
        assert "logs" in result.stdout

    def test_logs_command_shows_logs(self):
        """Test logs command shows existing log content."""
        result = subprocess.run(
            ["python", "-m", "photo_backup.main", "logs"],
            capture_output=True,
            text=True,
            cwd=".",
        )

        assert result.returncode == 0
        assert "Photo Backup v0.1.0" in result.stdout
        assert "PRODUCTION MODE" in result.stdout

    def test_logs_command_test_mode_path(self):
        """Test logs command uses correct path in test mode."""
        result = subprocess.run(
            ["python", "-m", "photo_backup.main", "--test-mode", "logs", "--help"],
            capture_output=True,
            text=True,
            cwd=".",
        )

        assert result.returncode == 0
        # The command should work in test mode
        assert "View and filter photo-backup log files" in result.stdout

    def test_logs_command_invalid_level(self):
        """Test logs command with invalid level."""
        result = subprocess.run(
            ["python", "-m", "photo_backup.main", "logs", "--level", "INVALID"],
            capture_output=True,
            text=True,
            cwd=".",
        )

        assert result.returncode == 2  # Click error
        assert "Invalid value" in result.stderr
