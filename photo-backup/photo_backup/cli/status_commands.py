#!/usr/bin/env python3
"""
Photo Backup System - Status CLI Commands

This module provides CLI commands for checking backup status and system health.
"""

import logging
import sys
from datetime import datetime

import click
from pathlib import Path

from ..backup import BackupEngine, check_rclone
from ..config.config import Config
from ..credentials.manager import CredentialManager
from ..logger import generate_job_id, setup_logger_from_config
from ..monitor import DriveMonitor


def _get_logger(config_obj: Config) -> logging.Logger:
    """Get configured logger for status commands."""
    job_id = generate_job_id("status")
    return setup_logger_from_config(config_obj, job_id, "photo_backup.status")


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


def _format_datetime(dt: datetime | None) -> str:
    """Format datetime to human-readable string."""
    if dt is None:
        return "Never"

    now = datetime.now()
    diff = now - dt

    if diff.days > 0:
        return f"{dt.strftime('%Y-%m-%d %H:%M:%S')} ({diff.days}d ago)"
    elif diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f"{dt.strftime('%Y-%m-%d %H:%M:%S')} ({hours}h ago)"
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        return f"{dt.strftime('%Y-%m-%d %H:%M:%S')} ({minutes}m ago)"
    else:
        return f"{dt.strftime('%Y-%m-%d %H:%M:%S')} (just now)"


