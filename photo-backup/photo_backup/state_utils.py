import os
import json
from .consts import TEST_MODE_BASE_DIR, PROD_MODE_BASE_DIR
from .fs_utils import ensure_directory

def get_state_directories(test_mode=False):
    """Create and return state, config, and temp directories for the application.
    
    Args:
        test_mode (bool): If True, use TEST_MODE_BASE_DIR as base dir. Otherwise, use PROD_MODE_BASE_DIR.
    Returns:
        dict: { 'base': str, 'state': str, 'config': str, 'temp': str }
    Raises:
        RuntimeError: If any directory cannot be created.
    """
    if test_mode:
        base_dir = TEST_MODE_BASE_DIR
    else:
        base_dir = os.path.expanduser(PROD_MODE_BASE_DIR)
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