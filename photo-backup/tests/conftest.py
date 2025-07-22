"""
Shared pytest fixtures and configuration for photo backup tests.
"""

import shutil
import subprocess
import tempfile
import time

import pytest
from pathlib import Path

# Test constants
MINIO_CONTAINER_NAME = "photo-backup-minio-test"
TEST_PHOTO_DIR = Path("/tmp/photo-backup-test-photos")


def run_docker_command(cmd, capture_output=True, timeout=30):
    """Run a docker command and return the result."""
    try:
        result = subprocess.run(["docker", *cmd], capture_output=capture_output, text=True, timeout=timeout)
        return result
    except subprocess.TimeoutExpired:
        pytest.fail(f"Docker command timed out after {timeout}s: docker {' '.join(cmd)}")
    except FileNotFoundError:
        pytest.fail("Docker command not found. Please ensure Docker is installed.")


def is_container_running(container_name):
    """Check if a container is running."""
    result = run_docker_command(["ps", "--filter", f"name={container_name}", "--format", "{{.Names}}"])
    return container_name in result.stdout


def container_exists(container_name):
    """Check if a container exists (running or stopped)."""
    result = run_docker_command(["ps", "-a", "--filter", f"name={container_name}", "--format", "{{.Names}}"])
    return container_name in result.stdout


def start_minio_container():
    """Starts a Minio Docker container for testing."""
    # Test Docker is accessible
    result = run_docker_command(["ps"])
    if result.returncode != 0:
        pytest.fail(f"Docker not accessible: {result.stderr}")

    # Check if container already running
    if is_container_running(MINIO_CONTAINER_NAME):
        return True

    # Stop and remove existing container if it exists
    if container_exists(MINIO_CONTAINER_NAME):
        run_docker_command(["stop", MINIO_CONTAINER_NAME])
        run_docker_command(["rm", MINIO_CONTAINER_NAME])

    # Start new container
    cmd = [
        "run",
        "-d",
        "--name",
        MINIO_CONTAINER_NAME,
        "-p",
        "9000:9000",
        "-p",
        "9090:9090",
        "minio/minio:latest",
        "server",
        "/data",
        "--console-address",
        ":9090",
    ]

    result = run_docker_command(cmd)
    if result.returncode != 0:
        if "Unable to find image" in result.stderr:
            # Try to pull the image
            pull_result = run_docker_command(["pull", "minio/minio:latest"], timeout=300)  # 5 minutes for pull
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
    run_docker_command(["stop", MINIO_CONTAINER_NAME])

    # Remove container
    run_docker_command(["rm", MINIO_CONTAINER_NAME])


def create_test_photos(base_dir=TEST_PHOTO_DIR):
    """Creates a dummy photo directory structure and files."""
    # Import the enhanced test photo generator
    from .fixtures.photo_fixtures import generate_test_photos

    return generate_test_photos(str(base_dir), num_files=5, min_size_mb=1, max_size_mb=2)


def cleanup_test_data(base_dir=TEST_PHOTO_DIR):
    """Removes the test photo directory."""
    if base_dir.exists():
        shutil.rmtree(base_dir)


# Pytest fixtures
@pytest.fixture(scope="session")
def minio_container():
    """Fixture to start/stop Minio container for integration tests."""
    start_minio_container()
    yield
    stop_minio_container()


@pytest.fixture
def test_photos():
    """Fixture to create/cleanup test photos."""
    photo_dir = create_test_photos()
    yield photo_dir
    cleanup_test_data()


@pytest.fixture
def temp_dir():
    """Fixture to provide a temporary directory."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        yield Path(tmp_dir)


@pytest.fixture
def sample_config():
    """Fixture to provide sample configuration data."""
    return {
        "backup": {"source_path": "/test/photos", "destination": "test-bucket"},
        "storage": {"endpoint": "localhost:9000", "access_key": "minioadmin", "secret_key": "minioadmin"},
    }


@pytest.fixture
def cli_runner():
    """Fixture to provide CLI command runner."""
    import subprocess
    import sys

    from pathlib import Path

    def run_command(args, timeout=10):
        cmd = [sys.executable, "-m", "photo_backup.main", *args]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=Path(__file__).parent.parent,  # Go up from tests/ to photo-backup/
            )
            return result
        except subprocess.TimeoutExpired:
            pytest.fail(f"CLI command timed out: {' '.join(cmd)}")

    return run_command
