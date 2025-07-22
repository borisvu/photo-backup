"""
Unit tests for ConfigValidator class.

These tests focus on configuration validation logic.
"""

import os
from unittest.mock import patch

import pytest
from pathlib import Path

from photo_backup.config.validator import ConfigValidator


class TestConfigSchemaValidation:
    """Test cases for config schema validation."""

    @pytest.mark.unit
    def test_validate_config_schema_valid(self):
        """Test schema validation with valid config."""
        validator = ConfigValidator()
        valid_config = {
            "backup": {"source_path": "/Volumes/4TB-SSD/Photo", "destination": "wasabi-photo:my-photo-backup-bucket"},
            "storage": {"endpoint": "s3.wasabisys.com", "access_key": None, "secret_key": None, "use_ssl": True},
            "monitoring": {"check_interval_hours": 4, "mount_delay_minutes": 15, "change_delay_minutes": 30},
            "logging": {"level": "INFO", "directory": "~/Library/Logs/photo-backup"},
            "state": {"directory": "~/Library/Application Support/photo-backup"},
        }

        errors = validator._validate_config_schema(valid_config)
        assert len(errors) == 0

    @pytest.mark.unit
    def test_validate_config_schema_missing_sections(self):
        """Test schema validation with missing required sections."""
        validator = ConfigValidator()
        invalid_config = {
            "backup": {"source_path": "/Volumes/4TB-SSD/Photo", "destination": "wasabi-photo:my-photo-backup-bucket"}
            # Missing storage, monitoring, logging, state sections
        }

        errors = validator._validate_config_schema(invalid_config)
        assert len(errors) == 4
        assert any("Missing required section: storage" in error for error in errors)
        assert any("Missing required section: monitoring" in error for error in errors)
        assert any("Missing required section: logging" in error for error in errors)
        assert any("Missing required section: state" in error for error in errors)

    @pytest.mark.unit
    def test_validate_config_schema_missing_backup_fields(self):
        """Test schema validation with missing backup fields."""
        validator = ConfigValidator()
        invalid_config = {
            "backup": {
                # Missing source_path and destination
            },
            "storage": {"endpoint": "s3.wasabisys.com", "access_key": None, "secret_key": None, "use_ssl": True},
            "monitoring": {"check_interval_hours": 4, "mount_delay_minutes": 15, "change_delay_minutes": 30},
            "logging": {"level": "INFO", "directory": "~/Library/Logs/photo-backup"},
            "state": {"directory": "~/Library/Application Support/photo-backup"},
        }

        errors = validator._validate_config_schema(invalid_config)
        assert len(errors) == 2
        assert any("backup.source_path is required" in error for error in errors)
        assert any("backup.destination is required" in error for error in errors)

    @pytest.mark.unit
    def test_validate_config_schema_invalid_types(self):
        """Test schema validation with invalid data types."""
        validator = ConfigValidator()
        invalid_config = {
            "backup": {
                "source_path": 123,  # Should be string
                "destination": "wasabi-photo:my-photo-backup-bucket",
            },
            "storage": {
                "endpoint": "s3.wasabisys.com",
                "access_key": "not_none",  # Should be None or string
                "secret_key": None,
                "use_ssl": "not_boolean",  # Should be boolean
            },
            "monitoring": {
                "check_interval_hours": "not_number",  # Should be number
                "mount_delay_minutes": 15,
                "change_delay_minutes": 30,
            },
            "logging": {
                "level": 123,  # Should be string
                "directory": "~/Library/Logs/photo-backup",
            },
            "state": {"directory": "~/Library/Application Support/photo-backup"},
        }

        errors = validator._validate_config_schema(invalid_config)
        assert len(errors) > 0
        assert any("backup.source_path must be a string" in error for error in errors)
        assert any("storage.use_ssl must be a boolean" in error for error in errors)
        assert any("monitoring.check_interval_hours must be a number" in error for error in errors)
        assert any("logging.level must be a string" in error for error in errors)

    @pytest.mark.unit
    def test_validate_config_schema_null_credentials_allowed(self):
        """Test that null credentials are allowed in storage section."""
        validator = ConfigValidator()
        valid_config = {
            "backup": {"source_path": "/Volumes/4TB-SSD/Photo", "destination": "wasabi-photo:my-photo-backup-bucket"},
            "storage": {
                "endpoint": "s3.wasabisys.com",
                "access_key": None,  # Should be allowed
                "secret_key": None,  # Should be allowed
                "use_ssl": True,
            },
            "monitoring": {"check_interval_hours": 4, "mount_delay_minutes": 15, "change_delay_minutes": 30},
            "logging": {"level": "INFO", "directory": "~/Library/Logs/photo-backup"},
            "state": {"directory": "~/Library/Application Support/photo-backup"},
        }

        errors = validator._validate_config_schema(valid_config)
        assert len(errors) == 0


