#!/usr/bin/env python3
"""
Installation script for Photo Backup System.

This script checks prerequisites and creates necessary directories
for the photo backup system.
"""

import sys

import click
from pathlib import Path

# Add the photo_backup package to the path
sys.path.insert(0, str(Path(__file__).parent))

from photo_backup.backup.rclone_utils import check_rclone
from photo_backup.credentials.utils import check_op_cli
from photo_backup.state_utils import get_state_directories


def check_python_version() -> tuple[bool, str]:
    """Check if Python version meets requirements.

    Returns:
        Tuple of (is_sufficient, message)
    """
    version = sys.version_info
    required_major = 3
    required_minor = 13

    if version.major > required_major or (version.major == required_major and version.minor >= required_minor):
        return True, f"Python {version.major}.{version.minor}.{version.micro} (meets requirement >=3.13)"
    else:
        return False, f"Python {version.major}.{version.minor}.{version.micro} is too old (requires >=3.13)"


def check_docker() -> tuple[bool, str]:
    """Check if Docker is available.

    Returns:
        Tuple of (is_available, message)
    """
    import subprocess

    try:
        result = subprocess.run(["docker", "--version"], capture_output=True, text=True, timeout=10.0)
        if result.returncode == 0:
            version = result.stdout.strip()
            return True, f"Docker available: {version}"
        else:
            return False, f"Docker command failed: {result.stderr.strip()}"
    except FileNotFoundError:
        return False, "Docker not found - required for test mode. Install from https://www.docker.com/"
    except subprocess.TimeoutExpired:
        return False, "Docker version check timed out"
    except Exception as e:
        return False, f"Error checking Docker: {e!s}"


def check_prerequisites(test_mode: bool = False) -> tuple[bool, list[str]]:
    """Check all prerequisites for installation.

    Args:
        test_mode: If True, skip 1Password check and require Docker

    Returns:
        Tuple of (all_passed, list of error messages)
    """
    errors = []
    all_passed = True

    # Check Python version
    click.echo("Checking Python version...")
    python_ok, python_msg = check_python_version()
    if python_ok:
        click.echo(f"  ✓ {python_msg}")
    else:
        click.echo(f"  ✗ {python_msg}")
        errors.append(python_msg)
        all_passed = False

    # Check rclone
    click.echo("Checking rclone...")
    rclone_ok, rclone_msg, _ = check_rclone()
    if rclone_ok:
        click.echo(f"  ✓ {rclone_msg}")
    else:
        click.echo(f"  ✗ {rclone_msg}")
        errors.append(rclone_msg)
        all_passed = False

    # Check Docker (required for test mode)
    if test_mode:
        click.echo("Checking Docker (required for test mode)...")
        docker_ok, docker_msg = check_docker()
        if docker_ok:
            click.echo(f"  ✓ {docker_msg}")
        else:
            click.echo(f"  ✗ {docker_msg}")
            errors.append(docker_msg)
            all_passed = False
    else:
        click.echo("Checking Docker (optional)...")
        docker_ok, docker_msg = check_docker()
        if docker_ok:
            click.echo(f"  ✓ {docker_msg}")
        else:
            click.echo(f"  ⚠ {docker_msg} (optional, only needed for test mode)")

    # Check 1Password CLI (skip in test mode)
    if not test_mode:
        click.echo("Checking 1Password CLI...")
        op_ok, op_msg = check_op_cli()
        if op_ok:
            click.echo(f"  ✓ {op_msg}")
        else:
            click.echo(f"  ⚠ {op_msg} (optional, can use environment variables instead)")
    else:
        click.echo("Checking 1Password CLI...")
        click.echo("  ⚠ Skipped in test mode")

    return all_passed, errors


def create_directories(test_mode: bool = False) -> tuple[bool, str]:
    """Create necessary directories for the application.

    Args:
        test_mode: If True, create test mode directories

    Returns:
        Tuple of (success, message)
    """
    try:
        click.echo("\nCreating directories...")
        dirs = get_state_directories(test_mode=test_mode)

        click.echo(f"  ✓ Base directory: {dirs['base']}")
        click.echo(f"  ✓ State directory: {dirs['state']}")
        click.echo(f"  ✓ Config directory: {dirs['config']}")
        click.echo(f"  ✓ Temp directory: {dirs['temp']}")

        return True, "Directories created successfully"
    except RuntimeError as e:
        return False, f"Failed to create directories: {e!s}"
    except Exception as e:
        return False, f"Unexpected error creating directories: {e!s}"


@click.command()
@click.option(
    "--test",
    "test_mode",
    is_flag=True,
    help="Run in test mode - creates test structure and requires Docker",
)
def install(test_mode: bool) -> None:
    """Install Photo Backup System - check prerequisites and create directories.

    This script verifies that all required dependencies are installed
    and creates the necessary directory structure for the application.
    """
    mode_text = "TEST MODE" if test_mode else "PRODUCTION MODE"
    click.echo(f"Photo Backup System Installation ({mode_text})")
    click.echo("=" * 60)

    # Check prerequisites
    click.echo("\nChecking prerequisites...")
    all_passed, errors = check_prerequisites(test_mode=test_mode)

    if not all_passed:
        click.echo("\n❌ Prerequisites check failed:")
        for error in errors:
            click.echo(f"  - {error}")
        click.echo("\nPlease install missing dependencies and try again.")
        sys.exit(1)

    # Create directories
    success, message = create_directories(test_mode=test_mode)
    if not success:
        click.echo(f"\n❌ {message}")
        sys.exit(1)

    # Success message
    click.echo("\n" + "=" * 60)
    click.echo("✅ Installation completed successfully!")
    click.echo("\nNext steps:")
    if test_mode:
        click.echo("  1. Start Minio container: docker run -d --name minio -p 9000:9000 minio/minio server /data")
        click.echo("  2. Configure your backup settings")
        click.echo("  3. Run: photo-backup sync --test-mode")
    else:
        click.echo("  1. Configure your backup settings")
        click.echo("  2. Set up credentials (1Password or environment variables)")
        click.echo("  3. Run: photo-backup sync")
    click.echo()


if __name__ == "__main__":
    install()
