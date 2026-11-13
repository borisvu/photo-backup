import logging
import subprocess
import time
from collections.abc import Callable
from functools import wraps
from typing import Any, ParamSpec, TypeVar

_P = ParamSpec("_P")
_R = TypeVar("_R")


def run_command(command: list[str] | str, timeout: float | None = None, shell: bool = False) -> dict[str, Any]:
    """Run a shell command and capture stdout, stderr, and return code.
    Args:
        command (list or str): Command to run (list preferred, or str if shell=True)
        timeout (float or None): Timeout in seconds
        shell (bool): Whether to run command in shell
    Returns:
        dict: { 'stdout': str, 'stderr': str, 'returncode': int, 'timeout': bool }
    """
    try:
        result = subprocess.run(command, shell=shell, capture_output=True, text=True, timeout=timeout)
        return {"stdout": result.stdout, "stderr": result.stderr, "returncode": result.returncode, "timeout": False}
    except subprocess.TimeoutExpired as e:
        return {"stdout": e.stdout or "", "stderr": e.stderr or "", "returncode": None, "timeout": True}
    except Exception as e:
        return {"stdout": "", "stderr": str(e), "returncode": None, "timeout": False}


def retry(
    max_attempts: int = 3,
    backoff: float = 1,
    exceptions: tuple[type[Exception], ...] = (Exception,),
    logger: logging.Logger | None = None,
) -> Callable[[Callable[_P, _R]], Callable[_P, _R]]:
    """Retry decorator for functions that may fail.
    Args:
        max_attempts (int): Maximum number of attempts (default 3)
        backoff (float): Seconds to wait between attempts (default 1)
        exceptions (tuple): Exception types to catch (default Exception)
        logger (logging.Logger or None): Logger to use for retry messages
    Returns:
        Decorated function with retry logic
    """

    def decorator(func: Callable[_P, _R]) -> Callable[_P, _R]:
        @wraps(func)
        def wrapper(*args: _P.args, **kwargs: _P.kwargs) -> _R:
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
