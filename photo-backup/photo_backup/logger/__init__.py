"""
Photo Backup Logger Package

This package provides comprehensive logging functionality for the photo backup system.
"""

# Core logging functionality
# Log cleanup
from .cleanup import cleanup_old_logs

# Context and operation tracking
from .context import (
    JobContextFilter,
    OperationContext,
)
from .core import (
    get_logger,
    set_log_level,
    setup_logger,
    setup_logger_from_config,
)

# Formatters
from .formatters import (
    DetailedFormatter,
    JSONFormatter,
    create_formatter,
)

# Progress logging
from .progress import ProgressLogger

# Summary statistics
from .summary import SummaryStatistics

# Utility functions
from .utils import (
    _parse_log_level,
    format_duration,
    generate_job_id,
    generate_operation_id,
)

__all__ = [
    "_parse_log_level",
    "cleanup_old_logs",
    "create_formatter",
    "DetailedFormatter",
    "format_duration",
    "generate_job_id",
    "generate_operation_id",
    "get_logger",
    "JobContextFilter",
    "JSONFormatter",
    "OperationContext",
    "ProgressLogger",
    "set_log_level",
    "setup_logger",
    "setup_logger_from_config",
    "SummaryStatistics",
]
