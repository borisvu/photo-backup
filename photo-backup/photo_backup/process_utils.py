import subprocess
import time
from functools import wraps

def run_command(command, timeout=None, shell=False):
    """Run a shell command and capture stdout, stderr, and return code.
    Args:
        command (list or str): Command to run (list preferred, or str if shell=True)
        timeout (float or None): Timeout in seconds
        shell (bool): Whether to run command in shell
    Returns:
        dict: { 'stdout': str, 'stderr': str, 'returncode': int, 'timeout': bool }
    """
    try:
        result = subprocess.run(
            command,
            shell=shell,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return {
            'stdout': result.stdout,
            'stderr': result.stderr,
            'returncode': result.returncode,
            'timeout': False
        }
    except subprocess.TimeoutExpired as e:
        return {
            'stdout': e.stdout or '',
            'stderr': e.stderr or '',
            'returncode': None,
            'timeout': True
        }
    except Exception as e:
        return {
            'stdout': '',
            'stderr': str(e),
            'returncode': None,
            'timeout': False
        }

def retry(max_attempts=3, backoff=1, exceptions=(Exception,), logger=None):
    """Retry decorator for functions that may fail.
    Args:
        max_attempts (int): Maximum number of attempts (default 3)
        backoff (float): Seconds to wait between attempts (default 1)
        exceptions (tuple): Exception types to catch (default Exception)
        logger (logging.Logger or None): Logger to use for retry messages
    Returns:
        Decorated function with retry logic
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            attempt = 0
            while True:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    attempt += 1
                    msg = f"Retry attempt {attempt} for {func.__name__} after exception: {e}"
                    if logger:
                        logger.warning(msg)
                    else:
                        print(msg)
                    if attempt >= max_attempts:
                        raise
                    time.sleep(backoff)
        return wrapper
    return decorator