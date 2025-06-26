"""Utilities for functional testing."""

import docker
import os
import shutil
import time
from pathlib import Path

MINIO_CONTAINER_NAME = "photo-backup-minio-test"
TEST_PHOTO_DIR = Path("/tmp/photo-backup-test-photos")

def start_minio_container():
    """Starts a Minio Docker container for testing."""
    client = docker.from_env()
    
    try:
        container = client.containers.get(MINIO_CONTAINER_NAME)
        if container.status == 'running':
            print(f"Minio container '{MINIO_CONTAINER_NAME}' is already running.")
            return container
        print(f"Found existing container '{MINIO_CONTAINER_NAME}'. Stopping and removing it.")
        container.stop()
        container.remove()
    except docker.errors.NotFound:
        pass # Container doesn't exist, which is fine

    print(f"Starting new Minio container '{MINIO_CONTAINER_NAME}'...")
    container = client.containers.run(
        "minio/minio:latest",
        command="server /data --console-address :9090",
        name=MINIO_CONTAINER_NAME,
        ports={"9000/tcp": 9000, "9090/tcp": 9090},
        detach=True,
    )
    
    # Wait for Minio to be ready
    print("Waiting for Minio to start...")
    time.sleep(5) 
    print("Minio container started.")
    return container

def stop_minio_container():
    """Stops and removes the Minio Docker container."""
    client = docker.from_env()
    try:
        container = client.containers.get(MINIO_CONTAINER_NAME)
        print(f"Stopping and removing container '{MINIO_CONTAINER_NAME}'...")
        container.stop()
        container.remove()
        print("Minio container stopped and removed.")
    except docker.errors.NotFound:
        print(f"Container '{MINIO_CONTAINER_NAME}' not found.")

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