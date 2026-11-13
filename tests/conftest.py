"""
Shared pytest fixtures and configuration for photo backup tests.
"""

import contextlib
import shutil
import subprocess
import sys
import tempfile
import time

import pytest
from pathlib import Path

from tests.fixtures.minio import MINIO_IMAGE

# Test constants
MINIO_CONTAINER_NAME = "photo-backup-minio-test"
TEST_PHOTO_DIR = Path("/tmp/photo-backup-test-photos")

# Known test container patterns
TEST_CONTAINER_PATTERNS = [
    "photo-backup-minio-test",
    "photo-backup-functional-test",
    "photo-backup-credential-test",
    "photo-backup-backup-sync-test",
]


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
        MINIO_IMAGE,
        "server",
        "/data",
        "--console-address",
        ":9090",
    ]

    result = run_docker_command(cmd)
    if result.returncode != 0:
        if "Unable to find image" in result.stderr:
            # Try to pull the image
            pull_result = run_docker_command(["pull", MINIO_IMAGE], timeout=300)  # 5 minutes for pull
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
    """Stops and removes the Minio Docker container.

    Handles errors gracefully to ensure cleanup always attempts removal.
    """
    if not container_exists(MINIO_CONTAINER_NAME):
        return

    try:
        # Stop container (might already be stopped)
        result = run_docker_command(["stop", MINIO_CONTAINER_NAME])
        if result.returncode != 0 and "is already stopped" not in result.stderr:
            print(f"⚠️  Warning: Failed to stop container: {result.stderr}")
    except Exception as e:
        print(f"⚠️  Warning: Exception stopping container: {e}")

    try:
        # Remove container (always attempt even if stop failed)
        result = run_docker_command(["rm", "-f", MINIO_CONTAINER_NAME])
        if result.returncode != 0:
            print(f"⚠️  Warning: Failed to remove container: {result.stderr}")
    except Exception as e:
        print(f"⚠️  Warning: Exception removing container: {e}")


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
    """Fixture to start/stop Minio container for integration tests.

    Session-scoped to share one container across all tests that need it.
    Ensures cleanup even if tests fail.
    """
    start_minio_container()
    try:
        yield
    finally:
        # Always cleanup, even if tests fail
        try:
            stop_minio_container()
        except Exception as e:
            print(f"\n⚠️  Warning: Failed to stop minio container: {e}")
            # Try force removal as last resort
            with contextlib.suppress(Exception):
                run_docker_command(["rm", "-f", MINIO_CONTAINER_NAME])


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

    from pathlib import Path

    def run_command(args, timeout=10):
        cmd = [sys.executable, "-m", "photo_backup.main", *args]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=Path(__file__).parent.parent,  # Go up from tests/ to the repo root
            )
            return result
        except subprocess.TimeoutExpired:
            pytest.fail(f"CLI command timed out: {' '.join(cmd)}")

    return run_command


def cleanup_orphaned_containers() -> list[str]:
    """Clean up any orphaned test containers.

    This function is called after test session to ensure no containers are left running.

    Returns:
        List of container names that were cleaned up (orphaned).
    """
    cleaned_containers = []

    try:
        result = subprocess.run(
            ["docker", "ps", "-a", "--format", "{{.Names}}"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode == 0:
            running_containers = result.stdout.strip().split("\n")

            for pattern in TEST_CONTAINER_PATTERNS:
                for container in running_containers:
                    if pattern in container:
                        print(f"\n⚠️  Cleaning up orphaned container: {container}")
                        # Stop the container
                        subprocess.run(
                            ["docker", "stop", container],
                            capture_output=True,
                            timeout=10,
                        )
                        # Remove the container
                        subprocess.run(
                            ["docker", "rm", container],
                            capture_output=True,
                            timeout=10,
                        )
                        print(f"✓ Cleaned up: {container}")
                        cleaned_containers.append(container)
    except Exception as e:
        print(f"\n⚠️  Warning: Failed to cleanup orphaned containers: {e}")

    return cleaned_containers


def pytest_collection_modifyitems(config, items):
    """Skip launchd-dependent tests (the macOS installer) where launchctl is missing."""
    if shutil.which("launchctl"):
        return
    skip = pytest.mark.skip(reason="needs macOS launchd (launchctl)")
    for item in items:
        if "launchd" in item.keywords:
            item.add_marker(skip)


def pytest_sessionfinish(session, exitstatus):
    """Pytest hook called after whole test run finished, right before returning exit status.

    This ensures all test containers are cleaned up even if tests fail or are interrupted.
    If orphaned containers are found, the test run will fail after cleanup.
    """
    print("\n" + "=" * 70)
    print("Cleaning up test containers...")
    print("=" * 70)
    orphaned = cleanup_orphaned_containers()
    print("=" * 70)

    if orphaned:
        error_msg = (
            f"\n❌ CONTAINER LEAK DETECTED!\n"
            f"Found {len(orphaned)} orphaned test container(s): {', '.join(orphaned)}\n\n"
            f"This indicates a test fixture failed to clean up properly.\n"
            f"Please investigate the test(s) that use these containers:\n"
        )
        for container_name in orphaned:
            error_msg += f"  - {container_name}\n"

        error_msg += (
            "\nContainers have been cleaned up, but the test run is marked as FAILED\n"
            "to prevent this issue from being ignored.\n"
        )

        pytest.fail(error_msg, pytrace=False)
