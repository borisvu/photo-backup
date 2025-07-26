"""
Configuration-related CLI commands.

This module contains commands for viewing and validating configuration settings.
"""

from typing import Any

import click

from ..config.config import Config
from ..config.env_override import EnvOverride


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


@click.command()
@click.pass_context
def config(ctx):
    """Display current configuration settings."""
    # Get test mode from CLI flag, or check environment variable
    test_mode = ctx.obj.get("test_mode", False)

    # If not set via CLI, check if Config would detect it from environment
    if not test_mode:
        test_mode = EnvOverride.is_test_mode_enabled()

    config_obj = Config(test_mode=test_mode)
    config_data = config_obj.load_config()

    # Header
    click.echo("Configuration for Photo Backup System")
    click.echo("=" * 40)

    # Mode and file info
    mode_text = "TEST MODE" if test_mode else "PRODUCTION MODE"
    click.echo(f"\nMode: {mode_text}")

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
