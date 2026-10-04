"""
Backend Package Initialization
Exposes primary services for local analytics, watch signal processing, and database interactions.
"""

from .security import SecurityManager
from .database_repository import DatabaseRepository
from .watch_ingestion import WatchSignalProcessor
from .analytics_pipeline import LocalAnalyticsService, backend_service

__all__ = [
    "SecurityManager",
    "DatabaseRepository",
    "WatchSignalProcessor",
    "LocalAnalyticsService",
    "backend_service",
]