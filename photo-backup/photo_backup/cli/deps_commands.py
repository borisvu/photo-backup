"""
Dependency checking CLI commands.

This module provides CLI commands for checking system dependencies.
"""

import sys

import click

from ..deps import get_dependency_status


@click.command()
@click.option("--json", is_flag=True, help="Output results in JSON format")
@click.pass_context
def check_deps(ctx: click.Context, json: bool) -> None:
    """Check system dependencies and requirements.

    This command verifies that all required dependencies are installed
    and available. It checks Python version, rclone, Docker (for test mode),
    and 1Password CLI (optional in production).

    Examples:
        photo-backup check-deps                    # Check dependencies
        photo-backup check-deps --test-mode        # Check dependencies for test mode
        photo-backup check-deps --json             # Output in JSON format
    """
    # Get test mode from context
    test_mode = ctx.obj.get("test_mode", False) if ctx.obj else False

    # Get dependency status
    all_passed, results = get_dependency_status(test_mode=test_mode)

    if json:
        # Output in JSON format
        import json as json_module

        json_results = {
            "test_mode": test_mode,
            "all_required_passed": all_passed,
            "dependencies": {
                name: {"available": available, "message": message} for name, (available, message) in results.items()
            },
        }
        click.echo(json_module.dumps(json_results, indent=2))
        sys.exit(0 if all_passed else 1)

    # Display dependency status
    mode_text = "TEST MODE" if test_mode else "PRODUCTION MODE"
    click.echo("Photo Backup System - Dependency Check")
    click.echo("=" * 40)
    click.echo(f"Mode: {mode_text}")
    click.echo()

    # Check Python version
    python_ok, python_msg = results["python"]
    click.echo("Python:")
    if python_ok:
        click.echo(f"  ✓ {python_msg}")
    else:
        click.echo(f"  ✗ {python_msg}")
    click.echo()

    # Check rclone
    rclone_ok, rclone_msg = results["rclone"]
    click.echo("rclone:")
    if rclone_ok:
        click.echo(f"  ✓ {rclone_msg}")
    else:
        click.echo(f"  ✗ {rclone_msg}")
    click.echo()

    # Check Docker
    docker_ok, docker_msg = results["docker"]
    click.echo("Docker:")
    if test_mode:
        if docker_ok:
            click.echo(f"  ✓ {docker_msg} (required for test mode)")
        else:
            click.echo(f"  ✗ {docker_msg} (required for test mode)")
    else:
        if docker_ok:
            click.echo(f"  ✓ {docker_msg} (optional, only needed for test mode)")
        else:
            click.echo(f"  ⚠ {docker_msg} (optional, only needed for test mode)")
    click.echo()

    # Check 1Password CLI
    op_ok, op_msg = results["1password"]
    click.echo("1Password CLI:")
    if test_mode:
        click.echo(f"  ⚠ {op_msg}")
    else:
        if op_ok:
            click.echo(f"  ✓ {op_msg}")
        else:
            click.echo(f"  ⚠ {op_msg} (optional, can use environment variables instead)")
    click.echo()

    # Summary
    click.echo("=" * 40)
    if all_passed:
        click.echo("✅ All required dependencies are available")
    else:
        click.echo("❌ Some required dependencies are missing")
        click.echo()
        click.echo("Please install missing dependencies:")
        if not python_ok:
            click.echo("  - Python >=3.13")
        if not rclone_ok:
            click.echo("  - rclone (https://rclone.org/install/)")
        if test_mode and not docker_ok:
            click.echo("  - Docker (https://www.docker.com/)")
        sys.exit(1)

    sys.exit(0)
