"""
Service management CLI commands.

This module provides CLI commands for managing the photo backup service:
- start: Start the service
- stop: Stop the service
- restart: Restart the service
- status: Show service status
"""

import sys

import click

from ..config.config import Config
from ..logger import generate_job_id, setup_logger_from_config
from ..service import ServiceManager


@click.command()
@click.option(
    "--background",
    "-b",
    is_flag=True,
    help="Run service in background (daemon mode)",
)
@click.option(
    "--foreground",
    "-f",
    is_flag=True,
    help="Run service in foreground (default in test mode)",
)
@click.pass_context
def start(ctx, background, foreground):
    """
    Start the photo backup service.

    The service will continuously monitor for changes and trigger backups
    as needed. In test mode, the service runs in foreground by default.
    In production mode, the service runs in background by default.

    Examples:
        photo-backup start               # Start with mode defaults
        photo-backup start --foreground  # Force foreground mode
        photo-backup start --background  # Force background mode
    """
    # Get context from main CLI
    test_mode = ctx.obj.get("test_mode", False)
    dry_run = ctx.obj.get("dry_run", False)

    # Load configuration
    config = Config(test_mode=test_mode, dry_run=dry_run)
    config.load_config()

    # Generate job ID for this service session
    job_id = generate_job_id("service")
    logger = setup_logger_from_config(config, job_id, "photo_backup.service")

    # Determine background mode
    if foreground and background:
        click.echo("Error: Cannot specify both --foreground and --background")
        sys.exit(1)

    if foreground:
        run_in_background = False
    elif background:
        run_in_background = True
    else:
        # Default: background in production, foreground in test mode
        run_in_background = config.get("service.background_mode", not test_mode)

    mode_text = "TEST MODE" if test_mode else "PRODUCTION MODE"
    run_mode_text = "background" if run_in_background else "foreground"

    logger.info(f"Starting photo backup service in {mode_text}")
    logger.info(f"Run mode: {run_mode_text}")

    click.echo(f"Starting photo backup service ({mode_text}, {run_mode_text})...")

    if dry_run:
        click.echo("DRY RUN MODE: Backups will be simulated only")
        logger.info("Service starting in dry-run mode")

    # Display configuration
    click.echo(f"Monitor path: {config.get('backup.source_path')}")
    click.echo(f"Destination: {config.get('backup.destination')}")
    click.echo(f"Check interval: {config.get('monitoring.check_interval_hours')} hours")
    click.echo(f"Loop interval: {config.get('service.loop_interval_seconds')} seconds")

    try:
        # Create service manager
        service = ServiceManager(config, logger=logger)
        logger.info("ServiceManager created successfully")

        if run_in_background:
            # TODO: Implement proper daemonization for Task 75 production use
            # For now, we'll run in foreground even if background requested
            click.echo("Note: Background mode not fully implemented yet, running in foreground")
            logger.warning("Background mode requested but not implemented, running in foreground")

        click.echo("Service starting...")
        click.echo("Press Ctrl+C to stop the service")

        # Start service (blocks until stopped)
        service.start()

        click.echo("Service stopped.")
        logger.info("Service stopped normally")

    except KeyboardInterrupt:
        click.echo("\nService interrupted by user")
        logger.info("Service interrupted by user (Ctrl+C)")
    except Exception as e:
        click.echo(f"Error starting service: {e}", err=True)
        logger.error(f"Failed to start service: {e}", exc_info=True)
        sys.exit(1)


@click.command()
@click.pass_context
def stop(ctx):
    """
    Stop the photo backup service.

    Sends a shutdown signal to the running service and waits for
    graceful termination.

    Examples:
        photo-backup stop
    """
    test_mode = ctx.obj.get("test_mode", False)

    config = Config(test_mode=test_mode)
    config.load_config()

    job_id = generate_job_id("stop")
    logger = setup_logger_from_config(config, job_id, "photo_backup.service")

    click.echo("Stop command not yet implemented")
    click.echo("Use Ctrl+C to stop a running service")
    logger.info("Stop command called (not yet implemented)")


@click.command()
@click.pass_context
def restart(ctx):
    """
    Restart the photo backup service.

    Stops the service if running and then starts it again.
    State is preserved across the restart.

    Examples:
        photo-backup restart
    """
    test_mode = ctx.obj.get("test_mode", False)

    config = Config(test_mode=test_mode)
    config.load_config()

    job_id = generate_job_id("restart")
    logger = setup_logger_from_config(config, job_id, "photo_backup.service")

    click.echo("Restart command not yet implemented")
    logger.info("Restart command called (not yet implemented)")
