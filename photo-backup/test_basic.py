#!/usr/bin/env python3
"""
Basic functional test for Photo Backup System (Task 11)

This test verifies that all foundation components work together:
- CLI entry point
- Configuration system
- Logger integration
- Test infrastructure
"""

import subprocess
import sys
import time
from pathlib import Path
import pytest


def test_basic_cli_import():
    """Test that main CLI can be imported without errors."""
    try:
        from photo_backup.main import main
        from photo_backup.config import Config
        from photo_backup.logger import setup_logger
        print("✅ All modules imported successfully")
    except ImportError as e:
        pytest.fail(f"Failed to import modules: {e}")


def test_basic_cli_execution():
    """Test that CLI runs without errors."""
    cmd = [sys.executable, "-m", "photo_backup.main", "--version"]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
            cwd=Path(__file__).parent
        )
        
        assert result.returncode == 0, f"CLI failed: {result.stderr}"
        assert "Photo Backup v0.1.0" in result.stdout, "Version not in output"
        print("✅ Basic CLI execution works")
        
    except subprocess.TimeoutExpired:
        pytest.fail("CLI execution timed out")


def test_production_mode_cli():
    """Test CLI in production mode."""
    cmd = [sys.executable, "-m", "photo_backup.main"]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=15,
            cwd=Path(__file__).parent
        )
        
        assert result.returncode == 0, f"Production mode failed: {result.stderr}"
        assert "Photo Backup v0.1.0" in result.stdout, "Version not displayed"
        assert "PRODUCTION MODE" in result.stdout, "Production mode not indicated"
        assert "s3.wasabisys.com" in result.stdout, "Wasabi endpoint not shown"
        assert "photo_backup" in result.stdout, "Logger output not present"
        assert "INFO" in result.stdout, "INFO log level not present"
        print("✅ Production mode CLI works")
        
    except subprocess.TimeoutExpired:
        pytest.fail("Production mode CLI timed out")


def test_test_mode_cli():
    """Test CLI in test mode."""
    cmd = [sys.executable, "-m", "photo_backup.main", "--test-mode"]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=15,
            cwd=Path(__file__).parent
        )
        
        assert result.returncode == 0, f"Test mode failed: {result.stderr}"
        assert "Photo Backup v0.1.0" in result.stdout, "Version not displayed"
        assert "TEST MODE" in result.stdout, "Test mode not indicated"
        assert "localhost:9000" in result.stdout, "Minio endpoint not shown"
        assert "minioadmin" in result.stdout, "Test credentials not shown"
        assert "photo_backup" in result.stdout, "Logger output not present"
        assert "DEBUG" in result.stdout, "DEBUG log level not present"
        print("✅ Test mode CLI works")
        
    except subprocess.TimeoutExpired:
        pytest.fail("Test mode CLI timed out")


def test_config_integration():
    """Test configuration system integration."""
    from photo_backup.config import Config
    
    # Test production config
    prod_config = Config(test_mode=False)
    prod_settings = prod_config.load_config()
    
    assert prod_settings is not None, "Production config should load"
    assert prod_config.get('storage.endpoint') == "s3.wasabisys.com", "Production endpoint incorrect"
    assert prod_config.get('backup.source_path') == "/Volumes/4TB-SSD/Photo", "Production source incorrect"
    
    # Test test mode config
    test_config = Config(test_mode=True)
    test_settings = test_config.load_config()
    
    assert test_settings is not None, "Test config should load"
    assert test_config.get('storage.endpoint') == "localhost:9000", "Test endpoint incorrect"
    assert test_config.get('storage.access_key') == "minioadmin", "Test credentials incorrect"
    
    print("✅ Configuration integration works")


def test_logger_integration():
    """Test logger system integration."""
    import logging
    from photo_backup.logger import setup_logger, get_logger, set_log_level
    
    # Test logger setup
    logger = setup_logger("test_integration", logging.INFO)
    assert logger is not None, "Logger should be created"
    assert logger.name == "test_integration", "Logger name incorrect"
    
    # Test logger retrieval
    same_logger = get_logger("test_integration")
    assert same_logger is logger, "Should get same logger instance"
    
    # Test log level changes
    set_log_level(logging.DEBUG, "test_integration")
    assert logger.level == logging.DEBUG, "Log level should change"
    
    print("✅ Logger integration works")


