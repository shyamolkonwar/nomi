"""Repository scanning for discovering and cataloging source files.

This module provides utilities to scan repositories, detect file types,
and collect metadata about source files.
"""

import fnmatch
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Iterator
import time

from nomi.discovery.language_detector import Language, LanguageDetector


@dataclass(frozen=True)
class DiscoveredFile:
    """Represents a discovered source file in the repository.

    Attributes:
        path: Absolute path to the file
        relative_path: Path relative to repository root
        language: Detected programming language
        size_bytes: File size in bytes
        last_modified: Last modification timestamp
    """

    path: str
    relative_path: str
    language: Language
    size_bytes: int
    last_modified: datetime


@dataclass
class ScanStats:
    """Statistics from a repository scan.

    Attributes:
        total_files: Total number of files discovered
        files_by_language: Count of files grouped by language
        total_size_bytes: Total size of all files in bytes
        scan_duration_ms: Time taken to complete the scan in milliseconds
    """

    total_files: int = 0
    files_by_language: Dict[Language, int] = field(default_factory=dict)
    total_size_bytes: int = 0
    scan_duration_ms: float = 0.0

    def add_file(self, file: DiscoveredFile) -> None:
        """Add a file to the statistics.

        Args:
            file: DiscoveredFile to include in stats
        """
        self.total_files += 1
        self.total_size_bytes += file.size_bytes
        self.files_by_language[file.language] = self.files_by_language.get(file.language, 0) + 1


