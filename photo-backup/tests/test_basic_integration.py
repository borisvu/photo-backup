"""
Basic integration test for pytest (Task 11)

This is the pytest version of the basic functionality test.
"""

import subprocess
import sys
from pathlib import Path
import pytest
import yaml


def test_modules_can_be_imported():
    """Test that all main modules can be imported."""
    from photo_backup.main import main
    from photo_backup.config import Config
    from photo_backup.logger import setup_logger
    
    assert main is not None
    assert Config is not None
    assert setup_logger is not None


def test_cli_version_command():
    """Test CLI version command."""
    cmd = [sys.executable, "-m", "photo_backup.main", "--version"]
    
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=10,
        cwd=Path(__file__).parent.parent
    )
    
    assert result.returncode == 0
    assert result.stdout.strip() == "Photo Backup v0.1.0"


def test_cli_production_mode():
    """Test CLI production mode execution."""
    cmd = [sys.executable, "-m", "photo_backup.main"]
    
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=15,
        cwd=Path(__file__).parent.parent
    )
    
    assert result.returncode == 0
    assert "PRODUCTION MODE" in result.stdout
    assert "s3.wasabisys.com" in result.stdout
    assert "INFO" in result.stdout


def test_cli_test_mode():
    """Test CLI test mode execution."""
    cmd = [sys.executable, "-m", "photo_backup.main", "--test-mode"]
    
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=15,
        cwd=Path(__file__).parent.parent
    )
    
    assert result.returncode == 0
    assert "TEST MODE" in result.stdout
    assert "localhost:9000" in result.stdout
    assert "DEBUG" in result.stdout


def test_config_system_integration():
    """Test that config system works in both modes."""
    from photo_backup.config import Config
    
    # Production config
    prod_config = Config(test_mode=False)
    assert prod_config.get('storage.endpoint') == "s3.wasabisys.com"
    
    # Test config
    test_config = Config(test_mode=True)
    assert test_config.get('storage.endpoint') == "localhost:9000"


def test_logger_system_integration():
    """Test that logger system works."""
    import logging
    from photo_backup.logger import setup_logger
    
    logger = setup_logger("integration_test", logging.INFO)
    assert logger.name == "integration_test"
    assert logger.level == logging.INFO


def test_config_example_exists_and_valid():
    """Test that config example file exists and is valid YAML."""
    config_file = Path(__file__).parent.parent / "config.yaml.example"
    assert config_file.exists()
    
    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)
    
    assert config is not None
    assert 'backup' in config
    assert 'test_mode' in config


@pytest.mark.slow
def test_full_infrastructure_integration():
    """Test complete integration with test infrastructure."""
    from tests.test_utils import (
        start_minio_container, 
        stop_minio_container,
        create_test_photos,
        cleanup_test_data,
        is_container_running,
        MINIO_CONTAINER_NAME
    )
    
    try:
        # Start infrastructure
        start_minio_container()
        assert is_container_running(MINIO_CONTAINER_NAME)
        
        photo_dir = create_test_photos()
        assert photo_dir.exists()
        
        # Run CLI in test mode
        cmd = [sys.executable, "-m", "photo_backup.main", "--test-mode"]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=20,
            cwd=Path(__file__).parent.parent
        )
        
        assert result.returncode == 0
        assert "TEST MODE" in result.stdout
        assert "starting in TEST MODE" in result.stdout
        assert "CLI initialization completed successfully" in result.stdout
        
    finally:
        # Always clean up
        try:
            cleanup_test_data()
            stop_minio_container()
        except Exception:
            pass  # Ignore cleanup errors in tests