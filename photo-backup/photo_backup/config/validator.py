import os
from typing import Any

from pathlib import Path


class ConfigValidator:
    """Configuration validation logic."""

    def __init__(self, test_mode=False):
        self.test_mode = test_mode

    def validate_config(self, config: dict[str, Any]) -> tuple[bool, list[str]]:
        """Comprehensive configuration validation.

        Args:
            config: Configuration dictionary to validate

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        # Basic schema validation
        errors.extend(self._validate_config_schema(config))

        # Path validation (collect all path errors)
        errors.extend(self._validate_paths(config))

        # Numeric range validation (collect all numeric errors)
        errors.extend(self._validate_numeric_ranges(config))

        # Test mode specific validation
        if self.test_mode:
            errors.extend(self._validate_test_mode_paths(config))

        return len(errors) == 0, errors

    def _validate_config_schema(self, config: dict[str, Any]) -> list[str]:
        """Basic schema validation for loaded config.

        Args:
            config: Configuration dictionary to validate

        Returns:
            List of validation errors
        """
        errors = []

        # Check required top-level sections
        required_sections = ["backup", "storage", "monitoring", "logging", "state"]
        for section in required_sections:
            if section not in config:
                errors.append(f"Missing required section: {section}")
            elif not isinstance(config[section], dict):
                errors.append(f"Section {section} must be a dictionary")

        # Validate backup section
        if "backup" in config and isinstance(config["backup"], dict):
            backup = config["backup"]
            if "source_path" not in backup:
                errors.append("backup.source_path is required")
            elif not isinstance(backup["source_path"], str):
                errors.append("backup.source_path must be a string")

            if "destination" not in backup:
                errors.append("backup.destination is required")
            elif not isinstance(backup["destination"], str):
                errors.append("backup.destination must be a string")

        # Validate storage section
        if "storage" in config and isinstance(config["storage"], dict):
            storage = config["storage"]
            if "endpoint" not in storage:
                errors.append("storage.endpoint is required")
            elif not isinstance(storage["endpoint"], str):
                errors.append("storage.endpoint must be a string")

            if "access_key" in storage and not isinstance(storage["access_key"], str | type(None)):
                errors.append("storage.access_key must be a string or null")

            if "secret_key" in storage and not isinstance(storage["secret_key"], str | type(None)):
                errors.append("storage.secret_key must be a string or null")

            if "use_ssl" in storage and not isinstance(storage["use_ssl"], bool):
                errors.append("storage.use_ssl must be a boolean")

        # Validate monitoring section
        if "monitoring" in config and isinstance(config["monitoring"], dict):
            monitoring = config["monitoring"]
            for key in ["check_interval_hours", "mount_delay_minutes", "change_delay_minutes"]:
                if key in monitoring and not isinstance(monitoring[key], int | float):
                    errors.append(f"monitoring.{key} must be a number")

        # Validate logging section
        if "logging" in config and isinstance(config["logging"], dict):
            logging_config = config["logging"]
            if "level" in logging_config and not isinstance(logging_config["level"], str):
                errors.append("logging.level must be a string")

            if "directory" in logging_config and not isinstance(logging_config["directory"], str):
                errors.append("logging.directory must be a string")

        # Validate state section
        if "state" in config and isinstance(config["state"], dict):
            state = config["state"]
            if "directory" in state and not isinstance(state["directory"], str):
                errors.append("state.directory must be a string")

        return errors

    def _validate_paths(self, config: dict[str, Any]) -> list[str]:
        """Validate that paths are absolute and accessible.

        Args:
            config: Configuration dictionary to validate

        Returns:
            List of validation errors
        """
        errors = []

        # Validate backup source path
        if "backup" in config and isinstance(config["backup"], dict):
            backup = config["backup"]
            if "source_path" in backup and isinstance(backup["source_path"], str):
                source_path = backup["source_path"]

                # Check if original path is absolute (before expansion)
                if not os.path.isabs(source_path):
                    errors.append("backup.source_path must be an absolute path")
                else:
                    # Expand the path
                    expanded_path = self._expand_path(source_path)

                    # In test mode, skip existence checks for paths
                    if not self.test_mode:
                        # Check if path exists and is accessible
                        try:
                            path_obj = Path(expanded_path)
                            if not path_obj.exists():
                                errors.append(f"backup.source_path does not exist: {expanded_path}")
                            elif not path_obj.is_dir():
                                errors.append(f"backup.source_path must be a directory: {expanded_path}")
                            elif not os.access(expanded_path, os.R_OK):
                                errors.append(f"backup.source_path is not readable: {expanded_path}")
                        except Exception as e:
                            errors.append(f"backup.source_path validation error: {e}")

        # Validate logging directory
        if "logging" in config and isinstance(config["logging"], dict):
            logging_config = config["logging"]
            if "directory" in logging_config and isinstance(logging_config["directory"], str):
                log_dir = logging_config["directory"]
                expanded_path = self._expand_path(log_dir)

                # In test mode, skip existence checks for paths
                if not self.test_mode:
                    # For logging directory, we'll create it if it doesn't exist
                    # But we need to check if the parent directory is writable
                    try:
                        path_obj = Path(expanded_path)
                        if path_obj.exists() and not path_obj.is_dir():
                            errors.append(f"logging.directory must be a directory: {expanded_path}")
                        elif path_obj.exists() and not os.access(expanded_path, os.W_OK):
                            errors.append(f"logging.directory is not writable: {expanded_path}")
                        elif not path_obj.exists():
                            # Check if parent directory is writable
                            parent = path_obj.parent
                            if not parent.exists():
                                errors.append(f"logging.directory parent does not exist: {parent}")
                            elif not os.access(parent, os.W_OK):
                                errors.append(f"logging.directory parent is not writable: {parent}")
                    except Exception as e:
                        errors.append(f"logging.directory validation error: {e}")

        # Validate state directory
        if "state" in config and isinstance(config["state"], dict):
            state = config["state"]
            if "directory" in state and isinstance(state["directory"], str):
                state_dir = state["directory"]
                expanded_path = self._expand_path(state_dir)

                # In test mode, skip existence checks for paths
                if not self.test_mode:
                    # For state directory, we'll create it if it doesn't exist
                    # But we need to check if the parent directory is writable
                    try:
                        path_obj = Path(expanded_path)
                        if path_obj.exists() and not path_obj.is_dir():
                            errors.append(f"state.directory must be a directory: {expanded_path}")
                        elif path_obj.exists() and not os.access(expanded_path, os.W_OK):
                            errors.append(f"state.directory is not writable: {expanded_path}")
                        elif not path_obj.exists():
                            # Check if parent directory is writable
                            parent = path_obj.parent
                            if not parent.exists():
                                errors.append(f"state.directory parent does not exist: {parent}")
                            elif not os.access(parent, os.W_OK):
                                errors.append(f"state.directory parent is not writable: {parent}")
                    except Exception as e:
                        errors.append(f"state.directory validation error: {e}")

        return errors

    def _validate_numeric_ranges(self, config: dict[str, Any]) -> list[str]:
        """Validate numeric values are within acceptable ranges.

        Args:
            config: Configuration dictionary to validate

        Returns:
            List of validation errors
        """
        errors: list[str] = []

        # Validate monitoring section
        if "monitoring" in config and isinstance(config["monitoring"], dict):
            monitoring = config["monitoring"]

            # Check interval hours: 0.1 to 24
            if "check_interval_hours" in monitoring:
                value = monitoring["check_interval_hours"]
                if isinstance(value, int | float):
                    if value < 0.1 or value > 24:
                        errors.append("monitoring.check_interval_hours must be between 0.1 and 24 hours")
                else:
                    errors.append("monitoring.check_interval_hours must be a number")

            # Mount delay minutes: 1 to 60
            if "mount_delay_minutes" in monitoring:
                value = monitoring["mount_delay_minutes"]
                if isinstance(value, int | float):
                    if value < 1 or value > 60:
                        errors.append("monitoring.mount_delay_minutes must be between 1 and 60 minutes")
                else:
                    errors.append("monitoring.mount_delay_minutes must be a number")

            # Change delay minutes: 1 to 120
            if "change_delay_minutes" in monitoring:
                value = monitoring["change_delay_minutes"]
                if isinstance(value, int | float):
                    if value < 1 or value > 120:
                        errors.append("monitoring.change_delay_minutes must be between 1 and 120 minutes")
                else:
                    errors.append("monitoring.change_delay_minutes must be a number")

        # Validate logging section
        if "logging" in config and isinstance(config["logging"], dict):
            logging_config = config["logging"]

            # Max size MB: 1 to 1000
            if "max_size_mb" in logging_config:
                value = logging_config["max_size_mb"]
                if isinstance(value, int | float):
                    if value < 1 or value > 1000:
                        errors.append("logging.max_size_mb must be between 1 and 1000 MB")
                else:
                    errors.append("logging.max_size_mb must be a number")

            # Backup count: 1 to 50
            if "backup_count" in logging_config:
                value = logging_config["backup_count"]
                if isinstance(value, int):
                    if value < 1 or value > 50:
                        errors.append("logging.backup_count must be between 1 and 50")
                else:
                    errors.append("logging.backup_count must be an integer")

        return errors

    def _validate_test_mode_paths(self, config: dict[str, Any]) -> list[str]:
        """Validate paths are appropriate for test mode.

        Args:
            config: Configuration dictionary to validate

        Returns:
            List of validation errors
        """
        errors: list[str] = []

        # In test mode, we're more lenient with paths
        # Allow any path, but warn about non-test paths
        if "backup" in config and isinstance(config["backup"], dict):
            backup = config["backup"]
            if "source_path" in backup and isinstance(backup["source_path"], str):
                source_path = backup["source_path"]
                expanded_path = self._expand_path(source_path)

                # In test mode, we allow any path but prefer test directories
                if not any(test_dir in expanded_path for test_dir in ["/tmp", "test", "temp"]):
                    # This is just a warning, not an error in test mode
                    pass  # Could add a warning here if desired

        return errors

    def _expand_path(self, path: str) -> str:
        """Expand relative paths and environment variables.

        Args:
            path: Path string to expand

        Returns:
            Expanded absolute path
        """
        # Expand environment variables
        expanded = os.path.expandvars(path)
        # Expand user home directory
        expanded = os.path.expanduser(expanded)
        # Convert to absolute path
        return os.path.abspath(expanded)
