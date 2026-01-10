"""
Functional tests for dependency check command.

These tests verify that the check-deps command correctly reports
dependency status in both test and production modes.
"""

import json
import subprocess

import pytest
from pathlib import Path


class TestDepsCommand:
    """Functional tests for check-deps command."""

    @pytest.mark.functional
    def test_check_deps_command_test_mode(self):
        """Test that check-deps command works in test mode."""
        result = subprocess.run(
            ["python3", "-m", "photo_backup.main", "--test-mode", "check-deps"],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent.parent),
        )

        assert result.returncode == 0, f"Command failed: {result.stderr}"
        assert "TEST MODE" in result.stdout
        assert "Python:" in result.stdout
        assert "rclone:" in result.stdout
        assert "Docker:" in result.stdout
        assert "1Password CLI:" in result.stdout
        assert (
            "All required dependencies are available" in result.stdout
            or "Some required dependencies are missing" in result.stdout
        )

    @pytest.mark.functional
    def test_check_deps_command_production_mode(self):
        """Test that check-deps command works in production mode."""
        result = subprocess.run(
            ["python3", "-m", "photo_backup.main", "check-deps"],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent.parent),
        )

        assert result.returncode == 0, f"Command failed: {result.stderr}"
        assert "PRODUCTION MODE" in result.stdout
        assert "Python:" in result.stdout
        assert "rclone:" in result.stdout
        assert "Docker:" in result.stdout
        assert "1Password CLI:" in result.stdout
        assert (
            "All required dependencies are available" in result.stdout
            or "Some required dependencies are missing" in result.stdout
        )

    @pytest.mark.functional
    def test_check_deps_command_json_output(self):
        """Test that check-deps command supports JSON output."""
        result = subprocess.run(
            ["python3", "-m", "photo_backup.main", "--test-mode", "check-deps", "--json"],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent.parent),
        )

        assert result.returncode == 0, f"Command failed: {result.stderr}"

        # Parse JSON output
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError as e:
            pytest.fail(f"Invalid JSON output: {e}")

        # Verify JSON structure
        assert "test_mode" in data
        assert "all_required_passed" in data
        assert "dependencies" in data
        assert isinstance(data["dependencies"], dict)
        assert "python" in data["dependencies"]
        assert "rclone" in data["dependencies"]
        assert "docker" in data["dependencies"]
        assert "1password" in data["dependencies"]

        # Verify dependency structure
        for _dep_name, dep_info in data["dependencies"].items():
            assert "available" in dep_info
            assert "message" in dep_info
            assert isinstance(dep_info["available"], bool)
            assert isinstance(dep_info["message"], str)

    @pytest.mark.functional
    def test_check_deps_reports_dependencies_correctly(self):
        """Test that check-deps reports dependencies correctly (task requirement)."""
        result = subprocess.run(
            ["python3", "-m", "photo_backup.main", "--test-mode", "check-deps"],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent.parent),
        )

        assert result.returncode == 0, f"Command failed: {result.stderr}"

        # Verify all dependencies are checked
        output = result.stdout
        assert "Python:" in output, "Should check Python version"
        assert "rclone:" in output, "Should check rclone"
        assert "Docker:" in output, "Should check Docker"
        assert "1Password CLI:" in output, "Should check 1Password CLI"

        # Verify status indicators are present
        assert "✓" in output or "✗" in output or "⚠" in output, "Should show status indicators"

        # Verify summary is present
        assert "All required dependencies are available" in output or "Some required dependencies are missing" in output

    @pytest.mark.functional
    def test_check_deps_json_in_production_mode(self):
        """Test JSON output in production mode."""
        result = subprocess.run(
            ["python3", "-m", "photo_backup.main", "check-deps", "--json"],
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).parent.parent.parent),
        )

        assert result.returncode == 0, f"Command failed: {result.stderr}"

        # Parse JSON output
        data = json.loads(result.stdout)

        # Verify test_mode is False
        assert data["test_mode"] is False

        # Verify all dependencies are present
        assert "python" in data["dependencies"]
        assert "rclone" in data["dependencies"]
        assert "docker" in data["dependencies"]
        assert "1password" in data["dependencies"]
