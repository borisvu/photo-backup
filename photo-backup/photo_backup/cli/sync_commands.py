#!/usr/bin/env python3
"""
Photo Backup System - Sync CLI Commands

This module provides CLI commands for manual backup synchronization.
"""

import logging
import sys
from datetime import datetime

import click

from ..backup import BackupEngine
from ..config.config import Config


def _get_logger(config_obj: Config) -> logging.Logger:
    """Get configured logger for sync commands."""
    from ..logger import generate_job_id, setup_logger_from_config

    job_id = generate_job_id("sync")
    return setup_logger_from_config(config_obj, job_id, "photo_backup.sync")


@click.command()
@click.option("--verbose", "-v", is_flag=True, help="Show detailed sync information")
@click.pass_context
def sync(ctx: click.Context, verbose: bool) -> None:
    """Run manual backup synchronization.

    This command performs a full backup sync from the configured source
    to the destination storage. It supports both test mode (Minio) and
    production mode (Wasabi).

    Examples:
        photo-backup sync                    # Run sync in current mode
        photo-backup sync --test-mode        # Run sync in test mode with Minio
        photo-backup sync --dry-run          # Show what would be synced without executing
        photo-backup sync --verbose          # Show detailed sync information
    """
    # Get config from context
    context_data = ctx.obj
    test_mode = context_data.get("test_mode", False)
    dry_run = context_data.get("dry_run", False)

    # Create config object
    config = Config(test_mode=test_mode, dry_run=dry_run)
    config.load_config()

    # Set up logger
    logger = _get_logger(config)
    logger.info("Sync command started")
    logger.debug(f"Test mode: {test_mode}, Dry run: {dry_run}, Verbose: {verbose}")

    # Header
    mode_text = "TEST MODE" if test_mode else "PRODUCTION MODE"
    dry_run_text = " (DRY RUN)" if dry_run else ""
    click.echo("Photo Backup Sync")
    click.echo("=" * 20)
    click.echo(f"Mode: {mode_text}{dry_run_text}")
    click.echo(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    click.echo()

    try:
        # Initialize backup engine
        engine = BackupEngine(config, test_mode=test_mode)
        logger.info("BackupEngine initialized successfully")

        # Validate backup environment
        click.echo("Validating backup environment...")
        is_valid, errors = engine.validate_backup_environment()

        if not is_valid:
            click.echo("❌ Backup environment validation failed:", err=True)
            for error in errors:
                click.echo(f"  - {error}", err=True)
            click.echo("\nPlease fix the issues above and try again.", err=True)
            logger.error(f"Environment validation failed: {errors}")
            sys.exit(1)

        click.echo("✅ Backup environment validated successfully")
        logger.info("Environment validation passed")

        # Get backup information
        backup_info = engine.get_backup_info()
        click.echo(f"Source: {backup_info['source_path']}")
        click.echo(f"Destination: {backup_info['destination']}")
        click.echo(f"Endpoint: {backup_info['endpoint']}")

        if verbose:
            click.echo(f"Credential Status: {backup_info['credential_status']}")
            rclone_status = backup_info["rclone_status"]
            click.echo(f"rclone: {rclone_status['message']}")

        click.echo()

        # Create backup job
        job = engine.create_backup_job()
        logger.info(f"Created backup job: {job}")

        # Show what will be synced
        if dry_run:
            click.echo("🔍 DRY RUN MODE - No files will be transferred")
        else:
            click.echo("🚀 Starting backup synchronization...")

        click.echo()

        # Execute sync with progress
        success, output, sync_info, backup_stats = engine.sync_with_progress(job)

        # Display results
        click.echo()
        click.echo("=" * 50)
        click.echo("BACKUP RESULTS")
        click.echo("=" * 50)

        if success:
            click.echo("✅ Backup completed successfully!")
        else:
            click.echo("❌ Backup failed!")
            click.echo(f"Error: {backup_stats.error_message}")

        # Show statistics
        click.echo()
        click.echo("📊 Backup Statistics:")
        for line in backup_stats.get_summary().split("\n"):
            click.echo(f"  {line}")

        # Show detailed information if verbose or if there were errors
        if verbose or not success or backup_stats.errors > 0:
            click.echo()
            click.echo("📋 Detailed Information:")

            if backup_stats.detailed_errors:
                click.echo(f"  Errors detected: {len(backup_stats.detailed_errors)}")
                for error in backup_stats.detailed_errors:
                    # Handle both BackupError objects and dict objects
                    if hasattr(error, "error_type"):
                        # It's a BackupError object
                        click.echo(f"    - {error.error_type.value}: {error.message}")  # type: ignore
                        if error.file_path:  # type: ignore
                            click.echo(f"      File: {error.file_path}")  # type: ignore
                        if error.suggestion:  # type: ignore
                            click.echo(f"      Suggestion: {error.suggestion}")  # type: ignore
                    elif isinstance(error, dict):
                        # It's a dict object (from serialization)
                        error_dict: dict = error
                        error_type = error_dict.get("error_type", "unknown_error")
                        message = error_dict.get("message", "Unknown error")
                        click.echo(f"    - {error_type}: {message}")
                        if error_dict.get("file_path"):
                            click.echo(f"      File: {error_dict['file_path']}")
                        if error_dict.get("suggestion"):
                            click.echo(f"      Suggestion: {error_dict['suggestion']}")
                    else:
                        # Fallback for unexpected types
                        click.echo(f"    - Unknown error: {error}")

            if verbose and sync_info:
                click.echo(f"  Duration: {sync_info.get('duration_seconds', 0):.2f} seconds")
                click.echo(f"  Return code: {sync_info.get('return_code', 'N/A')}")

                transfer_stats = sync_info.get("transfer_stats", {})
                if transfer_stats:
                    click.echo(f"  Transfer rate: {transfer_stats.get('transfer_rate_mbps', 0):.1f} MB/s")
                    click.echo(f"  Files rate: {transfer_stats.get('files_rate_per_second', 0):.1f} files/s")

        # Show next steps
        click.echo()
        if success:
            if dry_run:
                click.echo("💡 To perform the actual backup, run without --dry-run")
            else:
                click.echo("💡 Backup completed successfully!")
                if test_mode:
                    click.echo("   Check your Minio instance to verify files were uploaded")
                else:
                    click.echo("   Check your Wasabi bucket to verify files were uploaded")
        else:
            click.echo("💡 Troubleshooting tips:")
            if test_mode:
                click.echo("   - Ensure Minio container is running: docker ps")
                click.echo("   - Check Minio logs for issues")
                click.echo("   - Verify test photos exist in source directory")
            else:
                click.echo("   - Check your internet connection")
                click.echo("   - Verify Wasabi credentials are correct")
                click.echo("   - Check Wasabi service status")

            click.echo("   - Run 'photo-backup validate' to check configuration")
            click.echo("   - Use --verbose flag for more detailed information")

        # Log completion
        if success:
            logger.info("Sync command completed successfully")
        else:
            logger.error(f"Sync command failed: {backup_stats.error_message}")

        # Exit with appropriate code
        if not success:
            sys.exit(1)

    except KeyboardInterrupt:
        click.echo("\n⚠️  Backup interrupted by user")
        logger.warning("Sync command interrupted by user")
        sys.exit(1)
    except Exception as e:
        click.echo(f"\n❌ Unexpected error: {e}", err=True)
        logger.error(f"Unexpected error in sync command: {e}", exc_info=True)
        sys.exit(1)
