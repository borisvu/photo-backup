"""
Configuration-related CLI commands.

This module contains commands for viewing and validating configuration settings.
"""

import sys
from typing import Any

import click

from ..config.config import Config
from ..config.env_override import EnvOverride
from ..fs_utils import validate_path
from ..logger import generate_job_id, setup_logger_from_config
from ..process_utils import run_command


def _format_config_value(key: str, value: Any) -> str:
    """Format configuration value for display, masking sensitive information."""
    # Mask sensitive keys
    sensitive_keys = ["secret_key", "access_key", "password", "token"]

    if any(sensitive in key.lower() for sensitive in sensitive_keys):
        if value and isinstance(value, str) and len(value) > 4:
            return f"{value[:4]}{'*' * (len(value) - 4)}"
        else:
            return "[HIDDEN]"

    return str(value)


def _display_config_section(section_name: str, section_data: dict) -> None:
    """Display a configuration section with proper formatting."""
    click.echo(f"\n{section_name.title()} Settings:")

    for key, value in section_data.items():
        full_key = f"{section_name}.{key}"
        formatted_value = _format_config_value(full_key, value)

        # Format key name nicely
        display_key = key.replace("_", " ").title()
        click.echo(f"  {display_key}: {formatted_value}")


def _check_rclone_availability() -> tuple[bool, str]:
    """Check if rclone command is available in PATH."""
    result = run_command(["rclone", "version"], timeout=10.0)

    if result["returncode"] == 0:
        return True, "rclone is available"
    else:
        return False, f"rclone not found or not working: {result['stderr']}"


def _test_minio_connection(endpoint: str, _access_key: str, _secret_key: str) -> tuple[bool, str]:
    """Test basic connectivity to Minio endpoint."""
    try:
        # Use curl to test basic connectivity (simpler than full S3 client)
        # Test if we can reach the endpoint
        result = run_command(
            ["curl", "-s", "-o", "/dev/null", "-w", "%{http_code}", f"http://{endpoint}"], timeout=10.0
        )

        if result["returncode"] == 0 and result["stdout"].strip() in ["200", "403", "401"]:
            return True, f"Minio endpoint {endpoint} is reachable"
        else:
            return False, f"Cannot reach Minio endpoint {endpoint}: {result['stderr']}"

    except Exception as e:
        return False, f"Error testing Minio connection: {e!s}"


@click.command()
@click.pass_context
def config(ctx):
    """Display current configuration settings."""
    # Get test mode and dry-run from CLI flags, or check environment variable
    test_mode = ctx.obj.get("test_mode", False)
    dry_run = ctx.obj.get("dry_run", False)

    # If not set via CLI, check if Config would detect it from environment
    if not test_mode:
        test_mode = EnvOverride.is_test_mode_enabled()

    config_obj = Config(test_mode=test_mode, dry_run=dry_run)

    # Load and validate configuration
    try:
        config_data = config_obj.load_config()
    except ValueError as e:
        # Configuration validation failed - show clean error without traceback
        click.echo("❌ Configuration Error:", err=True)
        click.echo(str(e), err=True)
        sys.exit(1)

    # Set up logger with job context
    job_id = generate_job_id("config")
    logger = setup_logger_from_config(config_obj, job_id, "photo_backup.config")
    logger.info("Configuration display command started")
    logger.debug(f"Test mode: {test_mode}, Dry run: {dry_run}")

    # Header
    click.echo("Configuration for Photo Backup System")
    click.echo("=" * 40)

    # Mode and file info
    mode_text = "TEST MODE" if test_mode else "PRODUCTION MODE"
    dry_run_text = " (DRY RUN)" if config_obj.is_dry_run() else ""
    click.echo(f"\nMode: {mode_text}{dry_run_text}")

    config_file_path = config_obj.get_config_file_path()
    if config_file_path:
        click.echo(f"Config File: {config_file_path}")
    else:
        click.echo("Config File: Using defaults")

    # Environment overrides
    env_info = config_obj.get_env_override_info()
    if env_info["override_count"] > 0:
        click.echo(f"\nEnvironment Overrides: {env_info['override_count']} variables")
        for env_var in env_info["env_vars_used"]:
            click.echo(f"  - {env_var}")
    else:
        click.echo("\nEnvironment Overrides: None")

    # Configuration sections in logical order
    section_order = ["backup", "storage", "monitoring", "logging", "state", "security", "performance", "notifications"]

    # Display each section
    for section_name in section_order:
        if section_name in config_data:
            _display_config_section(section_name, config_data[section_name])
            logger.debug(f"Displayed {section_name} configuration section")

    logger.info("Configuration display completed successfully")
    click.echo("\nConfiguration display completed.")


