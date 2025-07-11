"""Utility functions for photo backup system."""

import os
import stat
import json
import errno


def format_bytes(bytes_value):
    """Convert bytes to human-readable format.
    
    Args:
        bytes_value (int): Number of bytes to format
        
    Returns:
        str: Human-readable size (e.g., "1.5 GB", "256 MB", "1.2 KB")
    """
    if not isinstance(bytes_value, (int, float)) or bytes_value < 0:
        return "0 B"
    
    if bytes_value == 0:
        return "0 B"
    
    # Define size units
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    unit_index = 0
    size = float(bytes_value)
    
    # Find the appropriate unit
    while size >= 1024.0 and unit_index < len(units) - 1:
        size /= 1024.0
        unit_index += 1
    
    # Format with appropriate precision
    if unit_index == 0:  # Bytes
        return f"{int(size)} {units[unit_index]}"
    elif size >= 100:
        return f"{size:.0f} {units[unit_index]}"
    elif size >= 10:
        return f"{size:.1f} {units[unit_index]}"
    else:
        return f"{size:.2f} {units[unit_index]}"


def ensure_directory(path):
    """Create directory if it doesn't exist.
    
    Args:
        path (str): Directory path to create
        
    Returns:
        tuple: (success: bool, error_message: str or None)
    """
    if not path:
        return False, "Path cannot be empty"
    
    try:
        # Convert to absolute path
        abs_path = os.path.abspath(path)
        
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
        return False, f"OS error creating directory {path}: {str(e)}"
    except Exception as e:
        return False, f"Unexpected error creating directory {path}: {str(e)}"


def validate_path(path):
    """Validate if a file or directory path exists and is accessible.
    
    Args:
        path (str): Path to validate
    Returns:
        tuple: (valid: bool, error: str or None)
    """
    if not path or not isinstance(path, str):
        return False, "Path must be a non-empty string"
    try:
        abs_path = os.path.abspath(path)
        if not os.path.exists(abs_path):
            return False, f"Path does not exist: {abs_path}"
        if not os.access(abs_path, os.R_OK):
            return False, f"Path is not accessible (read permission denied): {abs_path}"
        return True, None
    except Exception as e:
        return False, f"Error validating path {path}: {str(e)}"


def get_state_directories(test_mode=False):
    """Create and return state, config, and temp directories for the application.
    
    Args:
        test_mode (bool): If True, use /tmp/photo-backup-test/ as base dir. Otherwise, use user's Application Support.
    Returns:
        dict: { 'base': str, 'state': str, 'config': str, 'temp': str }
    Raises:
        RuntimeError: If any directory cannot be created.
    """
    if test_mode:
        base_dir = "/tmp/photo-backup-test"
    else:
        base_dir = os.path.expanduser("~/Library/Application Support/photo-backup")
    subdirs = ["state", "config", "temp"]
    paths = {"base": os.path.abspath(base_dir)}
    # Create base dir
    success, error = ensure_directory(base_dir)
    if not success:
        raise RuntimeError(f"Failed to create base directory: {error}")
    # Create subdirs
    for sub in subdirs:
        sub_path = os.path.join(base_dir, sub)
        success, error = ensure_directory(sub_path)
        if not success:
            raise RuntimeError(f"Failed to create {sub} directory: {error}")
        paths[sub] = os.path.abspath(sub_path)
    return paths


def save_json_state(data, filename, test_mode=False):
    """Save a dictionary as a JSON file in the state directory.
    Args:
        data (dict): Data to save
        filename (str): Name of the JSON file (e.g., 'backup_state.json')
        test_mode (bool): Use test mode state directory if True
    Returns:
        tuple: (success: bool, error: str or None)
    """
    try:
        dirs = get_state_directories(test_mode=test_mode)
        state_dir = dirs["state"]
        file_path = os.path.join(state_dir, filename)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        return True, None
    except Exception as e:
        return False, f"Error saving JSON state: {str(e)}"

def load_json_state(filename, test_mode=False):
    """Load a dictionary from a JSON file in the state directory.
    Args:
        filename (str): Name of the JSON file (e.g., 'backup_state.json')
        test_mode (bool): Use test mode state directory if True
    Returns:
        tuple: (data: dict or None, error: str or None)
    """
    try:
        dirs = get_state_directories(test_mode=test_mode)
        state_dir = dirs["state"]
        file_path = os.path.join(state_dir, filename)
        if not os.path.exists(file_path):
            return None, f"State file does not exist: {file_path}"
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data, None
    except Exception as e:
        return None, f"Error loading JSON state: {str(e)}"


def acquire_lock(lock_name="process.lock", test_mode=False):
    """Acquire a process lock using a PID file in the temp directory.
    Args:
        lock_name (str): Name of the lock file (default 'process.lock')
        test_mode (bool): Use test mode temp directory if True
    Returns:
        tuple: (success: bool, error: str or None)
    """
    try:
        dirs = get_state_directories(test_mode=test_mode)
        temp_dir = dirs["temp"]
        lock_path = os.path.join(temp_dir, lock_name)
        if os.path.exists(lock_path):
            # Check if the process is still running
            try:
                with open(lock_path, "r") as f:
                    pid = int(f.read().strip())
                # If process exists, fail
                if pid > 0:
                    try:
                        os.kill(pid, 0)
                        return False, f"Lock already acquired by PID {pid}"
                    except OSError as e:
                        if e.errno == errno.ESRCH:
                            # Process does not exist, stale lock
                            pass
                        else:
                            return False, f"Error checking lock PID: {e}"
            except Exception as e:
                return False, f"Error reading lock file: {e}"
        # Write our PID
        with open(lock_path, "w") as f:
            f.write(str(os.getpid()))
        return True, None
    except Exception as e:
        return False, f"Error acquiring lock: {str(e)}"

def release_lock(lock_name="process.lock", test_mode=False):
    """Release a process lock by removing the PID file in the temp directory.
    Args:
        lock_name (str): Name of the lock file (default 'process.lock')
        test_mode (bool): Use test mode temp directory if True
    Returns:
        tuple: (success: bool, error: str or None)
    """
    try:
        dirs = get_state_directories(test_mode=test_mode)
        temp_dir = dirs["temp"]
        lock_path = os.path.join(temp_dir, lock_name)
        if not os.path.exists(lock_path):
            return False, "Lock file does not exist"
        # Only allow release if we own the lock
        with open(lock_path, "r") as f:
            pid = int(f.read().strip())
        if pid != os.getpid():
            return False, f"Cannot release lock: owned by PID {pid}, current PID {os.getpid()}"
        os.remove(lock_path)
        return True, None
    except Exception as e:
        return False, f"Error releasing lock: {str(e)}"


# Quick test functionality for development
if __name__ == "__main__":
    # Test format_bytes
    test_sizes = [0, 512, 1024, 1536, 1048576, 1073741824, 1099511627776]
    print("Testing format_bytes:")
    for size in test_sizes:
        print(f"  {size} bytes -> {format_bytes(size)}")
    
    # Test ensure_directory
    print("\nTesting ensure_directory:")
    test_dir = "/tmp/photo-backup-utils-test"
    success, error = ensure_directory(test_dir)
    print(f"  Create {test_dir}: {'Success' if success else f'Failed: {error}'}")
    
    # Clean up test directory
    if success and os.path.exists(test_dir):
        os.rmdir(test_dir)
        print(f"  Cleaned up test directory")