"""
Logging formatters for the photo backup system.

This module provides formatters for different log output formats including
JSON, detailed, and simple text formats.
"""

import json
import logging
from typing import Optional


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def __init__(self, job_id: Optional[str] = None):
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

        # Add summary if present
        if hasattr(record, "summary"):
            log_entry["summary"] = record.summary

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry)


class DetailedFormatter(logging.Formatter):
    """Detailed formatter that handles missing operation fields gracefully."""

    def __init__(self, include_timestamps: bool = True, job_id: Optional[str] = None):
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
        if self.job_id or hasattr(record, "job_id"):
            parts.append("[%(job_id)s]")
        
        if hasattr(record, "operation"):
            parts.append("[%(operation)s]")
        
        if hasattr(record, "operation_id"):
            parts.append("[%(operation_id)s]")
        
        parts.append("-")
        parts.append("%(message)s")
        
        # Create format string
        format_string = " ".join(parts)
        
        # Create a temporary formatter with the dynamic format
        temp_formatter = logging.Formatter(format_string, datefmt="%Y-%m-%d %H:%M:%S")
        
        return temp_formatter.format(record)


def create_formatter(
    format_type: str = "detailed", include_timestamps: bool = True, job_id: Optional[str] = None
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