class RepoScanner:
    """Scanner for discovering files in a repository.

    Scans the repository root directory, identifies source files by language,
    and collects metadata while respecting ignore patterns and .gitignore.
    """

    DEFAULT_IGNORE_PATTERNS: List[str] = [
        # Version control
        ".git",
        ".gitignore",
        ".hg",
        ".svn",
        # Dependencies and build artifacts
        "node_modules",
        "dist",
        "build",
        "vendor",
        "target",
        # Python
        ".cache",
        "__pycache__",
        ".venv",
        "venv",
        ".env",
        "*.pyc",
        "*.pyo",
        "*.so",
        "*.dylib",
        "*.dll",
        # Compiled files
        "*.o",
        "*.a",
        "*.lib",
        "*.exe",
        # IDE and OS
        ".DS_Store",
        "Thumbs.db",
        ".idea",
        ".vscode",
        "*.swp",
        "*.swo",
        "*~",
        # Testing and coverage
        "coverage",
        ".pytest_cache",
        ".mypy_cache",
        ".tox",
        "htmlcov",
        # Documentation build
        "_build",
        "site",
        ".docusaurus",
    ]

    MAX_FILE_SIZE_BYTES: int = 10 * 1024 * 1024  # 10MB

    def __init__(
        self,
        root_path: str,
        ignore_patterns: Optional[List[str]] = None,
        respect_gitignore: bool = True,
        max_file_size_bytes: Optional[int] = None,
    ):
        """Initialize the repository scanner.

        Args:
            root_path: Root directory to scan
            ignore_patterns: Additional patterns to ignore (extends defaults)
            respect_gitignore: Whether to respect .gitignore files
            max_file_size_bytes: Maximum file size to include (default 10MB)
        """
        self.root_path = Path(root_path).resolve()
        if not self.root_path.exists():
            raise ValueError(f"Root path does not exist: {root_path}")
        if not self.root_path.is_dir():
            raise ValueError(f"Root path is not a directory: {root_path}")

        self.ignore_patterns = list(self.DEFAULT_IGNORE_PATTERNS)
        if ignore_patterns:
            self.ignore_patterns.extend(ignore_patterns)

        self.respect_gitignore = respect_gitignore
        self.max_file_size_bytes = max_file_size_bytes or self.MAX_FILE_SIZE_BYTES
        self.language_detector = LanguageDetector()
        self._gitignore_patterns: Dict[Path, List[str]] = {}
        self._stats: ScanStats = ScanStats()

    def scan(self) -> List[DiscoveredFile]:
        """Scan the entire repository.

        Returns:
            List of discovered files
        """
        start_time = time.time()
        discovered_files: List[DiscoveredFile] = []
        self._stats = ScanStats()

        if self.respect_gitignore:
            self._load_gitignore_patterns()

        for file_path in self._walk_directory():
            try:
                discovered_file = self._process_file(file_path)
                if discovered_file:
                    discovered_files.append(discovered_file)
                    self._stats.add_file(discovered_file)
            except (OSError, PermissionError):
                # Log but continue scanning other files
                continue

        self._stats.scan_duration_ms = (time.time() - start_time) * 1000
        return discovered_files

    def scan_incremental(self, changed_files: List[str]) -> List[DiscoveredFile]:
        """Scan only specific changed files.

        Args:
            changed_files: List of file paths that have changed

        Returns:
            List of discovered files (only existing, non-ignored files)
        """
        discovered_files: List[DiscoveredFile] = []

        for file_path_str in changed_files:
            file_path = Path(file_path_str).resolve()

            # Skip if not within root
            if not str(file_path).startswith(str(self.root_path)):
                continue

            # Skip if matches ignore patterns
            relative_path = file_path.relative_to(self.root_path)
            if self._should_ignore(relative_path):
                continue

            # Skip if doesn't exist
            if not file_path.exists() or not file_path.is_file():
                continue

            try:
                discovered_file = self._process_file(file_path)
                if discovered_file:
                    discovered_files.append(discovered_file)
            except (OSError, PermissionError):
                continue

        return discovered_files

    def get_stats(self) -> ScanStats:
        """Get statistics from the last scan.

        Returns:
            ScanStats with file counts and metadata
        """
        return self._stats

    def _walk_directory(self) -> Iterator[Path]:
        """Walk the directory tree and yield file paths.

        Yields:
            Path objects for files to process
        """
        for dirpath, dirnames, filenames in os.walk(self.root_path):
            dirpath_path = Path(dirpath)

            # Filter directories in-place to avoid descending into ignored dirs
            dirnames[:] = [d for d in dirnames if not self._should_ignore_dir(dirpath_path / d)]

            for filename in filenames:
                file_path = dirpath_path / filename
                relative_path = file_path.relative_to(self.root_path)

                if not self._should_ignore(relative_path):
                    yield file_path

    def _should_ignore_dir(self, dir_path: Path) -> bool:
        """Check if a directory should be ignored.

        Args:
            dir_path: Path to the directory

        Returns:
            True if directory should be skipped
        """
        relative_path = dir_path.relative_to(self.root_path)

        for pattern in self.ignore_patterns:
            # Check exact match
            if str(relative_path) == pattern or relative_path.name == pattern:
                return True
            # Check pattern match
            if fnmatch.fnmatch(str(relative_path), pattern) or fnmatch.fnmatch(relative_path.name, pattern):
                return True

        return False

    def _should_ignore(self, relative_path: Path) -> bool:
        """Check if a file should be ignored.

        Args:
            relative_path: Path relative to repository root

        Returns:
            True if file should be ignored
        """
        path_str = str(relative_path)
        name = relative_path.name

        # Check ignore patterns against file name and full path
        for pattern in self.ignore_patterns:
            if fnmatch.fnmatch(path_str, pattern) or fnmatch.fnmatch(name, pattern):
                return True

        # Check if any parent directory should be ignored
        for parent in relative_path.parents:
            parent_str = str(parent)
            parent_name = parent.name
            for pattern in self.ignore_patterns:
                # Check exact match for directory names
                if parent_name == pattern:
                    return True
                # Check pattern match
                if fnmatch.fnmatch(parent_str, pattern) or fnmatch.fnmatch(parent_name, pattern):
                    return True

        # Check .gitignore patterns
        if self.respect_gitignore and self._matches_gitignore(relative_path):
            return True

        return False

    def _load_gitignore_patterns(self) -> None:
        """Load .gitignore patterns from the repository."""
        for gitignore_path in self.root_path.rglob(".gitignore"):
            try:
                patterns = self._parse_gitignore(gitignore_path)
                self._gitignore_patterns[gitignore_path.parent] = patterns
            except (OSError, PermissionError):
                continue

    def _parse_gitignore(self, gitignore_path: Path) -> List[str]:
        """Parse a .gitignore file and return patterns.

        Args:
            gitignore_path: Path to .gitignore file

        Returns:
            List of ignore patterns
        """
        patterns: List[str] = []
        try:
            with open(gitignore_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    # Skip empty lines and comments
                    if not line or line.startswith("#"):
                        continue
                    patterns.append(line)
        except (OSError, PermissionError):
            pass
        return patterns

    def _matches_gitignore(self, relative_path: Path) -> bool:
        """Check if a path matches any .gitignore pattern.

        Args:
            relative_path: Path relative to repository root

        Returns:
            True if path matches a gitignore pattern
        """
        for gitignore_dir, patterns in self._gitignore_patterns.items():
            try:
                path_from_gitignore = relative_path.relative_to(gitignore_dir.relative_to(self.root_path))
            except ValueError:
                # Path is not relative to this gitignore's directory
                continue

            for pattern in patterns:
                # Handle negation patterns (starting with !)
                if pattern.startswith("!"):
                    continue  # Skip negation for simplicity

                # Normalize pattern
                clean_pattern = pattern.rstrip("/")

                # Match against the path
                path_str = str(path_from_gitignore)
                name = path_from_gitignore.name

                if fnmatch.fnmatch(path_str, clean_pattern) or fnmatch.fnmatch(path_str, f"**/{clean_pattern}"):
                    return True
                if fnmatch.fnmatch(name, clean_pattern):
                    return True

        return False

    def _process_file(self, file_path: Path) -> Optional[DiscoveredFile]:
        """Process a single file and return DiscoveredFile if valid.

        Args:
            file_path: Path to the file

        Returns:
            DiscoveredFile or None if file should be skipped
        """
        try:
            # Check if it's a regular file (not symlink, not socket, etc.)
            if not file_path.is_file() or file_path.is_symlink():
                return None

            stat = file_path.stat()

            # Skip files that are too large
            if stat.st_size > self.max_file_size_bytes:
                return None

            # Skip empty files
            if stat.st_size == 0:
                return None

            relative_path = file_path.relative_to(self.root_path)
            language = self.language_detector.detect_language(str(file_path))

            return DiscoveredFile(
                path=str(file_path),
                relative_path=str(relative_path),
                language=language,
                size_bytes=stat.st_size,
                last_modified=datetime.fromtimestamp(stat.st_mtime),
            )

        except (OSError, PermissionError):
            return None
