"""
Context management for logging operations.

This module provides context managers and filters for tracking
operations and adding context to log records.
"""

import logging
from datetime import datetime, timedelta
from typing import Optional

from .utils import generate_operation_id, format_duration


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

    def __init__(self, operation_type: str, description: str = "", logger: Optional[logging.Logger] = None):
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
        self.logger = logger or logging.getLogger("photo_backup")
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
    def duration(self) -> Optional[timedelta]:
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