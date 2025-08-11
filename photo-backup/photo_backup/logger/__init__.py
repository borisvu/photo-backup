"""
Photo Backup Logger Package

This package provides comprehensive logging functionality for the photo backup system.
"""

# Core logging functionality
from .core import (
    setup_logger,
    setup_logger_from_config,
    get_logger,
    set_log_level,
)

# Formatters
from .formatters import (
    JSONFormatter,
    DetailedFormatter,
    create_formatter,
)

# Context and operation tracking
from .context import (
    JobContextFilter,
    OperationContext,
)

# Progress logging
from .progress import ProgressLogger

# Log cleanup
from .cleanup import cleanup_old_logs

# Utility functions
from .utils import (
    generate_job_id,
    generate_operation_id,
    format_duration,
    _parse_log_level,
)

__all__ = [
    # Core
    "setup_logger",
    "setup_logger_from_config", 
    "get_logger",
    "set_log_level",
    
    # Formatters
    "JSONFormatter",
    "DetailedFormatter",
    "create_formatter",
    
    # Context
    "JobContextFilter",
    "OperationContext",
    
    # Progress
    "ProgressLogger",
    
    # Cleanup
    "cleanup_old_logs",
    
    # Utils
    "generate_job_id",
    "generate_operation_id", 
    "format_duration",
    "_parse_log_level",
] 