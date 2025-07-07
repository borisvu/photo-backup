"""Test Docker connectivity for the test infrastructure."""

import subprocess
import pytest

def test_docker_cli():
    """Test Docker CLI access."""
    try:
        result = subprocess.run(['docker', '--version'], 
                              capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, f"Docker CLI failed: {result.stderr}"
        assert "Docker version" in result.stdout, "Should show Docker version"
        
    except FileNotFoundError:
        pytest.fail("Docker command not found")
    except subprocess.TimeoutExpired:
        pytest.fail("Docker command timed out")

def test_docker_daemon():
    """Test Docker daemon connectivity."""
    try:
        result = subprocess.run(['docker', 'ps'], 
                              capture_output=True, text=True, timeout=10)
        assert result.returncode == 0, f"Docker daemon not accessible: {result.stderr}"
        
    except subprocess.TimeoutExpired:
        pytest.fail("Docker daemon connection timed out")

def test_docker_python_import():
    """Test Python Docker client import."""
    try:
        import docker
        # Just test import, don't test connection since it may fail
        # The actual tests use Docker CLI instead
        assert docker is not None, "Docker package should be importable"
        
    except ImportError:
        pytest.fail("Docker Python package not installed")