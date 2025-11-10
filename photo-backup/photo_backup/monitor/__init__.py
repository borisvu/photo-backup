"""
Monitor module for photo backup system.

This package provides file system monitoring capabilities for detecting
changes in photo directories and triggering automated backups.

Public API:
    - DriveMonitor: Main monitoring class for detecting changes
    - MonitorEvent: Enumeration of monitoring events
    - MonitorState: Enumeration of monitor states
"""

from .events import MonitorEvent, MonitorState
from .monitor import DriveMonitor

__all__ = [
    "DriveMonitor",
    "MonitorEvent",
    "MonitorState",
]
