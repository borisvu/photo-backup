"""
Backup engine core.

This module provides the main BackupEngine class that orchestrates
backup operations, progress tracking, and state management.
"""

import logging
import os
import subprocess
import tempfile
import time
from datetime import datetime
from typing import Any

from pathlib import Path

from ..config.config import Config
from ..credentials.manager import CredentialManager
from ..logger.context import OperationContext
from ..progress_parser import RcloneProgressParser
from .errors import BackupError, ErrorDetector, ErrorType
from .job import BackupJob
from .rclone_utils import check_rclone
from .state import BackupState, StateManager
from .stats import BackupStats


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
        self.error_detector = ErrorDetector(self.logger)
        self.state_manager = StateManager(test_mode=self.test_mode)

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

    def sync_with_progress(self, job: BackupJob) -> tuple[bool, str, dict[str, Any], BackupStats]:
        """Execute rclone sync operation with real-time progress parsing.

        This method enhances the basic sync with real-time progress monitoring,
        transfer statistics, and progress events.

        Args:
            job: BackupJob containing sync parameters

        Returns:
            Tuple of (success, output, sync_info, backup_stats)
            - success: True if sync completed successfully
            - output: Complete rclone output
            - sync_info: Dictionary with sync statistics and metadata including transfer_stats
            - backup_stats: BackupStats object with comprehensive metrics and analysis
        """
        # Create operation context for this sync operation
        operation_description = f"Sync {job.source_path} -> {job.destination}"
        if job.dry_run:
            operation_description += " (dry-run)"

        with OperationContext("backup", operation_description, self.logger) as operation_ctx:
            operation_ctx.log_progress(f"Starting sync: {job.source_path} -> {job.destination}")

            # Initialize progress parser
            progress_parser = RcloneProgressParser(self.logger)

            # Estimate total files for progress tracking
            total_files = 0
            try:
                source_path = Path(job.source_path)
                if source_path.exists():
                    total_files = len([f for f in source_path.rglob("*") if f.is_file()])
                    if total_files > 0:
                        # Initialize progress logger with operation context
                        from ..logger.progress import ProgressLogger

                        progress_logger = ProgressLogger(
                            total_items=total_files,
                            operation_type="files",
                            update_interval=2.0,
                            logger=self.logger,
                            operation_context=operation_ctx,
                        )
                        progress_parser.progress_logger = progress_logger
                        operation_ctx.log_progress(f"Estimated {total_files} files to sync")
            except Exception as e:
                self.logger.debug(f"Could not estimate file count: {e}")

            # Build the sync command
            cmd = self.build_sync_command(job)

            # Create temporary config file
            return self._execute_sync_with_context(job, cmd, progress_parser, operation_ctx)

    def _execute_sync_with_context(
        self,
        job: BackupJob,
        cmd: list[str],
        progress_parser: RcloneProgressParser,
        operation_ctx: OperationContext,
    ) -> tuple[bool, str, dict[str, Any], BackupStats]:
        """Execute sync with operation context tracking.

        Args:
            job: BackupJob containing sync parameters
            cmd: rclone command to execute
            progress_parser: Progress parser instance
            operation_ctx: Operation context for logging

        Returns:
            Tuple of (success, output, sync_info, backup_stats)
        """
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
                start_datetime = datetime.now()

                # Execute rclone command with real-time output parsing
                operation_ctx.log_progress(f"Executing rclone sync (config: {config_file.name})")

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
                end_datetime = datetime.now()
                duration = end_time - start_time

                # Mark progress as complete
                progress_parser.complete()

                # Combine all output
                complete_output = "\n".join(output_lines)

                # Parse errors from output using ErrorDetector
                detected_errors = self.error_detector.parse_errors(complete_output)
                error_summary = self.error_detector.get_error_summary(detected_errors)

                # Log detected errors and add to operation context
                if detected_errors:
                    operation_ctx.log_warning(f"Detected {len(detected_errors)} error(s) during sync")
                    for error in detected_errors:
                        error_msg = f"{error.error_type.value}: {error.message}"
                        if error.file_path:
                            error_msg += f" (File: {error.file_path})"
                        operation_ctx.log_warning(error_msg)
                        operation_ctx.add_error(error.message)
                        if error.suggestion:
                            operation_ctx.log_progress(f"Suggestion: {error.suggestion}")

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
                    operation_ctx.log_progress(f"Sync completed successfully in {duration:.2f}s")
                    operation_ctx.log_progress(
                        f"Transferred {transfer_stats.files_transferred} files ({transfer_stats.bytes_transferred / (1024 * 1024):.1f} MB)"
                    )
                    if transfer_stats.transfer_rate_mbps > 0:
                        operation_ctx.log_progress(
                            f"Average transfer rate: {transfer_stats.transfer_rate_mbps:.1f} MB/s"
                        )
                    if job.dry_run:
                        operation_ctx.log_progress("Dry run completed - no files were actually transferred")

                    # Add files to operation context summary
                    for _ in range(transfer_stats.files_transferred):
                        operation_ctx.add_file_processed(
                            size_bytes=transfer_stats.bytes_transferred // max(transfer_stats.files_transferred, 1),
                            success=True,
                        )
                else:
                    operation_ctx.log_error(f"Sync failed with return code {return_code}")
                    # Log last few lines of output as error details
                    error_lines = output_lines[-5:] if output_lines else ["No output captured"]
                    error_detail = "; ".join(error_lines)
                    operation_ctx.log_error(f"Error details: {error_detail}")
                    operation_ctx.add_error(error_detail)

                # Update job status
                job.status = "completed" if success else "error"
                error_message = None
                if not success:
                    error_message = "; ".join(output_lines[-3:]) if output_lines else "Unknown error"
                    job.error = error_message

                # Create backup statistics
                backup_stats = BackupStats.from_transfer_stats(
                    transfer_stats=transfer_stats,
                    start_time=start_datetime,
                    end_time=end_datetime,
                    source_path=job.source_path,
                    destination=job.destination,
                    dry_run=job.dry_run,
                    test_mode=self.test_mode,
                    success=success,
                    error_message=error_message,
                    detailed_errors=detected_errors,
                    error_summary=error_summary,
                )

                # Log backup statistics summary
                operation_ctx.log_progress("Backup Statistics:")
                for line in backup_stats.get_summary().split("\n"):
                    if line.strip():
                        operation_ctx.log_progress(f"  {line}")

                # Log operation context summary
                op_summary = operation_ctx.get_summary()
                summary_text = op_summary.format_summary()
                if summary_text:
                    operation_ctx.log_progress("Operation Summary:")
                    for line in summary_text.split("\n"):
                        if line.strip():
                            operation_ctx.log_progress(f"  {line}")

                # Save backup state
                try:
                    state_success, state_error = self.state_manager.update_and_save_state(backup_stats)
                    if state_success:
                        self.logger.info("Backup state saved successfully")
                    else:
                        self.logger.warning(f"Failed to save backup state: {state_error}")
                except Exception as e:
                    self.logger.warning(f"Exception while saving backup state: {e}")

                return success, complete_output, sync_info, backup_stats

            except subprocess.TimeoutExpired:
                operation_ctx.log_error("Sync operation timed out after 5 minutes")
                operation_ctx.add_error("Sync operation timed out after 5 minutes")
                job.status = "error"
                job.error = "Sync operation timed out"

                # Create backup statistics for timeout case
                end_datetime = datetime.now()
                transfer_stats = progress_parser.get_final_stats()

                # Create timeout error
                timeout_error = BackupError(
                    error_type=ErrorType.TIMEOUT_ERROR,
                    message="Sync operation timed out after 5 minutes",
                    suggestion="Try again or increase timeout settings",
                )
                timeout_errors = [timeout_error]
                timeout_error_summary = self.error_detector.get_error_summary(timeout_errors)

                backup_stats = BackupStats.from_transfer_stats(
                    transfer_stats=transfer_stats,
                    start_time=start_datetime,
                    end_time=end_datetime,
                    source_path=job.source_path,
                    destination=job.destination,
                    dry_run=job.dry_run,
                    test_mode=self.test_mode,
                    success=False,
                    error_message="Sync operation timed out",
                    detailed_errors=timeout_errors,
                    error_summary=timeout_error_summary,
                )

                sync_info = {
                    "command": cmd,
                    "return_code": -1,
                    "duration_seconds": 300.0,
                    "error": "Timeout",
                    "config_file": config_file.name,
                    "dry_run": job.dry_run,
                    "test_mode": self.test_mode,
                    "transfer_stats": transfer_stats.__dict__,
                }

                # Save backup state for timeout case
                try:
                    state_success, state_error = self.state_manager.update_and_save_state(backup_stats)
                    if state_success:
                        self.logger.info("Backup state saved successfully (timeout case)")
                    else:
                        self.logger.warning(f"Failed to save backup state (timeout): {state_error}")
                except Exception as e:
                    self.logger.warning(f"Exception while saving backup state (timeout): {e}")

                return False, "ERROR: Sync operation timed out after 5 minutes", sync_info, backup_stats

            except Exception as e:
                operation_ctx.log_error(f"Sync failed with exception: {e}")
                operation_ctx.add_error(str(e))
                job.status = "error"
                job.error = str(e)

                # Create backup statistics for exception case
                end_datetime = datetime.now()
                transfer_stats = progress_parser.get_final_stats()

                # Create exception error
                exception_error = BackupError(
                    error_type=ErrorType.UNKNOWN_ERROR,
                    message=f"Sync failed with exception: {e}",
                    suggestion="Check logs for details and retry",
                )
                exception_errors = [exception_error]
                exception_error_summary = self.error_detector.get_error_summary(exception_errors)

                backup_stats = BackupStats.from_transfer_stats(
                    transfer_stats=transfer_stats,
                    start_time=start_datetime,
                    end_time=end_datetime,
                    source_path=job.source_path,
                    destination=job.destination,
                    dry_run=job.dry_run,
                    test_mode=self.test_mode,
                    success=False,
                    error_message=str(e),
                    detailed_errors=exception_errors,
                    error_summary=exception_error_summary,
                )

                sync_info = {
                    "command": cmd,
                    "return_code": -1,
                    "error": str(e),
                    "config_file": config_file.name,
                    "dry_run": job.dry_run,
                    "test_mode": self.test_mode,
                    "transfer_stats": transfer_stats.__dict__,
                }

                # Save backup state for exception case
                try:
                    state_success, state_error = self.state_manager.update_and_save_state(backup_stats)
                    if state_success:
                        self.logger.info("Backup state saved successfully (exception case)")
                    else:
                        self.logger.warning(f"Failed to save backup state (exception): {state_error}")
                except Exception as state_exception:
                    self.logger.warning(f"Exception while saving backup state (exception): {state_exception}")

                return False, f"ERROR: {e}", sync_info, backup_stats

            finally:
                # Clean up temporary config file
                try:
                    os.unlink(config_file.name)
                    self.logger.debug(f"Cleaned up config file: {config_file.name}")
                except Exception as e:
                    self.logger.warning(f"Failed to clean up config file {config_file.name}: {e}")

    def sync_with_stats(self, job: BackupJob) -> BackupStats:
        """Execute sync and return comprehensive backup statistics.

        This is a convenience method that performs sync_with_progress and
        returns only the BackupStats for easier consumption.

        Args:
            job: BackupJob containing sync parameters

        Returns:
            BackupStats: Comprehensive backup statistics and metrics
        """
        success, output, sync_info, backup_stats = self.sync_with_progress(job)
        return backup_stats

    def get_backup_state_summary(self) -> dict[str, Any]:
        """Get current backup state summary.

        Returns:
            Dictionary with backup state metrics and history
        """
        return self.state_manager.get_state_summary()

    def get_backup_state(self) -> BackupState:
        """Get the current backup state object.

        Returns:
            BackupState object with full state information
        """
        return self.state_manager.load_state()
