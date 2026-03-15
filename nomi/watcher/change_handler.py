"""Change event handler for file watching.

This module provides the ChangeHandler class that processes filesystem events
from the watchdog library and invokes callbacks with debounced changes.
"""

import fnmatch
import os
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional

from watchdog.events import (
    DirCreatedEvent,
    DirDeletedEvent,
    DirModifiedEvent,
    DirMovedEvent,
    FileCreatedEvent,
    FileDeletedEvent,
    FileModifiedEvent,
    FileMovedEvent,
    FileSystemEvent,
    FileSystemEventHandler,
)

from nomi.utils.logger import LoggerMixin
from nomi.watcher.file_watcher import FileChangeType


@dataclass
class FileChange:
    """Represents a single file change event.

    Attributes:
        path: Absolute path to the changed file.
        change_type: Type of change (created, modified, deleted, moved).
        timestamp: When the change occurred.
        is_directory: Whether the change was to a directory.
    """

    path: str
    change_type: FileChangeType
    timestamp: datetime = field(default_factory=datetime.now)
    is_directory: bool = False


class ChangeHandler(FileSystemEventHandler, LoggerMixin):
    """Event handler for filesystem changes.

    Extends watchdog's FileSystemEventHandler to process file system events
    and invoke callbacks. Supports ignore patterns and change debouncing.

    Attributes:
        callback: Function to call when a file change is detected.
        ignore_patterns: List of glob patterns for paths to ignore.
    """

    def __init__(
        self,
        callback: Callable[[str, FileChangeType], None],
        ignore_patterns: List[str],
    ) -> None:
        """Initialize the change handler.

        Args:
            callback: Function to invoke when a file change is detected.
                Receives the file path and change type.
            ignore_patterns: List of glob patterns for files/directories to ignore.
        """
        self.callback = callback
        self.ignore_patterns = list(ignore_patterns)
        self._lock = threading.RLock()
        self._pending_changes: Dict[str, FileChange] = {}
        self._debounce_timer: Optional[threading.Timer] = None
        self._debounce_delay_ms = 500

        self.logger.debug(
            "ChangeHandler initialized",
            ignore_count=len(self.ignore_patterns),
        )

    def on_created(self, event: FileSystemEvent) -> None:
        """Handle file or directory creation events.

        Args:
            event: The creation event from watchdog.
        """
        if isinstance(event, (FileCreatedEvent, DirCreatedEvent)):
            if self.should_ignore(event.src_path):
                return

            change = FileChange(
                path=event.src_path,
                change_type=FileChangeType.CREATED,
                is_directory=event.is_directory,
            )
            self._queue_change(change)

    def on_modified(self, event: FileSystemEvent) -> None:
        """Handle file or directory modification events.

        Args:
            event: The modification event from watchdog.
        """
        if isinstance(event, (FileModifiedEvent, DirModifiedEvent)):
            if self.should_ignore(event.src_path):
                return

            change = FileChange(
                path=event.src_path,
                change_type=FileChangeType.MODIFIED,
                is_directory=event.is_directory,
            )
            self._queue_change(change)

    def on_deleted(self, event: FileSystemEvent) -> None:
        """Handle file or directory deletion events.

        Args:
            event: The deletion event from watchdog.
        """
        if isinstance(event, (FileDeletedEvent, DirDeletedEvent)):
            if self.should_ignore(event.src_path):
                return

            change = FileChange(
                path=event.src_path,
                change_type=FileChangeType.DELETED,
                is_directory=event.is_directory,
            )
            self._queue_change(change)

    def on_moved(self, event: FileSystemEvent) -> None:
        """Handle file or directory move/rename events.

        Args:
            event: The move event from watchdog.
        """
        if isinstance(event, (FileMovedEvent, DirMovedEvent)):
            if self.should_ignore(event.src_path) and self.should_ignore(
                event.dest_path
            ):
                return

            change = FileChange(
                path=event.src_path,
                change_type=FileChangeType.MOVED,
                is_directory=event.is_directory,
            )
            self._queue_change(change, dest_path=event.dest_path)

    def should_ignore(self, path: str) -> bool:
        """Check if a path should be ignored based on patterns.

        Args:
            path: The file or directory path to check.

        Returns:
            True if the path should be ignored, False otherwise.
        """
        path_parts = Path(path).parts
        filename = os.path.basename(path)

        for pattern in self.ignore_patterns:
            if fnmatch.fnmatch(filename, pattern):
                return True

            for part in path_parts:
                if fnmatch.fnmatch(part, pattern):
                    return True

            if fnmatch.fnmatch(path, pattern):
                return True

        return False

    def _queue_change(
        self, change: FileChange, dest_path: Optional[str] = None
    ) -> None:
        """Queue a change for debounced processing.

        Args:
            change: The file change to queue.
            dest_path: Optional destination path for move events.
        """
        with self._lock:
            self._pending_changes[change.path] = change

            if self._debounce_timer is not None:
                self._debounce_timer.cancel()

            self._debounce_timer = threading.Timer(
                self._debounce_delay_ms / 1000.0,
                self._flush_changes,
            )
            self._debounce_timer.daemon = True
            self._debounce_timer.start()

    def _flush_changes(self) -> None:
        """Flush all pending changes and invoke callbacks."""
        with self._lock:
            changes = list(self._pending_changes.values())
            self._pending_changes.clear()
            self._debounce_timer = None

        debounced = self.debounce_changes(changes, self._debounce_delay_ms)

        for change in debounced:
            try:
                if not change.is_directory:
                    self.callback(change.path, change.change_type)
            except Exception as e:
                self.logger.error(
                    "Error invoking change callback",
                    path=change.path,
                    change_type=change.change_type.value,
                    error=str(e),
                )

    def debounce_changes(
        self, changes: List[FileChange], delay_ms: int = 500
    ) -> List[FileChange]:
        """Debounce rapid successive changes to the same file.

        Groups multiple changes to the same file within the delay window,
        keeping only the most recent change type.

        Args:
            changes: List of file changes to debounce.
            delay_ms: Time window in milliseconds for grouping changes.

        Returns:
            List of debounced changes.
        """
        if not changes:
            return []

        delay_seconds = delay_ms / 1000.0

        path_changes: Dict[str, List[FileChange]] = {}
        for change in changes:
            if change.path not in path_changes:
                path_changes[change.path] = []
            path_changes[change.path].append(change)

        result: List[FileChange] = []

        for path, path_change_list in path_changes.items():
            path_change_list.sort(key=lambda c: c.timestamp)

            groups: List[List[FileChange]] = []
            current_group: List[FileChange] = []

            for change in path_change_list:
                if not current_group:
                    current_group.append(change)
                else:
                    last_change = current_group[-1]
                    time_diff = (change.timestamp - last_change.timestamp).total_seconds()
                    if time_diff <= delay_seconds:
                        current_group.append(change)
                    else:
                        groups.append(current_group)
                        current_group = [change]

            if current_group:
                groups.append(current_group)

            for group in groups:
                representative = group[-1]

                if len(group) > 1:
                    has_created = any(
                        c.change_type == FileChangeType.CREATED for c in group
                    )
                    has_deleted = any(
                        c.change_type == FileChangeType.DELETED for c in group
                    )

                    if has_created and has_deleted:
                        if group[-1].change_type == FileChangeType.CREATED:
                            representative = group[-1]
                        else:
                            representative = next(
                                c for c in reversed(group) if c.change_type == FileChangeType.CREATED
                            )

                result.append(representative)

        result.sort(key=lambda c: c.timestamp)
        return result