@click.command()
@click.pass_context
def validate(ctx):
    """Validate configuration settings and system requirements."""
    # Get test mode and dry-run from CLI flags, or check environment variable
    test_mode = ctx.obj.get("test_mode", False)
    dry_run = ctx.obj.get("dry_run", False)

    # If not set via CLI, check if Config would detect it from environment
    if not test_mode:
        test_mode = EnvOverride.is_test_mode_enabled()

    config_obj = Config(test_mode=test_mode, dry_run=dry_run)

    # Load and validate configuration
    try:
        config_data = config_obj.load_config()
    except ValueError as e:
        # Configuration validation failed - show clean error without traceback
        click.echo("❌ Configuration Error:", err=True)
        click.echo(str(e), err=True)
        sys.exit(1)

    # Set up logger with job context
    job_id = generate_job_id("validate")
    logger = setup_logger_from_config(config_obj, job_id, "photo_backup.validate")
    logger.info("Configuration validation command started")
    logger.debug(f"Test mode: {test_mode}, Dry run: {dry_run}")

    # Header
    click.echo("Configuration Validation for Photo Backup System")
    click.echo("=" * 50)

    mode_text = "TEST MODE" if test_mode else "PRODUCTION MODE"
    dry_run_text = " (DRY RUN)" if config_obj.is_dry_run() else ""
    click.echo(f"\nMode: {mode_text}{dry_run_text}")

    # Track validation results
    all_valid = True
    validation_results = []

    # 1. Validate configuration structure and values
    click.echo("\n1. Configuration Validation:")
    is_config_valid, config_errors = config_obj.validator.validate_config(config_data)

    if is_config_valid:
        click.echo("   ✅ Configuration structure and values are valid")
        validation_results.append(("Configuration", True, "Valid"))
    else:
        click.echo("   ❌ Configuration validation failed:")
        for error in config_errors:
            click.echo(f"      - {error}")
        validation_results.append(("Configuration", False, f"{len(config_errors)} errors"))
        all_valid = False

    # 2. Validate paths
    click.echo("\n2. Path Validation:")

    # Backup source path
    backup_source = config_data.get("backup", {}).get("source_path")
    if backup_source:
        is_valid, error = validate_path(backup_source)
        if is_valid:
            click.echo(f"   ✅ Backup source path: {backup_source}")
            validation_results.append(("Backup Source Path", True, "Valid"))
        else:
            click.echo(f"   ❌ Backup source path: {backup_source}")
            click.echo(f"      Error: {error}")
            validation_results.append(("Backup Source Path", False, error))
            all_valid = False

    # Logging directory
    log_dir = config_data.get("logging", {}).get("directory")
    if log_dir:
        is_valid, error = validate_path(log_dir)
        if is_valid:
            click.echo(f"   ✅ Logging directory: {log_dir}")
            validation_results.append(("Logging Directory", True, "Valid"))
        else:
            click.echo(f"   ❌ Logging directory: {log_dir}")
            click.echo(f"      Error: {error}")
            validation_results.append(("Logging Directory", False, error))
            all_valid = False

    # State directory
    state_dir = config_data.get("state", {}).get("directory")
    if state_dir:
        is_valid, error = validate_path(state_dir)
        if is_valid:
            click.echo(f"   ✅ State directory: {state_dir}")
            validation_results.append(("State Directory", True, "Valid"))
        else:
            click.echo(f"   ❌ State directory: {state_dir}")
            click.echo(f"      Error: {error}")
            validation_results.append(("State Directory", False, error))
            all_valid = False

    # 3. Check rclone availability
    click.echo("\n3. Rclone Availability:")
    rclone_available, rclone_message = _check_rclone_availability()
    if rclone_available:
        click.echo("   ✅ Rclone is available")
        validation_results.append(("Rclone", True, "Available"))
    else:
        click.echo(f"   ⚠️  Rclone: {rclone_message}")
        validation_results.append(("Rclone", False, rclone_message))
        # Don't fail validation for missing rclone, just warn

    # 4. Test Minio connection (test mode only)
    if test_mode:
        click.echo("\n4. Minio Connection Test:")
        endpoint = config_data.get("storage", {}).get("endpoint")
        access_key = config_data.get("storage", {}).get("access_key")
        secret_key = config_data.get("storage", {}).get("secret_key")

        if endpoint and access_key and secret_key:
            minio_ok, minio_message = _test_minio_connection(endpoint, access_key, secret_key)
            if minio_ok:
                click.echo(f"   ✅ {minio_message}")
                validation_results.append(("Minio Connection", True, "Connected"))
            else:
                click.echo(f"   ❌ {minio_message}")
                validation_results.append(("Minio Connection", False, minio_message))
                all_valid = False
        else:
            click.echo("   ❌ Missing Minio configuration (endpoint, access_key, or secret_key)")
            validation_results.append(("Minio Connection", False, "Missing configuration"))
            all_valid = False

    # Summary
    click.echo("\n" + "=" * 50)
    click.echo("VALIDATION SUMMARY:")

    passed = sum(1 for _, valid, _ in validation_results if valid)
    total = len(validation_results)

    for check_name, is_valid, message in validation_results:
        status = "✅ PASS" if is_valid else "❌ FAIL"
        click.echo(f"  {status} {check_name}: {message}")

    click.echo(f"\nOverall Status: {'✅ VALID' if all_valid else '❌ INVALID'}")
    click.echo(f"Passed: {passed}/{total} checks")

    if all_valid:
        click.echo("\n🎉 Configuration is valid and ready for use!")
        sys.exit(0)
    else:
        click.echo("\n⚠️  Please fix the issues above before proceeding.")
        sys.exit(1)


