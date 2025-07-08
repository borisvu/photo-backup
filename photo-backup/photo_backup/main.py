#!/usr/bin/env python3
"""
Photo Backup System - Main CLI Entry Point

This module provides the command-line interface for the photo backup system.
"""

import logging
import os
import click
from .__version__ import __version__
from .config import Config
from .logger import setup_logger
from .utils import format_bytes, ensure_directory


def _get_logger(test_mode: bool) -> logging.Logger:
    """Get configured logger based on mode."""
    log_level = logging.DEBUG if test_mode else logging.INFO
    return setup_logger("photo_backup", log_level)


def _log_operation(logger: logging.Logger, test_mode: bool, message: str, level: str = "info") -> None:
    """Log operation with appropriate level based on mode."""
    if level == "debug" or test_mode:
        logger.debug(message)
    else:
        logger.info(message)


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


@main.command()
@click.argument('bytes_value', type=int)
@click.pass_context
def format_size(ctx, bytes_value):
    """Format bytes value to human-readable size.
    
    BYTES_VALUE: Number of bytes to format (e.g., 1048576 for 1 MB)
    """
    test_mode = ctx.obj.get('test_mode', False)
    logger = _get_logger(test_mode)
    
    formatted = format_bytes(bytes_value)
    _log_operation(logger, test_mode, f"Formatted {bytes_value} bytes to {formatted}")
    
    click.echo(f"{bytes_value} bytes = {formatted}")


@main.command()
@click.argument('directory_path')
@click.pass_context
def create_dir(ctx, directory_path):
    """Create a directory if it doesn't exist.
    
    DIRECTORY_PATH: Path to the directory to create
    """
    test_mode = ctx.obj.get('test_mode', False)
    logger = _get_logger(test_mode)
    
    success, error = ensure_directory(directory_path)
    
    if success:
        _log_operation(logger, test_mode, f"Successfully ensured directory exists: {directory_path}")
        click.echo(f"✓ Directory ready: {directory_path}")
    else:
        logger.error(f"Failed to create directory {directory_path}: {error}")
        click.echo(f"✗ Failed to create directory: {error}")
        ctx.exit(1)


@main.command()
@click.pass_context
def test_utils(ctx):
    """Test utility functions with sample data."""
    test_mode = ctx.obj.get('test_mode', False)
    logger = _get_logger(test_mode)
    
    _log_operation(logger, test_mode, "Running utility function tests")
    
    click.echo("Testing utility functions:")
    click.echo()
    
    # Test format_bytes with various sizes
    click.echo("format_bytes() test:")
    test_sizes = [0, 512, 1024, 1536, 1048576, 1073741824, 1099511627776]
    for size in test_sizes:
        formatted = format_bytes(size)
        click.echo(f"  {size:>12} bytes -> {formatted}")
        logger.debug(f"format_bytes({size}) = {formatted}")
    
    click.echo()
    
    # Test ensure_directory
    click.echo("ensure_directory() test:")
    test_dir = "/tmp/photo-backup-utils-test"
    success, error = ensure_directory(test_dir)
    
    if success:
        click.echo(f"  ✓ Created directory: {test_dir}")
        _log_operation(logger, test_mode, f"Successfully created test directory: {test_dir}")
        
        # Clean up
        try:
            os.rmdir(test_dir)
            click.echo(f"  ✓ Cleaned up test directory")
            logger.debug(f"Cleaned up test directory: {test_dir}")
        except OSError as e:
            click.echo(f"  ⚠ Could not clean up test directory: {e}")
            logger.warning(f"Could not clean up test directory: {e}")
    else:
        click.echo(f"  ✗ Failed to create directory: {error}")
        logger.error(f"Failed to create test directory: {error}")
    
    _log_operation(logger, test_mode, "Utility function tests completed")


if __name__ == "__main__":
    main()