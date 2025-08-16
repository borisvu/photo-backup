"""
Backup Engine for Photo Backup System

This module provides the core backup functionality for synchronizing photos
to S3-compatible storage (Wasabi in production, Minio in test mode).
"""

import logging
import re
import subprocess
from typing import Any

from .config.config import Config
from .credentials.manager import CredentialManager


def check_rclone() -> tuple[bool, str, str | None]:
    """Check if rclone is installed and get version information.

    Returns:
        Tuple of (is_available, message, version_string)
        - is_available: True if rclone is installed and accessible
        - message: Human-readable status message
        - version_string: Version string if available, None otherwise
    """
    try:
        # Try to run rclone version command
        result = subprocess.run(["rclone", "version"], capture_output=True, text=True, timeout=10.0)

        if result.returncode == 0:
            # Parse version from output
            version_line = result.stdout.split("\n")[0] if result.stdout else ""
            # Extract version number from output like "rclone v1.64.2"
            version_match = re.search(r"rclone v(\d+\.\d+\.\d+)", version_line)
            version = version_match.group(1) if version_match else None

            if version:
                # Check minimum version (require 1.50.0 or higher)
                if _is_version_sufficient(version, "1.50.0"):
                    return True, f"rclone v{version} found (meets minimum requirement v1.50.0)", version
                else:
                    return False, f"rclone v{version} found but is too old (minimum required: v1.50.0)", version
            else:
                return True, "rclone found but version could not be determined", None
        else:
            return False, f"rclone command failed: {result.stderr.strip()}", None

    except FileNotFoundError:
        return False, "rclone not found - please install from https://rclone.org/install/", None
    except subprocess.TimeoutExpired:
        return False, "rclone version check timed out", None
    except Exception as e:
        return False, f"Error checking rclone: {e}", None


def _is_version_sufficient(current_version: str, minimum_version: str) -> bool:
    """Check if current version meets minimum version requirement.

    Args:
        current_version: Version string like "1.64.2"
        minimum_version: Minimum required version string like "1.50.0"

    Returns:
        True if current version >= minimum version
    """
    try:
        current_parts = [int(x) for x in current_version.split(".")]
        minimum_parts = [int(x) for x in minimum_version.split(".")]

        # Pad shorter version with zeros
        while len(current_parts) < len(minimum_parts):
            current_parts.append(0)
        while len(minimum_parts) < len(current_parts):
            minimum_parts.append(0)

        # Compare version parts
        for current, minimum in zip(current_parts, minimum_parts, strict=False):
            if current > minimum:
                return True
            elif current < minimum:
                return False

        return True  # Versions are equal
    except (ValueError, AttributeError):
        # If we can't parse versions, assume it's sufficient
        return True


class BackupJob:
    """Represents a single backup operation."""

    def __init__(self, source_path: str, destination: str, dry_run: bool = False):
        """Initialize a backup job.

        Args:
            source_path: Local path to backup from
            destination: Remote destination (e.g., 'wasabi-photo:bucket')
            dry_run: Whether to run in dry-run mode
        """
        self.source_path = source_path
        self.destination = destination
        self.dry_run = dry_run
        self.status = "pending"
        self.error = None

    def __repr__(self):
        return f"BackupJob(source='{self.source_path}', dest='{self.destination}', status='{self.status}')"


class BackupEngine:
    """Core backup engine for photo synchronization."""

    def __init__(self, config: Config | None = None, test_mode: bool = False):
        """Initialize the backup engine.

        Args:
            config: Configuration object. If None, creates a new one
            test_mode: Whether to run in test mode (uses Minio)
        """
        self.config = config or Config(test_mode=test_mode)
        self.test_mode = test_mode or self.config.is_test_mode()
        self.logger = logging.getLogger(__name__)
        self.credential_manager = CredentialManager(self.config)

        # Load configuration
        self.config.load_config()

        self.logger.info(f"BackupEngine initialized in {'test' if self.test_mode else 'production'} mode")

    def create_backup_job(self) -> BackupJob:
        """Create a backup job from current configuration.

        Returns:
            BackupJob: Configured backup job
        """
        source_path = self.config.get("backup.source_path")
        destination = self.config.get("backup.destination")
        dry_run = self.config.is_dry_run()

        job = BackupJob(source_path, destination, dry_run)

        self.logger.info(f"Created backup job: {job}")
        if dry_run:
            self.logger.info("Backup job is in DRY RUN mode - no actual transfers will occur")

        return job

    def get_backup_info(self) -> dict[str, Any]:
        """Get current backup configuration information.

        Returns:
            Dict containing backup configuration details
        """
        # Get rclone information
        rclone_available, rclone_message, rclone_version = check_rclone()

        return {
            "mode": "test" if self.test_mode else "production",
            "source_path": self.config.get("backup.source_path"),
            "destination": self.config.get("backup.destination"),
            "endpoint": self.config.get("storage.endpoint"),
            "dry_run": self.config.is_dry_run(),
            "credential_status": self.credential_manager.get_credential_status(),
            "rclone_status": {
                "available": rclone_available,
                "message": rclone_message,
                "version": rclone_version,
            },
        }

    def validate_backup_environment(self) -> tuple[bool, list[str]]:
        """Validate that the backup environment is ready.

        Returns:
            Tuple of (is_valid, list_of_errors)
        """
        errors = []

        # Check source path
        source_path = self.config.get("backup.source_path")
        if not source_path:
            errors.append("No source path configured")

        # Check destination
        destination = self.config.get("backup.destination")
        if not destination:
            errors.append("No destination configured")

        # Check rclone availability
        rclone_available, rclone_message, rclone_version = check_rclone()
        if not rclone_available:
            errors.append(f"rclone check failed: {rclone_message}")
        else:
            self.logger.info(f"rclone check passed: {rclone_message}")

        # Check credentials
        try:
            self.credential_manager.get_credentials()
            is_valid, validation_message = self.credential_manager.validate_credentials()
            if not is_valid:
                errors.append(f"Credential validation failed: {validation_message}")
        except Exception as e:
            errors.append(f"Credential validation failed: {e}")

        return len(errors) == 0, errors


# Quick test for the module
if __name__ == "__main__":
    import sys

    # Test rclone detection first
    print("Testing rclone detection...")
    try:
        rclone_available, rclone_message, rclone_version = check_rclone()
        print(f"✓ rclone check: available={rclone_available}, message='{rclone_message}', version={rclone_version}")
    except Exception as e:
        print(f"✗ rclone check failed: {e}")

    # Test basic instantiation
    print("Testing BackupEngine instantiation...")

    try:
        # Test production mode
        engine_prod = BackupEngine(test_mode=False)
        print(f"✓ Production engine created: {engine_prod}")

        # Test test mode
        engine_test = BackupEngine(test_mode=True)
        print(f"✓ Test engine created: {engine_test}")

        # Test backup job creation
        job = engine_test.create_backup_job()
        print(f"✓ Backup job created: {job}")

        # Test backup info (now includes rclone status)
        info = engine_test.get_backup_info()
        print(f"✓ Backup info includes rclone status: {info['rclone_status']}")

        # Test environment validation (now includes rclone check)
        is_valid, errors = engine_test.validate_backup_environment()
        print(f"✓ Environment validation: valid={is_valid}, errors={errors}")

        print("✓ All tests passed!")

    except Exception as e:
        print(f"✗ Test failed: {e}")
        sys.exit(1)
