"""
Backup Engine for Photo Backup System

This module provides the core backup functionality for synchronizing photos
to S3-compatible storage (Wasabi in production, Minio in test mode).
"""

import logging
from typing import Any

from .config.config import Config
from .credentials.manager import CredentialManager


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
        return {
            "mode": "test" if self.test_mode else "production",
            "source_path": self.config.get("backup.source_path"),
            "destination": self.config.get("backup.destination"),
            "endpoint": self.config.get("storage.endpoint"),
            "dry_run": self.config.is_dry_run(),
            "credential_status": self.credential_manager.get_credential_status(),
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

        # Test backup info
        info = engine_test.get_backup_info()
        print(f"✓ Backup info: {info}")

        # Test environment validation (may fail without Minio)
        is_valid, errors = engine_test.validate_backup_environment()
        print(f"✓ Environment validation: valid={is_valid}, errors={errors}")

        print("✓ All basic tests passed!")

    except Exception as e:
        print(f"✗ Test failed: {e}")
        sys.exit(1)
