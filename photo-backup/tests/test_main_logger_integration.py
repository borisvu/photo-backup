"""Test logger integration in main CLI."""

import subprocess
import sys
from pathlib import Path
import pytest
import re


def run_cli_command(args):
    """Run the CLI with given arguments and return result."""
    cmd = [sys.executable, "-m", "photo_backup.main"] + args
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
            cwd=Path(__file__).parent.parent
        )
        return result
    except subprocess.TimeoutExpired:
        pytest.fail(f"CLI command timed out: {' '.join(cmd)}")


def test_production_mode_logging():
    """Test that production mode uses INFO level logging."""
    result = run_cli_command([])
    
    assert result.returncode == 0
    
    # Should have INFO level logs
    assert "INFO" in result.stdout
    assert "starting in PRODUCTION MODE" in result.stdout
    assert "Initializing production mode configuration" in result.stdout
    assert "CLI initialization completed successfully" in result.stdout
    
    # Should NOT have DEBUG level logs in production mode
    assert "DEBUG" not in result.stdout


def test_test_mode_logging():
    """Test that test mode uses DEBUG level logging."""
    result = run_cli_command(["--test-mode"])
    
    assert result.returncode == 0
    
    # Should have both INFO and DEBUG level logs
    assert "INFO" in result.stdout
    assert "DEBUG" in result.stdout
    assert "starting in TEST MODE" in result.stdout
    assert "Initializing test mode configuration" in result.stdout
    assert "Test mode endpoint: localhost:9000" in result.stdout
    assert "CLI initialization completed successfully" in result.stdout


def test_logger_name_in_output():
    """Test that logger name appears in output."""
    result = run_cli_command([])
    
    assert result.returncode == 0
    assert "photo_backup" in result.stdout


def test_log_format():
    """Test that log messages follow the expected format."""
    result = run_cli_command([])
    
    assert result.returncode == 0
    
    # Look for the expected log format: timestamp - name - level - message
    log_pattern = r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} - photo_backup - INFO - .*'
    assert re.search(log_pattern, result.stdout) is not None


def test_version_flag_no_logging():
    """Test that --version flag doesn't trigger logging."""
    result = run_cli_command(["--version"])
    
    assert result.returncode == 0
    assert result.stdout.strip() == "Photo Backup v0.1.0"
    
    # Should not contain any log output
    assert "photo_backup" not in result.stdout or result.stdout.count("photo_backup") == 0
    assert "INFO" not in result.stdout
    assert "DEBUG" not in result.stdout


def test_config_values_logged():
    """Test that configuration values are logged appropriately."""
    result = run_cli_command(["--test-mode"])
    
    assert result.returncode == 0
    
    # Check that config values appear in debug logs
    assert "Test mode endpoint: localhost:9000" in result.stdout
    assert "Test mode source: /tmp/photo-backup-test-photos" in result.stdout


def test_startup_sequence():
    """Test the complete startup logging sequence."""
    result = run_cli_command(["--test-mode"])
    
    assert result.returncode == 0
    
    # Check that logs appear in the expected order
    output_lines = result.stdout.split('\n')
    
    startup_found = False
    config_found = False
    completion_found = False
    
    for line in output_lines:
        if "starting in TEST MODE" in line:
            startup_found = True
        elif "Initializing test mode configuration" in line and startup_found:
            config_found = True
        elif "CLI initialization completed successfully" in line and config_found:
            completion_found = True
    
    assert startup_found, "Startup log message not found"
    assert config_found, "Configuration log message not found"
    assert completion_found, "Completion log message not found"