"""
Functional tests for dry-run mode functionality.

These tests verify that dry-run mode works correctly with test mode
and shows operations without executing them.
"""

import subprocess
import sys


class TestDryRunMode:
    """Test dry-run mode functionality."""

    def test_dry_run_flag_available(self):
        """Test that --dry-run flag is available in help."""
        result = subprocess.run(
            [sys.executable, "-m", "photo_backup.main", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        assert result.returncode == 0
        assert "--dry-run" in result.stdout
        assert "Run in dry-run mode - show operations without executing them" in result.stdout

    def test_dry_run_with_test_mode_main(self):
        """Test dry-run + test mode shows operations without executing."""
        result = subprocess.run(
            [sys.executable, "-m", "photo_backup.main", "--test-mode", "--dry-run"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        assert result.returncode == 0
        assert "TEST MODE (DRY RUN)" in result.stdout
        assert "DRY RUN MODE: Operations will be shown but not executed" in result.stdout
        assert "localhost:9000" in result.stdout  # Test mode endpoint
        assert "/tmp/photo-backup-test-photos" in result.stdout  # Test mode source

    def test_dry_run_with_test_mode_config(self):
        """Test dry-run + test mode in config command."""
        result = subprocess.run(
            [sys.executable, "-m", "photo_backup.main", "--test-mode", "--dry-run", "config"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        assert result.returncode == 0
        assert "Mode: TEST MODE (DRY RUN)" in result.stdout
        assert "Dry Run: True" in result.stdout
        assert "localhost:9000" in result.stdout  # Test mode endpoint

    def test_dry_run_with_test_mode_validate(self):
        """Test dry-run + test mode in validate command."""
        result = subprocess.run(
            [sys.executable, "-m", "photo_backup.main", "--test-mode", "--dry-run", "validate"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        assert result.returncode == 1  # Validation fails because paths don't exist
        assert "Mode: TEST MODE (DRY RUN)" in result.stdout
        assert "localhost:9000" in result.stdout  # Test mode endpoint

    def test_dry_run_with_test_mode_setup_config(self):
        """Test dry-run + test mode in setup-config command."""
        result = subprocess.run(
            [sys.executable, "-m", "photo_backup.main", "--test-mode", "--dry-run", "setup-config"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        assert result.returncode == 0
        assert "Mode: TEST MODE (DRY RUN)" in result.stdout
        assert "Configuration created for testing" in result.stdout

    def test_dry_run_without_test_mode(self):
        """Test dry-run mode without test mode."""
        result = subprocess.run(
            [sys.executable, "-m", "photo_backup.main", "--dry-run"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        assert result.returncode == 0
        assert "PRODUCTION MODE (DRY RUN)" in result.stdout
        assert "DRY RUN MODE: Operations will be shown but not executed" in result.stdout
        assert "s3.wasabisys.com" in result.stdout  # Production endpoint

    def test_dry_run_config_value_set(self):
        """Test that dry-run flag sets the config value correctly."""
        result = subprocess.run(
            [sys.executable, "-m", "photo_backup.main", "--test-mode", "--dry-run", "config"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        assert result.returncode == 0
        # Check that the dry_run config value is set to True
        lines = result.stdout.split("\n")
        dry_run_line = None
        for line in lines:
            if "Dry Run:" in line:
                dry_run_line = line
                break

        assert dry_run_line is not None
        assert "True" in dry_run_line
