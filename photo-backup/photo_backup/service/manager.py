"""
Service manager for photo backup system.

This module provides the ServiceManager class that orchestrates the continuous
operation of the photo backup system by coordinating the monitor and backup engine.
"""

import errno
import logging
import os
import platform
import signal
import sys
import time
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

from ..backup import BackupEngine
from ..config.config import Config
from ..consts import SERVICE_PID_FILENAME
from ..monitor import DriveMonitor
from ..state_utils import get_state_directories


class ServiceState(Enum):
    """Service operational states."""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass
class ServiceStatus:
    """Service status information."""

    state: ServiceState
    started_at: datetime | None = None
    stopped_at: datetime | None = None
    error_message: str | None = None
    loop_count: int = 0
    last_check_time: datetime | None = None


class ServiceManager:
    """
    Manages the photo backup service lifecycle.

    The ServiceManager orchestrates the continuous operation of the backup system
    by coordinating the monitor and backup engine components. It handles:
    - Service lifecycle (start, stop, restart)
    - Monitor polling loop
    - Backup triggering when changes detected
    - Graceful shutdown with signal handling
    - Test mode support with accelerated timings

    Example:
        >>> config = Config(test_mode=True)
        >>> config.load_config()
        >>> service = ServiceManager(config)
        >>> service.start()  # Runs service loop
    """

    def __init__(
        self,
        config: Config,
        logger: logging.Logger | None = None,
        monitor: DriveMonitor | None = None,
        backup_engine: BackupEngine | None = None,
    ):
        """
        Initialize service manager.

        Args:
            config: Configuration object with service settings
            logger: Optional logger instance (creates one if not provided)
            monitor: Optional DriveMonitor instance (creates one if not provided)
            backup_engine: Optional BackupEngine instance (creates one if not provided)
        """
        self.config = config
        self.logger = logger or logging.getLogger(__name__)
        self._state = ServiceState.STOPPED
        self._status = ServiceStatus(state=ServiceState.STOPPED)
        self._shutdown_requested = False
        self._loop_interval = config.get("service.loop_interval_seconds", 60)

        # Initialize monitor and backup engine
        self.monitor = monitor or DriveMonitor(config)
        self.backup_engine = backup_engine or BackupEngine(config, test_mode=config.test_mode)

        # Signal handlers for graceful shutdown
        # Type matches signal.signal() return: Callable | int (SIG_DFL/SIG_IGN) | None
        self._original_sigint_handler: Any = None
        self._original_sigterm_handler: Any = None

        # PID file path
        self._pid_file_path = self._get_pid_file_path()

        # Track shutdown reason for logging
        self._shutdown_reason: str | None = None

        self.logger.info(
            f"ServiceManager initialized (test_mode={config.test_mode}, loop_interval={self._loop_interval}s)"
        )

    @property
    def state(self) -> ServiceState:
        """Get current service state."""
        return self._state

    @property
    def is_running(self) -> bool:
        """Check if service is currently running."""
        return self._state == ServiceState.RUNNING

    def _get_pid_file_path(self) -> str:
        """Get the path to the service PID file."""
        dirs = get_state_directories(test_mode=self.config.test_mode)
        return os.path.join(dirs["temp"], SERVICE_PID_FILENAME)

    def _write_pid_file(self) -> None:
        """Write current process PID to file."""
        try:
            pid = os.getpid()
            with open(self._pid_file_path, "w") as f:
                f.write(str(pid))
            self.logger.debug(f"Wrote PID {pid} to {self._pid_file_path}")
        except Exception as e:
            self.logger.error(f"Failed to write PID file: {e}")
            raise

    def _read_pid_file(self) -> int | None:
        """
        Read PID from file.

        Returns:
            Process ID if file exists and contains valid PID, None otherwise
        """
        try:
            if not os.path.exists(self._pid_file_path):
                return None
            with open(self._pid_file_path) as f:
                pid_str = f.read().strip()
                if not pid_str:
                    return None
                return int(pid_str)
        except (ValueError, OSError) as e:
            self.logger.warning(f"Failed to read PID file: {e}")
            return None

    def _remove_pid_file(self) -> None:
        """Remove PID file if it exists."""
        try:
            if os.path.exists(self._pid_file_path):
                os.remove(self._pid_file_path)
                self.logger.debug(f"Removed PID file {self._pid_file_path}")
        except Exception as e:
            self.logger.warning(f"Failed to remove PID file: {e}")

    @staticmethod
    def _is_process_running(pid: int) -> bool:
        """
        Check if a process is running.

        Args:
            pid: Process ID to check

        Returns:
            True if process is running, False otherwise
        """
        if pid <= 0:
            return False
        try:
            # os.kill with signal 0 checks if process exists without killing it
            os.kill(pid, 0)
            return True
        except OSError as e:
            if e.errno == errno.ESRCH:
                # Process does not exist
                return False
            # Process exists but we don't have permission (still running) or other error
            return e.errno == errno.EPERM

    def _check_existing_instance(self) -> None:
        """
        Check for existing service instance and handle stale PID files.

        Raises:
            RuntimeError: If another instance is already running
        """
        existing_pid = self._read_pid_file()
        if existing_pid is None:
            return

        if self._is_process_running(existing_pid):
            raise RuntimeError(
                f"Service is already running (PID {existing_pid}). Use 'photo-backup stop' to stop it first."
            )
        else:
            # Stale PID file, clean it up
            self.logger.warning(f"Found stale PID file (PID {existing_pid} not running), cleaning up")
            self._remove_pid_file()

    @classmethod
    def get_running_pid(cls, test_mode: bool = False) -> int | None:
        """
        Get the PID of a running service instance.

        Args:
            test_mode: Whether to check test mode PID file

        Returns:
            PID if service is running, None otherwise
        """
        try:
            dirs = get_state_directories(test_mode=test_mode)
            pid_file_path = os.path.join(dirs["temp"], SERVICE_PID_FILENAME)

            if not os.path.exists(pid_file_path):
                return None

            with open(pid_file_path) as f:
                pid = int(f.read().strip())

            # Verify process is actually running
            if cls._is_process_running(pid):
                return pid
            else:
                # Stale PID file
                return None

        except (ValueError, OSError):
            return None

    def get_status(self) -> ServiceStatus:
        """
        Get current service status.

        Returns:
            ServiceStatus object with current state and statistics
        """
        return ServiceStatus(
            state=self._state,
            started_at=self._status.started_at,
            stopped_at=self._status.stopped_at,
            error_message=self._status.error_message,
            loop_count=self._status.loop_count,
            last_check_time=self._status.last_check_time,
        )

    def _setup_signal_handlers(self) -> None:
        """Set up signal handlers for graceful shutdown."""
        self._original_sigint_handler = signal.signal(signal.SIGINT, self._handle_shutdown_signal)
        self._original_sigterm_handler = signal.signal(signal.SIGTERM, self._handle_shutdown_signal)
        self.logger.debug("Signal handlers installed for SIGINT and SIGTERM")

    def _restore_signal_handlers(self) -> None:
        """Restore original signal handlers."""
        if self._original_sigint_handler is not None:
            signal.signal(signal.SIGINT, self._original_sigint_handler)
        if self._original_sigterm_handler is not None:
            signal.signal(signal.SIGTERM, self._original_sigterm_handler)
        self.logger.debug("Original signal handlers restored")

    def _handle_shutdown_signal(self, signum: int, _frame: Any) -> None:
        """
        Handle shutdown signals (SIGINT, SIGTERM).

        Args:
            signum: Signal number
            _frame: Current stack frame (unused)
        """
        signal_name = "SIGINT" if signum == signal.SIGINT else "SIGTERM"
        self._shutdown_reason = f"signal_{signal_name}"
        self.logger.info(f"Received {signal_name}, initiating graceful shutdown...")
        self._shutdown_requested = True

    def start(self) -> None:
        """
        Start the service.

        This method initializes the service and enters the main loop.
        It will run until a shutdown signal is received or an error occurs.

        Raises:
            RuntimeError: If service is already running
        """
        if self._state == ServiceState.RUNNING:
            raise RuntimeError("Service is already running")

        # Check for existing instance (raises if running)
        self._check_existing_instance()

        self._log_service_start()
        self._state = ServiceState.STARTING
        self._log_state_change(ServiceState.STOPPED, ServiceState.STARTING)

        self._status.started_at = datetime.now()
        self._status.stopped_at = None
        self._status.error_message = None
        self._status.loop_count = 0
        self._shutdown_requested = False
        self._shutdown_reason = None

        # Write PID file
        self._write_pid_file()

        # Set up signal handlers
        self._setup_signal_handlers()

        try:
            self._state = ServiceState.RUNNING
            self._log_state_change(ServiceState.STARTING, ServiceState.RUNNING)
            self.logger.info(f"Service started successfully (loop_interval={self._loop_interval}s)")

            # Main service loop will be implemented in Task 74
            self._run_loop()

        except KeyboardInterrupt:
            self._shutdown_reason = "keyboard_interrupt"
            self.logger.info("Service interrupted by user")
        except Exception as e:
            self._shutdown_reason = f"error_{type(e).__name__}"
            self._state = ServiceState.ERROR
            self._status.error_message = str(e)
            self.logger.error(f"Service error: {e}", exc_info=True)
            raise
        finally:
            self._shutdown()

    def _run_loop(self) -> None:
        """
        Main service loop.

        Continuously polls the monitor for changes and triggers backups when needed.
        The loop:
        1. Checks if monitor should check for changes (interval-based)
        2. If so, checks for file changes
        3. If changes detected, triggers backup
        4. After successful backup, resets changes
        5. Sleeps for configured interval
        """
        self.logger.info("Entering main service loop")
        self.logger.info(f"Monitor: {self.monitor.watch_path}")
        self.logger.info(f"Backup destination: {self.config.get('backup.destination')}")

        while not self._shutdown_requested:
            try:
                self._status.loop_count += 1
                self._status.last_check_time = datetime.now()

                # Log periodic status
                if self._status.loop_count % 10 == 1:
                    self.logger.debug(
                        f"Service loop iteration {self._status.loop_count} (running for {self._get_uptime()})"
                    )

                # Check if it's time to poll the monitor
                if self.monitor.should_check():
                    self.logger.debug("Checking monitor for changes...")

                    # Check for changes
                    has_changes = self.monitor.check_for_changes()

                    if has_changes:
                        # Get change summary
                        summary = self.monitor.get_change_summary()
                        if summary:
                            self.logger.info(
                                f"Changes detected: {summary.total_files} files, {summary.get_formatted_size()}"
                            )
                            self.logger.debug(f"Change details: {summary}")

                            # Trigger backup
                            self._trigger_backup(summary)
                    else:
                        self.logger.debug("No changes detected")

                # Sleep for configured interval
                time.sleep(self._loop_interval)

            except Exception as e:
                self.logger.error(f"Error in service loop: {e}", exc_info=True)
                # Continue running unless shutdown requested
                if not self._shutdown_requested:
                    time.sleep(1)  # Brief pause before retry

        self.logger.info(f"Service loop exited after {self._status.loop_count} iterations")

    def _trigger_backup(self, _summary: Any) -> None:
        """
        Trigger a backup operation.

        Args:
            _summary: ChangeSummary from monitor with details of detected changes (logged already)
        """
        try:
            self.logger.info("Triggering backup operation...")

            # Create backup job
            job = self.backup_engine.create_backup_job()
            self.logger.info(f"Created backup job: {job}")

            # Execute backup
            stats = self.backup_engine.sync_with_stats(job)

            if stats.success:
                # Format size from bytes_transferred
                total_mb = stats.bytes_transferred / (1024 * 1024)
                size_display = f"{total_mb:.1f} MB" if total_mb < 1024 else f"{total_mb / 1024:.1f} GB"

                self.logger.info(
                    f"Backup completed successfully: {stats.files_transferred} files transferred, {size_display}"
                )

                # Reset monitor changes after successful backup
                self.monitor.reset_changes()
                self.logger.debug("Monitor changes reset after successful backup")
            else:
                self.logger.error(f"Backup failed: {stats.error_message or 'Unknown error'}")

        except Exception as e:
            self.logger.error(f"Error triggering backup: {e}", exc_info=True)

    def stop(self) -> None:
        """
        Stop the service gracefully.

        Requests a graceful shutdown and waits for the service to stop.
        """
        if self._state == ServiceState.STOPPED:
            self.logger.warning("Service is already stopped")
            return

        self._shutdown_reason = "stop_requested"
        self.logger.info("Stopping service...")
        self._shutdown_requested = True

    def _shutdown(self) -> None:
        """Perform cleanup and shutdown tasks."""
        self.logger.info("Shutting down service...")
        prev_state = self._state
        self._state = ServiceState.STOPPING
        self._log_state_change(prev_state, ServiceState.STOPPING)

        # Remove PID file
        self._remove_pid_file()

        # Restore signal handlers
        self._restore_signal_handlers()

        # Record shutdown time
        self._status.stopped_at = datetime.now()
        uptime = self._get_uptime()

        self._state = ServiceState.STOPPED
        self._log_state_change(ServiceState.STOPPING, ServiceState.STOPPED)
        self._log_service_stop(uptime)

    def _get_uptime(self) -> str:
        """Get service uptime as a formatted string."""
        if self._status.started_at is None:
            return "not started"

        end_time = self._status.stopped_at or datetime.now()
        uptime_seconds = (end_time - self._status.started_at).total_seconds()

        if uptime_seconds < 60:
            return f"{uptime_seconds:.1f}s"
        elif uptime_seconds < 3600:
            return f"{uptime_seconds / 60:.1f}m"
        else:
            hours = int(uptime_seconds / 3600)
            minutes = int((uptime_seconds % 3600) / 60)
            return f"{hours}h {minutes}m"

    def _log_service_start(self) -> None:
        """Log service start event with comprehensive information."""
        self.logger.info("=" * 70)
        self.logger.info("SERVICE STARTING")
        self.logger.info("=" * 70)
        self.logger.info(f"Timestamp: {datetime.now().isoformat()}")
        self.logger.info(f"PID: {os.getpid()}")
        self.logger.info(f"Mode: {'TEST' if self.config.test_mode else 'PRODUCTION'}")
        self.logger.info(f"Python: {sys.version.split()[0]}")
        self.logger.info(f"Platform: {platform.system()} {platform.release()}")
        self.logger.info(f"Monitor path: {self.config.get('backup.source_path')}")
        self.logger.info(f"Destination: {self.config.get('backup.destination')}")
        self.logger.info(f"Check interval: {self.config.get('monitoring.check_interval_hours')}h")
        self.logger.info(f"Loop interval: {self._loop_interval}s")
        self.logger.info("=" * 70)

    def _log_state_change(self, from_state: ServiceState, to_state: ServiceState) -> None:
        """
        Log service state change.

        Args:
            from_state: Previous state
            to_state: New state
        """
        self.logger.info(f"State transition: {from_state.value} -> {to_state.value}")
        if self.config.test_mode:
            # More verbose in test mode
            self.logger.debug(f"State change details: from={from_state.name}, to={to_state.name}")

    def _log_service_stop(self, uptime: str) -> None:
        """
        Log service stop event with summary statistics.

        Args:
            uptime: Formatted uptime string
        """
        self.logger.info("=" * 70)
        self.logger.info("SERVICE STOPPED")
        self.logger.info("=" * 70)
        self.logger.info(f"Timestamp: {datetime.now().isoformat()}")
        self.logger.info(f"Shutdown reason: {self._shutdown_reason or 'normal'}")
        self.logger.info(f"Uptime: {uptime}")
        self.logger.info(f"Loop iterations: {self._status.loop_count}")

        if self._status.started_at and self._status.stopped_at:
            duration = (self._status.stopped_at - self._status.started_at).total_seconds()
            if duration > 0:
                avg_loop_time = duration / max(self._status.loop_count, 1)
                self.logger.info(f"Average loop time: {avg_loop_time:.2f}s")

        if self._status.error_message:
            self.logger.info(f"Final error: {self._status.error_message}")

        self.logger.info("=" * 70)

    def __repr__(self) -> str:
        """String representation of service manager."""
        return (
            f"ServiceManager(state={self._state.value}, "
            f"loop_count={self._status.loop_count}, "
            f"test_mode={self.config.test_mode})"
        )
