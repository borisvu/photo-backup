"""Test configuration module."""

import pytest
from photo_backup.config import Config


def test_config_import():
    """Test that Config class can be imported."""
    assert Config is not None


def test_production_config():
    """Test production configuration."""
    config = Config(test_mode=False)
    settings = config.load_config()
    
    assert settings is not None
    assert "backup" in settings
    assert "storage" in settings
    assert settings["storage"]["endpoint"] == "s3.wasabisys.com"
    assert settings["backup"]["source_path"] == "/Volumes/4TB-SSD/Photo"
    assert settings["backup"]["destination"] == "wasabi-photo:my-photo-backup-bucket"


def test_test_mode_config():
    """Test test mode configuration uses Minio."""
    config = Config(test_mode=True)
    settings = config.load_config()
    
    assert settings is not None
    assert "backup" in settings
    assert "storage" in settings
    assert settings["storage"]["endpoint"] == "localhost:9000"
    assert settings["storage"]["access_key"] == "minioadmin"
    assert settings["storage"]["secret_key"] == "minioadmin"
    assert settings["backup"]["source_path"] == "/tmp/photo-backup-test-photos"


def test_config_get_method():
    """Test configuration get method with dot notation."""
    config = Config(test_mode=True)
    
    # Test simple key
    assert config.get("storage.endpoint") == "localhost:9000"
    assert config.get("storage.access_key") == "minioadmin"
    
    # Test nested key
    assert config.get("backup.source_path") == "/tmp/photo-backup-test-photos"
    
    # Test default value
    assert config.get("nonexistent.key", "default") == "default"
    assert config.get("nonexistent.key") is None


def test_test_mode_detection():
    """Test test mode detection."""
    prod_config = Config(test_mode=False)
    test_config = Config(test_mode=True)
    
    assert not prod_config.is_test_mode()
    assert test_config.is_test_mode()


def test_config_caching():
    """Test that configuration is cached after first load."""
    config = Config(test_mode=True)
    
    # Load config twice
    settings1 = config.load_config()
    settings2 = config.load_config()
    
    # Should be the same object (cached)
    assert settings1 is settings2


def test_test_mode_has_faster_timers():
    """Test that test mode has accelerated timers."""
    test_config = Config(test_mode=True)
    prod_config = Config(test_mode=False)
    
    test_settings = test_config.load_config()
    prod_settings = prod_config.load_config()
    
    # Test mode should have much shorter intervals
    assert test_settings["monitoring"]["check_interval_hours"] < 1
    assert prod_settings["monitoring"]["check_interval_hours"] >= 4
    
    assert test_settings["monitoring"]["mount_delay_minutes"] < 5
    assert prod_settings["monitoring"]["mount_delay_minutes"] >= 15