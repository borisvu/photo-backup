#!/usr/bin/env python3
"""
Installation script for Photo Backup System.

This script checks prerequisites and creates necessary directories
for the photo backup system.
"""

import os
import plistlib
import shutil
import sys

import click
from pathlib import Path

# Add the photo_backup package to the path
sys.path.insert(0, str(Path(__file__).parent))

from photo_backup.deps import get_dependency_status
from photo_backup.state_utils import get_state_directories


def check_prerequisites(test_mode: bool = False) -> tuple[bool, list[str]]:
    """Check all prerequisites for installation.

    Args:
        test_mode: If True, skip 1Password check and require Docker

    Returns:
        Tuple of (all_passed, list of error messages)
    """
    errors = []
    all_passed = True

    # Get dependency status
    all_passed, results = get_dependency_status(test_mode=test_mode)

    # Check Python version
    click.echo("Checking Python version...")
    python_ok, python_msg = results["python"]
    if python_ok:
        click.echo(f"  ✓ {python_msg}")
    else:
        click.echo(f"  ✗ {python_msg}")
        errors.append(python_msg)

    # Check rclone
    click.echo("Checking rclone...")
    rclone_ok, rclone_msg = results["rclone"]
    if rclone_ok:
        click.echo(f"  ✓ {rclone_msg}")
    else:
        click.echo(f"  ✗ {rclone_msg}")
        errors.append(rclone_msg)

    # Check Docker (required for test mode)
    docker_ok, docker_msg = results["docker"]
    if test_mode:
        click.echo("Checking Docker (required for test mode)...")
        if docker_ok:
            click.echo(f"  ✓ {docker_msg}")
        else:
            click.echo(f"  ✗ {docker_msg}")
            errors.append(docker_msg)
    else:
        click.echo("Checking Docker (optional)...")
        if docker_ok:
            click.echo(f"  ✓ {docker_msg}")
        else:
            click.echo(f"  ⚠ {docker_msg} (optional, only needed for test mode)")

    # Check 1Password CLI (skip in test mode)
    op_ok, op_msg = results["1password"]
    if not test_mode:
        click.echo("Checking 1Password CLI...")
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


def create_launchd_plist(test_mode: bool = False, output_path: str | None = None) -> tuple[bool, str]:
    """Create a launchd plist file for the photo backup service.

    Args:
        test_mode: If True, use test mode identifier and settings
        output_path: Optional path to write the plist file. If None, returns plist content as string.

    Returns:
        Tuple of (success, message or file path)
    """
    try:
        # Determine service identifier
        label = "com.example.photo-backup.test" if test_mode else "com.example.photo-backup"

        # Get Python executable path
        python_exe: str | None = sys.executable
        if not python_exe or not os.path.exists(python_exe):
            # Fallback to finding python3 in PATH
            python_exe = shutil.which("python3")
            if not python_exe:
                return False, "Could not find Python executable"

        # Get the main.py path or use the installed entry point
        # Try to find the installed entry point first
        entry_point = shutil.which("photo-backup")
        if entry_point:
            # Use the installed entry point
            program_args = [entry_point, "start"]
        else:
            # Fall back to using python -m photo_backup.main
            package_dir = Path(__file__).parent
            main_py = package_dir / "photo_backup" / "main.py"
            if not main_py.exists():
                return False, f"Could not find main.py at {main_py}"
            program_args = [python_exe, str(main_py), "start"]

        # Add test-mode flag if needed
        if test_mode:
            program_args.append("--test-mode")

        # Build plist dictionary based on mode
        if test_mode:
            # Test mode: simpler KeepAlive and test log paths
            test_log_dir = "/tmp/photo-backup-test/logs"
            os.makedirs(test_log_dir, exist_ok=True)
            plist_dict = {
                "Label": label,
                "ProgramArguments": program_args,
                "RunAtLoad": False,  # Don't start automatically on load
                "KeepAlive": {
                    "SuccessfulExit": False,  # Restart if process exits with non-zero code
                },
                "StandardOutPath": os.path.join(test_log_dir, "service.log"),
                "StandardErrorPath": os.path.join(test_log_dir, "service-error.log"),
            }
        else:
            # Production mode: watch for drive mount
            plist_dict = {
                "Label": label,
                "ProgramArguments": program_args,
                "RunAtLoad": False,  # Don't start automatically on load
                "StartOnMount": {
                    "/Volumes/4TB-SSD": True,  # Start when this drive is mounted
                },
                "KeepAlive": {
                    "PathState": {
                        "/Volumes/4TB-SSD": True,  # Keep alive while drive is mounted
                    }
                },
                "StandardOutPath": os.path.expanduser("~/Library/Logs/photo-backup/service.log"),
                "StandardErrorPath": os.path.expanduser("~/Library/Logs/photo-backup/service-error.log"),
            }

        # Generate plist XML
        plist_xml = plistlib.dumps(plist_dict, fmt=plistlib.FMT_XML, sort_keys=False)

        if output_path:
            # Write to file
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, "wb") as f:
                f.write(plist_xml)
            # Set permissions (600 for security)
            os.chmod(output_file, 0o600)
            return True, str(output_file)
        else:
            # Return as string
            return True, plist_xml.decode("utf-8")

    except Exception as e:
        return False, f"Failed to create plist: {e!s}"


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
