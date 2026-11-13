"""
Service management CLI commands.

This module provides CLI commands for managing the photo backup service:
- start: Start the service
- stop: Stop the service
- restart: Restart the service
- status: Show service status
"""

import os
import signal
import sys
import time

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
def start(ctx: click.Context, background: bool, foreground: bool) -> None:
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
    try:
        config.load_config()
    except ValueError as e:
        # Configuration validation failed - show clean error without traceback
        click.echo("❌ Configuration Error:", err=True)
        click.echo(str(e), err=True)
        sys.exit(1)

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
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Force stop using SIGKILL if graceful shutdown fails",
)
@click.option(
    "--timeout",
    "-t",
    type=int,
    default=10,
    help="Timeout in seconds to wait for graceful shutdown (default: 10)",
)
@click.pass_context
def stop(ctx: click.Context, force: bool, timeout: int) -> None:
    """
    Stop the photo backup service.

    Sends a shutdown signal to the running service and waits for
    graceful termination.

    Examples:
        photo-backup stop               # Graceful shutdown with 10s timeout
        photo-backup stop --force       # Force kill if graceful fails
        photo-backup stop --timeout 30  # Wait up to 30 seconds
    """
    test_mode = ctx.obj.get("test_mode", False)

    config = Config(test_mode=test_mode)
    try:
        config.load_config()
    except ValueError as e:
        # Configuration validation failed - show clean error without traceback
        click.echo("❌ Configuration Error:", err=True)
        click.echo(str(e), err=True)
        sys.exit(1)

    job_id = generate_job_id("stop")
    logger = setup_logger_from_config(config, job_id, "photo_backup.service")

    logger.info("=" * 60)
    logger.info("STOP COMMAND INITIATED")
    logger.info("=" * 60)
    logger.info(f"Mode: {'TEST' if test_mode else 'PRODUCTION'}")
    logger.info(f"Force: {force}")
    logger.info(f"Timeout: {timeout}s")

    # Get running service PID
    pid = ServiceManager.get_running_pid(test_mode=test_mode)

    if pid is None:
        click.echo("Service is not running")
        logger.info("No running service found")
        logger.info("=" * 60)
        return

    click.echo(f"Stopping service (PID {pid})...")
    logger.info(f"Found running service: PID {pid}")
    logger.info(f"Sending SIGTERM to PID {pid}")

    try:
        # Send SIGTERM for graceful shutdown
        os.kill(pid, signal.SIGTERM)

        # Wait for process to exit
        start_time = time.time()
        while time.time() - start_time < timeout:
            if not ServiceManager._is_process_running(pid):
                elapsed = time.time() - start_time
                click.echo("Service stopped successfully")
                logger.info(f"Service stopped (PID {pid}, took {elapsed:.1f}s)")
                logger.info("=" * 60)
                return
            time.sleep(0.1)

        # Timeout reached
        if force:
            click.echo(f"Graceful shutdown timed out after {timeout}s, forcing stop...")
            logger.warning(f"Graceful shutdown timeout, sending SIGKILL to PID {pid}")
            os.kill(pid, signal.SIGKILL)
            time.sleep(0.5)
            if not ServiceManager._is_process_running(pid):
                click.echo("Service force stopped")
                logger.info(f"Service force stopped (PID {pid})")
            else:
                click.echo("Failed to stop service", err=True)
                logger.error(f"Failed to kill PID {pid}")
                sys.exit(1)
        else:
            click.echo(
                f"Service did not stop within {timeout}s. Use --force to force stop or increase --timeout",
                err=True,
            )
            logger.warning(f"Service did not stop within {timeout}s")
            sys.exit(1)

    except ProcessLookupError:
        click.echo("Service was already stopped")
        logger.info("Process already terminated")
    except PermissionError:
        click.echo("Permission denied: cannot stop service", err=True)
        logger.error(f"Permission denied stopping PID {pid}")
        sys.exit(1)
    except Exception as e:
        click.echo(f"Error stopping service: {e}", err=True)
        logger.error(f"Error stopping service: {e}", exc_info=True)
        sys.exit(1)


@click.command()
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Force stop if graceful shutdown fails",
)
@click.pass_context
def restart(ctx: click.Context, force: bool) -> None:
    """
    Restart the photo backup service.

    Stops the service if running and then starts it again.
    State is preserved across the restart.

    Examples:
        photo-backup restart        # Graceful restart
        photo-backup restart --force # Force stop if needed
    """
    test_mode = ctx.obj.get("test_mode", False)
    dry_run = ctx.obj.get("dry_run", False)

    config = Config(test_mode=test_mode, dry_run=dry_run)
    try:
        config.load_config()
    except ValueError as e:
        # Configuration validation failed - show clean error without traceback
        click.echo("❌ Configuration Error:", err=True)
        click.echo(str(e), err=True)
        sys.exit(1)

    job_id = generate_job_id("restart")
    logger = setup_logger_from_config(config, job_id, "photo_backup.service")

    logger.info("=" * 60)
    logger.info("RESTART COMMAND INITIATED")
    logger.info("=" * 60)
    logger.info(f"Mode: {'TEST' if test_mode else 'PRODUCTION'}")
    logger.info(f"Dry run: {dry_run}")
    logger.info(f"Force: {force}")

    # Check if service is running
    pid = ServiceManager.get_running_pid(test_mode=test_mode)

    if pid is not None:
        click.echo(f"Stopping service (PID {pid})...")
        logger.info(f"Stopping existing service (PID {pid})")

        try:
            # Send SIGTERM for graceful shutdown
            os.kill(pid, signal.SIGTERM)

            # Wait for process to exit (10 second timeout)
            timeout = 10
            start_time = time.time()
            while time.time() - start_time < timeout:
                if not ServiceManager._is_process_running(pid):
                    click.echo("Service stopped")
                    logger.info("Service stopped successfully")
                    break
                time.sleep(0.1)
            else:
                # Timeout reached
                if force:
                    click.echo("Graceful shutdown timed out, forcing stop...")
                    logger.warning("Forcing stop with SIGKILL")
                    os.kill(pid, signal.SIGKILL)
                    time.sleep(0.5)
                else:
                    click.echo(
                        "Service did not stop within 10s. Use --force to force restart",
                        err=True,
                    )
                    logger.error("Graceful shutdown timeout, aborting restart")
                    sys.exit(1)

        except ProcessLookupError:
            click.echo("Service was already stopped")
            logger.info("Process already terminated")
        except Exception as e:
            click.echo(f"Error stopping service: {e}", err=True)
            logger.error(f"Error stopping service: {e}", exc_info=True)
            sys.exit(1)

    else:
        click.echo("Service is not running")
        logger.info("No running service found")

    # Brief pause before restart
    time.sleep(0.5)

    # Start service using the start command logic
    click.echo("\nStarting service...")
    logger.info("Starting service after stop")

    mode_text = "TEST MODE" if test_mode else "PRODUCTION MODE"
    run_in_background = config.get("service.background_mode", not test_mode)
    run_mode_text = "background" if run_in_background else "foreground"

    click.echo(f"Starting photo backup service ({mode_text}, {run_mode_text})...")

    if dry_run:
        click.echo("DRY RUN MODE: Backups will be simulated only")

    click.echo(f"Monitor path: {config.get('backup.source_path')}")
    click.echo(f"Destination: {config.get('backup.destination')}")

    try:
        service = ServiceManager(config, logger=logger)

        if run_in_background:
            click.echo("Note: Background mode not fully implemented yet, running in foreground")
            logger.warning("Background mode requested but not implemented")

        click.echo("Service starting...")
        click.echo("Press Ctrl+C to stop the service")

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
