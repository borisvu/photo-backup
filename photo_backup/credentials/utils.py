"""
Utility functions for credential management.
"""

import os
import subprocess


def check_op_cli() -> tuple[bool, str]:
    """Check if 1Password CLI is available and compatible.

    Returns:
        Tuple of (is_available, message)
    """
    try:
        # Check if op command exists
        result = subprocess.run(["op", "--version"], capture_output=True, text=True, timeout=10.0)

        if result.returncode == 0:
            version = result.stdout.strip()
            # Basic version check - 1Password CLI v2+ is required
            # Version format can be "2.x.x" or "v2.x.x"
            if (
                version.startswith("2.")
                or version.startswith("v2.")
                or version.startswith("1.")
                or version.startswith("v1.")
            ):
                return True, f"1Password CLI available: {version}"
            else:
                return False, f"1Password CLI version not supported: {version}"
        else:
            return False, f"1Password CLI command failed: {result.stderr.strip()}"

    except subprocess.TimeoutExpired:
        return False, "1Password CLI command timed out"
    except FileNotFoundError:
        return False, "1Password CLI not found in PATH"
    except Exception as e:
        return False, f"Error checking 1Password CLI: {e!s}"


def check_op_cli_in_test_mode() -> tuple[bool, str]:
    """Check 1Password CLI availability, skipping in test mode.

    Returns:
        Tuple of (is_available, message)
    """
    # In test mode, we don't need 1Password CLI
    if os.environ.get("PHOTO_BACKUP_TEST_MODE") == "1":
        return True, "1Password CLI check skipped in test mode"

    return check_op_cli()
