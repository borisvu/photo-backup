"""
Core verifier for photo backup integrity checking.

This module provides the main Verifier class that orchestrates
hash calculation, remote listing, comparison, repair, and reporting.

"""

import contextlib
import logging
import os
import subprocess
import tempfile
import time
from collections.abc import Callable
from typing import Any

from pathlib import Path

from ..config.config import Config
from ..credentials.manager import CredentialManager
from .hash_calculator import HashCalculator
from .models import (
    ComparisonResult,
    FileHash,
    FileMismatch,
    RepairResult,
    VerificationJob,
    VerificationReport,
)
from .remote_lister import RemoteLister


class Verifier:
    """Core verifier for photo backup integrity checking."""

    def __init__(self, config: Config | None = None, test_mode: bool = False):
        """Initialize the verifier.

        Args:
            config: Configuration object. If None, creates a new one
            test_mode: Whether to run in test mode (uses Minio)
        """
        self.config = config or Config(test_mode=test_mode)
        self.test_mode = test_mode or self.config.is_test_mode()
        self.logger = logging.getLogger(__name__)
        self.credential_manager = CredentialManager(self.config)
        self.hash_calculator = HashCalculator()
        self.remote_lister = RemoteLister(self.config, self.credential_manager)

        # Load configuration
        self.config.load_config()

        self.logger.info(f"Verifier initialized in {'test' if self.test_mode else 'production'} mode")

    def create_verification_job(self) -> VerificationJob:
        """Create a verification job from current configuration.

        Returns:
            VerificationJob: Configured verification job
        """
        source_path = self.config.get("backup.source_path")
        destination = self.config.get("backup.destination")

        job = VerificationJob(source_path=source_path, destination=destination)

        self.logger.info(f"Created verification job: {job}")
        return job

    def get_verification_info(self) -> dict[str, Any]:
        """Get current verification configuration information.

        Returns:
            Dict containing verification configuration details
        """
        return {
            "mode": "test" if self.test_mode else "production",
            "source_path": self.config.get("backup.source_path"),
            "destination": self.config.get("backup.destination"),
            "endpoint": self.config.get("storage.endpoint"),
            "credential_status": self.credential_manager.get_credential_status(),
        }

    def calculate_local_hashes(
        self,
        source_path: str | None = None,
        progress_callback: Callable[[int, int], None] | None = None,
    ) -> list[FileHash]:
        """Calculate hashes for all local files.

        Args:
            source_path: Path to local directory (uses config if None)
            progress_callback: Optional callback for progress reporting

        Returns:
            List of FileHash objects for local files
        """
        if source_path is None:
            source_path = self.config.get("backup.source_path")

        if not source_path:
            raise ValueError("No source path configured")

        # Set progress callback if provided
        if progress_callback:
            self.hash_calculator.progress_callback = progress_callback

        self.logger.info(f"Calculating hashes for local files in: {source_path}")
        return self.hash_calculator.calculate_directory_hashes(source_path)

    def list_remote_files(self, remote_path: str | None = None) -> list[FileHash]:
        """List files in remote storage.

        Args:
            remote_path: Remote path (uses config destination if None)

        Returns:
            List of FileHash objects for remote files
        """
        if remote_path is None:
            destination = self.config.get("backup.destination")
            # Extract bucket/path from destination
            remote_path = destination.split(":", 1)[1] if ":" in destination else destination

        if not remote_path:
            raise ValueError("No remote path configured")

        self.logger.info(f"Listing remote files in: {remote_path}")
        return self.remote_lister.list_remote_files(remote_path)

    def set_progress_callback(self, callback: Callable[[int, int], None]) -> None:
        """Set progress callback for hash calculations.

        Args:
            callback: Callback function(bytes_processed, total_bytes)
        """
        self.hash_calculator.progress_callback = callback

    # ==========================================================================
    # Task 96: Hash Comparison
    # ==========================================================================

    def compare_hashes(
        self,
        local_files: list[FileHash],
        remote_files: list[FileHash],
    ) -> ComparisonResult:
        """Compare local and remote file hashes to find differences.

        Task 96: Hash Comparison implementation.

        This method matches files by their relative paths and compares their
        MD5 hashes to identify:
        - Files that match perfectly
        - Files with hash mismatches (possibly corrupted)
        - Files present locally but missing on remote
        - Files present on remote but missing locally

        Args:
            local_files: List of FileHash objects from local storage
            remote_files: List of FileHash objects from remote storage

        Returns:
            ComparisonResult with detailed comparison information
        """
        start_time = time.time()
        self.logger.info(f"Comparing {len(local_files)} local files with {len(remote_files)} remote files")

        # Build lookup dictionaries for O(1) access
        local_by_path: dict[str, FileHash] = {fh.path: fh for fh in local_files}
        remote_by_path: dict[str, FileHash] = {fh.path: fh for fh in remote_files}

        # Track results
        matched_files: list[str] = []
        mismatched_files: list[FileMismatch] = []
        missing_remote: list[FileHash] = []
        missing_local: list[FileHash] = []

        # Compare local files against remote
        for path, local_fh in local_by_path.items():
            if path in remote_by_path:
                remote_fh = remote_by_path[path]

                # Compare hashes
                if local_fh.hash_md5 and remote_fh.hash_md5:
                    if local_fh.hash_md5 == remote_fh.hash_md5:
                        matched_files.append(path)
                    else:
                        # Determine mismatch type
                        hash_mismatch = local_fh.hash_md5 != remote_fh.hash_md5
                        size_mismatch = local_fh.size != remote_fh.size

                        if hash_mismatch and size_mismatch:
                            mismatch_type = "both"
                        elif hash_mismatch:
                            mismatch_type = "hash"
                        else:
                            mismatch_type = "size"

                        mismatched_files.append(
                            FileMismatch(
                                path=path,
                                local_hash=local_fh.hash_md5,
                                remote_hash=remote_fh.hash_md5,
                                local_size=local_fh.size,
                                remote_size=remote_fh.size,
                                mismatch_type=mismatch_type,
                            )
                        )
                else:
                    # Can't compare if hash is missing - assume match for now
                    self.logger.warning(f"Missing hash for comparison: {path}")
                    matched_files.append(path)
            else:
                # File exists locally but not on remote
                missing_remote.append(local_fh)

        # Find files that exist on remote but not locally
        for path, remote_fh in remote_by_path.items():
            if path not in local_by_path:
                missing_local.append(remote_fh)

        # Calculate comparison time
        comparison_time = time.time() - start_time

        result = ComparisonResult(
            matched_files=matched_files,
            mismatched_files=mismatched_files,
            missing_remote=missing_remote,
            missing_local=missing_local,
            comparison_time_seconds=comparison_time,
        )

        self.logger.info(result.get_summary())
        return result

    # ==========================================================================
    # Task 97: Repair Function
    # ==========================================================================

    def repair_files(
        self,
        comparison_result: ComparisonResult,
        source_path: str | None = None,
        verify_after_repair: bool = True,
    ) -> RepairResult:
        """Re-upload files that have mismatches or are missing on remote.

        Task 97: Repair Function implementation.

        This method:
        1. Re-uploads files that have hash mismatches
        2. Uploads files that are missing on remote
        3. Optionally verifies files after upload

        Args:
            comparison_result: Result from compare_hashes() with files to repair
            source_path: Local source path (uses config if None)
            verify_after_repair: Whether to verify files after uploading

        Returns:
            RepairResult with repair operation details
        """
        start_time = time.time()

        if source_path is None:
            source_path = self.config.get("backup.source_path")

        if not source_path:
            raise ValueError("No source path configured")

        # Collect files that need repair
        files_to_repair: list[str] = []

        # Add mismatched files
        for mismatch in comparison_result.mismatched_files:
            files_to_repair.append(mismatch.path)

        # Add files missing on remote
        for fh in comparison_result.missing_remote:
            files_to_repair.append(fh.path)

        if not files_to_repair:
            self.logger.info("No files need repair")
            return RepairResult(repair_time_seconds=time.time() - start_time)

        self.logger.info(f"Repairing {len(files_to_repair)} files")

        repaired_files: list[str] = []
        failed_files: list[dict[str, Any]] = []
        verified_after_repair: list[str] = []

        # Repair each file
        for file_path in files_to_repair:
            try:
                success = self._repair_single_file(source_path, file_path)
                if success:
                    repaired_files.append(file_path)
                    self.logger.info(f"Repaired: {file_path}")
                else:
                    failed_files.append({"path": file_path, "error": "Upload failed"})
                    self.logger.error(f"Failed to repair: {file_path}")
            except Exception as e:
                failed_files.append({"path": file_path, "error": str(e)})
                self.logger.error(f"Error repairing {file_path}: {e}")

        # Verify after repair if requested
        if verify_after_repair and repaired_files:
            self.logger.info("Verifying repaired files...")
            for file_path in repaired_files:
                try:
                    if self._verify_repaired_file(source_path, file_path):
                        verified_after_repair.append(file_path)
                    else:
                        self.logger.warning(f"Verification failed after repair: {file_path}")
                except Exception as e:
                    self.logger.warning(f"Error verifying {file_path}: {e}")

        repair_time = time.time() - start_time

        result = RepairResult(
            repaired_files=repaired_files,
            failed_files=failed_files,
            verified_after_repair=verified_after_repair,
            repair_time_seconds=repair_time,
        )

        self.logger.info(result.get_summary())
        return result

    def _repair_single_file(self, source_path: str, file_path: str) -> bool:
        """Upload a single file to repair it on remote.

        Args:
            source_path: Base local source path
            file_path: Relative path of file to repair

        Returns:
            True if upload succeeded, False otherwise
        """
        # Build full local path
        full_local_path = Path(source_path) / file_path

        if not full_local_path.exists():
            self.logger.error(f"Local file not found: {full_local_path}")
            return False

        # Get destination
        destination = self.config.get("backup.destination")
        if not destination:
            raise ValueError("No destination configured")

        # Extract bucket/path from destination
        remote_path = destination.split(":", 1)[1] if ":" in destination else destination

        # Build rclone copy command for single file
        # rclone copyto source test:bucket/path --config config.conf
        cmd = [
            "rclone",
            "copyto",
            str(full_local_path),
            f"test:{remote_path}/{file_path}",
            "--checksum",
        ]

        # Create temporary config file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".conf", delete=False) as config_file:
            config_content = self.remote_lister._build_rclone_config()
            config_file.write(config_content)
            config_file.flush()
            config_path = config_file.name

        try:
            cmd.extend(["--config", config_path])

            self.logger.debug(f"Repair command: {' '.join(cmd[:4])}...")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120.0,  # 2 minute timeout per file
            )

            if result.returncode != 0:
                self.logger.error(f"rclone copyto failed: {result.stderr}")
                return False

            return True

        except subprocess.TimeoutExpired:
            self.logger.error(f"Timeout uploading {file_path}")
            return False
        except Exception as e:
            self.logger.error(f"Error uploading {file_path}: {e}")
            return False
        finally:
            with contextlib.suppress(Exception):
                os.unlink(config_path)

    def _verify_repaired_file(self, source_path: str, file_path: str) -> bool:
        """Verify a single file after repair by comparing hashes.

        Args:
            source_path: Base local source path
            file_path: Relative path of file to verify

        Returns:
            True if local and remote hashes match, False otherwise
        """
        # Calculate local hash
        full_local_path = Path(source_path) / file_path
        local_hash = self.hash_calculator.calculate_md5(full_local_path)

        # Get remote hash for this specific file
        destination = self.config.get("backup.destination")
        remote_path = destination.split(":", 1)[1] if ":" in destination else destination

        # Use rclone to get hash of specific remote file
        cmd = [
            "rclone",
            "md5sum",
            f"test:{remote_path}/{file_path}",
        ]

        with tempfile.NamedTemporaryFile(mode="w", suffix=".conf", delete=False) as config_file:
            config_content = self.remote_lister._build_rclone_config()
            config_file.write(config_content)
            config_file.flush()
            config_path = config_file.name

        try:
            cmd.extend(["--config", config_path])

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60.0,
            )

            if result.returncode != 0:
                self.logger.warning(f"Failed to get remote hash for {file_path}")
                return False

            # Parse md5sum output (format: "hash  filename")
            output = result.stdout.strip()
            if output:
                remote_hash = output.split()[0]
                return local_hash == remote_hash

            return False

        except Exception as e:
            self.logger.warning(f"Error verifying {file_path}: {e}")
            return False
        finally:
            with contextlib.suppress(Exception):
                os.unlink(config_path)

    # ==========================================================================
    # Task 98: Verification Report
    # ==========================================================================

    def generate_report(
        self,
        comparison_result: ComparisonResult,
        repair_result: RepairResult | None = None,
        local_files: list[FileHash] | None = None,
    ) -> VerificationReport:
        """Generate a detailed verification report.

        Task 98: Verification Report implementation.

        Args:
            comparison_result: Result from compare_hashes()
            repair_result: Optional result from repair_files()
            local_files: Optional list of local files for byte count

        Returns:
            VerificationReport with comprehensive verification details
        """
        # Calculate total bytes if local_files provided
        total_bytes = 0
        if local_files:
            total_bytes = sum(fh.size for fh in local_files)

        # Determine if verification passed
        verification_passed = not comparison_result.has_issues

        # If repair was performed, check if all repairs succeeded
        if repair_result:
            verification_passed = repair_result.success and repair_result.all_verified

        # Calculate total duration
        total_duration = comparison_result.comparison_time_seconds
        if repair_result:
            total_duration += repair_result.repair_time_seconds

        report = VerificationReport(
            source_path=self.config.get("backup.source_path", ""),
            destination=self.config.get("backup.destination", ""),
            mode="test" if self.test_mode else "production",
            comparison_result=comparison_result,
            repair_result=repair_result,
            total_files_checked=comparison_result.total_local_files,
            total_bytes_checked=total_bytes,
            verification_passed=verification_passed,
            total_duration_seconds=total_duration,
        )

        self.logger.info(f"Generated verification report: {report.report_id}")
        return report

    def run_full_verification(
        self,
        repair: bool = False,
        save_report: bool = False,
        report_path: str | None = None,
    ) -> VerificationReport:
        """Run a complete verification workflow.

        This is a convenience method that:
        1. Calculates local hashes
        2. Lists remote files
        3. Compares hashes
        4. Optionally repairs mismatches
        5. Generates and optionally saves a report

        Args:
            repair: Whether to repair any found issues
            save_report: Whether to save the report to file
            report_path: Custom path for the report file

        Returns:
            VerificationReport with all verification details
        """
        self.logger.info("Starting full verification...")
        start_time = time.time()

        errors: list[str] = []

        # Step 1: Calculate local hashes
        try:
            self.logger.info("Calculating local file hashes...")
            local_files = self.calculate_local_hashes()
            self.logger.info(f"Found {len(local_files)} local files")
        except Exception as e:
            errors.append(f"Failed to calculate local hashes: {e}")
            self.logger.error(errors[-1])
            # Return error report
            return VerificationReport(
                source_path=self.config.get("backup.source_path", ""),
                destination=self.config.get("backup.destination", ""),
                mode="test" if self.test_mode else "production",
                verification_passed=False,
                errors=errors,
                total_duration_seconds=time.time() - start_time,
            )

        # Step 2: List remote files
        try:
            self.logger.info("Listing remote files...")
            remote_files = self.list_remote_files()
            self.logger.info(f"Found {len(remote_files)} remote files")
        except Exception as e:
            errors.append(f"Failed to list remote files: {e}")
            self.logger.error(errors[-1])
            return VerificationReport(
                source_path=self.config.get("backup.source_path", ""),
                destination=self.config.get("backup.destination", ""),
                mode="test" if self.test_mode else "production",
                verification_passed=False,
                errors=errors,
                total_duration_seconds=time.time() - start_time,
            )

        # Step 3: Compare hashes
        self.logger.info("Comparing file hashes...")
        comparison_result = self.compare_hashes(local_files, remote_files)

        # Step 4: Optionally repair
        repair_result = None
        if repair and comparison_result.has_issues:
            self.logger.info("Repairing issues...")
            try:
                repair_result = self.repair_files(comparison_result)
            except Exception as e:
                errors.append(f"Repair failed: {e}")
                self.logger.error(errors[-1])

        # Step 5: Generate report
        report = self.generate_report(comparison_result, repair_result, local_files)
        report.errors = errors
        report.total_duration_seconds = time.time() - start_time

        # Step 6: Optionally save report
        if save_report:
            if report_path is None:
                # Default to state directory
                state_dir = Path.home() / ".photo-backup"
                if self.test_mode:
                    state_dir = state_dir / "test"
                report_path = str(state_dir / "reports" / f"{report.report_id}.json")

            if report.save_to_file(report_path, format="json"):
                self.logger.info(f"Report saved to: {report_path}")
            else:
                self.logger.warning(f"Failed to save report to: {report_path}")

        return report
