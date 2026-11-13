"""
Backup job representation.

This module provides the BackupJob class for representing individual
backup operations.
"""


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
        self.error: str | None = None

    def __repr__(self) -> str:
        return f"BackupJob(source='{self.source_path}', dest='{self.destination}', status='{self.status}')"
