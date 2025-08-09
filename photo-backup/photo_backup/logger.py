"""
Enhanced logging configuration for photo backup system.

This module provides centralized logging setup with console output,
file output, configurable log levels, formatters, and job context.
"""

import json
import logging
import sys
import uuid
from datetime import datetime, timedelta
from typing import Any

from pathlib import Path


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


def cleanup_old_logs(log_directory: str, config_obj: Any = None, logger: logging.Logger | None = None) -> int:
    """Clean up old log files based on configuration.

    Args:
        log_directory: Directory containing log files
        config_obj: Configuration object with cleanup settings (optional)
        logger: Logger instance for logging cleanup operations (optional)

    Returns:
        Number of files deleted
    """
    if not log_directory:
        return 0

    try:
        log_dir_path = Path(log_directory).expanduser()
        if not log_dir_path.exists():
            if logger:
                logger.debug(f"Log directory does not exist: {log_directory}")
            return 0

        # Get cleanup settings from config or use defaults
        if config_obj:
            auto_cleanup = config_obj.get("logging.auto_cleanup", True)
            cleanup_days = config_obj.get("logging.cleanup_days", 30)
            cleanup_count = config_obj.get("logging.cleanup_count", 10)
            cleanup_mode = config_obj.get("logging.cleanup_mode", "age")
        else:
            auto_cleanup = True
            cleanup_days = 30
            cleanup_count = 10
            cleanup_mode = "age"

        if not auto_cleanup:
            if logger:
                logger.debug("Log cleanup is disabled")
            return 0

        deleted_count = 0
        log_files = []

        # Collect all log files
        for log_file in log_dir_path.glob("*.log*"):
            if log_file.is_file():
                try:
                    # Get file modification time
                    mtime = log_file.stat().st_mtime
                    log_files.append((log_file, mtime))
                except OSError as e:
                    if logger:
                        logger.warning(f"Could not access log file {log_file}: {e}")

        # Sort files by modification time (oldest first)
        log_files.sort(key=lambda x: x[1])

        if cleanup_mode == "age":
            # Age-based cleanup
            cutoff_time = datetime.now() - timedelta(days=cleanup_days)
            cutoff_timestamp = cutoff_time.timestamp()

            for log_file, mtime in log_files:
                if mtime < cutoff_timestamp:
                    try:
                        log_file.unlink()
                        deleted_count += 1
                        if logger:
                            logger.debug(f"Deleted old log file: {log_file.name}")
                    except OSError as e:
                        if logger:
                            logger.warning(f"Failed to delete log file {log_file}: {e}")

        elif cleanup_mode == "count":
            # Count-based cleanup - keep only the N most recent files
            if len(log_files) > cleanup_count:
                files_to_delete = log_files[:-cleanup_count]  # Keep the most recent files
                for log_file, _ in files_to_delete:
                    try:
                        log_file.unlink()
                        deleted_count += 1
                        if logger:
                            logger.debug(f"Deleted log file (count-based cleanup): {log_file.name}")
                    except OSError as e:
                        if logger:
                            logger.warning(f"Failed to delete log file {log_file}: {e}")

        if logger and deleted_count > 0:
            logger.info(f"Cleaned up {deleted_count} old log files from {log_directory}")

        return deleted_count

    except Exception as e:
        if logger:
            logger.error(f"Error during log cleanup: {e}")
        return 0


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
