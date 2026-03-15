"""Maintenance scheduler for periodic tasks.

This module provides the MaintenanceScheduler class for managing
periodic maintenance tasks like database vacuum, cache cleanup,
and metrics collection.
"""

import sqlite3
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from nomi.storage.cache.context_cache import ContextCache
from nomi.utils.logger import LoggerMixin


class MaintenanceScheduler(LoggerMixin):
    """Scheduler for periodic maintenance tasks.

    Runs maintenance tasks at regular intervals (hourly by default)
    including database vacuum, cache cleanup, and metrics collection.

    Attributes:
        storage_dir: Directory containing the SQLite database.
        interval_seconds: Interval between maintenance runs.
    """

    DEFAULT_INTERVAL_SECONDS: int = 3600  # 1 hour

    def __init__(
        self,
        storage_dir: Path,
        interval_seconds: int = DEFAULT_INTERVAL_SECONDS,
    ) -> None:
        """Initialize the maintenance scheduler.

        Args:
            storage_dir: Directory containing SQLite database.
            interval_seconds: Seconds between maintenance runs.
        """
        self.storage_dir = Path(storage_dir)
        self.interval_seconds = interval_seconds

        self._lock = threading.RLock()
        self._shutdown_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None
        self._context_cache = ContextCache()

        self._last_vacuum: Optional[datetime] = None
        self._last_cache_cleanup: Optional[datetime] = None
        self._last_stats_collection: Optional[datetime] = None

        self._start_worker()
        self.logger.info(
            "MaintenanceScheduler initialized",
            interval_seconds=interval_seconds,
        )

    def _start_worker(self) -> None:
        """Start the background maintenance worker thread."""
        self._worker_thread = threading.Thread(
            target=self._maintenance_loop,
            name="MaintenanceSchedulerWorker",
            daemon=True,
        )
        self._worker_thread.start()
        self.logger.debug("Maintenance worker thread started")

    def _maintenance_loop(self) -> None:
        """Main loop for periodic maintenance.

        Runs maintenance tasks at the configured interval.
        """
        self.logger.debug("Maintenance loop running")

        while not self._shutdown_event.is_set():
            try:
                self._run_maintenance_tasks()
            except Exception as e:
                self.logger.error("Maintenance task failed", error=str(e))

            self._shutdown_event.wait(timeout=self.interval_seconds)

        self.logger.debug("Maintenance loop stopped")

    def _run_maintenance_tasks(self) -> None:
        """Execute all maintenance tasks."""
        self.logger.info("Running maintenance tasks...")
        start_time = time.time()

        self.schedule_vacuum()
        self.schedule_cache_cleanup()
        self.schedule_stats_collection()

        duration = time.time() - start_time
        self.logger.info("Maintenance tasks completed", duration_ms=duration * 1000)

    def schedule_vacuum(self) -> None:
        """Vacuum the SQLite database to reclaim space.

        Rebuilds the database file to compact it and reclaim
        space from deleted records.
        """
        self.logger.debug("Scheduling database vacuum...")

        db_path = self.storage_dir / "nomi.db"

        if not db_path.exists():
            self.logger.debug("Database file not found, skipping vacuum")
            return

        try:
            with sqlite3.connect(str(db_path), timeout=30.0) as conn:
                conn.execute("VACUUM")

            self._last_vacuum = datetime.now()
            self.logger.info("Database vacuum completed")

        except sqlite3.Error as e:
            self.logger.error("Database vacuum failed", error=str(e))

    def schedule_cache_cleanup(self) -> None:
        """Clear expired cache entries.

        Removes stale entries from the context cache to free memory.
        """
        self.logger.debug("Scheduling cache cleanup...")

        try:
            cleared_count = len(self._context_cache)
            self._context_cache.clear()

            self._last_cache_cleanup = datetime.now()
            self.logger.info("Cache cleanup completed", cleared_count=cleared_count)

        except Exception as e:
            self.logger.error("Cache cleanup failed", error=str(e))

    def schedule_stats_collection(self) -> None:
        """Collect and store system metrics.

        Gathers statistics about the database and system state
        for monitoring and analysis.
        """
        self.logger.debug("Scheduling stats collection...")

        try:
            stats = self._collect_stats()
            self._last_stats_collection = datetime.now()

            self.logger.info(
                "Stats collection completed",
                database_size_bytes=stats.get("database_size_bytes", 0),
                cache_entries=stats.get("cache_entries", 0),
            )

        except Exception as e:
            self.logger.error("Stats collection failed", error=str(e))

    def _collect_stats(self) -> dict:
        """Collect system statistics.

        Returns:
            Dictionary containing collected statistics.
        """
        stats: dict = {
            "timestamp": datetime.now().isoformat(),
            "database_size_bytes": 0,
            "cache_entries": len(self._context_cache),
        }

        db_path = self.storage_dir / "nomi.db"
        if db_path.exists():
            stats["database_size_bytes"] = db_path.stat().st_size

        return stats

    def get_last_run_times(self) -> dict:
        """Get timestamps of last maintenance runs.

        Returns:
            Dictionary with last run timestamps.
        """
        with self._lock:
            return {
                "last_vacuum": self._last_vacuum,
                "last_cache_cleanup": self._last_cache_cleanup,
                "last_stats_collection": self._last_stats_collection,
            }

    def shutdown(self) -> None:
        """Shutdown the scheduler gracefully.

        Stops the worker thread.
        """
        self.logger.info("Shutting down MaintenanceScheduler...")
        self._shutdown_event.set()

        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=5.0)
            if self._worker_thread.is_alive():
                self.logger.warning("Maintenance worker did not terminate gracefully")

        self.logger.info("MaintenanceScheduler shutdown complete")
