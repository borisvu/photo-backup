"""
Backup Engine for Photo Backup System

This module provides the core backup functionality for synchronizing photos
to S3-compatible storage (Wasabi in production, Minio in test mode).
"""

import logging
import os
import re
import subprocess
import tempfile
import time
from typing import Any

from pathlib import Path

from .config.config import Config
from .credentials.manager import CredentialManager
from .progress_parser import RcloneProgressParser


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
        self.error: str | None = None

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

    def build_sync_command(self, job: BackupJob) -> list[str]:
        """Build rclone sync command with all parameters.

        Args:
            job: BackupJob containing source, destination, and options

        Returns:
            List of command arguments for rclone sync
        """
        # Base rclone sync command
        cmd = ["rclone", "sync"]

        # Add source path
        cmd.append(job.source_path)

        # Add destination with proper remote name
        # Always use 'test' as remote name (matches rclone config section)
        destination_parts = job.destination.split(":", 1)
        if len(destination_parts) == 2:
            bucket_path = destination_parts[1]
            cmd.append(f"test:{bucket_path}")
        else:
            cmd.append(f"test:{job.destination}")

        # Add performance and reliability options
        cmd.extend(
            [
                "--transfers",
                str(self.config.get("rclone.transfers", 8)),
                "--checkers",
                str(self.config.get("rclone.checkers", 16)),
                "--s3-chunk-size",
                str(self.config.get("rclone.s3_chunk_size", "10M")),
                "--s3-upload-concurrency",
                str(self.config.get("rclone.s3_upload_concurrency", 4)),
            ]
        )

        # Add progress and verbosity options
        cmd.extend(
            [
                "--progress",
                "--stats",
                "1s",
                "--verbose" if self.test_mode else "--quiet",
            ]
        )

        # Add backup-specific options
        cmd.extend(
            [
                "--checksum",  # Use checksums for file comparison
                "--create-empty-src-dirs",  # Create empty directories on destination
                "--exclude",
                ".*",  # Exclude hidden files
                "--exclude",
                "Thumbs.db",  # Exclude Windows thumbnails
                "--exclude",
                ".DS_Store",  # Exclude macOS metadata
            ]
        )

        # Add dry-run option if enabled
        if job.dry_run:
            cmd.append("--dry-run")

        # Add config file option (will be set when executing)
        # This is a placeholder - actual config file path will be added during execution
        cmd.extend(["--config", "RCLONE_CONFIG_PATH"])

        self.logger.info(f"Built rclone command: {' '.join(cmd[:5])}... ({len(cmd)} total args)")
        if job.dry_run:
            self.logger.info("Command includes --dry-run flag")

        return cmd

    def _build_rclone_config(self) -> str:
        """Build rclone configuration content for sync operations.

        Returns:
            rclone configuration content as string
        """
        credentials = self.credential_manager.get_credentials()

        # Ensure endpoint has proper scheme
        endpoint = credentials["endpoint"]
        if not endpoint.startswith(("http://", "https://")):
            endpoint = f"https://{endpoint}" if credentials["use_ssl"] else f"http://{endpoint}"

        # Use 'test' as remote name for both test and production modes
        # This matches the pattern used in credential validation
        config = f"""[test]
type = s3
provider = Other
access_key_id = {credentials["access_key"]}
secret_access_key = {credentials["secret_key"]}
endpoint = {endpoint}
region = {credentials["region"]}
use_ssl = {str(credentials["use_ssl"]).lower()}
"""
        return config

    def sync(self, job: BackupJob) -> tuple[bool, str, dict[str, Any]]:
        """Execute rclone sync operation.

        Args:
            job: BackupJob containing sync parameters

        Returns:
            Tuple of (success, output, sync_info)
            - success: True if sync completed successfully
            - output: Complete rclone output (stdout + stderr)
            - sync_info: Dictionary with sync statistics and metadata
        """
        self.logger.info(f"Starting sync: {job.source_path} -> {job.destination}")

        # Build the sync command
        cmd = self.build_sync_command(job)

        # Create temporary config file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".conf", delete=False) as config_file:
            config_content = self._build_rclone_config()
            config_file.write(config_content)
            config_file.flush()

            # Update command to use the config file
            for i, arg in enumerate(cmd):
                if arg == "--config" and i + 1 < len(cmd):
                    cmd[i + 1] = config_file.name
                    break

            try:
                # Record start time
                start_time = time.time()

                # Execute rclone command
                self.logger.info(f"Executing: {' '.join(cmd[:3])} ... (config file: {config_file.name})")

                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=300.0,  # 5 minute timeout
                )

                # Record completion time
                end_time = time.time()
                duration = end_time - start_time

                # Combine stdout and stderr for complete output
                complete_output = f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"

                # Build sync info
                sync_info = {
                    "command": cmd,
                    "return_code": result.returncode,
                    "duration_seconds": duration,
                    "start_time": start_time,
                    "end_time": end_time,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "config_file": config_file.name,
                    "dry_run": job.dry_run,
                    "test_mode": self.test_mode,
                }

                # Determine success
                success = result.returncode == 0

                if success:
                    self.logger.info(f"Sync completed successfully in {duration:.2f}s")
                    if job.dry_run:
                        self.logger.info("Dry run completed - no files were actually transferred")
                else:
                    self.logger.error(f"Sync failed with return code {result.returncode}")
                    self.logger.error(f"Error output: {result.stderr}")

                # Update job status
                job.status = "completed" if success else "error"
                if not success:
                    job.error = result.stderr

                return success, complete_output, sync_info

            except subprocess.TimeoutExpired:
                self.logger.error("Sync operation timed out after 5 minutes")
                job.status = "error"
                job.error = "Sync operation timed out"

                sync_info = {
                    "command": cmd,
                    "return_code": -1,
                    "duration_seconds": 300.0,
                    "error": "Timeout",
                    "config_file": config_file.name,
                    "dry_run": job.dry_run,
                    "test_mode": self.test_mode,
                }

                return False, "ERROR: Sync operation timed out after 5 minutes", sync_info

            except Exception as e:
                self.logger.error(f"Sync failed with exception: {e}")
                job.status = "error"
                job.error = str(e)

                sync_info = {
                    "command": cmd,
                    "return_code": -1,
                    "error": str(e),
                    "config_file": config_file.name,
                    "dry_run": job.dry_run,
                    "test_mode": self.test_mode,
                }

                return False, f"ERROR: {e}", sync_info

            finally:
                # Clean up temporary config file
                try:
                    os.unlink(config_file.name)
                    self.logger.debug(f"Cleaned up config file: {config_file.name}")
                except Exception as e:
                    self.logger.warning(f"Failed to clean up config file {config_file.name}: {e}")

    def sync_with_progress(self, job: BackupJob) -> tuple[bool, str, dict[str, Any]]:
        """Execute rclone sync operation with real-time progress parsing.

        This method enhances the basic sync with real-time progress monitoring,
        transfer statistics, and progress events.

        Args:
            job: BackupJob containing sync parameters

        Returns:
            Tuple of (success, output, sync_info)
            - success: True if sync completed successfully
            - output: Complete rclone output
            - sync_info: Dictionary with sync statistics and metadata including transfer_stats
        """
        self.logger.info(f"Starting sync with progress: {job.source_path} -> {job.destination}")

        # Initialize progress parser
        progress_parser = RcloneProgressParser(self.logger)

        # Estimate total files for progress tracking
        total_files = 0
        try:
            source_path = Path(job.source_path)
            if source_path.exists():
                total_files = len([f for f in source_path.rglob("*") if f.is_file()])
                if total_files > 0:
                    progress_parser.init_progress_logger(total_files, "backup")
                    self.logger.info(f"Estimated {total_files} files to sync")
        except Exception as e:
            self.logger.debug(f"Could not estimate file count: {e}")

        # Build the sync command
        cmd = self.build_sync_command(job)

        # Create temporary config file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".conf", delete=False) as config_file:
            config_content = self._build_rclone_config()
            config_file.write(config_content)
            config_file.flush()

            # Update command to use the config file
            for i, arg in enumerate(cmd):
                if arg == "--config" and i + 1 < len(cmd):
                    cmd[i + 1] = config_file.name
                    break

            try:
                # Record start time
                start_time = time.time()

                # Execute rclone command with real-time output parsing
                self.logger.info(f"Executing: {' '.join(cmd[:3])} ... (config file: {config_file.name})")

                # Use Popen for real-time output processing
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,  # Combine stderr into stdout
                    text=True,
                    bufsize=1,  # Line buffered
                    universal_newlines=True,
                )

                # Capture output while parsing progress
                output_lines = []

                try:
                    # Process output line by line in real-time
                    if process.stdout:
                        for line in iter(process.stdout.readline, ""):
                            if line:
                                output_lines.append(line.rstrip())
                                # Parse progress from this line
                                progress_parser.parse_line(line)

                    # Wait for process to complete
                    return_code = process.wait(timeout=300.0)  # 5 minute timeout

                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                    raise

                # Record completion time
                end_time = time.time()
                duration = end_time - start_time

                # Mark progress as complete
                progress_parser.complete()

                # Combine all output
                complete_output = "\n".join(output_lines)

                # Get final transfer statistics
                transfer_stats = progress_parser.get_final_stats()

                # Build sync info with progress statistics
                sync_info = {
                    "command": cmd,
                    "return_code": return_code,
                    "duration_seconds": duration,
                    "start_time": start_time,
                    "end_time": end_time,
                    "stdout": complete_output,
                    "stderr": "",  # Combined with stdout
                    "config_file": config_file.name,
                    "dry_run": job.dry_run,
                    "test_mode": self.test_mode,
                    "transfer_stats": {
                        "files_transferred": transfer_stats.files_transferred,
                        "files_total": transfer_stats.files_total,
                        "bytes_transferred": transfer_stats.bytes_transferred,
                        "bytes_total": transfer_stats.bytes_total,
                        "transfer_rate_mbps": transfer_stats.transfer_rate_mbps,
                        "percentage": transfer_stats.percentage,
                        "errors": transfer_stats.errors,
                    },
                }

                # Determine success
                success = return_code == 0

                if success:
                    self.logger.info(f"Sync completed successfully in {duration:.2f}s")
                    self.logger.info(
                        f"Transferred {transfer_stats.files_transferred} files ({transfer_stats.bytes_transferred / (1024 * 1024):.1f} MB)"
                    )
                    if transfer_stats.transfer_rate_mbps > 0:
                        self.logger.info(f"Average transfer rate: {transfer_stats.transfer_rate_mbps:.1f} MB/s")
                    if job.dry_run:
                        self.logger.info("Dry run completed - no files were actually transferred")
                else:
                    self.logger.error(f"Sync failed with return code {return_code}")
                    # Log last few lines of output as error details
                    error_lines = output_lines[-5:] if output_lines else ["No output captured"]
                    self.logger.error(f"Error details: {'; '.join(error_lines)}")

                # Update job status
                job.status = "completed" if success else "error"
                if not success:
                    job.error = "; ".join(output_lines[-3:]) if output_lines else "Unknown error"

                return success, complete_output, sync_info

            except subprocess.TimeoutExpired:
                self.logger.error("Sync operation timed out after 5 minutes")
                job.status = "error"
                job.error = "Sync operation timed out"

                sync_info = {
                    "command": cmd,
                    "return_code": -1,
                    "duration_seconds": 300.0,
                    "error": "Timeout",
                    "config_file": config_file.name,
                    "dry_run": job.dry_run,
                    "test_mode": self.test_mode,
                    "transfer_stats": progress_parser.get_final_stats().__dict__,
                }

                return False, "ERROR: Sync operation timed out after 5 minutes", sync_info

            except Exception as e:
                self.logger.error(f"Sync failed with exception: {e}")
                job.status = "error"
                job.error = str(e)

                sync_info = {
                    "command": cmd,
                    "return_code": -1,
                    "error": str(e),
                    "config_file": config_file.name,
                    "dry_run": job.dry_run,
                    "test_mode": self.test_mode,
                    "transfer_stats": progress_parser.get_final_stats().__dict__,
                }

                return False, f"ERROR: {e}", sync_info

            finally:
                # Clean up temporary config file
                try:
                    os.unlink(config_file.name)
                    self.logger.debug(f"Cleaned up config file: {config_file.name}")
                except Exception as e:
                    self.logger.warning(f"Failed to clean up config file {config_file.name}: {e}")


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

        # Test rclone command building
        job = engine_test.create_backup_job()
        cmd = engine_test.build_sync_command(job)
        print(f"✓ Built rclone command with {len(cmd)} arguments")
        print(f"  Command: {' '.join(cmd[:8])}...")

        # Test rclone config building
        config = engine_test._build_rclone_config()
        print(f"✓ Built rclone config ({len(config)} chars)")

        # Test environment validation (now includes rclone check)
        is_valid, errors = engine_test.validate_backup_environment()
        print(f"✓ Environment validation: valid={is_valid}, errors={errors}")

        # Test sync functionality with dry run (if environment is valid)
        if rclone_available:
            print("Testing sync functionality...")
            job = engine_test.create_backup_job()
            job.dry_run = True  # Use dry run to avoid needing real Minio

            success, output, sync_info = engine_test.sync(job)
            print(f"✓ Sync test: success={success}, duration={sync_info.get('duration_seconds', 0):.2f}s")
            if success:
                print("  Dry run sync completed successfully")
            else:
                print(f"  Sync failed (expected without Minio): {sync_info.get('error', 'Unknown error')}")
        else:
            print("⏭️  Skipping sync test (rclone not available)")

        print("✓ All tests passed!")

    except Exception as e:
        print(f"✗ Test failed: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
