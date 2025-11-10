"""
Rclone utility functions.

This module provides utility functions for checking rclone availability
and version requirements.
"""

import re
import subprocess


def check_rclone() -> tuple[bool, str, str | None]:
    """Check if rclone is installed and get version information.

    Returns:
        Tuple of (is_available, message, version_string)
        - is_available: True if rclone is installed and accessible
        - message: Human-readable status message
        - version_string: Version string if available, None otherwise
    """
    try:
        # Try to run rclone version command
        result = subprocess.run(["rclone", "version"], capture_output=True, text=True, timeout=10.0)

        if result.returncode == 0:
            # Parse version from output
            version_line = result.stdout.split("\n")[0] if result.stdout else ""
            # Extract version number from output like "rclone v1.64.2"
            version_match = re.search(r"rclone v(\d+\.\d+\.\d+)", version_line)
            version = version_match.group(1) if version_match else None

            if version:
                # Check minimum version (require 1.50.0 or higher)
                if _is_version_sufficient(version, "1.50.0"):
                    return True, f"rclone v{version} found (meets minimum requirement v1.50.0)", version
                else:
                    return False, f"rclone v{version} found but is too old (minimum required: v1.50.0)", version
            else:
                return True, "rclone found but version could not be determined", None
        else:
            return False, f"rclone command failed: {result.stderr.strip()}", None

    except FileNotFoundError:
        return False, "rclone not found - please install from https://rclone.org/install/", None
    except subprocess.TimeoutExpired:
        return False, "rclone version check timed out", None
    except Exception as e:
        return False, f"Error checking rclone: {e}", None


def _is_version_sufficient(current_version: str, minimum_version: str) -> bool:
    """Check if current version meets minimum version requirement.

    Args:
        current_version: Version string like "1.64.2"
        minimum_version: Minimum required version string like "1.50.0"

    Returns:
        True if current version >= minimum version
    """
    try:
        current_parts = [int(x) for x in current_version.split(".")]
        minimum_parts = [int(x) for x in minimum_version.split(".")]

        # Pad shorter version with zeros
        while len(current_parts) < len(minimum_parts):
            current_parts.append(0)
        while len(minimum_parts) < len(current_parts):
            minimum_parts.append(0)

        # Compare version parts
        for current, minimum in zip(current_parts, minimum_parts, strict=False):
            if current > minimum:
                return True
            elif current < minimum:
                return False

        return True  # Versions are equal
    except (ValueError, AttributeError):
        # If we can't parse versions, assume it's sufficient
        return True