@click.command()
@click.pass_context
def setup_config(ctx):
    """Create user config directory and copy example configuration."""
    # Get test mode and dry-run from CLI flags, or check environment variable
    test_mode = ctx.obj.get("test_mode", False)
    dry_run = ctx.obj.get("dry_run", False)

    # If not set via CLI, check if Config would detect it from environment
    if not test_mode:
        test_mode = EnvOverride.is_test_mode_enabled()

    config_obj = Config(test_mode=test_mode, dry_run=dry_run)

    # Create user config directory
    success, message = config_obj.loader.create_user_config_directory()

    # Header
    click.echo("Photo Backup Configuration Setup")
    click.echo("=" * 35)

    mode_text = "TEST MODE" if test_mode else "PRODUCTION MODE"
    dry_run_text = " (DRY RUN)" if dry_run else ""
    click.echo(f"\nMode: {mode_text}{dry_run_text}")

    if success:
        click.echo(f"✅ {message}")

        # Show next steps
        click.echo("\n📝 Next Steps:")
        if test_mode:
            click.echo("1. Configuration created for testing")
            click.echo("2. Run 'photo-backup validate --test-mode' to verify setup")
        else:
            click.echo("1. Edit the configuration file with your settings:")
            if "config.yaml" in message:
                config_path = message.split("to ")[-1] if "to " in message else "~/.config/photo-backup/config.yaml"
                click.echo(f"   {config_path}")
            click.echo("2. Update storage credentials and backup paths")
            click.echo("3. Run 'photo-backup validate' to verify your configuration")
            click.echo("4. Run 'photo-backup config' to view current settings")

        sys.exit(0)
    else:
        click.echo(f"❌ {message}")
        sys.exit(1)
