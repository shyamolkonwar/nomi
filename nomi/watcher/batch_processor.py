"""Batch processor for file changes.

This module provides the BatchProcessor class for efficiently processing
file changes in batches, reducing thrashing from rapid successive changes.
"""

import threading
import time
from typing import Callable, List, Optional, Set

from nomi.utils.logger import LoggerMixin


class BatchProcessor(LoggerMixin):
    """Processor for batching file changes.

    Collects file changes and processes them in batches after a delay,
    reducing the overhead of processing rapid successive changes to
    the same or different files.

    Attributes:
        processor: Callback function that processes batches of file paths.
        batch_delay_ms: Delay in milliseconds before processing a batch.
    """

    def __init__(
        self,
        processor: Callable[[List[str]], None],
        batch_delay_ms: int = 1000,
    ) -> None:
        """Initialize the batch processor.

        Args:
            processor: Callback function that receives a list of file paths
                to process. Called when a batch is flushed.
            batch_delay_ms: Delay in milliseconds before processing a batch.
                Changes within this window are grouped together.
        """
        self.processor = processor
        self.batch_delay_ms = batch_delay_ms

        self._pending: Set[str] = set()
        self._lock = threading.RLock()
        self._timer: Optional[threading.Timer] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._shutdown_event = threading.Event()

        self.logger.debug(
            "BatchProcessor initialized",
            batch_delay_ms=batch_delay_ms,
        )

    def start(self) -> None:
        """Start the batch processor.

        Starts the background processing thread.
        """
        with self._lock:
            if self._running:
                self.logger.debug("BatchProcessor already running")
                return

            self._running = True
            self._shutdown_event.clear()
            self._thread = threading.Thread(
                target=self._process_loop,
                name="BatchProcessorThread",
                daemon=True,
            )
            self._thread.start()

            self.logger.info("BatchProcessor started")

    def stop(self) -> None:
        """Stop the batch processor.

        Flushes any pending changes and stops the background thread.
        """
        with self._lock:
            if not self._running:
                self.logger.debug("BatchProcessor not running")
                return

            self.logger.info("Stopping BatchProcessor...")
            self._shutdown_event.set()

            if self._timer is not None:
                self._timer.cancel()
                self._timer = None

            self._running = False

        self.flush()

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)
            if self._thread.is_alive():
                self.logger.warning("BatchProcessor thread did not terminate gracefully")

        self.logger.info("BatchProcessor stopped")

    def add_change(self, file_path: str) -> None:
        """Add a file change to the pending batch.

        Args:
            file_path: Path to the file that changed.
        """
        with self._lock:
            if not self._running:
                self.logger.warning(
                    "Cannot add change - BatchProcessor not running",
                    file_path=file_path,
                )
                return

            self._pending.add(file_path)

            if self._timer is not None:
                self._timer.cancel()

            self._timer = threading.Timer(
                self.batch_delay_ms / 1000.0,
                self.flush,
            )
            self._timer.daemon = True
            self._timer.start()

            self.logger.debug(
                "Change added to batch",
                file_path=file_path,
                pending_count=len(self._pending),
            )

    def flush(self) -> None:
        """Process all pending changes immediately.

        Invokes the processor callback with all pending file paths
        and clears the pending set.
        """
        with self._lock:
            if not self._pending:
                return

            files_to_process = list(self._pending)
            self._pending.clear()

            if self._timer is not None:
                self._timer.cancel()
                self._timer = None

        self.logger.debug(
            "Flushing batch",
            file_count=len(files_to_process),
        )

        try:
            self.processor(files_to_process)
            self.logger.debug(
                "Batch processed successfully",
                file_count=len(files_to_process),
            )
        except Exception as e:
            self.logger.error(
                "Error processing batch",
                file_count=len(files_to_process),
                error=str(e),
            )

    def _process_loop(self) -> None:
        """Background processing loop.

        Runs until shutdown event is set. Periodically checks for
        pending changes and flushes them.
        """
        self.logger.debug("BatchProcessor loop started")

        while not self._shutdown_event.is_set():
            time.sleep(0.1)

            with self._lock:
                if self._pending and self._timer is None:
                    pass

        self.logger.debug("BatchProcessor loop stopped")

    def get_pending_count(self) -> int:
        """Get the number of pending changes.

        Returns:
            Number of files waiting to be processed.
        """
        with self._lock:
            return len(self._pending)

    def is_running(self) -> bool:
        """Check if the processor is running.

        Returns:
            True if running, False otherwise.
        """
        with self._lock:
            return self._running

    def __enter__(self):
        """Context manager entry - start the processor."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - stop the processor."""
        self.stop()
        return False
