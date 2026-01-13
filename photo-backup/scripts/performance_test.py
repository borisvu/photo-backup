#!/usr/bin/env python3
"""
Performance Test for Photo Backup System (Task 105).

Standalone script (not pytest) that measures backup performance with 1000 files.

Usage:
    cd photo-backup
    python scripts/performance_test.py

Requirements:
    - Docker running (for Minio)
    - Project installed: pip install -e .
"""

import os
import resource
import subprocess
import sys
import tempfile
import time

from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Imports after path modification
from tests.fixtures.photo_fixtures import generate_test_photos  # noqa: E402
from tests.functional.minio_test_utils import MinioTestUtils  # noqa: E402

# Configuration
NUM_FILES = 1000
MIN_SIZE_MB = 1
MAX_SIZE_MB = 5
MINIO_PORT = 9050
CONTAINER_NAME = "photo-backup-perf-test"
BUCKET_NAME = "my-photo-backup-bucket-test"


def format_size(bytes_val: int) -> str:
    """Format bytes as human-readable string."""
    size = float(bytes_val)
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} TB"


def format_duration(seconds: float) -> str:
    """Format seconds as human-readable duration."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    secs = seconds % 60
    return f"{minutes}m {secs:.1f}s"


def create_test_bucket(container_name: str) -> bool:
    """Create test bucket in Minio."""
    result = subprocess.run(
        ["docker", "exec", container_name, "mc", "mb", f"test/{BUCKET_NAME}", "--ignore-existing"],
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.returncode == 0


def run_backup(source_path: str, project_dir: Path) -> tuple[bool, str, float]:
    """Run backup and return (success, output, duration)."""
    env = os.environ.copy()
    env["PHOTO_BACKUP_BACKUP_SOURCE_PATH"] = source_path
    env["PHOTO_BACKUP_STORAGE_ENDPOINT"] = f"localhost:{MINIO_PORT}"
    env["PHOTO_BACKUP_STORAGE_ACCESS_KEY"] = "minioadmin"
    env["PHOTO_BACKUP_STORAGE_SECRET_KEY"] = "minioadmin"
    env["PHOTO_BACKUP_STORAGE_USE_SSL"] = "false"
    env["PHOTO_BACKUP_STORAGE_BUCKET"] = BUCKET_NAME

    start_time = time.time()
    result = subprocess.run(
        [sys.executable, "-m", "photo_backup.main", "--test-mode", "sync"],
        capture_output=True,
        text=True,
        cwd=str(project_dir),
        env=env,
        timeout=1800,  # 30 min max
    )
    duration = time.time() - start_time

    output = result.stdout + result.stderr
    return result.returncode == 0, output, duration


def get_memory_usage_mb() -> float:
    """Get current process memory usage in MB."""
    usage = resource.getrusage(resource.RUSAGE_CHILDREN)
    # macOS reports ru_maxrss in bytes, Linux in KB
    if sys.platform == "darwin":
        return usage.ru_maxrss / (1024 * 1024)  # bytes to MB
    return usage.ru_maxrss / 1024  # KB to MB


def main():
    print("=" * 70)
    print("PHOTO BACKUP PERFORMANCE TEST")
    print("=" * 70)
    print("\nConfiguration:")
    print(f"  Files: {NUM_FILES}")
    print(f"  Size range: {MIN_SIZE_MB}-{MAX_SIZE_MB} MB per file")
    print(f"  Estimated total: {NUM_FILES * (MIN_SIZE_MB + MAX_SIZE_MB) / 2 / 1024:.1f} GB")
    print()

    # Check Docker
    client = MinioTestUtils.get_docker_client()
    if client is None:
        print("ERROR: Docker not available")
        sys.exit(1)
    print("✓ Docker available")

    # Start Minio
    print("\nStarting Minio container...")
    try:
        container = MinioTestUtils.start_or_reuse_minio(client, CONTAINER_NAME, port=MINIO_PORT)
        MinioTestUtils.wait_for_minio_ready(container.name, port=MINIO_PORT)
        print(f"✓ Minio ready on port {MINIO_PORT}")

        if not create_test_bucket(container.name):
            print("ERROR: Failed to create test bucket")
            sys.exit(1)
        print(f"✓ Bucket '{BUCKET_NAME}' ready")
    except Exception as e:
        print(f"ERROR: Failed to start Minio: {e}")
        sys.exit(1)

    # Generate test files
    print(f"\nGenerating {NUM_FILES} test files...")
    gen_start = time.time()

    with tempfile.TemporaryDirectory() as temp_dir:
        source_path = generate_test_photos(
            base_dir=temp_dir,
            num_files=NUM_FILES,
            min_size_mb=MIN_SIZE_MB,
            max_size_mb=MAX_SIZE_MB,
        )
        gen_duration = time.time() - gen_start

        # Calculate actual stats
        files = list(source_path.rglob("*"))
        files = [f for f in files if f.is_file()]
        total_size = sum(f.stat().st_size for f in files)

        print(f"✓ Generated {len(files)} files in {format_duration(gen_duration)}")
        print(f"  Total size: {format_size(total_size)}")
        print(f"  Avg file size: {format_size(total_size // len(files))}")

        # Run backup
        print("\n" + "=" * 70)
        print("RUNNING BACKUP")
        print("=" * 70)

        success, output, duration = run_backup(str(source_path), project_root)
        peak_memory = get_memory_usage_mb()

        # Results
        print("\n" + "=" * 70)
        print("RESULTS")
        print("=" * 70)

        if success:
            throughput_files = len(files) / duration
            throughput_bytes = total_size / duration

            print("\n✓ BACKUP COMPLETED SUCCESSFULLY")
            print("\nMetrics:")
            print(f"  Duration:        {format_duration(duration)}")
            print(f"  Files:           {len(files)}")
            print(f"  Total size:      {format_size(total_size)}")
            print(f"  Throughput:      {throughput_files:.1f} files/sec")
            print(f"  Throughput:      {format_size(int(throughput_bytes))}/sec")
            print(f"  Peak memory:     {peak_memory:.1f} MB")

            # Basic performance assessment
            print("\nAssessment:")
            if throughput_files >= 1.0:
                print("  ✓ File throughput acceptable (>= 1 file/sec)")
            else:
                print("  ⚠ File throughput low (< 1 file/sec)")

            if duration < 1800:  # 30 min
                print("  ✓ Completed within time limit (< 30 min)")
            else:
                print("  ⚠ Exceeded time limit (> 30 min)")

            print("\n" + "=" * 70)
            print("PERFORMANCE TEST PASSED")
            print("=" * 70)
        else:
            print("\n✗ BACKUP FAILED")
            print(f"\nOutput:\n{output[-2000:]}")  # Last 2000 chars
            print("\n" + "=" * 70)
            print("PERFORMANCE TEST FAILED")
            print("=" * 70)
            sys.exit(1)

    # Cleanup container
    print("\nCleaning up...")
    try:
        container = client.containers.get(CONTAINER_NAME)
        container.stop(timeout=5)
        container.remove(force=True)
        print("✓ Minio container removed")
    except Exception:
        pass

    print("\nDone.")


if __name__ == "__main__":
    main()
