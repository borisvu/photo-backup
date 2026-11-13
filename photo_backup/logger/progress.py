"""
Progress logging for long-running operations.

This module provides progress tracking functionality with rate limiting
and ETA calculation for long-running operations.
"""

import logging
from datetime import datetime, timedelta

from .context import OperationContext
from .utils import format_duration


class ProgressLogger:
    """Progress logger for tracking long-running operations with rate limiting."""

    def __init__(
        self,
        total_items: int,
        operation_type: str = "operation",
        update_interval: float = 5.0,
        logger: logging.Logger | None = None,
        operation_context: OperationContext | None = None,
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
        self.logger = logger or logging.getLogger("photo_backup")
        self.operation_context = operation_context

        self.current_item: int = 0
        self.start_time: datetime = datetime.now()
        self.last_update_time: datetime | None = None  # Set to None so first update is always logged
        self.completed: bool = False

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
        extra: dict[str, float | int | str] = {
            "progress_percentage": percentage,
            "current_item": self.current_item,
            "total_items": self.total_items,
            "eta_seconds": eta_seconds,
            "elapsed_seconds": elapsed_time.total_seconds(),
        }

        # Add operation context if available
        if self.operation_context:
            extra.update(
                {
                    "operation": self.operation_context.operation_type,
                    "operation_id": self.operation_context.operation_id,
                }
            )

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
        extra: dict[str, float | int | str | bool] = {
            "progress_percentage": 100.0,
            "current_item": self.total_items,
            "total_items": self.total_items,
            "eta_seconds": 0,
            "elapsed_seconds": total_time.total_seconds(),
            "completed": True,
        }

        # Add operation context if available
        if self.operation_context:
            extra.update(
                {
                    "operation": self.operation_context.operation_type,
                    "operation_id": self.operation_context.operation_id,
                }
            )

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