class TestConfigPathValidation:
    """Test cases for path validation."""

    @pytest.mark.unit
    def test_validate_paths_valid_absolute_paths(self):
        """Test path validation with valid absolute paths."""
        validator = ConfigValidator()
        valid_config = {
            "backup": {"source_path": "/Volumes/4TB-SSD/Photo"},
            "logging": {"directory": "~/Library/Logs/photo-backup"},
            "state": {"directory": "~/Library/Application Support/photo-backup"},
        }

        with (
            patch("os.path.isabs", return_value=True),
            patch("os.access", return_value=True),
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "is_dir", return_value=True),
        ):
            errors = validator._validate_paths(valid_config)
            assert len(errors) == 0

    @pytest.mark.unit
    def test_validate_paths_relative_path_error(self):
        """Test path validation with relative path error."""
        validator = ConfigValidator()
        invalid_config = {
            "backup": {
                "source_path": "relative/path"  # Should be absolute
            }
        }

        with patch("os.path.isabs", return_value=False):
            errors = validator._validate_paths(invalid_config)
            assert len(errors) == 1
            assert any("backup.source_path must be an absolute path" in error for error in errors)

    @pytest.mark.unit
    def test_validate_paths_nonexistent_path_error(self):
        """Test path validation with nonexistent path error."""
        validator = ConfigValidator()
        invalid_config = {"backup": {"source_path": "/nonexistent/path"}}

        with (
            patch("os.path.isabs", return_value=True),
            patch.object(Path, "exists", return_value=False),
        ):
            errors = validator._validate_paths(invalid_config)
            assert len(errors) == 1
            assert any("backup.source_path does not exist" in error for error in errors)

    @pytest.mark.unit
    def test_validate_paths_not_directory_error(self):
        """Test path validation with non-directory error."""
        validator = ConfigValidator()
        invalid_config = {
            "backup": {
                "source_path": "/path/to/file.txt"  # Should be directory
            }
        }

        with (
            patch("os.path.isabs", return_value=True),
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "is_dir", return_value=False),
        ):
            errors = validator._validate_paths(invalid_config)
            assert len(errors) == 1
            assert any("backup.source_path must be a directory" in error for error in errors)

    @pytest.mark.unit
    def test_validate_paths_not_readable_error(self):
        """Test path validation with non-readable path error."""
        validator = ConfigValidator()
        invalid_config = {"backup": {"source_path": "/unreadable/path"}}

        with (
            patch("os.path.isabs", return_value=True),
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "is_dir", return_value=True),
            patch("os.access", return_value=False),
        ):
            errors = validator._validate_paths(invalid_config)
            assert len(errors) == 1
            assert any("backup.source_path is not readable" in error for error in errors)

    @pytest.mark.unit
    def test_expand_path(self):
        """Test path expansion functionality."""
        validator = ConfigValidator()

        # Test environment variable expansion
        with patch.dict(os.environ, {"TEST_PATH": "/test/path"}):
            expanded = validator._expand_path("$TEST_PATH/subdir")
            assert expanded == "/test/path/subdir"

        # Test home directory expansion
        with patch("os.path.expanduser", return_value="/home/user/documents"):
            expanded = validator._expand_path("~/documents")
            assert expanded == "/home/user/documents"

        # Test absolute path conversion
        with patch("os.path.abspath", return_value="/absolute/path"):
            expanded = validator._expand_path("relative/path")
            assert expanded == "/absolute/path"


