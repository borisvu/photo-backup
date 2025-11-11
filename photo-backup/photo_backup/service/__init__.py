"""
Service module for photo backup system.

This package provides service management capabilities for running the photo backup
system as a continuous service with lifecycle management, health checks, and
graceful shutdown handling.

Public API:
    - ServiceManager: Main service orchestration class
    - ServiceState: Service state enumeration
    - ServiceStatus: Service status information
"""

from .manager import ServiceManager, ServiceState, ServiceStatus

__all__ = [
    "ServiceManager",
    "ServiceState",
    "ServiceStatus",
]

