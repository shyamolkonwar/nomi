"""Indexing scheduler for background processing.

This module provides the IndexingScheduler class for managing
background indexing operations with queue-based task processing.
"""

import queue
import threading
import time
from typing import List, Optional

from nomi.core.index.symbol_index import SymbolIndex
from nomi.discovery.repo_scanner import RepoScanner
from nomi.utils.logger import LoggerMixin


class IndexingScheduler(LoggerMixin):
    """Scheduler for background indexing operations.

    Manages a queue of indexing tasks and processes them in a
    background thread. Supports full repository scans and
    incremental updates for changed files.

    Attributes:
        symbol_index: The SymbolIndex instance for indexing files.
        repo_scanner: The RepoScanner instance for discovering files.
    """

    def __init__(
        self,
        symbol_index: SymbolIndex,
        repo_scanner: RepoScanner,
    ) -> None:
        """Initialize the indexing scheduler.

        Args:
            symbol_index: SymbolIndex instance for indexing operations.
            repo_scanner: RepoScanner instance for file discovery.
        """
        self.symbol_index = symbol_index
        self.repo_scanner = repo_scanner

        self._queue: queue.Queue = queue.Queue()
        self._lock = threading.RLock()
        self._paused = False
        self._worker_thread: Optional[threading.Thread] = None
        self._shutdown_event = threading.Event()

        self._start_worker()
        self.logger.info("IndexingScheduler initialized")

    def _start_worker(self) -> None:
        """Start the background worker thread."""
        self._worker_thread = threading.Thread(
            target=self._process_queue,
            name="IndexingSchedulerWorker",
            daemon=True,
        )
        self._worker_thread.start()
        self.logger.debug("Worker thread started")

    def _process_queue(self) -> None:
        """Process tasks from the queue in a background thread.

        Runs continuously until shutdown event is set.
        """
        self.logger.debug("Worker thread running")

        while not self._shutdown_event.is_set():
            try:
                task = self._queue.get(timeout=1.0)

                with self._lock:
                    if self._paused:
                        self._queue.put(task)
                        time.sleep(0.1)
                        continue

                self._execute_task(task)
                self._queue.task_done()

            except queue.Empty:
                continue
            except Exception as e:
                self.logger.error(f"Error processing indexing task: {e}")

        self.logger.debug("Worker thread stopped")

    def _execute_task(self, task: dict) -> None:
        """Execute a single indexing task.

        Args:
            task: Dictionary containing task type and data.
        """
        task_type = task.get("type")

        try:
            if task_type == "full_index":
                self._execute_full_index()
            elif task_type == "incremental":
                file_paths = task.get("file_paths", [])
                self._execute_incremental_update(file_paths)
            else:
                self.logger.warning(f"Unknown task type: task_type={task_type}")
        except Exception as e:
            self.logger.error(f"Task execution failed: task_type={task_type}, error={e}")

    def _execute_full_index(self) -> None:
        """Execute a full repository scan and index."""
        self.logger.info("Starting full repository index...")

        try:
            discovered_files = self.repo_scanner.scan()
            file_paths = [f.path for f in discovered_files]

            if file_paths:
                result = self.symbol_index.index_files(file_paths)

                self.logger.info(
                    f"Full index complete: indexed_count={result.indexed_count}, "
                    f"file_count={len(file_paths)}, duration_ms={result.duration_ms}"
                )
            else:
                self.logger.info("No files to index")

        except Exception as e:
            self.logger.error(f"Full index failed: {e}")
            raise

    def _execute_incremental_update(self, file_paths: List[str]) -> None:
        """Execute incremental update for changed files.

        Args:
            file_paths: List of file paths to update.
        """
        self.logger.info(f"Starting incremental update: file_count={len(file_paths)}")

        try:
            discovered_files = self.repo_scanner.scan_incremental(file_paths)
            valid_paths = [f.path for f in discovered_files]

            if valid_paths:
                result = self.symbol_index.index_files(valid_paths)

                self.logger.info(
                    f"Incremental update complete: indexed_count={result.indexed_count}, "
                    f"file_count={len(valid_paths)}, duration_ms={result.duration_ms}"
                )
            else:
                self.logger.debug("No valid files to update")

        except Exception as e:
            self.logger.error(f"Incremental update failed: {e}")
            raise

    def schedule_full_index(self) -> None:
        """Queue a full repository scan and index operation."""
        task = {"type": "full_index"}
        self._queue.put(task)
        self.logger.debug("Full index scheduled")

    def schedule_incremental_update(self, file_paths: List[str]) -> None:
        """Queue an incremental update for changed files.

        Args:
            file_paths: List of file paths that have changed.
        """
        if not file_paths:
            self.logger.debug("No files to schedule for incremental update")
            return

        task = {"type": "incremental", "file_paths": file_paths}
        self._queue.put(task)
        self.logger.debug(f"Incremental update scheduled: file_count={len(file_paths)}")

    def get_queue_size(self) -> int:
        """Get the current number of pending tasks.

        Returns:
            Number of tasks in the queue.
        """
        return self._queue.qsize()

    def pause(self) -> None:
        """Pause the scheduler from processing new tasks.

        Tasks will continue to be queued but won't be processed
        until resume() is called.
        """
        with self._lock:
            self._paused = True
            self.logger.info("Indexing scheduler paused")

    def resume(self) -> None:
        """Resume processing tasks after a pause."""
        with self._lock:
            self._paused = False
            self.logger.info("Indexing scheduler resumed")

    def shutdown(self) -> None:
        """Shutdown the scheduler gracefully.

        Stops the worker thread and clears pending tasks.
        """
        self.logger.info("Shutting down IndexingScheduler...")
        self._shutdown_event.set()

        if self._worker_thread and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=5.0)
            if self._worker_thread.is_alive():
                self.logger.warning("Worker thread did not terminate gracefully")

        while not self._queue.empty():
            try:
                self._queue.get_nowait()
                self._queue.task_done()
            except queue.Empty:
                break

        self.logger.info("IndexingScheduler shutdown complete")
