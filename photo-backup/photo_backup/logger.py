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
        return DetailedFormatter(include_timestamps=include_timestamps, job_id=job_id)


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

        if hasattr(record, "operation_id"):
            log_entry["operation_id"] = record.operation_id

        if hasattr(record, "description"):
            log_entry["description"] = record.description

        if hasattr(record, "duration_seconds"):
            log_entry["duration_seconds"] = record.duration_seconds

        if hasattr(record, "file_path"):
            log_entry["file_path"] = record.file_path

        # Add progress fields if present
        if hasattr(record, "progress_percentage"):
            log_entry["progress_percentage"] = record.progress_percentage

        if hasattr(record, "current_item"):
            log_entry["current_item"] = record.current_item

        if hasattr(record, "total_items"):
            log_entry["total_items"] = record.total_items

        if hasattr(record, "eta_seconds"):
            log_entry["eta_seconds"] = record.eta_seconds

        if hasattr(record, "elapsed_seconds"):
            log_entry["elapsed_seconds"] = record.elapsed_seconds

        if hasattr(record, "completed"):
            log_entry["completed"] = record.completed

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry)


class DetailedFormatter(logging.Formatter):
    """Detailed formatter that handles missing operation fields gracefully."""

    def __init__(self, include_timestamps: bool = True, job_id: str | None = None):
        super().__init__()
        self.include_timestamps = include_timestamps
        self.job_id = job_id

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with operation context."""
        # Build format string based on available fields
        parts = []

        if self.include_timestamps:
            parts.append("%(asctime)s")

        parts.extend(["%(name)s", "%(levelname)s"])

        # Only include job_id if it's provided or exists in record
        if self.job_id or (hasattr(record, "job_id") and record.job_id):
            parts.append("[%(job_id)s]")

        # Only include operation if it exists in record
        if hasattr(record, "operation") and record.operation:
            parts.append("[%(operation)s]")

        parts.append("%(message)s")

        format_string = " - ".join(parts)
        formatter = logging.Formatter(format_string, datefmt="%Y-%m-%d %H:%M:%S")

        return formatter.format(record)


class JobContextFilter(logging.Filter):
    """Filter to add job context to log records."""

    def __init__(self, job_id: str):
        super().__init__()
        self.job_id = job_id

    def filter(self, record: logging.LogRecord) -> bool:
        """Add job_id to log record."""
        record.job_id = self.job_id
        return True


class OperationContext:
    """Context manager for tracking operations with logging."""

    def __init__(self, operation_type: str, description: str = "", logger: logging.Logger | None = None):
        """Initialize operation context.

        Args:
            operation_type: Type of operation (e.g., 'backup', 'restore', 'verify')
            description: Human-readable description of the operation
            logger: Logger instance to use for operation logging
        """
        self.operation_type = operation_type
        self.description = description
        self.operation_id = generate_operation_id(operation_type)
        self.start_time = datetime.now()
        self.end_time = None
        self.logger = logger or get_logger()
        self._active = False

    def __enter__(self):
        """Enter operation context."""
        self._active = True
        self.logger.info(
            f"Starting {self.operation_type} operation",
            extra={
                "operation": self.operation_type,
                "operation_id": self.operation_id,
                "description": self.description,
            },
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit operation context."""
        self._active = False
        self.end_time = datetime.now()
        duration = self.end_time - self.start_time

        if exc_type is None:
            # Operation completed successfully
            self.logger.info(
                f"Completed {self.operation_type} operation in {format_duration(duration.total_seconds())}",
                extra={
                    "operation": self.operation_type,
                    "operation_id": self.operation_id,
                    "duration_seconds": duration.total_seconds(),
                },
            )
        else:
            # Operation failed
            self.logger.error(
                f"Failed {self.operation_type} operation after {format_duration(duration.total_seconds())}: {exc_val}",
                extra={
                    "operation": self.operation_type,
                    "operation_id": self.operation_id,
                    "duration_seconds": duration.total_seconds(),
                    "exception": str(exc_val),
                },
                exc_info=(exc_type, exc_val, exc_tb),
            )

    @property
    def duration(self) -> timedelta | None:
        """Get operation duration."""
        if self.end_time:
            return self.end_time - self.start_time
        elif self._active:
            return datetime.now() - self.start_time
        return None

    def log_progress(self, message: str, **kwargs):
        """Log progress message with operation context."""
        extra = {
            "operation": self.operation_type,
            "operation_id": self.operation_id,
        }
        extra.update(kwargs)
        self.logger.info(message, extra=extra)

    def log_warning(self, message: str, **kwargs):
        """Log warning message with operation context."""
        extra = {
            "operation": self.operation_type,
            "operation_id": self.operation_id,
        }
        extra.update(kwargs)
        self.logger.warning(message, extra=extra)

    def log_error(self, message: str, **kwargs):
        """Log error message with operation context."""
        extra = {
            "operation": self.operation_type,
            "operation_id": self.operation_id,
        }
        extra.update(kwargs)
        self.logger.error(message, extra=extra)