@click.command()
@click.option("--verbose", "-v", is_flag=True, help="Show detailed status information")
@click.option("--json", is_flag=True, help="Output status in JSON format")
@click.pass_context
def status(ctx: click.Context, verbose: bool, json: bool) -> None:
    """Show backup system status and health information.

    This command displays comprehensive information about the backup system
    including configuration, credentials, last backup status, and system health.

    Examples:
        photo-backup status                    # Show basic status
        photo-backup status --verbose          # Show detailed information
        photo-backup status --json             # Output in JSON format
        photo-backup --test-mode status        # Show test mode status
    """
    # Get test mode and dry-run from CLI flags
    context_data = ctx.obj
    test_mode = context_data.get("test_mode", False)
    dry_run = context_data.get("dry_run", False)

    # Create config object
    config_obj = Config(test_mode=test_mode, dry_run=dry_run)
    try:
        config_obj.load_config()
    except ValueError as e:
        # Configuration validation failed - show clean error without traceback
        click.echo("❌ Configuration Error:", err=True)
        click.echo(str(e), err=True)
        sys.exit(1)

    # Set up logger with job context
    logger = _get_logger(config_obj)
    logger.info("Status command started")
    logger.debug(f"Test mode: {test_mode}, Dry run: {dry_run}, Verbose: {verbose}, JSON: {json}")

    try:
        # Initialize backup engine
        engine = BackupEngine(config=config_obj, test_mode=test_mode)
        logger.info("BackupEngine initialized successfully")

        # Get backup information
        backup_info = engine.get_backup_info()
        backup_state = engine.get_backup_state()
        backup_state_summary = engine.get_backup_state_summary()

        # Get credential status
        credential_manager = CredentialManager(config=config_obj)
        credential_status = credential_manager.get_credential_status()

        if json:
            # Output in JSON format
            import json as json_module

            status_data = {
                "timestamp": datetime.now().isoformat(),
                "mode": "test" if test_mode else "production",
                "dry_run": dry_run,
                "backup_info": backup_info,
                "backup_state": backup_state_summary,
                "credential_status": credential_status,
                "system_health": {
                    "config_loaded": True,
                    "backup_engine_ready": True,
                    "credentials_available": credential_status.get("available", False),
                },
            }
            click.echo(json_module.dumps(status_data, indent=2, default=str))
            return

        # Display status information
        click.echo("Photo Backup System Status")
        click.echo("=" * 30)

        # Mode information
        mode_text = "TEST MODE" if test_mode else "PRODUCTION MODE"
        dry_run_text = " (DRY RUN)" if dry_run else ""
        click.echo(f"Mode: {mode_text}{dry_run_text}")
        click.echo(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        click.echo()

        # Configuration status
        click.echo("📋 Configuration:")
        click.echo(f"  Source: {backup_info.get('source_path', 'N/A')}")
        click.echo(f"  Destination: {backup_info.get('destination', 'N/A')}")
        click.echo(f"  Endpoint: {backup_info.get('endpoint', 'N/A')}")
        click.echo(f"  State Directory: {backup_info.get('state_directory', 'N/A')}")
        click.echo()

        # Credential status
        click.echo("🔐 Credentials:")
        click.echo(f"  Status: {'✅ Available' if credential_status.get('available') else '❌ Not Available'}")
        if credential_status.get("available"):
            click.echo(f"  Source: {credential_status.get('source', 'Unknown')}")
            click.echo(f"  Endpoint: {credential_status.get('endpoint', 'N/A')}")
            if verbose:
                click.echo(f"  Access Key: {credential_status.get('access_key', 'N/A')}")
                click.echo(f"  Region: {credential_status.get('region', 'N/A')}")
        else:
            click.echo(f"  Error: {credential_status.get('error', 'Unknown error')}")
        click.echo()

        # Backup state
        click.echo("📊 Backup Status:")

        # Last sync information
        last_sync = backup_state.last_sync_time
        last_successful = backup_state.last_successful_sync

        click.echo(f"  Last Sync: {_format_datetime(last_sync)}")
        click.echo(f"  Last Successful: {_format_datetime(last_successful)}")

        # Sync statistics
        total_syncs = backup_state.total_syncs
        successful_syncs = backup_state.successful_syncs
        failed_syncs = backup_state.failed_syncs

        if total_syncs > 0:
            success_rate = (successful_syncs / total_syncs) * 100
            click.echo(f"  Total Syncs: {total_syncs}")
            click.echo(f"  Successful: {successful_syncs} ({success_rate:.1f}%)")
            click.echo(f"  Failed: {failed_syncs}")
            click.echo(f"  Consecutive Failures: {backup_state.consecutive_failures}")
        else:
            click.echo("  No backup operations recorded yet")

        click.echo()

        # Transfer statistics
        if backup_state.total_files_transferred > 0 or backup_state.total_bytes_transferred > 0:
            click.echo("📈 Transfer Statistics:")
            click.echo(f"  Total Files: {backup_state.total_files_transferred:,}")
            click.echo(f"  Total Data: {_format_bytes(backup_state.total_bytes_transferred)}")
            click.echo(f"  Total Time: {_format_duration(backup_state.total_sync_time)}")

            if backup_state.total_sync_time > 0:
                avg_rate = backup_state.total_bytes_transferred / backup_state.total_sync_time
                click.echo(f"  Average Rate: {_format_bytes(int(avg_rate))}/s")
            click.echo()

        # Last backup details
        if backup_state.last_stats:
            click.echo("🔄 Last Backup Details:")
            last_stats = backup_state.last_stats
            click.echo(f"  Status: {'✅ Success' if last_stats.success else '❌ Failed'}")
            click.echo(f"  Duration: {_format_duration(last_stats.duration_seconds)}")
            click.echo(f"  Files: {last_stats.files_transferred}/{last_stats.files_total}")
            click.echo(f"  Data: {_format_bytes(last_stats.bytes_transferred)}/{_format_bytes(last_stats.bytes_total)}")

            if last_stats.errors > 0:
                click.echo(f"  Errors: {last_stats.errors}")

            if verbose and last_stats.detailed_errors:
                click.echo("  Error Details:")
                for error in last_stats.detailed_errors[:5]:  # Show first 5 errors
                    if hasattr(error, "error_type"):
                        click.echo(f"    - {error.error_type.value}: {error.message}")
                    elif isinstance(error, dict):
                        click.echo(
                            f"    - {error.get('error_type', 'unknown')}: {error.get('message', 'Unknown error')}"
                        )

            click.echo()

        # Monitor status
        try:
            monitor = DriveMonitor(config_obj)
            monitor_status = monitor.get_status()

            click.echo("👁️  Monitor Status:")
            click.echo(f"  State: {monitor_status.get('state', 'Unknown')}")
            click.echo(f"  Watch Path: {monitor_status.get('watch_path', 'N/A')}")

            if monitor_status.get("drive_mounted"):
                click.echo("  Drive: ✅ Mounted")
            else:
                click.echo("  Drive: ❌ Not Mounted")

            click.echo(f"  Files Tracked: {monitor_status.get('files_tracked', 0):,}")
            click.echo(f"  Pending Changes: {monitor_status.get('pending_changes', 0)}")

            if verbose and monitor_status.get("last_check_time"):
                click.echo(f"  Last Check: {monitor_status['last_check_time']}")
            if verbose and monitor_status.get("last_change_time"):
                click.echo(f"  Last Change: {monitor_status['last_change_time']}")

            # Show persistent state info if available
            if verbose and monitor_status.get("total_checks") is not None:
                click.echo(f"  Total Checks: {monitor_status['total_checks']:,}")
                click.echo(f"  Total Changes Detected: {monitor_status['total_changes_detected']:,}")

            click.echo()
        except Exception as e:
            logger.debug(f"Could not get monitor status: {e}")
            click.echo("👁️  Monitor Status: Not available")
            click.echo()

        # System health
        click.echo("🏥 System Health:")

        # Check source directory
        source_path = Path(backup_info.get("source_path", ""))
        if source_path.exists():
            click.echo("  Source Directory: ✅ Accessible")
            if verbose:
                try:
                    file_count = len(list(source_path.rglob("*")))
                    click.echo(f"    Files: {file_count:,}")
                except PermissionError:
                    click.echo("    Files: Permission denied")
        else:
            click.echo("  Source Directory: ❌ Not accessible")

        # Check state directory
        state_dir = Path(backup_info.get("state_directory", ""))
        if state_dir.exists():
            click.echo("  State Directory: ✅ Accessible")
        else:
            click.echo("  State Directory: ❌ Not accessible")

        # Check rclone
        rclone_available, rclone_message, rclone_version = check_rclone()
        if rclone_available:
            click.echo(f"  rclone: ✅ Available ({rclone_version})")
        else:
            click.echo(f"  rclone: ❌ {rclone_message}")

        click.echo()

        # Recommendations
        recommendations = []

        if not credential_status.get("available"):
            recommendations.append("Configure credentials using environment variables or 1Password")

        if backup_state.consecutive_failures > 0:
            recommendations.append(f"Address {backup_state.consecutive_failures} consecutive backup failures")

        if not rclone_available:
            recommendations.append("Install rclone for backup operations")

        if not source_path.exists():
            recommendations.append("Check source directory path configuration")

        if recommendations:
            click.echo("💡 Recommendations:")
            for i, rec in enumerate(recommendations, 1):
                click.echo(f"  {i}. {rec}")
            click.echo()

        # Summary
        if backup_state.consecutive_failures == 0 and credential_status.get("available") and rclone_available:
            click.echo("✅ System Status: Healthy")
        elif backup_state.consecutive_failures > 0:
            click.echo("⚠️  System Status: Issues detected (consecutive failures)")
        else:
            click.echo("⚠️  System Status: Configuration issues")

        logger.info("Status command completed successfully")

    except Exception as e:
        logger.exception("An unexpected error occurred during status command execution")
        click.echo(f"❌ Error retrieving status: {e}")
        if verbose:
            import traceback

            click.echo("Detailed error information:")
            click.echo(traceback.format_exc())
        sys.exit(1)
