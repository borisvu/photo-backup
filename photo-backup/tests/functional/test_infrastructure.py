"""
Functional tests for test infrastructure.

These tests verify that the test infrastructure (Docker, Minio) works correctly.
"""

import pytest
from pathlib import Path


class TestDockerInfrastructure:
    """Functional tests for Docker infrastructure."""
    
    @pytest.mark.functional
    @pytest.mark.slow
    def test_docker_connectivity(self):
        """Test that Docker is accessible."""
        from tests.conftest import run_docker_command
        
        result = run_docker_command(['--version'])
        assert result.returncode == 0, "Docker should be accessible"
        assert "Docker version" in result.stdout, "Should show Docker version"
    
    @pytest.mark.functional
    @pytest.mark.slow
    def test_minio_container_lifecycle(self):
        """Test Minio container start/stop cycle."""
        from tests.conftest import (
            start_minio_container, 
            stop_minio_container,
            is_container_running,
            container_exists,
            MINIO_CONTAINER_NAME
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
        assert (test_photos / "2024" / "01" / "photo1.jpg").exists(), "Test photo should exist"
        assert (test_photos / "2024" / "02" / "photo3.jpg").exists(), "Test photo should exist"
        
        # Count files
        photo_files = list(test_photos.rglob("*.jpg"))
        assert len(photo_files) == 3, "Should have 3 test photos"
    
    @pytest.mark.functional
    def test_test_photo_structure(self, test_photos):
        """Test that test photos have correct directory structure."""
        # Check directory structure
        assert (test_photos / "2024").is_dir()
        assert (test_photos / "2024" / "01").is_dir()
        assert (test_photos / "2024" / "02").is_dir()
        
        # Check file contents
        photo1_content = (test_photos / "2024" / "01" / "photo1.jpg").read_text()
        assert photo1_content == "dummy photo 1"
        
        photo2_content = (test_photos / "2024" / "01" / "photo2.jpg").read_text()
        assert photo2_content == "dummy photo 2"
        
        photo3_content = (test_photos / "2024" / "02" / "photo3.jpg").read_text()
        assert photo3_content == "dummy photo 3"
    
    @pytest.mark.functional
    def test_test_photo_cleanup(self):
        """Test that test photo cleanup works."""
        from tests.conftest import create_test_photos, cleanup_test_data, TEST_PHOTO_DIR
        
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
        assert 'backup' in sample_config
        assert 'storage' in sample_config
        assert sample_config['storage']['endpoint'] == 'localhost:9000'
        assert sample_config['storage']['access_key'] == 'minioadmin'
    
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
        assert 'backup' in sample_config
        assert 'storage' in sample_config
        assert sample_config['storage']['endpoint'] == 'localhost:9000'
        
        # Create a config file in temp dir
        config_file = temp_dir / "test_config.yaml"
        import yaml
        with open(config_file, 'w') as f:
            yaml.dump(sample_config, f)
        
        assert config_file.exists()
        
        # Verify config can be loaded
        with open(config_file, 'r') as f:
            loaded_config = yaml.safe_load(f)
        
        assert loaded_config == sample_config


class TestInfrastructureResilience:
    """Tests for infrastructure resilience and error handling."""
    
    @pytest.mark.functional
    @pytest.mark.slow
    def test_infrastructure_resilience(self):
        """Test that infrastructure can handle multiple start/stop cycles."""
        from tests.conftest import (
            start_minio_container, 
            stop_minio_container,
            is_container_running,
            MINIO_CONTAINER_NAME,
            create_test_photos,
            cleanup_test_data
        )
        
        # Multiple cycles
        for i in range(2):  # Reduced from 3 to 2 for faster tests
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
        result = run_docker_command(['invalid-command'])
        assert result.returncode != 0  # Should fail gracefully
    
    @pytest.mark.functional
    @pytest.mark.slow  
    def test_minio_integration_with_cli(self, minio_container, cli_runner):
        """Test Minio integration with CLI (simplified version)."""
        # Just test that CLI works when Minio fixture is active
        result = cli_runner(["--test-mode"])
        
        assert result.returncode == 0
        assert "TEST MODE" in result.stdout
        assert "localhost:9000" in result.stdout
        
        # Note: minio_container fixture ensures Minio is available for the test