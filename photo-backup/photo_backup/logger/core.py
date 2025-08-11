"""
Core logging functionality for the photo backup system.

This module provides the main logging setup and configuration functions.
"""

import logging
import sys
from pathlib import Path
from typing import Any, Optional

from .formatters import create_formatter
from .context import JobContextFilter
from .utils import _parse_log_level
from .cleanup import cleanup_old_logs


def setup_logger_from_config(config_obj: Any, job_id: Optional[str] = None, name: str = "photo_backup") -> logging.Logger:
    """Set up logger using configuration settings.

    Args:
        config_obj: Config object with logging settings
        job_id: Optional job ID for context
        name: Logger name

    Returns:
        Configured logger instance
    """
    # Get logging configuration from config object
    log_level_str = config_obj.get("logging.level", "INFO")
    log_format = config_obj.get("logging.format", "detailed")
    console_output = config_obj.get("logging.console_output", True)
    file_output = config_obj.get("logging.file_output", False)
    include_timestamps = config_obj.get("logging.include_timestamps", True)
    log_directory = config_obj.get("logging.directory")

    # Parse log level
    log_level = _parse_log_level(log_level_str)

    # Get or create logger
    logger = logging.getLogger(name)

    # Clear existing handlers and filters to avoid duplicates
    logger.handlers.clear()
    logger.filters.clear()

    logger.setLevel(log_level)

    # Create formatter
    formatter = create_formatter(log_format, include_timestamps, job_id)

    # Add console handler if enabled
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(log_level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    # Add file handler if enabled
    if file_output and log_directory:
        try:
            from logging.handlers import RotatingFileHandler

            log_dir = Path(log_directory).expanduser()
            log_dir.mkdir(parents=True, exist_ok=True)

            max_size_mb = config_obj.get("logging.max_size_mb", 100)
            backup_count = config_obj.get("logging.backup_count", 5)

            file_handler = RotatingFileHandler(
                log_dir / "photo-backup.log", maxBytes=max_size_mb * 1024 * 1024, backupCount=backup_count
            )
            file_handler.setLevel(log_level)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

        except Exception as e:
            # Fallback to console if file logging fails
            if not console_output:
                console_handler = logging.StreamHandler(sys.stdout)
                console_handler.setLevel(log_level)
                console_handler.setFormatter(formatter)
                logger.addHandler(console_handler)
            logger.warning(f"Failed to set up file logging: {e}")

    # Add job context filter if job_id provided
    if job_id:
        job_filter = JobContextFilter(job_id)
        logger.addFilter(job_filter)

    # Prevent propagation to root logger to avoid duplicate messages
    logger.propagate = False

    # Run log cleanup if enabled and we have a log directory
    if config_obj.get("logging.auto_cleanup", True) and log_directory:
        try:
            cleanup_old_logs(log_directory, config_obj, logger)
        except Exception as e:
            # Don't let cleanup failures prevent logger setup
            logger.warning(f"Log cleanup failed: {e}")

    return logger


def setup_logger(name: str = "photo_backup", level: int = logging.INFO) -> logging.Logger:
    """Set up logger with console output (backward compatibility).

    Args:
        name: Logger name
        level: Logging level (e.g., logging.INFO, logging.DEBUG)

    Returns:
        Configured logger instance
    """
    # Get or create logger
    logger = logging.getLogger(name)

    # Avoid adding multiple handlers if logger already exists
    if logger.handlers:
        return logger

    logger.setLevel(level)

    # Create console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)

    # Create formatter
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
    console_handler.setFormatter(formatter)

    # Add handler to logger
    logger.addHandler(console_handler)

    # Prevent propagation to root logger to avoid duplicate messages
    logger.propagate = False

    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Get an existing logger or create a new one.

    Args:
        name: Logger name. If None, returns the main photo_backup logger

    Returns:
        Logger instance
    """
    if name is None:
        name = "photo_backup"

    return logging.getLogger(name)


def set_log_level(level: int, logger_name: str = "photo_backup") -> None:
    """Set log level for a specific logger.

    Args:
        level: New logging level
        logger_name: Name of logger to modify
    """
    logger = logging.getLogger(logger_name)
    logger.setLevel(level)

    # Update all handlers
    for handler in logger.handlers:
        handler.setLevel(level) 