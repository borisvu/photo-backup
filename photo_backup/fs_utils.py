import os


def ensure_directory(path: str) -> tuple[bool, str | None]:
    """Create directory if it doesn't exist.

    Args:
        path (str): Directory path to create

    Returns:
        tuple: (success: bool, error_message: str or None)
    """
    if not path:
        return False, "Path cannot be empty"

    try:
        # Expand ~ and environment variables, then convert to absolute path
        expanded_path = os.path.expanduser(path)
        abs_path = os.path.abspath(expanded_path)

        # Check if it already exists
        if os.path.exists(abs_path):
            if os.path.isdir(abs_path):
                return True, None
            else:
                return False, f"Path exists but is not a directory: {abs_path}"

        # Create the directory (including parent directories)
        os.makedirs(abs_path, mode=0o755, exist_ok=True)

        # Verify it was created
        if os.path.isdir(abs_path):
            return True, None
        else:
            return False, f"Failed to create directory: {abs_path}"

    except PermissionError:
        return False, f"Permission denied creating directory: {path}"
    except OSError as e:
        return False, f"OS error creating directory {path}: {e!s}"
    except Exception as e:
        return False, f"Unexpected error creating directory {path}: {e!s}"


def validate_path(path: str) -> tuple[bool, str | None]:
    """Validate if a file or directory path exists and is accessible.

    Args:
        path (str): Path to validate
    Returns:
        tuple: (valid: bool, error: str or None)
    """
    if not path or not isinstance(path, str):
        return False, "Path must be a non-empty string"
    try:
        # Expand ~ and environment variables, then convert to absolute path
        expanded_path = os.path.expanduser(path)
        abs_path = os.path.abspath(expanded_path)
        if not os.path.exists(abs_path):
            return False, f"Path does not exist: {abs_path}"
        if not os.access(abs_path, os.R_OK):
            return False, f"Path is not accessible (read permission denied): {abs_path}"
        return True, None
    except Exception as e:
        return False, f"Error validating path {path}: {e!s}"


def calculate_directory_size(path: str) -> tuple[int, int]:
    """Recursively calculate total size and file count of a directory.
    Args:
        path (str): Directory path
    Returns:
        tuple: (total_bytes: int, file_count: int)
    Notes:
        Skips files/dirs with permission errors and continues.
    """
    total_bytes: int = 0
    file_count: int = 0
    for root, _dirs, files in os.walk(path, onerror=lambda _: None):
        for f in files:
            try:
                fp = os.path.join(root, f)
                if os.path.islink(fp):
                    continue  # skip symlinks
                total_bytes += os.path.getsize(fp)
                file_count += 1
            except (OSError, PermissionError):
                continue
    return total_bytes, file_count
