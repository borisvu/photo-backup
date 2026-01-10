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


def uninstall_service(test_mode: bool = False, remove_data: bool = False) -> tuple[bool, str]:
    """Uninstall the photo backup service.

    This function:
    1. Stops the service if running
    2. Unloads the service from launchctl
    3. Removes the plist file
    4. Optionally removes data directories

    Args:
        test_mode: If True, uninstall test service
        remove_data: If True, also remove config and state directories

    Returns:
        Tuple of (success, message)
    """
    label = get_service_label(test_mode)
    plist_path = get_plist_path(test_mode)
    errors = []

    try:
        click.echo(f"\nUninstalling service: {label}")

        # Stop service if running
        if is_service_loaded(test_mode):
            click.echo("  Stopping and unloading service...")
            success, msg = unload_service(test_mode)
            if success:
                click.echo(f"  ✓ {msg}")
            else:
                click.echo(f"  ⚠ {msg}")
                errors.append(msg)
        else:
            click.echo("  ✓ Service not running")

        # Remove plist file
        if os.path.exists(plist_path):
            click.echo(f"  Removing plist file: {plist_path}")
            os.unlink(plist_path)
            click.echo("  ✓ Plist file removed")
        else:
            click.echo("  ✓ Plist file already removed")

        # Optionally remove data directories
        if remove_data:
            click.echo("\nRemoving data directories...")
            from photo_backup.consts import PROD_MODE_BASE_DIR, TEST_MODE_BASE_DIR

            base_dir = TEST_MODE_BASE_DIR if test_mode else os.path.expanduser(PROD_MODE_BASE_DIR)

            if os.path.exists(base_dir):
                click.echo(f"  Removing {base_dir}...")
                shutil.rmtree(base_dir)
                click.echo("  ✓ Data directories removed")
            else:
                click.echo("  ✓ Data directories already removed")

            # Also clean up log directory in test mode
            if test_mode:
                test_log_dir = "/tmp/photo-backup-test/logs"
                if os.path.exists(test_log_dir):
                    shutil.rmtree(test_log_dir)
                    click.echo("  ✓ Test logs removed")
        else:
            click.echo("\n  ⚠ Data directories preserved (use --remove-data to delete)")

        if errors:
            return False, f"Uninstall completed with warnings: {'; '.join(errors)}"
        return True, f"Service {label} uninstalled successfully"

    except Exception as e:
        return False, f"Failed to uninstall: {e!s}"


def check_minio_connectivity() -> tuple[bool, str]:
    """Check if Minio is accessible for test mode.

    Returns:
        Tuple of (success, message)
    """
    try:
        import socket

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex(("localhost", 9000))
        sock.close()

        if result == 0:
            return True, "Minio is accessible at localhost:9000"
        else:
            return (
                False,
                "Minio is not accessible at localhost:9000 (start with: docker run -d -p 9000:9000 minio/minio server /data)",
            )
    except Exception as e:
        return False, f"Error checking Minio connectivity: {e!s}"


def validate_installation(test_mode: bool = False) -> tuple[bool, list[tuple[str, bool, str]]]:
    """Validate that the installation is complete and correct.

    This function checks:
    1. Required directories exist
    2. Config file exists and is readable
    3. Plist file exists
    4. Service is loaded (optional)
    5. Permissions are correct
    6. In test mode, checks Minio connectivity

    Args:
        test_mode: If True, validate test mode installation

    Returns:
        Tuple of (all_passed, list of (check_name, passed, message))
    """
    results: list[tuple[str, bool, str]] = []
    all_passed = True

    # Get paths
    from photo_backup.consts import PROD_MODE_BASE_DIR, TEST_MODE_BASE_DIR

    base_dir = TEST_MODE_BASE_DIR if test_mode else os.path.expanduser(PROD_MODE_BASE_DIR)
    plist_path = get_plist_path(test_mode)
    config_path = os.path.join(base_dir, "config", "config.yaml")

    # Check 1: Base directory exists
    if os.path.isdir(base_dir):
        results.append(("Base directory", True, f"Exists: {base_dir}"))
    else:
        results.append(("Base directory", False, f"Missing: {base_dir}"))
        all_passed = False

    # Check 2: State directory exists
    state_dir = os.path.join(base_dir, "state")
    if os.path.isdir(state_dir):
        results.append(("State directory", True, f"Exists: {state_dir}"))
    else:
        results.append(("State directory", False, f"Missing: {state_dir}"))
        all_passed = False

    # Check 3: Config directory exists
    config_dir = os.path.join(base_dir, "config")
    if os.path.isdir(config_dir):
        results.append(("Config directory", True, f"Exists: {config_dir}"))
    else:
        results.append(("Config directory", False, f"Missing: {config_dir}"))
        all_passed = False

    # Check 4: Temp directory exists
    temp_dir = os.path.join(base_dir, "temp")
    if os.path.isdir(temp_dir):
        results.append(("Temp directory", True, f"Exists: {temp_dir}"))
    else:
        results.append(("Temp directory", False, f"Missing: {temp_dir}"))
        all_passed = False

    # Check 5: Config file exists and is readable
    if os.path.isfile(config_path):
        try:
            with open(config_path) as f:
                f.read(1)  # Try to read
            results.append(("Config file", True, f"Exists and readable: {config_path}"))

            # Check config file permissions
            mode = os.stat(config_path).st_mode & 0o777
            if mode == 0o600:
                results.append(("Config permissions", True, "Secure (0600)"))
            else:
                results.append(("Config permissions", False, f"Insecure ({oct(mode)}), should be 0600"))
                all_passed = False
        except PermissionError:
            results.append(("Config file", False, f"Not readable: {config_path}"))
            all_passed = False
    else:
        results.append(("Config file", False, f"Missing: {config_path}"))
        all_passed = False

    # Check 6: Plist file exists
    if os.path.isfile(plist_path):
        results.append(("Plist file", True, f"Exists: {plist_path}"))

        # Check plist file permissions
        mode = os.stat(plist_path).st_mode & 0o777
        if mode == 0o600:
            results.append(("Plist permissions", True, "Secure (0600)"))
        else:
            results.append(("Plist permissions", False, f"Insecure ({oct(mode)}), should be 0600"))
            all_passed = False
    else:
        results.append(("Plist file", False, f"Missing: {plist_path}"))
        all_passed = False

    # Check 7: Service is loaded
    if is_service_loaded(test_mode):
        results.append(("Service loaded", True, f"Service {get_service_label(test_mode)} is loaded"))
    else:
        results.append(("Service loaded", False, f"Service {get_service_label(test_mode)} is not loaded"))
        # This is not a critical failure - service might be intentionally stopped
        # all_passed = False

    # Check 8: Directory permissions
    for dir_name, dir_path in [("Base", base_dir), ("State", state_dir), ("Config", config_dir), ("Temp", temp_dir)]:
        if os.path.isdir(dir_path):
            mode = os.stat(dir_path).st_mode & 0o777
            if mode == 0o755:
                results.append((f"{dir_name} dir permissions", True, "Correct (0755)"))
            else:
                results.append((f"{dir_name} dir permissions", False, f"Unexpected ({oct(mode)}), expected 0755"))
                # Not critical
                # all_passed = False

    # Check 9: In test mode, check Minio connectivity
    if test_mode:
        minio_ok, minio_msg = check_minio_connectivity()
        results.append(("Minio connectivity", minio_ok, minio_msg))
        if not minio_ok:
            all_passed = False

    # Check 10: Dependencies
    deps_ok, deps_results = get_dependency_status(test_mode=test_mode)
    for dep_name, (dep_ok, dep_msg) in deps_results.items():
        # Skip 1password check in test mode
        if test_mode and dep_name == "1password":
            continue
        # Docker is only required in test mode
        if not test_mode and dep_name == "docker":
            continue
        results.append((f"Dependency: {dep_name}", dep_ok, dep_msg))
        if not dep_ok and dep_name in ["python", "rclone"]:
            all_passed = False
        if not dep_ok and test_mode and dep_name == "docker":
            all_passed = False

    return all_passed, results