def test_with_test_infrastructure():
    """Test complete workflow with test infrastructure."""
    from tests.test_utils import (
        start_minio_container, 
        stop_minio_container,
        create_test_photos,
        cleanup_test_data,
        is_container_running,
        MINIO_CONTAINER_NAME,
        TEST_PHOTO_DIR
    )
    
    try:
        print("🚀 Starting comprehensive infrastructure test...")
        
        # 1. Start Minio container
        print("📦 Starting Minio container...")
        start_minio_container()
        assert is_container_running(MINIO_CONTAINER_NAME), "Minio should be running"
        print("✅ Minio container started")
        
        # 2. Create test photos
        print("📸 Creating test photos...")
        photo_dir = create_test_photos()
        assert photo_dir.exists(), "Test photo directory should exist"
        
        # Verify test photos were created
        photo_files = list(photo_dir.rglob("*.jpg"))
        assert len(photo_files) >= 3, "Should have at least 3 test photos"
        print(f"✅ Created {len(photo_files)} test photos")
        
        # 3. Run CLI in test mode with infrastructure
        print("🖥️  Running CLI in test mode...")
        cmd = [sys.executable, "-m", "photo_backup.main", "--test-mode"]
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=20,
            cwd=Path(__file__).parent
        )
        
        assert result.returncode == 0, f"CLI with infrastructure failed: {result.stderr}"
        assert "TEST MODE" in result.stdout, "Test mode not indicated"
        assert "localhost:9000" in result.stdout, "Minio endpoint not shown"
        assert "/tmp/photo-backup-test-photos" in result.stdout, "Test photo path not shown"
        print("✅ CLI works with test infrastructure")
        
        # 4. Verify all components logged properly
        assert "starting in TEST MODE" in result.stdout, "Startup log missing"
        assert "Initializing test mode configuration" in result.stdout, "Config log missing"
        assert "CLI initialization completed successfully" in result.stdout, "Completion log missing"
        print("✅ All logging components working")
        
        print("🎉 Comprehensive infrastructure test completed successfully!")
        
    except Exception as e:
        print(f"❌ Infrastructure test failed: {e}")
        raise
        
    finally:
        # Always clean up, even if test fails
        print("🧹 Cleaning up test infrastructure...")
        try:
            cleanup_test_data()
            stop_minio_container()
            print("✅ Cleanup completed")
        except Exception as cleanup_error:
            print(f"⚠️  Cleanup warning: {cleanup_error}")


def test_config_example_file():
    """Test that config example file exists and is valid."""
    config_file = Path(__file__).parent / "config.yaml.example"
    assert config_file.exists(), "config.yaml.example should exist"
    
    # Test that it's valid YAML
    import yaml
    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)
    
    assert config is not None, "Config example should be valid YAML"
    assert 'backup' in config, "Config should have backup section"
    assert 'test_mode' in config, "Config should have test_mode section"
    print("✅ Configuration example file is valid")


def main():
    """Run all basic functionality tests."""
    print("=" * 60)
    print("Photo Backup System - Basic Functionality Test")
    print("=" * 60)
    
    try:
        print("\n1. Testing module imports...")
        test_basic_cli_import()
        
        print("\n2. Testing basic CLI execution...")
        test_basic_cli_execution()
        
        print("\n3. Testing production mode...")
        test_production_mode_cli()
        
        print("\n4. Testing test mode...")
        test_test_mode_cli()
        
        print("\n5. Testing configuration integration...")
        test_config_integration()
        
        print("\n6. Testing logger integration...")
        test_logger_integration()
        
        print("\n7. Testing configuration example...")
        test_config_example_file()
        
        print("\n8. Testing with full test infrastructure...")
        test_with_test_infrastructure()
        
        print("\n" + "=" * 60)
        print("🎉 ALL TESTS PASSED! Foundation is solid and ready.")
        print("=" * 60)
        return 0
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())