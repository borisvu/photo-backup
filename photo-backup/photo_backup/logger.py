"""
Enhanced logging configuration for photo backup system.

This module provides centralized logging setup with console output,
file output, configurable log levels, formatters, and job context.
"""

import json
import logging
import sys
import uuid
from typing import Any


def create_formatter(
    format_type: str = "detailed", include_timestamps: bool = True, job_id: str | None = None
) -> logging.Formatter:
    """Create formatter based on configuration.

    Args:
        format_type: Format type - 'simple', 'detailed', or 'json'
        include_timestamps: Whether to include timestamps
        job_id: Optional job ID to include in log messages

    Returns:
        Configured formatter instance
    """
    if format_type == "json":
        return JSONFormatter(job_id=job_id)
    elif format_type == "simple":
        if include_timestamps:
            return logging.Formatter("%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")
        else:
            return logging.Formatter("%(levelname)s - %(message)s")
    else:  # detailed (default)
        if include_timestamps:
            if job_id:
                return logging.Formatter(
                    "%(asctime)s - %(name)s - %(levelname)s - [%(job_id)s] - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
                )
            else:
                return logging.Formatter(
                    "%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
                )
        else:
            if job_id:
                return logging.Formatter("%(name)s - %(levelname)s - [%(job_id)s] - %(message)s")
            else:
                return logging.Formatter("%(name)s - %(levelname)s - %(message)s")


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def __init__(self, job_id: str | None = None):
        super().__init__()
        self.job_id = job_id

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_entry = {
            "timestamp": self.formatTime(record),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        if self.job_id:
            log_entry["job_id"] = self.job_id

        # Add extra fields if present
        if hasattr(record, "job_id"):
            log_entry["job_id"] = record.job_id

        if hasattr(record, "operation"):
            log_entry["operation"] = record.operation

        if hasattr(record, "file_path"):
            log_entry["file_path"] = record.file_path

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry)


class JobContextFilter(logging.Filter):
    """Filter to add job context to log records."""

    def __init__(self, job_id: str):
        super().__init__()
        self.job_id = job_id

    def filter(self, record: logging.LogRecord) -> bool:
        """Add job_id to log record."""
        record.job_id = self.job_id
        return True


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


def setup_logger_from_config(config_obj: Any, job_id: str | None = None, name: str = "photo_backup") -> logging.Logger:
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
    if file_output:
        log_directory = config_obj.get("logging.directory")
        if log_directory:
            try:
                from pathlib import Path

                log_dir = Path(log_directory).expanduser()
                log_dir.mkdir(parents=True, exist_ok=True)

                from logging.handlers import RotatingFileHandler

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

    return logger


def generate_job_id(prefix: str = "job") -> str:
    """Generate a unique job ID.

    Args:
        prefix: Prefix for the job ID

    Returns:
        Unique job ID string
    """
    timestamp = uuid.uuid4().hex[:8]
    return f"{prefix}-{timestamp}"


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


def get_logger(name: str | None = None) -> logging.Logger:
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


# Quick test functionality
if __name__ == "__main__":
    # Test the logger setup
    test_logger = setup_logger("test_logger", logging.DEBUG)

    test_logger.debug("Debug message")
    test_logger.info("Info message")
    test_logger.warning("Warning message")
    test_logger.error("Error message")
    test_logger.critical("Critical message")

    print("Logger test completed successfully!")
