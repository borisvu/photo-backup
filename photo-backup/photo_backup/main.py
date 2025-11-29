#!/usr/bin/env python3
"""
Photo Backup System - Main CLI Entry Point

This module provides the command-line interface for the photo backup system.
"""

import logging

import click

from .__version__ import __version__
from .cli.auth_commands import test_auth
from .cli.config_commands import config, setup_config, validate
from .cli.log_commands import logs
from .cli.service_commands import restart, start, stop
from .cli.status_commands import status
from .cli.sync_commands import sync
from .config.config import Config
from .logger import generate_job_id, setup_logger_from_config


def _get_logger(config_obj: Config, job_id: str | None = None) -> logging.Logger:
    """Get configured logger using config settings."""
    return setup_logger_from_config(config_obj, job_id, "photo_backup")


@click.group(invoke_without_command=True)
@click.option(
    "--test-mode",
    is_flag=True,
    help="Run in test mode with optimized defaults for testing (faster intervals, debug logging, temp paths). Storage backend determined by config.",
)
@click.option("--dry-run", is_flag=True, help="Run in dry-run mode - show operations without executing them")
@click.option("--version", is_flag=True, help="Show version and exit")
@click.pass_context
def main(ctx, test_mode, dry_run, version):
    """Photo Backup System - Automated photo backup to S3-compatible storage.

    Works with any S3-compatible backend (Wasabi, MinIO, AWS S3, etc.).
    Storage backend is configured via config file, not by mode flags.
    """

    if version:
        click.echo(f"Photo Backup v{__version__}")
        return

    # Store context for subcommands
    ctx.ensure_object(dict)
    ctx.obj["test_mode"] = test_mode
    ctx.obj["dry_run"] = dry_run

    # If no subcommand provided, show system status
    if ctx.invoked_subcommand is None:
        config_obj = Config(test_mode=test_mode, dry_run=dry_run)
        config_obj.load_config()  # Load config but don't store result

        # Generate job ID for this CLI session
        job_id = generate_job_id("cli")
        logger = _get_logger(config_obj, job_id)

        mode_text = "TEST MODE" if test_mode else "PRODUCTION MODE"
        dry_run_text = " (DRY RUN)" if dry_run else ""
        logger.info(f"Photo Backup v{__version__} starting in {mode_text}{dry_run_text}")

        click.echo(f"Photo Backup v{__version__}")

        if test_mode:
            logger.debug("Initializing test mode configuration")
            click.echo(f"Running in TEST MODE{dry_run_text} - using Minio instead of Wasabi")
            click.echo("Test mode configuration:")
            click.echo(f"  - Endpoint: {config_obj.get('storage.endpoint')}")
            click.echo(
                f"  - Credentials: {config_obj.get('storage.access_key')}/{config_obj.get('storage.secret_key')}"
            )
            click.echo(f"  - Source: {config_obj.get('backup.source_path')}")
            click.echo(f"  - Destination: {config_obj.get('backup.destination')}")
            click.echo(f"  - State directory: {config_obj.get('state.directory')}")
            click.echo(f"  - Log level: {config_obj.get('logging.level')}")
            click.echo(f"  - Log format: {config_obj.get('logging.format')}")
            if dry_run:
                click.echo("  - DRY RUN MODE: Operations will be shown but not executed")
            logger.debug(f"Test mode endpoint: {config_obj.get('storage.endpoint')}")
            logger.debug(f"Test mode source: {config_obj.get('backup.source_path')}")
            logger.debug(f"Test mode log level: {config_obj.get('logging.level')}")
        else:
            logger.info("Initializing production mode configuration")
            click.echo(f"Running in PRODUCTION MODE{dry_run_text}")
            click.echo("Configuration:")
            click.echo(f"  - Source: {config_obj.get('backup.source_path')}")
            click.echo(f"  - Destination: {config_obj.get('backup.destination')}")
            click.echo(f"  - Endpoint: {config_obj.get('storage.endpoint')}")
            click.echo(f"  - State directory: {config_obj.get('state.directory')}")
            click.echo(f"  - Log level: {config_obj.get('logging.level')}")
            click.echo(f"  - Log format: {config_obj.get('logging.format')}")
            if dry_run:
                click.echo("  - DRY RUN MODE: Operations will be shown but not executed")
            logger.info(f"Production mode endpoint: {config_obj.get('storage.endpoint')}")
            logger.info(f"Production mode source: {config_obj.get('backup.source_path')}")
            logger.info(f"Production mode log level: {config_obj.get('logging.level')}")

        logger.info("CLI initialization completed successfully")
        click.echo("CLI interface ready. Use 'photo-backup --help' to see available commands.")


# Register CLI commands
main.add_command(config)
main.add_command(setup_config)
main.add_command(validate)
main.add_command(logs)
main.add_command(status)
main.add_command(test_auth)
main.add_command(sync)
# Service management commands
main.add_command(start)
main.add_command(stop)
main.add_command(restart)


if __name__ == "__main__":
    main()
