"""Utilities for functional testing."""

import subprocess
import os
import shutil
import time
import json
from pathlib import Path

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
        print(f"Docker command timed out after {timeout}s: docker {' '.join(cmd)}")
        raise
    except FileNotFoundError:
        print("Docker command not found. Please ensure Docker is installed.")
        raise

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
    print("Checking Docker connectivity...")
    
    # Test Docker is accessible
    result = run_docker_command(['ps'])
    if result.returncode != 0:
        print(f"Docker not accessible: {result.stderr}")
        raise RuntimeError("Docker daemon not accessible")
    
    # Check if container already running
    if is_container_running(MINIO_CONTAINER_NAME):
        print(f"Minio container '{MINIO_CONTAINER_NAME}' is already running.")
        return True
    
    # Stop and remove existing container if it exists
    if container_exists(MINIO_CONTAINER_NAME):
        print(f"Found existing container '{MINIO_CONTAINER_NAME}'. Stopping and removing it.")
        run_docker_command(['stop', MINIO_CONTAINER_NAME])
        run_docker_command(['rm', MINIO_CONTAINER_NAME])
    
    print(f"Starting new Minio container '{MINIO_CONTAINER_NAME}'...")
    
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
            print("Minio image not found. Pulling minio/minio:latest...")
            print("This may take several minutes for the first download...")
            pull_result = run_docker_command(['pull', 'minio/minio:latest'], timeout=300)  # 5 minutes for pull
            if pull_result.returncode != 0:
                print(f"Failed to pull Minio image: {pull_result.stderr}")
                raise RuntimeError("Failed to pull Minio image")
            
            # Try starting again after pull
            result = run_docker_command(cmd)
            if result.returncode != 0:
                print(f"Failed to start Minio container: {result.stderr}")
                raise RuntimeError("Failed to start Minio container")
        else:
            print(f"Failed to start Minio container: {result.stderr}")
            raise RuntimeError("Failed to start Minio container")
    
    # Wait for Minio to be ready
    print("Waiting for Minio to start...")
    time.sleep(5)
    
    # Verify container is running
    if is_container_running(MINIO_CONTAINER_NAME):
        print("Minio container started successfully.")
        print("Access Minio at: http://localhost:9000")
        print("Login: minioadmin / minioadmin")
        return True
    else:
        print("Minio container failed to start properly.")
        return False

def stop_minio_container():
    """Stops and removes the Minio Docker container."""
    if not container_exists(MINIO_CONTAINER_NAME):
        print(f"Container '{MINIO_CONTAINER_NAME}' not found.")
        return
    
    print(f"Stopping and removing container '{MINIO_CONTAINER_NAME}'...")
    
    # Stop container
    result = run_docker_command(['stop', MINIO_CONTAINER_NAME])
    if result.returncode != 0:
        print(f"Warning: Failed to stop container: {result.stderr}")
    
    # Remove container
    result = run_docker_command(['rm', MINIO_CONTAINER_NAME])
    if result.returncode != 0:
        print(f"Warning: Failed to remove container: {result.stderr}")
    else:
        print("Minio container stopped and removed.")

def create_test_photos(base_dir=TEST_PHOTO_DIR):
    """Creates a dummy photo directory structure and files."""
    if base_dir.exists():
        shutil.rmtree(base_dir)
    
    print(f"Creating test photos in {base_dir}...")
    
    (base_dir / "2024" / "01").mkdir(parents=True, exist_ok=True)
    (base_dir / "2024" / "02").mkdir(exist_ok=True)
    
    (base_dir / "2024" / "01" / "photo1.jpg").write_text("dummy photo 1")
    (base_dir / "2024" / "01" / "photo2.jpg").write_text("dummy photo 2")
    (base_dir / "2024" / "02" / "photo3.jpg").write_text("dummy photo 3")
    
    print("Test photos created.")
    return base_dir

def cleanup_test_data(base_dir=TEST_PHOTO_DIR):
    """Removes the test photo directory."""
    if base_dir.exists():
        print(f"Cleaning up test data in {base_dir}...")
        shutil.rmtree(base_dir)
        print("Test data cleaned up.")

if __name__ == "__main__":
    print("Running test_utils directly...")
    
    print("\n--- Starting Minio ---")
    start_minio_container()
    
    print("\n--- Creating Test Photos ---")
    create_test_photos()
    
    print(f"\nListing test photo directory:")
    for path in sorted(TEST_PHOTO_DIR.rglob("*")):
        print(path)
        
    input("\nPress Enter to stop Minio and clean up...")
    
    print("\n--- Stopping Minio ---")
    stop_minio_container()
    
    print("\n--- Cleaning up data ---")
    cleanup_test_data()
    
    print("\nDone.") 