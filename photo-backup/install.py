#!/usr/bin/env python3
"""
Installation script for Photo Backup System.

This script checks prerequisites and creates necessary directories
for the photo backup system.
"""

import os
import plistlib
import shutil
import subprocess
import sys

import click
from pathlib import Path

# Add the photo_backup package to the path
sys.path.insert(0, str(Path(__file__).parent))

from photo_backup.deps import get_dependency_status
from photo_backup.state_utils import get_state_directories

# Service identifiers
PROD_SERVICE_LABEL = "com.example.photo-backup"
TEST_SERVICE_LABEL = "com.example.photo-backup.test"


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


def get_plist_path(test_mode: bool = False) -> str:
    """Get the path where the plist should be installed.

    Args:
        test_mode: If True, use test service path

    Returns:
        Path to the plist file
    """
    label = TEST_SERVICE_LABEL if test_mode else PROD_SERVICE_LABEL
    plist_filename = f"{label}.plist"

    if test_mode:
        # For test mode, use a temp directory
        return f"/tmp/photo-backup-test/{plist_filename}"
    else:
        # Production: use ~/Library/LaunchAgents
        launch_agents_dir = os.path.expanduser("~/Library/LaunchAgents")
        return os.path.join(launch_agents_dir, plist_filename)


def get_service_label(test_mode: bool = False) -> str:
    """Get the launchd service label.

    Args:
        test_mode: If True, return test service label

    Returns:
        Service label string
    """
    return TEST_SERVICE_LABEL if test_mode else PROD_SERVICE_LABEL


def is_service_loaded(test_mode: bool = False) -> bool:
    """Check if the service is loaded in launchctl.

    Args:
        test_mode: If True, check for test service

    Returns:
        True if service is loaded, False otherwise
    """
    label = get_service_label(test_mode)
    try:
        result = subprocess.run(
            ["launchctl", "list", label],
            capture_output=True,
            text=True,
        )
        # launchctl list returns 0 if service is found
        return result.returncode == 0
    except Exception:
        return False


def unload_service(test_mode: bool = False) -> tuple[bool, str]:
    """Unload the service from launchctl if it's loaded.

    Args:
        test_mode: If True, unload test service

    Returns:
        Tuple of (success, message)
    """
    if not is_service_loaded(test_mode):
        return True, "Service not loaded, nothing to unload"

    plist_path = get_plist_path(test_mode)
    label = get_service_label(test_mode)

    try:
        # Try to unload using the plist file if it exists
        if os.path.exists(plist_path):
            result = subprocess.run(
                ["launchctl", "unload", plist_path],
                capture_output=True,
                text=True,
            )
        else:
            # Fall back to using bootout with the label
            result = subprocess.run(
                ["launchctl", "bootout", f"gui/{os.getuid()}/{label}"],
                capture_output=True,
                text=True,
            )

        if result.returncode == 0:
            return True, f"Service {label} unloaded successfully"
        else:
            # Some errors are acceptable (e.g., service already unloaded)
            if "No such process" in result.stderr or "Could not find" in result.stderr:
                return True, f"Service {label} was not loaded"
            return False, f"Failed to unload service: {result.stderr}"
    except Exception as e:
        return False, f"Error unloading service: {e!s}"


def install_plist(test_mode: bool = False) -> tuple[bool, str]:
    """Install the launchd plist and load the service.

    This function:
    1. Creates the plist file at the appropriate location
    2. Unloads any existing service with the same label
    3. Loads the new service with launchctl
    4. Verifies the service is loaded

    Args:
        test_mode: If True, install test service

    Returns:
        Tuple of (success, message)
    """
    label = get_service_label(test_mode)
    plist_path = get_plist_path(test_mode)

    try:
        click.echo(f"\nInstalling launchd service: {label}")

        # Unload existing service if loaded
        if is_service_loaded(test_mode):
            click.echo("  Unloading existing service...")
            success, msg = unload_service(test_mode)
            if not success:
                return False, f"Failed to unload existing service: {msg}"
            click.echo(f"  ✓ {msg}")

        # Create the plist file
        click.echo(f"  Creating plist at {plist_path}...")
        success, result = create_launchd_plist(test_mode=test_mode, output_path=plist_path)
        if not success:
            return False, f"Failed to create plist: {result}"
        click.echo("  ✓ Plist created")

        # Load the service
        click.echo("  Loading service with launchctl...")
        load_result = subprocess.run(
            ["launchctl", "load", plist_path],
            capture_output=True,
            text=True,
        )

        if load_result.returncode != 0:
            return False, f"Failed to load service: {load_result.stderr}"
        click.echo("  ✓ Service loaded")

        # Verify service is loaded
        if is_service_loaded(test_mode):
            click.echo(f"  ✓ Verified: service {label} is loaded")
            return True, f"Service {label} installed and loaded at {plist_path}"
        else:
            return False, "Service loaded but verification failed"

    except Exception as e:
        return False, f"Failed to install plist: {e!s}"


