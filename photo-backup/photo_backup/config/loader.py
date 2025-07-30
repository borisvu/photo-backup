import logging
import shutil
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

    def create_user_config_directory(self) -> tuple[bool, str]:
        """Create user config directory and copy example config if needed.
        
        Returns:
            tuple: (success: bool, message: str)
        """
        try:
            if self.test_mode:
                # In test mode, use temporary directory
                config_dir = Path("/tmp/photo-backup-test")
                config_file = config_dir / "config.yaml"
            else:
                # In production mode, use user config directory
                config_dir = Path.home() / ".config" / "photo-backup"
                config_file = config_dir / "config.yaml"
            
            # Create config directory if it doesn't exist
            if not config_dir.exists():
                config_dir.mkdir(parents=True, exist_ok=True)
                # Set directory permissions to 700 (user read/write/execute only)
                config_dir.chmod(0o700)
            
            # Copy example config if config file doesn't exist
            if not config_file.exists():
                # Find example config file
                example_config_paths = [
                    Path.cwd() / "config.yaml.example",  # Current directory
                    Path(__file__).parent.parent.parent / "config.yaml.example",  # Package directory
                ]
                
                example_config_path = None
                for path in example_config_paths:
                    if path.exists():
                        example_config_path = path
                        break
                
                if example_config_path:
                    # Copy example config to user config location
                    shutil.copy2(example_config_path, config_file)
                    # Set file permissions to 600 (user read/write only)
                    config_file.chmod(0o600)
                    return True, f"Created config directory and copied example config to {config_file}"
                else:
                    # Create a minimal config file if example doesn't exist
                    minimal_config = {
                        "backup": {
                            "source_path": "~/Photos",
                            "destination": "wasabi:your-bucket-name"
                        },
                        "storage": {
                            "endpoint": "s3.wasabisys.com",
                            "access_key": "your-access-key",
                            "secret_key": "your-secret-key"
                        }
                    }
                    
                    with open(config_file, 'w') as f:
                        yaml.dump(minimal_config, f, default_flow_style=False, indent=2)
                    
                    config_file.chmod(0o600)
                    return True, f"Created config directory and minimal config file at {config_file}"
            else:
                return True, f"Config directory already exists at {config_dir}"
                
        except Exception as e:
            return False, f"Failed to create user config directory: {str(e)}"

    def _load_config_from_file(self, config_path: Path) -> dict[str, Any] | None:
        """Load configuration from a specific file.

        Args:
            config_path: Path to config file

        Returns:
            Configuration dictionary or None if loading fails
        """
        try:
            with open(config_path, encoding="utf-8") as f:
                config = yaml.safe_load(f)

            if config is None:
                logging.warning(f"Config file {config_path} is empty")
                return None

            self._config_file_path = config_path
            logging.info(f"Loaded configuration from {config_path}")
            return config

        except Exception as e:
            logging.error(f"Failed to load config from {config_path}: {e}")
            return None

    def load_config_from_file(self) -> dict[str, Any] | None:
        """Load configuration from file.

        Returns:
            Configuration dictionary or None if no valid config found
        """
        config_path = self._find_config_file()

        if config_path is None:
            logging.info("No configuration file found, using defaults")
            return None

        return self._load_config_from_file(config_path)

    def get_config_file_path(self) -> Path | None:
        """Get the path of the loaded config file.

        Returns:
            Path to config file or None if no file was loaded
        """
        return self._config_file_path
