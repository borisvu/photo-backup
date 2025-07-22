import errno
import os

from .consts import DEFAULT_LOCK_FILENAME
from .state_utils import get_state_directories


def acquire_lock(lock_name=DEFAULT_LOCK_FILENAME, test_mode=False):
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
                with open(lock_path) as f:
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
        return False, f"Error acquiring lock: {e!s}"


def release_lock(lock_name=DEFAULT_LOCK_FILENAME, test_mode=False):
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
        with open(lock_path) as f:
            pid = int(f.read().strip())
        if pid != os.getpid():
            return False, f"Cannot release lock: owned by PID {pid}, current PID {os.getpid()}"
        os.remove(lock_path)
        return True, None
    except Exception as e:
        return False, f"Error releasing lock: {e!s}"
