import logging
from typing import Any

import yaml
from pathlib import Path


class ConfigLoader:
    """Configuration file loading and discovery."""

    def __init__(self, test_mode: bool = False):
        self.test_mode = test_mode
        self._config_file_path: Path | None = None

    # File Discovery
    def get_search_paths(self) -> list[Path]:
        """Get the list of search paths for configuration files.

        Returns:
            List of paths to search for configuration files in order
        """
        search_paths = []

        # Add test mode specific config location first if in test mode
        if self.test_mode:
            test_config_path = Path("/tmp/photo-backup-test/config.yaml")
            search_paths.append(test_config_path)

        # Standard search paths
        search_paths.extend(
            [
                Path.cwd() / "config.yaml",  # Current directory
                Path.home() / ".config" / "photo-backup" / "config.yaml",  # User config
                Path("/etc/photo-backup/config.yaml"),  # System config
            ]
        )

        return search_paths

    def _find_config_file(self) -> Path | None:
        """Find config file in standard locations.

        Returns:
            Path to config file if found, None otherwise
        """
        search_paths = self.get_search_paths()

        for config_path in search_paths:
            if config_path.exists() and config_path.is_file():
                return config_path

        return None

    # File Loading
    def load_config_from_file(self) -> dict[str, Any] | None:
        """Load configuration from YAML file.

        Returns:
            Loaded configuration dict or None if file not found/invalid
        """
        config_path = self._find_config_file()
        if config_path is None:
            logging.info("No configuration file found, using default configuration")
            return None

        try:
            with open(config_path, encoding="utf-8") as f:
                config: dict[str, Any] = yaml.safe_load(f) or {}
                self._config_file_path = config_path
                logging.info(f"Loaded configuration from: {config_path}")
                return config
        except (yaml.YAMLError, OSError) as e:
            logging.error(f"Error loading config file {config_path}: {e}")
            return None
