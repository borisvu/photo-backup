"""
Functional test for CLI entry point (Task 5)
"""

import subprocess
import sys
from pathlib import Path
import pytest

def run_cli_command(args):
    """Run the CLI with given arguments and return result."""
    cmd = [sys.executable, "-m", "photo_backup.main"] + args
    try:
        # Run from the parent directory (photo-backup/) so imports work
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
            cwd=Path(__file__).parent.parent  # Go up from tests/ to photo-backup/
        )
        return result
    except subprocess.TimeoutExpired:
        pytest.fail(f"CLI command timed out: {' '.join(cmd)}")

def test_basic_cli():
    """Test basic CLI execution."""
    result = run_cli_command([])
    
    assert result.returncode == 0, f"CLI failed with return code {result.returncode}: {result.stderr}"
    assert "Photo Backup v0.1.0" in result.stdout, "Version not displayed in basic run"
    assert "PRODUCTION MODE" in result.stdout, "Production mode not indicated"

def test_version_flag():
    """Test --version flag."""
    result = run_cli_command(["--version"])
    
    assert result.returncode == 0, f"Version command failed: {result.stderr}"
    assert result.stdout.strip() == "Photo Backup v0.1.0", f"Unexpected version output: {result.stdout}"

def test_test_mode_flag():
    """Test --test-mode flag."""
    result = run_cli_command(["--test-mode"])
    
    assert result.returncode == 0, f"Test mode failed: {result.stderr}"
    assert "Photo Backup v0.1.0" in result.stdout, "Version not displayed in test mode"
    assert "TEST MODE" in result.stdout, "Test mode not indicated"
    assert "localhost:9000" in result.stdout, "Minio endpoint not shown"
    assert "minioadmin" in result.stdout, "Test credentials not shown"

def test_help_flag():
    """Test --help flag."""
    result = run_cli_command(["--help"])
    
    assert result.returncode == 0, f"Help command failed: {result.stderr}"
    assert "--test-mode" in result.stdout, "Test mode option not in help"
    assert "--version" in result.stdout, "Version option not in help"
    assert "Photo Backup System" in result.stdout, "Description not in help"

def test_version_priority():
    """Test that --version takes priority over other flags."""
    result = run_cli_command(["--test-mode", "--version"])
    
    assert result.returncode == 0, f"Combined flags failed: {result.stderr}"
    assert result.stdout.strip() == "Photo Backup v0.1.0", "Version should be only output when --version used"