"""Utility functions for photo backup system."""

import os
import stat


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