class ProgressLogger:
    """Progress logger for tracking long-running operations with rate limiting."""

    def __init__(
        self, 
        total_items: int, 
        operation_type: str = "operation",
        update_interval: float = 5.0,
        logger: logging.Logger | None = None,
        operation_context: OperationContext | None = None
    ):
        """Initialize progress logger.

        Args:
            total_items: Total number of items to process
            operation_type: Type of operation (e.g., 'files', 'bytes', 'items')
            update_interval: Minimum seconds between progress updates
            logger: Logger instance to use for progress logging
            operation_context: Optional operation context for additional logging context
        """
        self.total_items = total_items
        self.operation_type = operation_type
        self.update_interval = update_interval
        self.logger = logger or get_logger()
        self.operation_context = operation_context
        
        self.current_item = 0
        self.start_time = datetime.now()
        self.last_update_time = None  # Set to None so first update is always logged
        self.completed = False

    def update(self, current_item: int, message: str = "") -> None:
        """Update progress.

        Args:
            current_item: Current item number (1-based)
            message: Optional message to include with progress update
        """
        # Ensure current_item is within valid range
        self.current_item = max(0, min(current_item, self.total_items))
        current_time = datetime.now()
        
        # Check if enough time has passed for an update (skip rate limiting for first update)
        if self.last_update_time and (current_time - self.last_update_time).total_seconds() < self.update_interval:
            return
        
        self.last_update_time = current_time
        
        # Calculate progress metrics
        percentage = (self.current_item / self.total_items) * 100 if self.total_items > 0 else 0
        elapsed_time = current_time - self.start_time
        
        # Calculate ETA
        eta_seconds = self._calculate_eta(elapsed_time)
        eta_str = format_duration(eta_seconds) if eta_seconds > 0 else "unknown"
        
        # Build progress message
        progress_msg = f"Progress: {self.current_item}/{self.total_items} {self.operation_type} ({percentage:.1f}%) - ETA: {eta_str}"
        if message:
            progress_msg += f" - {message}"
        
        # Prepare extra fields for logging
        extra = {
            "progress_percentage": percentage,
            "current_item": self.current_item,
            "total_items": self.total_items,
            "eta_seconds": eta_seconds,
            "elapsed_seconds": elapsed_time.total_seconds(),
        }
        
        # Add operation context if available
        if self.operation_context:
            extra.update({
                "operation": self.operation_context.operation_type,
                "operation_id": self.operation_context.operation_id,
            })
        
        self.logger.info(progress_msg, extra=extra)

    def complete(self, message: str = "") -> None:
        """Mark operation as complete.

        Args:
            message: Optional completion message
        """
        self.current_item = self.total_items
        self.completed = True
        
        total_time = datetime.now() - self.start_time
        total_time_str = format_duration(total_time.total_seconds())
        
        completion_msg = f"Progress: {self.total_items}/{self.total_items} {self.operation_type} (100.0%) - Completed in {total_time_str}"
        if message:
            completion_msg += f" - {message}"
        
        # Prepare extra fields for logging
        extra = {
            "progress_percentage": 100.0,
            "current_item": self.total_items,
            "total_items": self.total_items,
            "eta_seconds": 0,
            "elapsed_seconds": total_time.total_seconds(),
            "completed": True,
        }
        
        # Add operation context if available
        if self.operation_context:
            extra.update({
                "operation": self.operation_context.operation_type,
                "operation_id": self.operation_context.operation_id,
            })
        
        self.logger.info(completion_msg, extra=extra)

    def _calculate_eta(self, elapsed_time: timedelta) -> float:
        """Calculate estimated time to completion.

        Args:
            elapsed_time: Time elapsed so far

        Returns:
            Estimated seconds remaining, or 0 if cannot calculate
        """
        if self.current_item <= 0 or self.total_items <= 0:
            return 0
        
        elapsed_seconds = elapsed_time.total_seconds()
        if elapsed_seconds <= 0:
            return 0
        
        # Calculate rate (items per second)
        rate = self.current_item / elapsed_seconds
        
        # Calculate remaining items
        remaining_items = self.total_items - self.current_item
        
        # Calculate ETA
        eta_seconds = remaining_items / rate if rate > 0 else 0
        
        return max(0, eta_seconds)

    @property
    def percentage(self) -> float:
        """Get current progress percentage."""
        return (self.current_item / self.total_items) * 100 if self.total_items > 0 else 0

    @property
    def elapsed_time(self) -> timedelta:
        """Get elapsed time."""
        return datetime.now() - self.start_time


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
