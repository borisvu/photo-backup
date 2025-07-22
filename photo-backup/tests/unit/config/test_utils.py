"""
Unit tests for ConfigUtils class.

These tests focus on configuration utility functions.
"""

import pytest

from photo_backup.config.defaults import DEFAULT_CONFIG, TEST_MODE_DEFAULTS
from photo_backup.config.utils import ConfigUtils


class TestConfigUtils:
    """Test cases for ConfigUtils class."""

    @pytest.mark.unit
    def test_merge_dicts_basic(self):
        """Test basic dictionary merging."""
        base = {"a": 1, "b": 2}
        override = {"b": 3, "c": 4}

        result = ConfigUtils.merge_dicts(base, override)

        assert result["a"] == 1
        assert result["b"] == 3  # Overridden
        assert result["c"] == 4  # Added
        assert len(result) == 3

    @pytest.mark.unit
    def test_merge_dicts_nested(self):
        """Test nested dictionary merging."""
        base = {
            "backup": {"source_path": "/default/path", "destination": "default:backup"},
            "storage": {"endpoint": "default.s3.com", "use_ssl": True},
        }

        override = {
            "backup": {
                "source_path": "/custom/path"  # Override nested value
            },
            "monitoring": {
                "check_interval_hours": 4  # Add new section
            },
        }

        result = ConfigUtils.merge_dicts(base, override)

        # Nested value should be overridden
        assert result["backup"]["source_path"] == "/custom/path"
        # Other nested values should be preserved
        assert result["backup"]["destination"] == "default:backup"
        assert result["storage"]["endpoint"] == "default.s3.com"
        # New section should be added
        assert result["monitoring"]["check_interval_hours"] == 4

    @pytest.mark.unit
    def test_merge_dicts_deep_nested(self):
        """Test deeply nested dictionary merging."""
        base = {
            "notifications": {
                "email": {"smtp_server": "default.smtp.com", "smtp_port": 587, "username": "default_user"}
            }
        }

        override = {"notifications": {"email": {"smtp_server": "custom.smtp.com", "password": "custom_password"}}}

        result = ConfigUtils.merge_dicts(base, override)

        # Deep nested value should be overridden
        assert result["notifications"]["email"]["smtp_server"] == "custom.smtp.com"
        # Other deep nested values should be preserved
        assert result["notifications"]["email"]["smtp_port"] == 587
        assert result["notifications"]["email"]["username"] == "default_user"
        # New deep nested value should be added
        assert result["notifications"]["email"]["password"] == "custom_password"

    @pytest.mark.unit
    def test_get_nested_value_simple(self):
        """Test getting simple nested values."""
        utils = ConfigUtils()

        data = {"backup": {"source_path": "/test/path"}}

        value = utils.get_nested_value(data, "backup.source_path")
        assert value == "/test/path"

        value = utils.get_nested_value(data, "backup")
        assert value == {"source_path": "/test/path"}

    @pytest.mark.unit
    def test_get_nested_value_deep(self):
        """Test getting deeply nested values."""
        utils = ConfigUtils()

        data = {
            "notifications": {
                "email": {
                    "smtp_server": "test.smtp.com",
                    "credentials": {"username": "test_user", "password": "test_pass"},
                }
            }
        }

        value = utils.get_nested_value(data, "notifications.email.smtp_server")
        assert value == "test.smtp.com"

        value = utils.get_nested_value(data, "notifications.email.credentials.username")
        assert value == "test_user"

    @pytest.mark.unit
    def test_get_nested_value_missing(self):
        """Test getting missing nested values."""
        utils = ConfigUtils()

        data = {"backup": {"source_path": "/test/path"}}

        # Missing key should return default
        value = utils.get_nested_value(data, "backup.missing", "default_value")
        assert value == "default_value"

        # Missing section should return default
        value = utils.get_nested_value(data, "missing.section", "default_value")
        assert value == "default_value"

        # No default specified should return None
        value = utils.get_nested_value(data, "backup.missing")
        assert value is None

    @pytest.mark.unit
    def test_merge_with_defaults(self):
        """Test merging file config with defaults."""
        utils = ConfigUtils()

        file_config = {
            "backup": {
                "source_path": "/custom/photos"
                # destination not specified, should use default
            },
            "storage": {
                "endpoint": "custom.s3.com"
                # other fields not specified, should use defaults
            },
        }

        merged = utils.merge_with_defaults(file_config, DEFAULT_CONFIG)

        # File config should override defaults
        assert merged["backup"]["source_path"] == "/custom/photos"
        assert merged["storage"]["endpoint"] == "custom.s3.com"

        # Defaults should be preserved for unspecified fields
        assert merged["backup"]["destination"] == "wasabi-photo:my-photo-backup-bucket"
        assert merged["storage"]["access_key"] is None
        assert merged["storage"]["use_ssl"] is True

    @pytest.mark.unit
    def test_apply_test_mode_overrides(self):
        """Test applying test mode overrides to config."""
        utils = ConfigUtils()

        base_config = {
            "backup": {"source_path": "/custom/photos", "destination": "custom:backup"},
            "storage": {
                "endpoint": "custom.s3.com",
                "access_key": "custom_key",
                "secret_key": "custom_secret",
                "use_ssl": True,
            },
        }

        overridden = utils.apply_test_mode_overrides(base_config, TEST_MODE_DEFAULTS)

        # Test mode overrides should take precedence
        assert overridden["backup"]["source_path"] == "/tmp/photo-backup-test-photos"
        assert overridden["storage"]["endpoint"] == "localhost:9000"
        assert overridden["storage"]["access_key"] == "minioadmin"
        assert overridden["storage"]["secret_key"] == "minioadmin"
        assert overridden["storage"]["use_ssl"] is False

    @pytest.mark.unit
    def test_merge_dicts_immutable(self):
        """Test that merge_dicts doesn't modify original dictionaries."""
        base = {"a": 1, "b": {"c": 2}}
        override = {"b": {"d": 3}}

        result = ConfigUtils.merge_dicts(base, override)

        # Original dictionaries should be unchanged
        assert base == {"a": 1, "b": {"c": 2}}
        assert override == {"b": {"d": 3}}

        # Result should be a new dictionary
        assert result is not base
        assert result is not override

    @pytest.mark.unit
    def test_get_nested_value_with_default_config(self):
        """Test getting nested values from default config."""
        utils = ConfigUtils()

        # Test getting values from DEFAULT_CONFIG
        value = utils.get_nested_value(DEFAULT_CONFIG, "backup.source_path")
        assert value == "/Volumes/4TB-SSD/Photo"

        value = utils.get_nested_value(DEFAULT_CONFIG, "storage.endpoint")
        assert value == "s3.wasabisys.com"

        value = utils.get_nested_value(DEFAULT_CONFIG, "monitoring.check_interval_hours")
        assert value == 4
