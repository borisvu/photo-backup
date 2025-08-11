"""
Log cleanup functionality.

This module provides log file cleanup functionality based on age or count.
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional


def cleanup_old_logs(log_directory: str, config_obj: Optional[Any] = None, logger: Optional[logging.Logger] = None) -> int:
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