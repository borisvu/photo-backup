"""
Functional tests for test infrastructure.

These tests verify that the test infrastructure (Docker, Minio) works correctly.
"""

import sys

import pytest


class TestDockerInfrastructure:
    """Functional tests for Docker infrastructure."""

    @pytest.mark.functional
    @pytest.mark.slow
    def test_docker_connectivity(self):
        """Test that Docker is accessible."""
        from tests.conftest import run_docker_command

        result = run_docker_command(["--version"])
        assert result.returncode == 0, "Docker should be accessible"
        assert "Docker version" in result.stdout, "Should show Docker version"

    @pytest.mark.functional
    @pytest.mark.slow
    def test_minio_container_lifecycle(self):
        """Test Minio container start/stop cycle."""
        from tests.conftest import (
            MINIO_CONTAINER_NAME,
            container_exists,
            is_container_running,
            start_minio_container,
            stop_minio_container,
        )

        # Clean up any existing container
        if container_exists(MINIO_CONTAINER_NAME):
            stop_minio_container()

        # Start container
        assert start_minio_container(), "Should start Minio container"
        assert is_container_running(MINIO_CONTAINER_NAME), "Container should be running"

        # Stop container
        stop_minio_container()
        assert not is_container_running(MINIO_CONTAINER_NAME), "Container should be stopped"


class TestPhotoInfrastructure:
    """Functional tests for test photo infrastructure."""

    @pytest.mark.functional
    def test_test_photo_creation(self, test_photos):
        """Test test photo directory creation."""
        assert test_photos.exists(), "Test photo directory should exist"

        # Count all photo files (should be 5 from conftest.py)
        photo_files = list(test_photos.rglob("*"))
        photo_files = [f for f in photo_files if f.is_file() and f.suffix.lower() in [".jpg", ".jpeg", ".dng", ".cr2"]]
        assert len(photo_files) == 5, f"Should have 5 test photos, found {len(photo_files)}"

        # Check that we have some files in year/month structure
        year_dirs = [d for d in test_photos.iterdir() if d.is_dir()]
        assert len(year_dirs) > 0, "Should have year directories"

        # Check that at least one year directory has month directories
        month_dirs = []
        for year_dir in year_dirs:
            month_dirs.extend([d for d in year_dir.iterdir() if d.is_dir()])
        assert len(month_dirs) > 0, "Should have month directories"

    @pytest.mark.functional
    def test_test_photo_structure(self, test_photos):
        """Test that test photos have correct directory structure."""
        # Check that we have year directories
        year_dirs = [d for d in test_photos.iterdir() if d.is_dir()]
        assert len(year_dirs) > 0, "Should have year directories"

        # Check that year directories contain month directories
        for year_dir in year_dirs:
            month_dirs = [d for d in year_dir.iterdir() if d.is_dir()]
            assert len(month_dirs) > 0, f"Year directory {year_dir.name} should have month directories"

            # Check that month directories contain photo files
            for month_dir in month_dirs:
                photo_files = [
                    f
                    for f in month_dir.iterdir()
                    if f.is_file() and f.suffix.lower() in [".jpg", ".jpeg", ".dng", ".cr2"]
                ]
                assert len(photo_files) > 0, f"Month directory {month_dir.name} should have photo files"

                # Check that files have the expected naming pattern (IMG_XXXX.ext)
                for photo_file in photo_files:
                    assert photo_file.stem.startswith("IMG_"), f"File {photo_file.name} should start with IMG_"
                    assert photo_file.stem[4:].isdigit(), f"File {photo_file.name} should have numeric part after IMG_"

        # Check that files have random content (not empty)
        all_photo_files = list(test_photos.rglob("*"))
        all_photo_files = [
            f for f in all_photo_files if f.is_file() and f.suffix.lower() in [".jpg", ".jpeg", ".dng", ".cr2"]
        ]
        assert len(all_photo_files) > 0, "Should have photo files"

        for photo_file in all_photo_files:
            content = photo_file.read_text()
            assert len(content) > 0, f"Photo file {photo_file.name} should have content"
            assert len(content) > 100, f"Photo file {photo_file.name} should have substantial content"

    @pytest.mark.functional
    def test_test_photo_cleanup(self):
        """Test that test photo cleanup works."""
        from tests.conftest import cleanup_test_data, create_test_photos

        # Create photos
        photo_dir = create_test_photos()
        assert photo_dir.exists()

        # Clean up
        cleanup_test_data()
        assert not photo_dir.exists()