# CLI Commands
@click.group()
def cli():
    """Photo Backup System Installation Tools."""
    pass


@cli.command()
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


@cli.command()
@click.option(
    "--test",
    "test_mode",
    is_flag=True,
    help="Uninstall test mode service",
)
@click.option(
    "--remove-data",
    is_flag=True,
    help="Also remove config and state directories (WARNING: deletes all data)",
)
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    help="Skip confirmation prompt",
)
def uninstall(test_mode: bool, remove_data: bool, yes: bool) -> None:
    """Uninstall Photo Backup System - stop service and remove files.

    This command stops the launchd service, removes the plist file,
    and optionally removes all data directories.
    """
    mode_text = "TEST MODE" if test_mode else "PRODUCTION MODE"
    click.echo(f"Photo Backup System Uninstall ({mode_text})")
    click.echo("=" * 60)

    # Confirm uninstall
    if not yes:
        if remove_data:
            click.echo("\n⚠️  WARNING: This will remove ALL data including:")
            click.echo("    - Configuration files")
            click.echo("    - State files")
            click.echo("    - Temporary files")
            if not click.confirm("\nAre you sure you want to continue?"):
                click.echo("Uninstall cancelled.")
                sys.exit(0)
        else:
            if not click.confirm("\nThis will stop and remove the service. Continue?"):
                click.echo("Uninstall cancelled.")
                sys.exit(0)

    # Perform uninstall
    success, message = uninstall_service(test_mode=test_mode, remove_data=remove_data)

    if success:
        click.echo("\n" + "=" * 60)
        click.echo("✅ Uninstall completed successfully!")
        if not remove_data:
            click.echo("\nNote: Data directories were preserved.")
            click.echo("Run with --remove-data to delete all data.")
    else:
        click.echo(f"\n❌ {message}")
        sys.exit(1)

    click.echo()


@cli.command()
@click.option(
    "--test",
    "test_mode",
    is_flag=True,
    help="Validate test mode installation",
)
def validate(test_mode: bool) -> None:
    """Validate Photo Backup System installation.

    This command checks that all components are correctly installed
    and configured, including directories, config files, permissions,
    and service status.
    """
    mode_text = "TEST MODE" if test_mode else "PRODUCTION MODE"
    click.echo(f"Photo Backup System Validation ({mode_text})")
    click.echo("=" * 60)

    # Run validation
    all_passed, results = validate_installation(test_mode=test_mode)

    # Display results
    click.echo("\nValidation Results:")
    click.echo("-" * 60)

    passed_count = 0
    failed_count = 0

    for check_name, passed, message in results:
        if passed:
            click.echo(f"  ✓ {check_name}: {message}")
            passed_count += 1
        else:
            click.echo(f"  ✗ {check_name}: {message}")
            failed_count += 1

    # Summary
    click.echo("\n" + "=" * 60)
    click.echo(f"Summary: {passed_count} passed, {failed_count} failed")

    if all_passed:
        click.echo("\n✅ Installation is valid and ready to use!")
        if test_mode:
            click.echo("\nYou can now run: photo-backup sync --test-mode")
        else:
            click.echo("\nYou can now run: photo-backup sync")
    else:
        click.echo("\n❌ Installation has issues that need to be resolved.")
        click.echo("\nRun 'python install.py install" + (" --test" if test_mode else "") + "' to fix issues.")
        sys.exit(1)

    click.echo()


if __name__ == "__main__":
    cli()
