"""
Unit tests for config defaults module.

These tests focus on default configuration constants and their structure.
"""

import pytest

from photo_backup.config.defaults import DEFAULT_CONFIG, DEFAULT_CONFIG_DOCS, TEST_MODE_DEFAULTS


class TestConfigDefaults:
    """Test cases for default configuration constants."""

    @pytest.mark.unit
    def test_default_config_structure(self):
        """Test that DEFAULT_CONFIG has the expected structure."""
        # Check that all required sections exist
        required_sections = ["backup", "storage", "monitoring", "logging", "state"]
        for section in required_sections:
            assert section in DEFAULT_CONFIG
            assert isinstance(DEFAULT_CONFIG[section], dict)

        # Check that backup section has required fields
        backup = DEFAULT_CONFIG["backup"]
        assert "source_path" in backup
        assert "destination" in backup
        assert "strategy" in backup
        assert backup["strategy"] == "incremental"

        # Check that storage section has required fields
        storage = DEFAULT_CONFIG["storage"]
        assert "endpoint" in storage
        assert "access_key" in storage
        assert "secret_key" in storage
        assert storage["endpoint"] == "s3.wasabisys.com"

        # Check that monitoring section has required fields
        monitoring = DEFAULT_CONFIG["monitoring"]
        assert "check_interval_hours" in monitoring
        assert "mount_delay_minutes" in monitoring
        assert "change_delay_minutes" in monitoring

    @pytest.mark.unit
    def test_default_config_documentation(self):
        """Test that DEFAULT_CONFIG_DOCS has documentation for all settings."""
        # Check that all sections in DEFAULT_CONFIG have documentation
        for section in DEFAULT_CONFIG:
            assert section in DEFAULT_CONFIG_DOCS
            assert isinstance(DEFAULT_CONFIG_DOCS[section], dict)

            # Check that all fields in each section have documentation
            for field in DEFAULT_CONFIG[section]:
                if isinstance(DEFAULT_CONFIG[section][field], dict):
                    # For nested dictionaries, check if the field itself has documentation
                    if field in DEFAULT_CONFIG_DOCS[section]:
                        assert isinstance(DEFAULT_CONFIG_DOCS[section][field], dict)
                else:
                    # For simple fields, check that documentation exists
                    assert field in DEFAULT_CONFIG_DOCS[section]
                    assert isinstance(DEFAULT_CONFIG_DOCS[section][field], str)
                    assert len(DEFAULT_CONFIG_DOCS[section][field]) > 0

    @pytest.mark.unit
    def test_test_mode_defaults(self):
        """Test that TEST_MODE_DEFAULTS has appropriate test settings."""
        # Check that test mode has faster intervals
        monitoring = TEST_MODE_DEFAULTS["monitoring"]
        assert monitoring["check_interval_hours"] == 0.1  # 6 minutes
        assert monitoring["mount_delay_minutes"] == 1
        assert monitoring["change_delay_minutes"] == 1

        # Check that test mode uses local storage
        storage = TEST_MODE_DEFAULTS["storage"]
        assert storage["endpoint"] == "localhost:9000"
        assert storage["access_key"] == "minioadmin"
        assert storage["secret_key"] == "minioadmin"
        assert storage["use_ssl"] is False

        # Check that test mode uses debug logging
        logging = TEST_MODE_DEFAULTS["logging"]
        assert logging["level"] == "DEBUG"
        assert "/tmp/photo-backup-test" in logging["directory"]

    @pytest.mark.unit
    def test_default_config_has_new_sections(self):
        """Test that DEFAULT_CONFIG includes new sections."""
        # Check for new sections
        assert "security" in DEFAULT_CONFIG
        assert "performance" in DEFAULT_CONFIG
        assert "notifications" in DEFAULT_CONFIG

        # Check security section
        security = DEFAULT_CONFIG["security"]
        assert "encrypt_backups" in security
        assert "verify_checksums" in security
        assert "checksum_algorithm" in security

        # Check performance section
        performance = DEFAULT_CONFIG["performance"]
        assert "buffer_size_mb" in performance
        assert "max_memory_usage_mb" in performance
        assert "parallel_uploads" in performance

        # Check notifications section
        notifications = DEFAULT_CONFIG["notifications"]
        assert "enabled" in notifications
        assert "email" in notifications
        assert "webhook" in notifications

    @pytest.mark.unit
    def test_test_mode_defaults_optimized_for_testing(self):
        """Test that test mode defaults are optimized for testing."""
        # Check performance settings are reduced for testing
        performance = TEST_MODE_DEFAULTS["performance"]
        assert performance["buffer_size_mb"] == 1  # Smaller buffer
        assert performance["max_memory_usage_mb"] == 64  # Lower memory
        assert performance["chunk_size_mb"] == 1  # Smaller chunks
        assert performance["enable_caching"] is False  # No caching

        # Check security settings are relaxed for testing
        security = TEST_MODE_DEFAULTS["security"]
        assert security["verify_checksums"] is False  # Skip verification
        assert security["encrypt_backups"] is False  # No encryption

        # Check backup settings are optimized for testing
        backup = TEST_MODE_DEFAULTS["backup"]
        assert backup["compression"] is False  # No compression
        assert backup["verify_after_backup"] is False  # Skip verification

    @pytest.mark.unit
    def test_default_config_backward_compatibility(self):
        """Test that default config maintains backward compatibility."""
        # Check that original fields still exist with same values
        assert DEFAULT_CONFIG["backup"]["source_path"] == "/Volumes/4TB-SSD/Photo"
        assert DEFAULT_CONFIG["backup"]["destination"] == "wasabi-photo:my-photo-backup-bucket"
        assert DEFAULT_CONFIG["storage"]["endpoint"] == "s3.wasabisys.com"
        assert DEFAULT_CONFIG["storage"]["access_key"] is None
        assert DEFAULT_CONFIG["storage"]["secret_key"] is None
        assert DEFAULT_CONFIG["storage"]["use_ssl"] is True
        assert DEFAULT_CONFIG["monitoring"]["check_interval_hours"] == 4
        assert DEFAULT_CONFIG["monitoring"]["mount_delay_minutes"] == 15
        assert DEFAULT_CONFIG["monitoring"]["change_delay_minutes"] == 30
        assert DEFAULT_CONFIG["logging"]["level"] == "INFO"
        assert DEFAULT_CONFIG["logging"]["directory"] == "~/Library/Logs/photo-backup"
        assert DEFAULT_CONFIG["state"]["directory"] == "~/Library/Application Support/photo-backup"

    @pytest.mark.unit
    def test_default_config_data_types(self):
        """Test that default config has correct data types."""
        # Test string fields
        assert isinstance(DEFAULT_CONFIG["backup"]["source_path"], str)
        assert isinstance(DEFAULT_CONFIG["backup"]["destination"], str)
        assert isinstance(DEFAULT_CONFIG["storage"]["endpoint"], str)

        # Test numeric fields
        assert isinstance(DEFAULT_CONFIG["monitoring"]["check_interval_hours"], int | float)
        assert isinstance(DEFAULT_CONFIG["monitoring"]["mount_delay_minutes"], int)
        assert isinstance(DEFAULT_CONFIG["logging"]["max_size_mb"], int)
        assert isinstance(DEFAULT_CONFIG["logging"]["backup_count"], int)

        # Test boolean fields
        assert isinstance(DEFAULT_CONFIG["storage"]["use_ssl"], bool)
        assert isinstance(DEFAULT_CONFIG["security"]["encrypt_backups"], bool)
        assert isinstance(DEFAULT_CONFIG["security"]["verify_checksums"], bool)

    @pytest.mark.unit
    def test_test_mode_defaults_data_types(self):
        """Test that test mode defaults have correct data types."""
        # Test string fields
        assert isinstance(TEST_MODE_DEFAULTS["backup"]["source_path"], str)
        assert isinstance(TEST_MODE_DEFAULTS["storage"]["endpoint"], str)
        assert isinstance(TEST_MODE_DEFAULTS["storage"]["access_key"], str)
        assert isinstance(TEST_MODE_DEFAULTS["storage"]["secret_key"], str)

        # Test numeric fields
        assert isinstance(TEST_MODE_DEFAULTS["monitoring"]["check_interval_hours"], int | float)
        assert isinstance(TEST_MODE_DEFAULTS["monitoring"]["mount_delay_minutes"], int)

        # Test boolean fields
        assert isinstance(TEST_MODE_DEFAULTS["storage"]["use_ssl"], bool)
        assert isinstance(TEST_MODE_DEFAULTS["security"]["encrypt_backups"], bool)
        assert isinstance(TEST_MODE_DEFAULTS["security"]["verify_checksums"], bool)

    @pytest.mark.unit
    def test_default_config_documentation_quality(self):
        """Test that default config documentation is high quality."""
        # Check that documentation is descriptive
        backup_docs = DEFAULT_CONFIG_DOCS["backup"]
        assert len(backup_docs["source_path"]) > 20  # Should be descriptive
        assert len(backup_docs["destination"]) > 20

        storage_docs = DEFAULT_CONFIG_DOCS["storage"]
        assert len(storage_docs["endpoint"]) > 20
        assert len(storage_docs["use_ssl"]) > 20

        # Check that documentation explains the purpose
        assert "path" in backup_docs["source_path"].lower()
        assert "s3" in storage_docs["endpoint"].lower()
        assert "ssl" in storage_docs["use_ssl"].lower()

    @pytest.mark.unit
    def test_test_mode_defaults_consistency(self):
        """Test that test mode defaults are internally consistent."""
        # Test mode should use consistent paths
        backup_path = TEST_MODE_DEFAULTS["backup"]["source_path"]
        logging_path = TEST_MODE_DEFAULTS["logging"]["directory"]
        state_path = TEST_MODE_DEFAULTS["state"]["directory"]

        # All should contain test directory
        assert "/tmp/photo-backup-test" in backup_path
        assert "/tmp/photo-backup-test" in logging_path
        assert "/tmp/photo-backup-test" in state_path

        # Test mode should use consistent credentials
        assert TEST_MODE_DEFAULTS["storage"]["access_key"] == "minioadmin"
        assert TEST_MODE_DEFAULTS["storage"]["secret_key"] == "minioadmin"

        # Test mode should have consistent performance settings
        performance = TEST_MODE_DEFAULTS["performance"]
        assert performance["buffer_size_mb"] <= performance["max_memory_usage_mb"]
        assert performance["chunk_size_mb"] <= performance["buffer_size_mb"]
