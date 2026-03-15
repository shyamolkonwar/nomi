"""Health monitoring for daemon subsystems.

This module provides the HealthChecker class for monitoring
the health of daemon subsystems including database connections,
file watchers, and API servers.
"""

import sqlite3
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

from nomi.utils.logger import LoggerMixin


@dataclass
class HealthStatus:
    """Health status of daemon subsystems.

    Attributes:
        is_healthy: True if all subsystems are healthy.
        database_connected: True if database connection is working.
        watcher_active: True if file watcher is running.
        api_available: True if API server is responding.
        last_check: Timestamp of last health check.
    """

    is_healthy: bool
    database_connected: bool
    watcher_active: bool
    api_available: bool
    last_check: datetime


class HealthChecker(LoggerMixin):
    """Monitor the health of daemon subsystems.

    Performs periodic health checks on database connections,
    file watchers, and API servers. Reports overall health status.

    Attributes:
        storage_dir: Directory containing the SQLite database.
        check_interval_seconds: Seconds between health checks.
    """

    DEFAULT_CHECK_INTERVAL_SECONDS: int = 60  # 1 minute

    def __init__(
        self,
        storage_dir: Path,
        check_interval_seconds: int = DEFAULT_CHECK_INTERVAL_SECONDS,
    ) -> None:
        """Initialize the health checker.

        Args:
            storage_dir: Directory containing the SQLite database.
            check_interval_seconds: Seconds between health checks.
        """
        self.storage_dir = Path(storage_dir)
        self.check_interval_seconds = check_interval_seconds

        self._lock = threading.RLock()
        self._shutdown_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None

        self._last_status: Optional[HealthStatus] = None

        self._start_worker()
        self.logger.info(
            "HealthChecker initialized",
            check_interval_seconds=check_interval_seconds,
        )

    def _start_worker(self) -> None:
        """Start the background health check worker thread."""
        self._worker_thread = threading.Thread(
            target=self._health_check_loop,
            name="HealthCheckerWorker",
            daemon=True,
        )
        self._worker_thread.start()
        self.logger.debug("Health check worker thread started")

    def _health_check_loop(self) -> None:
        """Main loop for periodic health checks.

        Runs health checks at the configured interval.
        """
        self.logger.debug("Health check loop running")

        while not self._shutdown_event.is_set():
            try:
                self._last_status = self.get_health_status()

                if not self._last_status.is_healthy:
                    self.logger.warning(
                        "Health check failed",
                        database_connected=self._last_status.database_connected,
                        watcher_active=self._last_status.watcher_active,
                        api_available=self._last_status.api_available,
                    )
                else:
                    self.logger.debug("Health check passed")

            except Exception as e:
                self.logger.error("Health check error", error=str(e))

            self._shutdown_event.wait(timeout=self.check_interval_seconds)

        self.logger.debug("Health check loop stopped")

    def check_database_connection(self) -> bool:
        """Check if the database connection is working.

        Returns:
            True if database is accessible and responding.
        """
        db_path = self.storage_dir / "nomi.db"

        if not db_path.exists():
            self.logger.debug("Database file not found")
            return False

        try:
            with sqlite3.connect(str(db_path), timeout=5.0) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                cursor.fetchone()
            return True
        except sqlite3.Error as e:
            self.logger.debug("Database connection check failed", error=str(e))
            return False

    def check_file_watcher(self) -> bool:
        """Check if the file watcher is active.

        Returns:
            True if file watcher subsystem is running.
        """
        # Placeholder: File watcher implementation will set this
        # For now, assume watcher is active if storage directory exists
        return self.storage_dir.exists()

    def check_api_server(self) -> bool:
        """Check if the API server is available.

        Returns:
            True if API server is responding.
        """
        # Placeholder: API server implementation will set this
        # For now, assume API is available if storage directory exists
        return self.storage_dir.exists()

    def get_health_status(self) -> HealthStatus:
        """Get current health status of all subsystems.

        Performs health checks on all subsystems and returns
        aggregated status.

        Returns:
            HealthStatus with detailed subsystem states.
        """
        database_connected = self.check_database_connection()
        watcher_active = self.check_file_watcher()
        api_available = self.check_api_server()

        is_healthy = all(
            [
                database_connected,
                watcher_active,
                api_available,
            ]
        )

        status = HealthStatus(
            is_healthy=is_healthy,
            database_connected=database_connected,
            watcher_active=watcher_active,
            api_available=api_available,
            last_check=datetime.now(),
        )

        return status

    def get_last_status(self) -> Optional[HealthStatus]:
        """Get the last known health status.

        Returns:
            Last HealthStatus or None if no check has run.
        """
        with self._lock:
            return self._last_status

    def shutdown(self) -> None:
        """Shutdown the health checker gracefully.

        Stops the worker thread.
        """
        self.logger.info("Shutting down HealthChecker...")
        self._shutdown_event.set()

        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=5.0)
            if self._worker_thread.is_alive():
                self.logger.warning("Health check worker did not terminate gracefully")

        self.logger.info("HealthChecker shutdown complete")
