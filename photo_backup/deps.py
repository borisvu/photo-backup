"""
Dependency checking utilities for photo backup system.

This module provides functions to check if all required dependencies
are installed and available.
"""

import subprocess
import sys

from .backup.rclone_utils import check_rclone
from .credentials.utils import check_op_cli


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


def check_all_dependencies(test_mode: bool = False) -> dict[str, tuple[bool, str]]:
    """Check all dependencies and return results.

    Args:
        test_mode: If True, skip 1Password check and require Docker

    Returns:
        Dictionary mapping dependency names to (is_available, message) tuples
    """
    results = {}

    # Check Python version
    results["python"] = check_python_version()

    # Check rclone
    rclone_ok, rclone_msg, _ = check_rclone()
    results["rclone"] = (rclone_ok, rclone_msg)

    # Check Docker
    docker_ok, docker_msg = check_docker()
    results["docker"] = (docker_ok, docker_msg)

    # Check 1Password CLI (skip in test mode)
    if not test_mode:
        op_ok, op_msg = check_op_cli()
        results["1password"] = (op_ok, op_msg)
    else:
        results["1password"] = (True, "Skipped in test mode")

    return results


def get_dependency_status(test_mode: bool = False) -> tuple[bool, dict[str, tuple[bool, str]]]:
    """Get dependency status and determine if all required dependencies are available.

    Args:
        test_mode: If True, skip 1Password check and require Docker

    Returns:
        Tuple of (all_required_passed, dependency_results_dict)
    """
    results = check_all_dependencies(test_mode=test_mode)
    all_passed = True

    # Python is always required
    if not results["python"][0]:
        all_passed = False

    # rclone is always required
    if not results["rclone"][0]:
        all_passed = False

    # Docker is required in test mode
    if test_mode and not results["docker"][0]:
        all_passed = False

    # 1Password is optional (can use env vars), but we check it anyway
    # It's not a blocker unless explicitly required

    return all_passed, results
