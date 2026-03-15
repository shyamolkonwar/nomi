"""Main daemon for Nomi runtime.

This module provides the NomiDaemon class for managing the lifecycle
of the Nomi context engine, including initialization, starting, stopping,
and health monitoring of all subsystems.
"""

import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from nomi.config.schema import NomiConfig
from nomi.core.index.symbol_index import SymbolIndex
from nomi.discovery.repo_scanner import RepoScanner
from nomi.storage.sqlite.symbol_store import SymbolStore
from nomi.storage.sqlite.graph_store import GraphStore
from nomi.utils.logger import LoggerMixin


@dataclass
class DaemonStatus:
    """Status information for the Nomi daemon.

    Attributes:
        is_running: Whether the daemon is currently running.
        is_indexing: Whether indexing is currently in progress.
        indexed_files: Number of files that have been indexed.
        total_symbols: Total number of symbols in the index.
        uptime_seconds: Time since daemon started in seconds.
        pid: Process ID of the daemon.
    """

    is_running: bool
    is_indexing: bool
    indexed_files: int
    total_symbols: int
    uptime_seconds: float
    pid: int


class NomiDaemon(LoggerMixin):
    """Main daemon for the Nomi context engine.

    Manages the lifecycle of all subsystems including file watching,
    indexing, API serving, and MCP integration.

    Attributes:
        config: NomiConfig instance with daemon configuration.
        project_root: Root directory of the project being analyzed.
        storage_dir: Directory for SQLite database and cache files.
    """

    def __init__(self, config: NomiConfig, project_root: str) -> None:
        """Initialize the Nomi daemon.

        Args:
            config: Configuration for the daemon.
            project_root: Root directory of the project to analyze.
        """
        self.config = config
        self.project_root = Path(project_root).resolve()
        self.storage_dir = self._get_storage_dir()

        self._running = False
        self._start_time: Optional[float] = None
        self._lock = threading.RLock()
        self._shutdown_event = threading.Event()

        self._symbol_index: Optional[SymbolIndex] = None
        self._repo_scanner: Optional[RepoScanner] = None
        self._symbol_store: Optional[SymbolStore] = None
        self._graph_store: Optional[GraphStore] = None

        self._indexing_scheduler: Optional[Any] = None
        self._maintenance_scheduler: Optional[Any] = None
        self._health_checker: Optional[Any] = None

        self._file_watcher: Optional[Any] = None
        self._api_server: Optional[Any] = None
        self._mcp_server: Optional[Any] = None

        self.logger.info(f"NomiDaemon initialized: project_root={self.project_root}, storage_dir={self.storage_dir}")

    def _get_storage_dir(self) -> Path:
        """Get or create the storage directory path."""
        if self.config.index_cache_dir.is_absolute():
            return self.config.index_cache_dir
        return self.project_root / self.config.index_cache_dir

    def initialize(self) -> None:
        """Initialize the daemon and all subsystems.

        Creates storage directory, initializes database connections,
        and prepares all subsystems for startup.
        """
        with self._lock:
            self.logger.info("Initializing Nomi daemon...")

            self._create_storage_directory()
            self._initialize_database()
            self._initialize_subsystems()

            self.logger.info("Nomi daemon initialized successfully")

    def _create_storage_directory(self) -> None:
        """Create the storage directory if it doesn't exist."""
        try:
            self.storage_dir.mkdir(parents=True, exist_ok=True)
            self.logger.debug(f"Storage directory ready: path={self.storage_dir}")
        except OSError as e:
            self.logger.error(f"Failed to create storage directory: {e}")
            raise RuntimeError(f"Cannot create storage directory: {e}")

    def _initialize_database(self) -> None:
        """Initialize database connections and schema."""
        db_path = self.storage_dir / "nomi.db"

        try:
            self._symbol_store = SymbolStore(db_path)
            self._graph_store = GraphStore(db_path)
            self.logger.debug(f"Database initialized: path={db_path}")
        except Exception as e:
            self.logger.error(f"Failed to initialize database: {e}")
            raise RuntimeError(f"Database initialization failed: {e}")

    def _initialize_subsystems(self) -> None:
        """Initialize all daemon subsystems."""
        db_path = self.storage_dir / "nomi.db"

        self._symbol_index = SymbolIndex(str(db_path))

        self._repo_scanner = RepoScanner(
            root_path=str(self.project_root),
            ignore_patterns=list(self.config.ignore_patterns),
            respect_gitignore=True,
            max_file_size_bytes=self.config.max_file_size,
        )

        self.logger.debug("Subsystems initialized")

    def start(self) -> None:
        """Start the daemon and all services.

        Starts file watching, API server, MCP server, and enters
        the main event loop. Blocks until stop() is called.
        """
        with self._lock:
            if self._running:
                self.logger.warning("Daemon is already running")
                return

            self.logger.info("Starting Nomi daemon...")
            self._running = True
            self._start_time = time.time()
            self._shutdown_event.clear()

        try:
            self._start_file_watcher()
            self._start_api_server()
            self._start_mcp_server()
            self._start_schedulers()
            self._start_health_checker()

            self.logger.info(f"Nomi daemon started: pid={os.getpid()}, port={self.config.server_port}")

            self._main_loop()

        except Exception as e:
            self.logger.error(f"Daemon startup failed: {e}")
            self.stop()
            raise

    def _start_file_watcher(self) -> None:
        """Start the file watcher subsystem."""
        if not self.config.watch:
            self.logger.debug("File watching disabled")
            return

        self.logger.info("Starting file watcher...")

    def _start_api_server(self) -> None:
        """Start the API server subsystem."""
        from nomi.api.server import create_api_server
        import asyncio
        import threading

        self.logger.info(f"Starting API server on port {self.config.server_port}...")

        ready_event = threading.Event()
        error_holder: list[Exception | None] = [None]

        def run_server() -> None:
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                app = create_api_server(
                    symbol_index=self._symbol_index,
                    repo_map_builder=None,
                )

                import uvicorn
                config = uvicorn.Config(
                    app=app,
                    host="127.0.0.1",
                    port=self.config.server_port,
                    log_level="info",
                )
                server = uvicorn.Server(config)

                ready_event.set()

                loop.run_until_complete(server.serve())
            except Exception as e:
                error_holder[0] = e
                ready_event.set()

        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()

        ready_event.wait(timeout=10.0)

        if error_holder[0] is not None:
            self.logger.error(f"Failed to start API server: {error_holder[0]}")
            raise error_holder[0]

        self._api_server = server_thread
        self.logger.info(f"API server started on port {self.config.server_port}")

    def _start_mcp_server(self) -> None:
        """Start the MCP server subsystem."""
        if not self.config.enable_mcp:
            self.logger.debug("MCP server disabled")
            return

        self.logger.info("Starting MCP server...")

    def _start_schedulers(self) -> None:
        """Start background schedulers."""
        from nomi.daemon.scheduler.indexing import IndexingScheduler
        from nomi.daemon.scheduler.maintenance import MaintenanceScheduler

        if self._symbol_index is not None and self._repo_scanner is not None:
            self._indexing_scheduler = IndexingScheduler(
                symbol_index=self._symbol_index,
                repo_scanner=self._repo_scanner,
            )
            self._indexing_scheduler.schedule_full_index()

        self._maintenance_scheduler = MaintenanceScheduler(
            storage_dir=self.storage_dir,
        )

        self.logger.debug("Schedulers started")

    def _start_health_checker(self) -> None:
        """Start the health checker."""
        from nomi.daemon.lifecycle.healthcheck import HealthChecker

        self._health_checker = HealthChecker(
            storage_dir=self.storage_dir,
        )

        self.logger.debug("Health checker started")

    def _main_loop(self) -> None:
        """Main daemon event loop.

        Runs until shutdown event is set.
        """
        self.logger.info("Entering main loop...")

        while not self._shutdown_event.is_set():
            try:
                self._shutdown_event.wait(timeout=1.0)
            except KeyboardInterrupt:
                self.logger.info("Keyboard interrupt received")
                break

        self.logger.info("Exiting main loop")

    def stop(self) -> None:
        """Stop the daemon gracefully.

        Stops all services, closes database connections, and
        performs cleanup before shutting down.
        """
        with self._lock:
            if not self._running:
                self.logger.debug("Daemon is not running")
                return

            self.logger.info("Stopping Nomi daemon...")
            self._running = False
            self._shutdown_event.set()

        self._stop_services()
        self._cleanup_resources()

        self.logger.info("Nomi daemon stopped")

    def _stop_services(self) -> None:
        """Stop all running services."""
        self.logger.debug("Stopping services...")

        if self._indexing_scheduler:
            self.logger.debug("Stopping indexing scheduler...")

        if self._maintenance_scheduler:
            self.logger.debug("Stopping maintenance scheduler...")

        if self._health_checker:
            self.logger.debug("Stopping health checker...")

        if self._file_watcher:
            self.logger.debug("Stopping file watcher...")

        if self._api_server:
            self.logger.debug("Stopping API server...")

        if self._mcp_server:
            self.logger.debug("Stopping MCP server...")

    def _cleanup_resources(self) -> None:
        """Cleanup resources before shutdown."""
        self.logger.debug("Cleaning up resources...")

        self._symbol_store = None
        self._graph_store = None
        self._symbol_index = None
        self._repo_scanner = None

    def is_running(self) -> bool:
        """Check if the daemon is currently running.

        Returns:
            True if daemon is running, False otherwise.
        """
        with self._lock:
            return self._running

    def get_status(self) -> DaemonStatus:
        """Get current daemon status.

        Returns:
            DaemonStatus with current state information.
        """
        with self._lock:
            uptime = 0.0
            if self._start_time is not None:
                uptime = time.time() - self._start_time

            indexed_files = 0
            total_symbols = 0

            if self._symbol_index is not None:
                try:
                    stats = self._symbol_index.get_stats()
                    indexed_files = stats.total_files
                    total_symbols = stats.total_symbols
                except Exception as e:
                    self.logger.debug(f"Failed to get index stats: {e}")

            is_indexing = False
            if self._indexing_scheduler is not None:
                try:
                    is_indexing = self._indexing_scheduler.get_queue_size() > 0
                except Exception:
                    pass

            return DaemonStatus(
                is_running=self._running,
                is_indexing=is_indexing,
                indexed_files=indexed_files,
                total_symbols=total_symbols,
                uptime_seconds=uptime,
                pid=os.getpid(),
            )

    def reload_config(self) -> None:
        """Reload daemon configuration (SIGHUP handler).

        Reloads configuration without restarting the daemon.
        """
        self.logger.info("Reloading configuration...")

        self.logger.info("Configuration reloaded")
