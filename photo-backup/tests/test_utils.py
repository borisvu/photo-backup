"""Test utilities and infrastructure tests."""

import subprocess
import os
import shutil
import time
import json
from pathlib import Path
import pytest

MINIO_CONTAINER_NAME = "photo-backup-minio-test"
TEST_PHOTO_DIR = Path("/tmp/photo-backup-test-photos")

def run_docker_command(cmd, capture_output=True, timeout=30):
    """Run a docker command and return the result."""
    try:
        result = subprocess.run(
            ['docker'] + cmd,
            capture_output=capture_output,
            text=True,
            timeout=timeout
        )
        return result
    except subprocess.TimeoutExpired:
        pytest.fail(f"Docker command timed out after {timeout}s: docker {' '.join(cmd)}")
    except FileNotFoundError:
        pytest.fail("Docker command not found. Please ensure Docker is installed.")

def is_container_running(container_name):
    """Check if a container is running."""
    result = run_docker_command(['ps', '--filter', f'name={container_name}', '--format', '{{.Names}}'])
    return container_name in result.stdout

def container_exists(container_name):
    """Check if a container exists (running or stopped)."""
    result = run_docker_command(['ps', '-a', '--filter', f'name={container_name}', '--format', '{{.Names}}'])
    return container_name in result.stdout

def start_minio_container():
    """Starts a Minio Docker container for testing."""
    # Test Docker is accessible
    result = run_docker_command(['ps'])
    if result.returncode != 0:
        pytest.fail(f"Docker not accessible: {result.stderr}")
    
    # Check if container already running
    if is_container_running(MINIO_CONTAINER_NAME):
        return True
    
    # Stop and remove existing container if it exists
    if container_exists(MINIO_CONTAINER_NAME):
        run_docker_command(['stop', MINIO_CONTAINER_NAME])
        run_docker_command(['rm', MINIO_CONTAINER_NAME])
    
    # Start new container
    cmd = [
        'run', '-d',
        '--name', MINIO_CONTAINER_NAME,
        '-p', '9000:9000',
        '-p', '9090:9090',
        'minio/minio:latest',
        'server', '/data', '--console-address', ':9090'
    ]
    
    result = run_docker_command(cmd)
    if result.returncode != 0:
        if "Unable to find image" in result.stderr:
            # Try to pull the image
            pull_result = run_docker_command(['pull', 'minio/minio:latest'], timeout=300)  # 5 minutes for pull
            if pull_result.returncode != 0:
                pytest.fail(f"Failed to pull Minio image: {pull_result.stderr}")
            
            # Try starting again after pull
            result = run_docker_command(cmd)
            if result.returncode != 0:
                pytest.fail(f"Failed to start Minio container: {result.stderr}")
        else:
            pytest.fail(f"Failed to start Minio container: {result.stderr}")
    
    # Wait for Minio to be ready
    time.sleep(5)
    
    # Verify container is running
    if not is_container_running(MINIO_CONTAINER_NAME):
        pytest.fail("Minio container failed to start properly.")
    
    return True

def stop_minio_container():
    """Stops and removes the Minio Docker container."""
    if not container_exists(MINIO_CONTAINER_NAME):
        return
    
    # Stop container
    run_docker_command(['stop', MINIO_CONTAINER_NAME])
    
    # Remove container
    run_docker_command(['rm', MINIO_CONTAINER_NAME])

def create_test_photos(base_dir=TEST_PHOTO_DIR):
    """Creates a dummy photo directory structure and files."""
    if base_dir.exists():
        shutil.rmtree(base_dir)
    
    (base_dir / "2024" / "01").mkdir(parents=True, exist_ok=True)
    (base_dir / "2024" / "02").mkdir(exist_ok=True)
    
    (base_dir / "2024" / "01" / "photo1.jpg").write_text("dummy photo 1")
    (base_dir / "2024" / "01" / "photo2.jpg").write_text("dummy photo 2")
    (base_dir / "2024" / "02" / "photo3.jpg").write_text("dummy photo 3")
    
    return base_dir

def cleanup_test_data(base_dir=TEST_PHOTO_DIR):
    """Removes the test photo directory."""
    if base_dir.exists():
        shutil.rmtree(base_dir)

# Pytest fixtures
@pytest.fixture(scope="session")
def minio_container():
    """Fixture to start/stop Minio container for tests."""
    start_minio_container()
    yield
    stop_minio_container()

@pytest.fixture
def test_photos():
    """Fixture to create/cleanup test photos."""
    photo_dir = create_test_photos()
    yield photo_dir
    cleanup_test_data()

# Test functions
def test_docker_connectivity():
    """Test that Docker is accessible."""
    result = run_docker_command(['--version'])
    assert result.returncode == 0, "Docker should be accessible"
    assert "Docker version" in result.stdout, "Should show Docker version"

def test_minio_container_lifecycle():
    """Test Minio container start/stop cycle."""
    # Clean up any existing container
    if container_exists(MINIO_CONTAINER_NAME):
        stop_minio_container()
    
    # Start container
    assert start_minio_container(), "Should start Minio container"
    assert is_container_running(MINIO_CONTAINER_NAME), "Container should be running"
    
    # Stop container
    stop_minio_container()
    assert not is_container_running(MINIO_CONTAINER_NAME), "Container should be stopped"

def test_test_photo_creation(test_photos):
    """Test test photo directory creation."""
    assert test_photos.exists(), "Test photo directory should exist"
    assert (test_photos / "2024" / "01" / "photo1.jpg").exists(), "Test photo should exist"
    assert (test_photos / "2024" / "02" / "photo3.jpg").exists(), "Test photo should exist"
    
    # Count files
    photo_files = list(test_photos.rglob("*.jpg"))
    assert len(photo_files) == 3, "Should have 3 test photos"