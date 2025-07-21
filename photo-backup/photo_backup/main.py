#!/usr/bin/env python3
"""
Photo Backup System - Main CLI Entry Point

This module provides the command-line interface for the photo backup system.
"""

import logging
import click
from .__version__ import __version__
from .config.config import Config
from .logger import setup_logger


def _get_logger(test_mode: bool) -> logging.Logger:
    """Get configured logger based on mode."""
    log_level = logging.DEBUG if test_mode else logging.INFO
    return setup_logger("photo_backup", log_level)


@click.group(invoke_without_command=True)
@click.option('--test-mode', is_flag=True, help='Run in test mode using Minio instead of Wasabi')
@click.option('--version', is_flag=True, help='Show version and exit')
@click.pass_context
def main(ctx, test_mode, version):
    """Photo Backup System - Automated photo backup to S3-compatible storage."""
    
    if version:
        click.echo(f"Photo Backup v{__version__}")
        return
    
    # Store context for subcommands
    ctx.ensure_object(dict)
    ctx.obj['test_mode'] = test_mode
    
    # If no subcommand provided, show system status
    if ctx.invoked_subcommand is None:
        config = Config(test_mode=test_mode)
        settings = config.load_config()
        logger = _get_logger(test_mode)
        
        mode_text = "TEST MODE" if test_mode else "PRODUCTION MODE"
        logger.info(f"Photo Backup v{__version__} starting in {mode_text}")
        
        click.echo(f"Photo Backup v{__version__}")
        
        if test_mode:
            logger.debug("Initializing test mode configuration")
            click.echo("Running in TEST MODE - using Minio instead of Wasabi")
            click.echo("Test mode configuration:")
            click.echo(f"  - Endpoint: {config.get('storage.endpoint')}")
            click.echo(f"  - Credentials: {config.get('storage.access_key')}/{config.get('storage.secret_key')}")
            click.echo(f"  - Source: {config.get('backup.source_path')}")
            click.echo(f"  - Destination: {config.get('backup.destination')}")
            click.echo(f"  - State directory: {config.get('state.directory')}")
            logger.debug(f"Test mode endpoint: {config.get('storage.endpoint')}")
            logger.debug(f"Test mode source: {config.get('backup.source_path')}")
        else:
            logger.info("Initializing production mode configuration")
            click.echo("Running in PRODUCTION MODE")
            click.echo("Configuration:")
            click.echo(f"  - Source: {config.get('backup.source_path')}")
            click.echo(f"  - Destination: {config.get('backup.destination')}")
            click.echo(f"  - Endpoint: {config.get('storage.endpoint')}")
            click.echo(f"  - State directory: {config.get('state.directory')}")
            logger.info(f"Production mode endpoint: {config.get('storage.endpoint')}")
            logger.info(f"Production mode source: {config.get('backup.source_path')}")
        
        logger.info("CLI initialization completed successfully")
        click.echo("CLI interface ready. Use 'photo-backup --help' to see available commands.")


if __name__ == "__main__":
    main()