class TestFixtureIntegration:
    """Functional tests for fixture integration."""

    @pytest.mark.functional
    def test_temp_dir_fixture(self, temp_dir):
        """Test that temp_dir fixture works."""
        assert temp_dir.exists()
        assert temp_dir.is_dir()

        # Create a test file
        test_file = temp_dir / "test.txt"
        test_file.write_text("test content")
        assert test_file.exists()

    @pytest.mark.functional
    def test_sample_config_fixture(self, sample_config):
        """Test that sample_config fixture works."""
        assert "backup" in sample_config
        assert "storage" in sample_config
        assert sample_config["storage"]["endpoint"] == "localhost:9000"
        assert sample_config["storage"]["access_key"] == "minioadmin"

    @pytest.mark.functional
    def test_cli_runner_fixture(self, cli_runner):
        """Test that cli_runner fixture works."""
        result = cli_runner(["--version"])
        assert result.returncode == 0
        assert "Photo Backup v0.1.0" in result.stdout

    @pytest.mark.functional
    def test_fixtures_work_together(self, temp_dir, sample_config):
        """Test that multiple fixtures work together correctly."""
        # Use temp_dir fixture
        test_file = temp_dir / "test.txt"
        test_file.write_text("test content")
        assert test_file.exists()

        # Use sample_config fixture
        assert "backup" in sample_config
        assert "storage" in sample_config
        assert sample_config["storage"]["endpoint"] == "localhost:9000"

        # Create a config file in temp dir
        config_file = temp_dir / "test_config.yaml"
        import yaml

        with open(config_file, "w") as f:
            yaml.dump(sample_config, f)

        assert config_file.exists()

        # Verify config can be loaded
        with open(config_file) as f:
            loaded_config = yaml.safe_load(f)

        assert loaded_config == sample_config


class TestInfrastructureResilience:
    """Tests for infrastructure resilience and error handling."""

    MINIO_PORT = 9007

    # Use shared fixture factory to avoid code duplication
    from tests.functional.minio_test_utils import MinioTestUtils

    minio_container = MinioTestUtils.create_minio_fixture("photo-backup-infra-test", port=MINIO_PORT)

    @pytest.mark.functional
    @pytest.mark.slow
    def test_infrastructure_resilience(self):
        """Test that infrastructure can handle multiple start/stop cycles."""
        from tests.conftest import (
            MINIO_CONTAINER_NAME,
            cleanup_test_data,
            create_test_photos,
            is_container_running,
            start_minio_container,
            stop_minio_container,
        )

        # Multiple cycles
        for _ in range(2):  # Reduced from 3 to 2 for faster tests
            # Start Minio
            start_minio_container()
            assert is_container_running(MINIO_CONTAINER_NAME)

            # Create test photos
            photo_dir = create_test_photos()
            assert photo_dir.exists()

            # Clean up photos
            cleanup_test_data()
            assert not photo_dir.exists()

            # Stop Minio
            stop_minio_container()
            assert not is_container_running(MINIO_CONTAINER_NAME)

    @pytest.mark.functional
    def test_infrastructure_error_handling(self):
        """Test infrastructure error handling."""
        from tests.conftest import run_docker_command

        # Test with invalid docker command
        result = run_docker_command(["invalid-command"])
        assert result.returncode != 0  # Should fail gracefully

    @pytest.mark.functional
    @pytest.mark.slow
    def test_minio_integration_with_cli(self, minio_container):
        """Test Minio integration with CLI (simplified version)."""
        # Just test that CLI works when Minio fixture is active
        import os
        import subprocess

        env = os.environ.copy()
        env["PHOTO_BACKUP_STORAGE_ENDPOINT"] = f"localhost:{self.MINIO_PORT}"
        env["PHOTO_BACKUP_STORAGE_ACCESS_KEY"] = "minioadmin"
        env["PHOTO_BACKUP_STORAGE_SECRET_KEY"] = "minioadmin"
        env["PHOTO_BACKUP_STORAGE_USE_SSL"] = "false"
        env["PHOTO_BACKUP_STORAGE_BUCKET"] = "test-bucket"

        result = subprocess.run(
            [sys.executable, "-m", "photo_backup.main", "--test-mode"],
            capture_output=True,
            text=True,
            cwd=".",
            env=env,
        )

        assert result.returncode == 0
        combined_output = result.stdout + result.stderr
        assert "TEST MODE" in combined_output
        assert f"localhost:{self.MINIO_PORT}" in combined_output

        # Note: minio_container fixture ensures Minio is available for the test
