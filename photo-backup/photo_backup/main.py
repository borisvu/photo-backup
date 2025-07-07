#!/usr/bin/env python3
"""
Photo Backup System - Main CLI Entry Point

This module provides the command-line interface for the photo backup system.
"""

import click
from .__version__ import __version__
from .config import Config


@click.command()
@click.option('--test-mode', is_flag=True, help='Run in test mode using Minio instead of Wasabi')
@click.option('--version', is_flag=True, help='Show version and exit')
def main(test_mode, version):
    """Photo Backup System - Automated photo backup to S3-compatible storage."""
    
    if version:
        click.echo(f"Photo Backup v{__version__}")
        return
    
    # Initialize configuration
    config = Config(test_mode=test_mode)
    settings = config.load_config()
    
    # Display startup message
    click.echo(f"Photo Backup v{__version__}")
    
    if test_mode:
        click.echo("Running in TEST MODE - using Minio instead of Wasabi")
        click.echo("Test mode configuration:")
        click.echo(f"  - Endpoint: {config.get('storage.endpoint')}")
        click.echo(f"  - Credentials: {config.get('storage.access_key')}/{config.get('storage.secret_key')}")
        click.echo(f"  - Source: {config.get('backup.source_path')}")
        click.echo(f"  - Destination: {config.get('backup.destination')}")
        click.echo(f"  - State directory: {config.get('state.directory')}")
    else:
        click.echo("Running in PRODUCTION MODE")
        click.echo("Configuration:")
        click.echo(f"  - Source: {config.get('backup.source_path')}")
        click.echo(f"  - Destination: {config.get('backup.destination')}")
        click.echo(f"  - Endpoint: {config.get('storage.endpoint')}")
        click.echo(f"  - State directory: {config.get('state.directory')}")
    
    # For now, just show the mode and exit
    click.echo("CLI interface ready. Additional commands will be added in future tasks.")


if __name__ == "__main__":
    main()