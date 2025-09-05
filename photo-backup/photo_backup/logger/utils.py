"""
Utility functions for logging operations.

This module provides utility functions for ID generation, duration formatting,
and log level parsing.
"""

import logging
import uuid
from datetime import datetime


def _parse_log_level(level_str: str) -> int:
    """Parse log level string to logging constant.

    Args:
        level_str: Log level string (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Returns:
        Logging level constant

    Raises:
        ValueError: If level_str is invalid
    """
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }

    level_str = level_str.upper()
    if level_str not in level_map:
        raise ValueError(f"Invalid log level: {level_str}. Must be one of: {list(level_map.keys())}")

    return level_map[level_str]


def generate_job_id(prefix: str = "job") -> str:
    """Generate a unique job ID.

    Args:
        prefix: Prefix for the job ID

    Returns:
        Unique job ID string
    """
    timestamp = uuid.uuid4().hex[:8]
    return f"{prefix}-{timestamp}"


def generate_operation_id(operation_type: str) -> str:
    """Generate a unique operation ID.

    Args:
        operation_type: Type of operation (e.g., 'backup', 'restore', 'verify')

    Returns:
        Unique operation ID string
    """
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3]  # Remove microseconds, keep milliseconds
    return f"{operation_type}-{timestamp}"


def format_duration(seconds: float) -> str:
    """Format duration in seconds to a human-readable string.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted duration string
    """
    if seconds < 60:
        return f"{seconds:.2f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.2f}m"
    elif seconds < 86400:
        hours = seconds / 3600
        return f"{hours:.2f}h"
    else:
        days = seconds / 86400
        return f"{days:.2f}d"
