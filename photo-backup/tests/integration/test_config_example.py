"""Test the example configuration file."""

import yaml
import pytest
from pathlib import Path


class TestConfigExample:
    """Integration tests for config.yaml.example file."""
    
    @pytest.mark.integration
    def test_config_example_exists(self):
        """Test that config.yaml.example file exists."""
        config_file = Path(__file__).parent.parent.parent / "config.yaml.example"
        assert config_file.exists(), "config.yaml.example file should exist"

    @pytest.mark.integration
    def test_config_example_is_valid_yaml(self):
        """Test that config.yaml.example is valid YAML."""
        config_file = Path(__file__).parent.parent.parent / "config.yaml.example"
        
        with open(config_file, 'r') as f:
            try:
                config = yaml.safe_load(f)
                assert config is not None, "Config should not be empty"
            except yaml.YAMLError as e:
                pytest.fail(f"config.yaml.example is not valid YAML: {e}")

    @pytest.mark.integration
    def test_config_example_has_required_sections(self):
        """Test that config.yaml.example has all required sections."""
        config_file = Path(__file__).parent.parent.parent / "config.yaml.example"
        
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
        
        # Check main sections
        required_sections = [
            'backup',
            'storage', 
            'monitoring',
            'verification',
            'rclone',
            'logging',
            'state',
            'notifications',
            'test_mode'
        ]
        
        for section in required_sections:
            assert section in config, f"Config should have '{section}' section"

    @pytest.mark.integration
    def test_config_example_backup_section(self):
        """Test backup section structure."""
        config_file = Path(__file__).parent.parent.parent / "config.yaml.example"
        
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
        
        backup = config['backup']
        assert 'source_path' in backup
        assert 'destination' in backup
        assert backup['source_path'] == "/Volumes/4TB-SSD/Photo"
        assert backup['destination'] == "wasabi-photo:my-photo-backup-bucket"

    @pytest.mark.integration
    def test_config_example_storage_section(self):
        """Test storage section structure."""
        config_file = Path(__file__).parent.parent.parent / "config.yaml.example"
        
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
        
        storage = config['storage']
        assert 'endpoint' in storage
        assert 'access_key' in storage
        assert 'secret_key' in storage
        assert 'use_ssl' in storage
        assert storage['endpoint'] == "s3.wasabisys.com"
        assert storage['use_ssl'] is True

    @pytest.mark.integration
    def test_config_example_test_mode_section(self):
        """Test test_mode section structure."""
        config_file = Path(__file__).parent.parent.parent / "config.yaml.example"
        
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
        
        test_mode = config['test_mode']
        assert 'backup' in test_mode
        assert 'storage' in test_mode
        assert 'monitoring' in test_mode
        assert 'logging' in test_mode
        assert 'state' in test_mode
        
        # Check test mode backup
        backup = test_mode['backup']
        assert backup['source_path'] == "/tmp/photo-backup-test-photos"
        assert backup['destination'] == "minio-test:my-photo-backup-bucket-test"
        
        # Check test mode storage
        storage = test_mode['storage']
        assert storage['endpoint'] == "localhost:9000"
        assert storage['access_key'] == "minioadmin"
        assert storage['secret_key'] == "minioadmin"
        assert storage['use_ssl'] is False

    @pytest.mark.integration
    def test_config_example_has_comments(self):
        """Test that config.yaml.example has helpful comments."""
        config_file = Path(__file__).parent.parent.parent / "config.yaml.example"
        
        with open(config_file, 'r') as f:
            content = f.read()
        
        # Check for key comment sections
        assert "Photo Backup System Configuration" in content
        assert "BACKUP CONFIGURATION" in content
        assert "STORAGE CONFIGURATION" in content
        assert "TEST MODE OVERRIDES" in content
        assert "SETUP INSTRUCTIONS" in content

    @pytest.mark.integration
    def test_config_example_test_mode_faster_timers(self):
        """Test that test mode has accelerated timers."""
        config_file = Path(__file__).parent.parent.parent / "config.yaml.example"
        
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
        
        # Production timers
        prod_monitoring = config['monitoring']
        
        # Test mode timers
        test_monitoring = config['test_mode']['monitoring']
        
        # Test mode should have much faster timers
        assert test_monitoring['check_interval_hours'] < prod_monitoring['check_interval_hours']
        assert test_monitoring['mount_delay_minutes'] < prod_monitoring['mount_delay_minutes']
        assert test_monitoring['change_delay_minutes'] < prod_monitoring['change_delay_minutes']

    @pytest.mark.integration
    def test_config_example_test_mode_debug_logging(self):
        """Test that test mode uses DEBUG logging."""
        config_file = Path(__file__).parent.parent.parent / "config.yaml.example"
        
        with open(config_file, 'r') as f:
            config = yaml.safe_load(f)
        
        # Production logging
        prod_logging = config['logging']
        
        # Test mode logging
        test_logging = config['test_mode']['logging']
        
        assert prod_logging['level'] == "INFO"
        assert test_logging['level'] == "DEBUG"