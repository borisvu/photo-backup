#!/usr/bin/env python3
"""
Photo Backup System - Verify CLI Commands

This module provides CLI commands for verifying backup integrity.
Add Verify Command implementation.
"""

import logging
import sys
from datetime import datetime

import click

from ..config.config import Config
from ..verify import Verifier


def _get_logger(config_obj: Config) -> logging.Logger:
    """Get configured logger for verify commands."""
    from ..logger import generate_job_id, setup_logger_from_config

    job_id = generate_job_id("verify")
    return setup_logger_from_config(config_obj, job_id, "photo_backup.verify")


def _format_bytes(bytes_count: int) -> str:
    """Format byte count to human-readable string."""
    if bytes_count < 1024:
        return f"{bytes_count} B"
    elif bytes_count < 1024**2:
        return f"{bytes_count / 1024:.1f} KB"
    elif bytes_count < 1024**3:
        return f"{bytes_count / (1024**2):.1f} MB"
    elif bytes_count < 1024**4:
        return f"{bytes_count / (1024**3):.1f} GB"
    else:
        return f"{bytes_count / (1024**4):.1f} TB"


def _format_duration(seconds: float) -> str:
    """Format duration in seconds to human-readable string."""
    if seconds < 60:
        return f"{seconds:.1f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.1f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"


