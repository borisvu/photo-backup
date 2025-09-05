#!/usr/bin/env python3
"""
Photo Backup System - Authentication CLI Commands

This module provides CLI commands for testing and validating credentials.
"""

import logging

import click

from ..config.config import Config
from ..credentials import CredentialManager


def _get_logger(config_obj: Config) -> logging.Logger:
    """Get configured logger for auth commands."""
    from ..logger import generate_job_id, setup_logger_from_config

    job_id = generate_job_id("auth")
    return setup_logger_from_config(config_obj, job_id, "photo_backup.auth")


@click.command()
@click.option("--verbose", "-v", is_flag=True, help="Show detailed credential information")
@click.pass_context
def test_auth(ctx, verbose):
    """Test credential setup and S3 access.

    This command validates your credential configuration and tests S3 access.
    In test mode, it will create a test bucket if needed.
    """
    # Get configuration from context
    test_mode = ctx.obj.get("test_mode", False)
    dry_run = ctx.obj.get("dry_run", False)

    config_obj = Config(test_mode=test_mode, dry_run=dry_run)
    logger = _get_logger(config_obj)

    mode_text = "TEST MODE" if test_mode else "PRODUCTION MODE"
    logger.info(f"Testing authentication in {mode_text}")
    click.echo(f"🔐 Testing authentication in {mode_text}")

    try:
        # Initialize credential manager
        manager = CredentialManager(config_obj)

        # Get credential status
        status = manager.get_credential_status()

        # Display basic status
        click.echo(f"📋 Mode: {status['mode']}")
        click.echo(f"🔑 Has credentials: {'✅ Yes' if status['has_credentials'] else '❌ No'}")

        if status["has_credentials"]:
            # Show credential info (masked)
            cred_info = status.get("credential_info", {})
            if cred_info:
                click.echo(f"🏢 Endpoint: {cred_info.get('endpoint', 'N/A')}")
                click.echo(f"📦 Bucket: {cred_info.get('bucket', 'N/A')}")
                click.echo(f"🌍 Region: {cred_info.get('region', 'N/A')}")
                click.echo(f"🔒 SSL: {'Enabled' if cred_info.get('use_ssl') else 'Disabled'}")

            # Show validation status
            validation = status.get("validation", {})
            if validation.get("is_valid"):
                click.echo("✅ Credential validation: PASSED")
            else:
                click.echo("❌ Credential validation: FAILED")
                click.echo(f"   Error: {validation.get('message', 'Unknown error')}")

            # Test S3 access
            click.echo("\n🔍 Testing S3 access...")
            is_valid, message = manager.validate_credentials()

            if is_valid:
                click.echo("✅ S3 access test: PASSED")
                click.echo(f"   {message}")

                # In test mode, ensure bucket exists
                if test_mode:
                    click.echo("\n🪣 Ensuring test bucket exists...")
                    _ensure_test_bucket(manager, logger)

            else:
                click.echo("❌ S3 access test: FAILED")
                click.echo(f"   {message}")

        else:
            # Show error details
            if status.get("error"):
                click.echo(f"❌ Error: {status['error']}")
            if status.get("suggestion"):
                click.echo(f"💡 Suggestion: {status['suggestion']}")
            if verbose and status.get("details"):
                click.echo(f"🔍 Details: {status['details']}")

        # Show verbose information if requested
        if verbose:
            click.echo("\n📊 Detailed Status:")
            for key, value in status.items():
                if key not in ["credential_info"]:  # Skip credential info in verbose mode
                    click.echo(f"   {key}: {value}")

        # Return appropriate exit code
        validation = status.get("validation", {})
        if status["has_credentials"] and validation.get("is_valid"):
            logger.info("Authentication test completed successfully")
            click.echo("\n🎉 Authentication test completed successfully!")
        else:
            logger.error("Authentication test failed")
            click.echo("\n💥 Authentication test failed!")
            import sys
            sys.exit(1)

    except Exception as e:
        logger.error(f"Unexpected error during authentication test: {e}")
        click.echo(f"💥 Unexpected error: {e}")
        import sys
        sys.exit(1)


def _ensure_test_bucket(manager: CredentialManager, logger: logging.Logger) -> None:
    """Ensure test bucket exists in Minio."""
    try:
        import subprocess

        # Get credentials for bucket creation
        credentials = manager.get_credentials()
        bucket = credentials.get("bucket", "test-bucket")
        endpoint = credentials.get("endpoint", "localhost:9000")

        # Use rclone to create bucket if it doesn't exist
        # First, try to list the bucket to see if it exists
        cmd = [
            "rclone", "ls", f"minio:{bucket}",
            "--config", "/dev/null",  # Use minimal config
            "--s3-endpoint", endpoint,
            "--s3-access-key-id", credentials["access_key"],
            "--s3-secret-access-key", credentials["secret_key"],
            "--s3-region", credentials.get("region", "us-east-1"),
            "--s3-no-ssl" if not credentials.get("use_ssl", False) else "",
        ]

        # Remove empty string arguments
        cmd = [arg for arg in cmd if arg]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

        if result.returncode == 0:
            click.echo(f"✅ Test bucket '{bucket}' already exists")
            logger.info(f"Test bucket '{bucket}' already exists")
        else:
            # Bucket doesn't exist, create it
            click.echo(f"🪣 Creating test bucket '{bucket}'...")

            # Use rclone mkdir to create bucket
            mkdir_cmd = [
                "rclone", "mkdir", f"minio:{bucket}",
                "--config", "/dev/null",
                "--s3-endpoint", endpoint,
                "--s3-access-key-id", credentials["access_key"],
                "--s3-secret-access-key", credentials["secret_key"],
                "--s3-region", credentials.get("region", "us-east-1"),
                "--s3-no-ssl" if not credentials.get("use_ssl", False) else "",
            ]

            # Remove empty string arguments
            mkdir_cmd = [arg for arg in mkdir_cmd if arg]

            mkdir_result = subprocess.run(mkdir_cmd, capture_output=True, text=True, timeout=10)

            if mkdir_result.returncode == 0:
                click.echo(f"✅ Test bucket '{bucket}' created successfully")
                logger.info(f"Test bucket '{bucket}' created successfully")
            else:
                click.echo(f"⚠️  Warning: Could not create test bucket '{bucket}'")
                click.echo(f"   Error: {mkdir_result.stderr.strip()}")
                logger.warning(f"Could not create test bucket '{bucket}': {mkdir_result.stderr.strip()}")

    except Exception as e:
        click.echo(f"⚠️  Warning: Could not ensure test bucket exists: {e}")
        logger.warning(f"Could not ensure test bucket exists: {e}")


# Export the command
test_auth_command = test_auth