def setup_config(test_mode: bool = False) -> tuple[bool, str]:
    """Set up configuration file by copying example config.

    This function:
    1. Ensures the config directory exists
    2. Copies config.yaml.example to config.yaml if it doesn't exist
    3. Sets appropriate paths based on mode

    Args:
        test_mode: If True, set up test mode configuration

    Returns:
        Tuple of (success, message)
    """
    try:
        click.echo("\nSetting up configuration...")

        # Get state directories (this also creates them)
        dirs = get_state_directories(test_mode=test_mode)
        config_dir = dirs["config"]
        config_path = os.path.join(config_dir, "config.yaml")

        # Find the example config file
        install_script_dir = Path(__file__).parent
        example_config = install_script_dir / "config.yaml.example"

        if not example_config.exists():
            return False, f"Example config not found at {example_config}"

        # Check if config already exists
        if os.path.exists(config_path):
            click.echo(f"  ⚠ Config file already exists at {config_path}")
            click.echo("    To reset, delete the existing config and run again.")
            return True, f"Config already exists at {config_path}"

        # Copy example config
        click.echo(f"  Copying config template to {config_path}...")
        shutil.copy2(example_config, config_path)
        click.echo("  ✓ Configuration file created")

        # Set permissions (600 for security - config may contain sensitive paths)
        os.chmod(config_path, 0o600)
        click.echo("  ✓ Permissions set (0600)")

        # Create state directories if needed
        state_dir = dirs["state"]
        if os.path.exists(state_dir):
            click.echo(f"  ✓ State directory ready: {state_dir}")

        return True, f"Configuration set up at {config_path}"

    except Exception as e:
        return False, f"Failed to set up config: {e!s}"


@click.command()
@click.option(
    "--test",
    "test_mode",
    is_flag=True,
    help="Run in test mode - creates test structure and requires Docker",
)
@click.option(
    "--skip-service",
    is_flag=True,
    help="Skip launchd service installation",
)
@click.option(
    "--skip-config",
    is_flag=True,
    help="Skip configuration file setup",
)
def install(test_mode: bool, skip_service: bool, skip_config: bool) -> None:
    """Install Photo Backup System - check prerequisites, create directories, and set up service.

    This script verifies that all required dependencies are installed,
    creates the necessary directory structure, sets up configuration,
    and installs the launchd service.
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

    # Set up configuration
    if not skip_config:
        success, message = setup_config(test_mode=test_mode)
        if not success:
            click.echo(f"\n❌ {message}")
            sys.exit(1)
    else:
        click.echo("\n⚠ Skipping configuration setup (--skip-config)")

    # Install launchd service
    if not skip_service:
        success, message = install_plist(test_mode=test_mode)
        if not success:
            click.echo(f"\n❌ {message}")
            sys.exit(1)
    else:
        click.echo("\n⚠ Skipping service installation (--skip-service)")

    # Success message
    click.echo("\n" + "=" * 60)
    click.echo("✅ Installation completed successfully!")
    click.echo("\nNext steps:")
    if test_mode:
        click.echo("  1. Start Minio container: docker run -d --name minio -p 9000:9000 minio/minio server /data")
        click.echo("  2. Edit your config at /tmp/photo-backup-test/config/config.yaml")
        click.echo("  3. Run: photo-backup sync --test-mode")
    else:
        click.echo("  1. Edit your config at ~/Library/Application Support/photo-backup/config/config.yaml")
        click.echo("  2. Set up credentials (1Password or environment variables)")
        click.echo("  3. Run: photo-backup sync")
        click.echo("\nThe launchd service is installed but not started.")
        click.echo("To start it manually: launchctl start com.example.photo-backup")
    click.echo()


if __name__ == "__main__":
    install()