@click.command()
@click.option("--verbose", "-v", is_flag=True, help="Show detailed verification information")
@click.option("--repair", "-r", is_flag=True, help="Automatically repair mismatched or missing files")
@click.option("--save-report", is_flag=True, help="Save verification report to file")
@click.option(
    "--report-format",
    type=click.Choice(["json", "text"]),
    default="json",
    help="Report output format (default: json)",
)
@click.option("--report-path", type=click.Path(), default=None, help="Custom path for the report file")
@click.pass_context
def verify(
    ctx: click.Context,
    verbose: bool,
    repair: bool,
    save_report: bool,
    report_format: str,
    report_path: str | None,
) -> None:
    """Verify backup integrity by comparing local and remote file hashes.

    This command performs a full verification of backed up files by:
    1. Calculating MD5 hashes for all local files
    2. Listing remote files with their hashes
    3. Comparing local and remote hashes
    4. Optionally repairing any mismatches

    Examples:
        photo-backup verify                     # Run verification
        photo-backup verify --repair            # Verify and repair mismatches
        photo-backup verify --save-report       # Save report to default location
        photo-backup verify --verbose           # Show detailed information
        photo-backup --test-mode verify         # Verify against Minio
    """
    # Get configuration from context
    context_data = ctx.obj
    test_mode = context_data.get("test_mode", False)
    dry_run = context_data.get("dry_run", False)

    # Create config object
    config = Config(test_mode=test_mode, dry_run=dry_run)
    try:
        config.load_config()
    except ValueError as e:
        click.echo("❌ Configuration Error:", err=True)
        click.echo(str(e), err=True)
        sys.exit(1)

    # Set up logger
    logger = _get_logger(config)
    logger.info("Verify command started")
    logger.debug(f"Test mode: {test_mode}, Repair: {repair}, Verbose: {verbose}")

    # Header
    mode_text = "TEST MODE" if test_mode else "PRODUCTION MODE"
    dry_run_text = " (DRY RUN)" if dry_run else ""
    click.echo("Photo Backup Verification")
    click.echo("=" * 25)
    click.echo(f"Mode: {mode_text}{dry_run_text}")
    click.echo(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    click.echo()

    try:
        # Initialize verifier
        click.echo("🔍 Initializing verifier...")
        verifier = Verifier(config=config, test_mode=test_mode)
        logger.info("Verifier initialized successfully")

        # Show verification info
        verify_info = verifier.get_verification_info()
        click.echo(f"Source: {verify_info['source_path']}")
        click.echo(f"Destination: {verify_info['destination']}")
        if verbose:
            click.echo(f"Endpoint: {verify_info['endpoint']}")
            click.echo(f"Credential Status: {verify_info['credential_status']}")
        click.echo()

        # Step 1: Scan local files (size + existence; no hashing)
        click.echo("📊 Scanning local files (size + existence)...")
        local_files = verifier.scan_local_files()
        local_count = len(local_files)
        total_bytes = sum(f.size for f in local_files)
        click.echo(f"   Found {local_count} local files ({_format_bytes(total_bytes)})")
        logger.info(f"Scanned {local_count} local files")

        # Step 2: List remote files
        click.echo("🌐 Listing remote files...")
        remote_files = verifier.list_remote_files()
        remote_count = len(remote_files)
        click.echo(f"   Found {remote_count} remote files")
        logger.info(f"Listed {remote_count} remote files")

        # Step 3: Compare by size + existence
        click.echo("🔄 Comparing files (size + existence)...")
        comparison_result = verifier.compare_hashes(local_files, remote_files)

        # Display comparison results
        click.echo()
        click.echo("-" * 50)
        click.echo("COMPARISON RESULTS")
        click.echo("-" * 50)

        matched = len(comparison_result.matched_files)
        mismatched = len(comparison_result.mismatched_files)
        missing_remote = len(comparison_result.missing_remote)
        missing_local = len(comparison_result.missing_local)

        click.echo(f"✅ Matched files: {matched}")

        if mismatched > 0:
            click.echo(f"❌ Mismatched files: {mismatched}")
        else:
            click.echo(f"✅ Mismatched files: {mismatched}")

        if missing_remote > 0:
            click.echo(f"⚠️  Missing on remote: {missing_remote}")
        else:
            click.echo(f"✅ Missing on remote: {missing_remote}")

        if missing_local > 0:
            click.echo(f"⚠️  Missing locally: {missing_local}")
        else:
            click.echo(f"✅ Missing locally: {missing_local}")

        click.echo(f"⏱️  Comparison time: {_format_duration(comparison_result.comparison_time_seconds)}")

        # Show detailed mismatches if verbose
        if verbose and comparison_result.mismatched_files:
            click.echo()
            click.echo("Mismatched Files Details:")
            for mismatch in comparison_result.mismatched_files[:10]:
                click.echo(f"  - {mismatch.path}")
                click.echo(f"    Local hash:  {mismatch.local_hash}")
                click.echo(f"    Remote hash: {mismatch.remote_hash}")
                click.echo(f"    Type: {mismatch.mismatch_type}")
            if len(comparison_result.mismatched_files) > 10:
                click.echo(f"  ... and {len(comparison_result.mismatched_files) - 10} more")

        if verbose and comparison_result.missing_remote:
            click.echo()
            click.echo("Missing on Remote:")
            for fh in comparison_result.missing_remote[:10]:
                click.echo(f"  - {fh.path} ({_format_bytes(fh.size)})")
            if len(comparison_result.missing_remote) > 10:
                click.echo(f"  ... and {len(comparison_result.missing_remote) - 10} more")

        # Step 4: Repair if requested
        repair_result = None
        if repair and comparison_result.has_issues:
            if dry_run:
                click.echo()
                click.echo("🔧 DRY RUN - Would repair the following:")
                click.echo(f"   - {mismatched} mismatched files")
                click.echo(f"   - {missing_remote} missing remote files")
            else:
                click.echo()
                click.echo("🔧 Repairing issues...")
                repair_result = verifier.repair_files(comparison_result)

                click.echo()
                click.echo("-" * 50)
                click.echo("REPAIR RESULTS")
                click.echo("-" * 50)
                click.echo(f"✅ Repaired: {len(repair_result.repaired_files)}")
                click.echo(f"❌ Failed: {len(repair_result.failed_files)}")
                click.echo(f"✓  Verified: {len(repair_result.verified_after_repair)}")
                click.echo(f"⏱️  Repair time: {_format_duration(repair_result.repair_time_seconds)}")

                if verbose and repair_result.failed_files:
                    click.echo()
                    click.echo("Failed Repairs:")
                    for fail in repair_result.failed_files[:5]:
                        click.echo(f"  - {fail.get('path', 'unknown')}: {fail.get('error', 'unknown')}")

        # Generate report
        report = verifier.generate_report(comparison_result, repair_result, local_files)

        # Save report if requested
        if save_report:
            if report_path:
                save_path = report_path
            else:
                # Use default path
                from pathlib import Path

                state_dir = Path.home() / ".photo-backup"
                if test_mode:
                    state_dir = state_dir / "test"
                reports_dir = state_dir / "reports"
                save_path = str(reports_dir / f"{report.report_id}.{report_format}")

            if report.save_to_file(save_path, format=report_format):
                click.echo()
                click.echo(f"📄 Report saved to: {save_path}")
                logger.info(f"Report saved to: {save_path}")
            else:
                click.echo()
                click.echo(f"⚠️  Failed to save report to: {save_path}", err=True)
                logger.warning(f"Failed to save report to: {save_path}")

        # Final summary
        click.echo()
        click.echo("=" * 50)
        # Check if repair was performed successfully
        repair_succeeded = repair and repair_result and repair_result.success

        if report.verification_passed or repair_succeeded:
            if repair_succeeded:
                click.echo("✅ VERIFICATION PASSED (after repair)")
                logger.info("Verification completed - issues repaired successfully")
            else:
                click.echo("✅ VERIFICATION PASSED")
                logger.info("Verification completed successfully - no issues found")
        else:
            click.echo("❌ VERIFICATION FAILED")
            logger.warning("Verification completed with issues")

        click.echo(f"Total duration: {_format_duration(report.total_duration_seconds)}")
        click.echo("=" * 50)

        # Exit with appropriate code
        if not report.verification_passed and not (repair and repair_result and repair_result.success):
            sys.exit(1)

    except KeyboardInterrupt:
        click.echo("\n⚠️  Verification interrupted by user")
        logger.warning("Verify command interrupted by user")
        sys.exit(1)
    except Exception as e:
        click.echo(f"\n❌ Unexpected error: {e}", err=True)
        logger.error(f"Unexpected error in verify command: {e}", exc_info=True)
        if verbose:
            import traceback

            click.echo(traceback.format_exc())
        sys.exit(1)


# Export the command
verify_command = verify
