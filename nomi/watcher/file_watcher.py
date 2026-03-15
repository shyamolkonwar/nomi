"""File watching module for Nomi.

This module provides filesystem monitoring capabilities using the watchdog library
for cross-platform file change detection.
"""

import threading
from enum import Enum
from pathlib import Path
from typing import Callable, List, Optional

from watchdog.observers import Observer
from watchdog.observers.api import ObservedWatch

from nomi.utils.logger import LoggerMixin


class FileChangeType(Enum):
    """Enumeration of file change event types."""

    CREATED = "created"
    MODIFIED = "modified"
    DELETED = "deleted"
    MOVED = "moved"


class FileWatcher(LoggerMixin):
    """Main file watcher for monitoring filesystem changes.

    Uses the watchdog library to monitor a directory tree for file changes
    and invokes a callback when changes are detected. Supports ignore patterns
    and thread-safe operations.

    Attributes:
        watch_path: The root directory path to watch.
        ignore_patterns: List of glob patterns for files/directories to ignore.
        on_file_changed: Callback function invoked when a file changes.
    """

    def __init__(
        self,
        watch_path: str,
        ignore_patterns: List[str],
        on_file_changed: Callable[[str, FileChangeType], None],
    ) -> None:
        """Initialize the file watcher.

        Args:
            watch_path: The root directory path to watch.
            ignore_patterns: List of glob patterns for files/directories to ignore.
            on_file_changed: Callback function invoked when a file changes.
                Receives the file path and change type as arguments.
        """
        self.watch_path = Path(watch_path).resolve()
        self.ignore_patterns = list(ignore_patterns)
        self.on_file_changed = on_file_changed

        self._observer: Optional[Observer] = None
        self._watch: Optional[ObservedWatch] = None
        self._lock = threading.RLock()
        self._is_watching = False

        self.logger.info(
            f"FileWatcher initialized: watch_path={self.watch_path}, "
            f"ignore_count={len(self.ignore_patterns)}"
        )

    def start(self) -> None:
        """Start watching the filesystem for changes.

        Creates and starts the watchdog Observer with a custom event handler.
        Thread-safe - can be called from any thread.
        """
        with self._lock:
            if self._is_watching:
                self.logger.debug("FileWatcher already watching, ignoring start() call")
                return

            from nomi.watcher.change_handler import ChangeHandler

            self._observer = Observer()
            self._handler = ChangeHandler(
                callback=self._handle_change,
                ignore_patterns=self.ignore_patterns,
            )

            self._watch = self._observer.schedule(
                self._handler,
                str(self.watch_path),
                recursive=True,
            )

            self._observer.start()
            self._is_watching = True

            self.logger.info(f"FileWatcher started: watch_path={self.watch_path}")

    def stop(self) -> None:
        """Stop watching the filesystem.

        Stops and joins the observer thread. Thread-safe.
        """
        with self._lock:
            if not self._is_watching or self._observer is None:
                self.logger.debug("FileWatcher not watching, ignoring stop() call")
                return

            self.logger.info("Stopping FileWatcher...")

            self._observer.stop()
            self._observer.join(timeout=5.0)

            if self._observer.is_alive():
                self.logger.warning("Observer thread did not terminate gracefully")

            self._observer = None
            self._watch = None
            self._is_watching = False

            self.logger.info("FileWatcher stopped")

    def is_watching(self) -> bool:
        """Check if the watcher is currently active.

        Returns:
            True if watching, False otherwise.
        """
        with self._lock:
            return self._is_watching

    def add_ignore_pattern(self, pattern: str) -> None:
        """Add a new ignore pattern.

        Args:
            pattern: Glob pattern to add to the ignore list.
        """
        with self._lock:
            if pattern not in self.ignore_patterns:
                self.ignore_patterns.append(pattern)
                self.logger.debug(f"Added ignore pattern: pattern={pattern}")

    def remove_ignore_pattern(self, pattern: str) -> bool:
        """Remove an ignore pattern.

        Args:
            pattern: Glob pattern to remove from the ignore list.

        Returns:
            True if pattern was found and removed, False otherwise.
        """
        with self._lock:
            if pattern in self.ignore_patterns:
                self.ignore_patterns.remove(pattern)
                self.logger.debug(f"Removed ignore pattern: pattern={pattern}")
                return True
            return False

    def get_watched_paths(self) -> List[str]:
        """Get the list of paths being watched.

        Returns:
            List of watched directory paths.
        """
        with self._lock:
            if self._watch is not None:
                return [str(self.watch_path)]
            return []

    def _handle_change(self, file_path: str, change_type: FileChangeType) -> None:
        """Internal handler for file changes.

        Args:
            file_path: Path to the changed file.
            change_type: Type of change that occurred.
        """
        self.logger.debug(f"File change detected: file_path={file_path}, change_type={change_type.value}")

        try:
            self.on_file_changed(file_path, change_type)
        except Exception as e:
            self.logger.error(
                f"Error in file change callback: file_path={file_path}, "
                f"change_type={change_type.value}, error={e}"
            )

    def __enter__(self):
        """Context manager entry - start watching."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - stop watching."""
        self.stop()
        return False
