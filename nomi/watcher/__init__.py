"""File watching package for Nomi.

This package provides filesystem monitoring capabilities for tracking
file changes and coordinating with the indexing system.
"""

from nomi.watcher.batch_processor import BatchProcessor
from nomi.watcher.change_handler import ChangeHandler, FileChange
from nomi.watcher.file_watcher import FileChangeType, FileWatcher
from nomi.watcher.indexing_coordinator import IndexingCoordinator

__all__ = [
    "FileWatcher",
    "FileChangeType",
    "ChangeHandler",
    "FileChange",
    "BatchProcessor",
    "IndexingCoordinator",
]
