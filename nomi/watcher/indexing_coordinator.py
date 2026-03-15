"""Indexing coordinator for file watching.

This module provides the IndexingCoordinator class that coordinates
between the file watcher and the symbol index, handling file changes
and triggering appropriate indexing operations.
"""

from nomi.core.index.symbol_index import SymbolIndex
from nomi.utils.logger import LoggerMixin
from nomi.watcher.batch_processor import BatchProcessor
from nomi.watcher.file_watcher import FileChangeType, FileWatcher


class IndexingCoordinator(LoggerMixin):
    """Coordinates file watching with symbol indexing.

    Acts as a bridge between the file watcher and the symbol index,
    handling file change events and triggering appropriate indexing
    operations. Uses batch processing to optimize indexing performance.

    Attributes:
        symbol_index: The SymbolIndex instance for indexing operations.
        file_watcher: The FileWatcher instance for monitoring file changes.
        batch_processor: Processes file changes in batches.
    """

    def __init__(
        self,
        symbol_index: SymbolIndex,
        file_watcher: FileWatcher,
    ) -> None:
        """Initialize the indexing coordinator.

        Args:
            symbol_index: SymbolIndex instance for indexing operations.
            file_watcher: FileWatcher instance for monitoring file changes.
        """
        self.symbol_index = symbol_index
        self.file_watcher = file_watcher

        self.batch_processor = BatchProcessor(
            processor=self._process_batch,
            batch_delay_ms=1000,
        )

        self._moved_files: dict[str, str] = {}

        self.logger.info("IndexingCoordinator initialized")

    def start(self) -> None:
        """Start the coordinator.

        Starts the batch processor and file watcher.
        """
        self.logger.info("Starting IndexingCoordinator...")
        self.batch_processor.start()
        self.file_watcher.start()
        self.logger.info("IndexingCoordinator started")

    def stop(self) -> None:
        """Stop the coordinator.

        Stops the file watcher and batch processor gracefully.
        """
        self.logger.info("Stopping IndexingCoordinator...")
        self.file_watcher.stop()
        self.batch_processor.stop()
        self.logger.info("IndexingCoordinator stopped")

    def on_file_changed(self, file_path: str, change_type: FileChangeType) -> None:
        """Callback for file change events.

        Called by the file watcher when a file change is detected.
        Queues the change for batch processing.

        Args:
            file_path: Path to the changed file.
            change_type: Type of change that occurred.
        """
        self.logger.debug(f"File change received: file_path={file_path}, change_type={change_type.value}")

        try:
            if change_type == FileChangeType.CREATED:
                self.handle_created(file_path)
            elif change_type == FileChangeType.MODIFIED:
                self.handle_modified(file_path)
            elif change_type == FileChangeType.DELETED:
                self.handle_deleted(file_path)
            elif change_type == FileChangeType.MOVED:
                self._handle_moved_event(file_path)
            else:
                self.logger.warning(f"Unknown change type: change_type={change_type.value}")
        except Exception as e:
            self.logger.error(
                f"Error handling file change: file_path={file_path}, "
                f"change_type={change_type.value}, error={e}"
            )

    def handle_created(self, file_path: str) -> None:
        """Handle a file creation event.

        Queues the new file for indexing.

        Args:
            file_path: Path to the created file.
        """
        self.logger.debug(f"Handling file creation: file_path={file_path}")
        self.batch_processor.add_change(file_path)

    def handle_modified(self, file_path: str) -> None:
        """Handle a file modification event.

        Queues the modified file for re-indexing.

        Args:
            file_path: Path to the modified file.
        """
        self.logger.debug(f"Handling file modification: file_path={file_path}")
        self.batch_processor.add_change(file_path)

    def handle_deleted(self, file_path: str) -> None:
        """Handle a file deletion event.

        Removes the file from the index immediately.

        Args:
            file_path: Path to the deleted file.
        """
        self.logger.debug(f"Handling file deletion: file_path={file_path}")

        try:
            self.symbol_index.remove_file(file_path)
            self.logger.info(f"Removed deleted file from index: file_path={file_path}")
        except Exception as e:
            self.logger.error(f"Failed to remove file from index: file_path={file_path}, error={e}")

    def _handle_moved_event(self, src_path: str) -> None:
        """Handle a file move event (internal).

        For move events, we need to track the source path and
        queue the destination for indexing.

        Args:
            src_path: Original path of the moved file.
        """
        self.logger.debug(f"Handling file move: src_path={src_path}")

        try:
            self.symbol_index.remove_file(src_path)
            self.logger.debug(f"Removed moved file from index: src_path={src_path}")
        except Exception as e:
            self.logger.error(f"Failed to remove moved file from index: src_path={src_path}, error={e}")

    def handle_moved(self, src_path: str, dest_path: str) -> None:
        """Handle a file move/rename event.

        Updates the index to reflect the new file path.

        Args:
            src_path: Original path of the moved file.
            dest_path: New path of the moved file.
        """
        self.logger.debug(f"Handling file move: src_path={src_path}, dest_path={dest_path}")

        try:
            self.symbol_index.remove_file(src_path)
            self.batch_processor.add_change(dest_path)
            self.logger.info(f"Queued moved file for re-indexing: src_path={src_path}, dest_path={dest_path}")
        except Exception as e:
            self.logger.error(f"Failed to handle file move: src_path={src_path}, dest_path={dest_path}, error={e}")

    def _process_batch(self, file_paths: list[str]) -> None:
        """Process a batch of file changes.

        Called by the BatchProcessor when a batch is ready.
        Invokes incremental indexing on the symbol index.

        Args:
            file_paths: List of file paths to process.
        """
        if not file_paths:
            return

        self.logger.info(f"Processing batch of file changes: file_count={len(file_paths)}")

        try:
            self.symbol_index.index_files(file_paths)
            self.logger.info(f"Batch processing complete: file_count={len(file_paths)}")
        except Exception as e:
            self.logger.error(f"Batch processing failed: file_count={len(file_paths)}, error={e}")

    def __enter__(self):
        """Context manager entry - start the coordinator."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - stop the coordinator."""
        self.stop()
        return False
