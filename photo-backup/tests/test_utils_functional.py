"""
Functional tests for utils module via CLI interface (Task 12).

This test verifies that the utility functions work correctly when called
through the main CLI interface, as required by Task 12.
"""

import subprocess
import sys
import os
import tempfile
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


def test_help_shows_new_commands():
    """Test that help shows the new utility commands."""
    result = run_cli_command(["--help"])
    
    assert result.returncode == 0, f"Help command failed: {result.stderr}"
    
    expected_commands = ["format-size", "create-dir", "test-utils"]
    
    for command in expected_commands:
        assert command in result.stdout, f"Help output missing command: {command}"


def test_format_size_command():
    """Test format_size command via CLI."""
    # Test various byte values
    test_cases = [
        (0, "0 B"),
        (512, "512 B"),
        (1024, "1.00 KB"),
        (1048576, "1.00 MB"),
        (1073741824, "1.00 GB"),
    ]
    
    for bytes_value, expected_contains in test_cases:
        result = run_cli_command(["format-size", str(bytes_value)])
        
        assert result.returncode == 0, f"format-size {bytes_value} failed: {result.stderr}"
        assert expected_contains in result.stdout, f"Expected '{expected_contains}' in output: {result.stdout}"
        assert f"{bytes_value} bytes =" in result.stdout, f"Expected bytes value in output: {result.stdout}"


def test_create_dir_command():
    """Test create_dir command via CLI."""
    # Create a temporary directory for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        test_dir = os.path.join(temp_dir, "test_subdir")
        
        # Test creating a new directory
        result = run_cli_command(["create-dir", test_dir])
        
        assert result.returncode == 0, f"create-dir failed: {result.stderr}"
        assert "✓ Directory ready:" in result.stdout, f"Expected success message in: {result.stdout}"
        
        # Verify directory was actually created
        assert os.path.isdir(test_dir), f"Directory was not actually created: {test_dir}"
        
        # Test with existing directory (should succeed)
        result = run_cli_command(["create-dir", test_dir])
        
        assert result.returncode == 0, f"create-dir on existing directory failed: {result.stderr}"
        assert "✓ Directory ready:" in result.stdout, f"Expected success message for existing dir: {result.stdout}"


def test_create_dir_command_failure():
    """Test create_dir command with invalid path."""
    # Try to create directory in a location that should fail (like root with no permissions)
    invalid_path = "/root/should_fail_permission_test"
    
    result = run_cli_command(["create-dir", invalid_path])
    
    # Should fail with exit code 1
    assert result.returncode == 1, f"Expected failure for invalid path, got: {result.stdout}"
    assert "✗ Failed to create directory:" in result.stdout, f"Expected failure message in: {result.stdout}"


def test_test_utils_command():
    """Test test_utils command via CLI."""
    result = run_cli_command(["test-utils"])
    
    assert result.returncode == 0, f"test-utils failed: {result.stderr}"
    
    # Check that output contains expected test results
    expected_strings = [
        "Testing utility functions:",
        "format_bytes() test:",
        "0 bytes ->",
        "1048576 bytes ->",
        "ensure_directory() test:",
        "Created directory:",
        "Cleaned up test directory"
    ]
    
    for expected in expected_strings:
        assert expected in result.stdout, f"test-utils output missing expected string '{expected}' in: {result.stdout}"


def test_format_size_with_test_mode():
    """Test format_size command in test mode (should have debug logging)."""
    result = run_cli_command(["--test-mode", "format-size", "1048576"])
    
    assert result.returncode == 0, f"format-size in test mode failed: {result.stderr}"
    assert "1048576 bytes = 1.00 MB" in result.stdout, f"Expected formatted output in: {result.stdout}"
    # In test mode, should have debug logging
    assert "DEBUG" in result.stdout, f"Expected debug logging in test mode: {result.stdout}"


def test_test_utils_with_test_mode():
    """Test test_utils command in test mode."""
    result = run_cli_command(["--test-mode", "test-utils"])
    
    assert result.returncode == 0, f"test-utils in test mode failed: {result.stderr}"
    assert "Testing utility functions:" in result.stdout, f"Expected test output in: {result.stdout}"
    # In test mode, should have debug logging
    assert "DEBUG" in result.stdout, f"Expected debug logging in test mode: {result.stdout}"


# Test the utils module directly as well
def test_format_bytes_function():
    """Test format_bytes function directly."""
    from photo_backup.utils import format_bytes
    
    assert format_bytes(0) == "0 B"
    assert format_bytes(512) == "512 B"
    assert format_bytes(1024) == "1.00 KB"
    assert format_bytes(1536) == "1.50 KB"
    assert format_bytes(1048576) == "1.00 MB"
    assert format_bytes(1073741824) == "1.00 GB"
    assert format_bytes(1099511627776) == "1.00 TB"
    
    # Test edge cases
    assert format_bytes(-1) == "0 B"
    assert format_bytes("invalid") == "0 B"


def test_ensure_directory_function():
    """Test ensure_directory function directly."""
    from photo_backup.utils import ensure_directory
    
    with tempfile.TemporaryDirectory() as temp_dir:
        test_dir = os.path.join(temp_dir, "test_subdir")
        
        # Test creating new directory
        success, error = ensure_directory(test_dir)
        assert success is True, f"Failed to create directory: {error}"
        assert error is None
        assert os.path.isdir(test_dir)
        
        # Test with existing directory
        success, error = ensure_directory(test_dir)
        assert success is True, f"Failed with existing directory: {error}"
        assert error is None
        
        # Test with empty path
        success, error = ensure_directory("")
        assert success is False
        assert "Path cannot be empty" in error
        
        # Test with file instead of directory
        test_file = os.path.join(temp_dir, "test_file.txt")
        with open(test_file, 'w') as f:
            f.write("test")
        
        success, error = ensure_directory(test_file)
        assert success is False
        assert "not a directory" in error