class TestConfigNumericValidation:
    """Test cases for numeric range validation."""

    @pytest.mark.unit
    def test_validate_numeric_ranges_valid(self):
        """Test numeric validation with valid ranges."""
        validator = ConfigValidator()
        valid_config = {
            "monitoring": {
                "check_interval_hours": 4,  # 0.1-24
                "mount_delay_minutes": 15,  # 1-60
                "change_delay_minutes": 30,  # 1-120
            },
            "logging": {
                "max_size_mb": 100,  # 1-1000
                "backup_count": 5,  # 1-50
            },
        }

        errors = validator._validate_numeric_ranges(valid_config)
        assert len(errors) == 0

    @pytest.mark.unit
    def test_validate_numeric_ranges_check_interval_too_low(self):
        """Test numeric validation with check_interval_hours too low."""
        validator = ConfigValidator()
        invalid_config = {
            "monitoring": {
                "check_interval_hours": 0.05,  # Below 0.1
                "mount_delay_minutes": 15,
                "change_delay_minutes": 30,
            }
        }

        errors = validator._validate_numeric_ranges(invalid_config)
        assert len(errors) == 1
        assert any("check_interval_hours must be between 0.1 and 24 hours" in error for error in errors)

    @pytest.mark.unit
    def test_validate_numeric_ranges_check_interval_too_high(self):
        """Test numeric validation with check_interval_hours too high."""
        validator = ConfigValidator()
        invalid_config = {
            "monitoring": {
                "check_interval_hours": 25,  # Above 24
                "mount_delay_minutes": 15,
                "change_delay_minutes": 30,
            }
        }

        errors = validator._validate_numeric_ranges(invalid_config)
        assert len(errors) == 1
        assert any("check_interval_hours must be between 0.1 and 24 hours" in error for error in errors)

    @pytest.mark.unit
    def test_validate_numeric_ranges_mount_delay_too_low(self):
        """Test numeric validation with mount_delay_minutes too low."""
        validator = ConfigValidator()
        invalid_config = {
            "monitoring": {
                "check_interval_hours": 4,
                "mount_delay_minutes": 0,  # Below 1
                "change_delay_minutes": 30,
            }
        }

        errors = validator._validate_numeric_ranges(invalid_config)
        assert len(errors) == 1
        assert any("mount_delay_minutes must be between 1 and 60 minutes" in error for error in errors)

    @pytest.mark.unit
    def test_validate_numeric_ranges_max_size_mb_too_high(self):
        """Test numeric validation with max_size_mb too high."""
        validator = ConfigValidator()
        invalid_config = {
            "logging": {
                "max_size_mb": 1500,  # Above 1000
                "backup_count": 5,
            }
        }

        errors = validator._validate_numeric_ranges(invalid_config)
        assert len(errors) == 1
        assert any("max_size_mb must be between 1 and 1000 MB" in error for error in errors)

    @pytest.mark.unit
    def test_validate_numeric_ranges_backup_count_not_integer(self):
        """Test numeric validation with backup_count not an integer."""
        validator = ConfigValidator()
        invalid_config = {
            "logging": {
                "max_size_mb": 100,
                "backup_count": 5.5,  # Should be integer
            }
        }

        errors = validator._validate_numeric_ranges(invalid_config)
        assert len(errors) == 1
        assert any("backup_count must be an integer" in error for error in errors)
