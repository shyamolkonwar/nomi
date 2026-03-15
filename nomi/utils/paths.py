"""Path utilities for Nomi.

This module provides utilities for working with file paths,
including project root detection, path resolution, and ignore pattern matching.
"""

import fnmatch
import os
from pathlib import Path
from typing import List


# Common directories and files to ignore
DEFAULT_IGNORE_PATTERNS = [
    ".git",
    "node_modules",
    "dist",
    "build",
    "vendor",
    ".cache",
    "__pycache__",
    ".venv",
    "venv",
    "*.pyc",
    "*.pyo",
    "*.so",
    "*.dylib",
    "*.dll",
    ".DS_Store",
    "Thumbs.db",
    "*.log",
    ".env",
    ".env.*",
    "*.min.js",
    "*.min.css",
]

# Files that indicate a project root
PROJECT_ROOT_INDICATORS = [
    ".git",
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "package.json",
    "Cargo.toml",
    "go.mod",
    "pom.xml",
    "build.gradle",
    "Gemfile",
    ".nomi.json",
]


def get_project_root(start_path: Path | str | None = None) -> Path:
    """Find the project root directory.

    Searches upward from the start path (or current directory) looking
    for common project root indicators like .git directory or config files.

    Args:
        start_path: The path to start searching from. Defaults to current directory.

    Returns:
        Path to the project root directory.

    Example:
        >>> root = get_project_root()
        >>> root = get_project_root("/path/to/some/file.py")
    """
    if start_path is None:
        current = Path.cwd()
    else:
        current = Path(start_path).resolve()

    # If start_path is a file, start from its parent
    if current.is_file():
        current = current.parent

    # Search upward for project root indicators
    for path in [current, *current.parents]:
        for indicator in PROJECT_ROOT_INDICATORS:
            if (path / indicator).exists():
                return path

    # No indicator found, return the start path or current directory
    return current


def resolve_path(
    path: Path | str,
    base_path: Path | str | None = None,
) -> Path:
    """Resolve a path relative to a base directory.

    Args:
        path: The path to resolve.
        base_path: The base directory for relative paths. Defaults to project root.

    Returns:
        Absolute Path object.

    Example:
        >>> resolve_path("src/main.py")
        >>> resolve_path("../config.json", "/path/to/project")
    """
    path_obj = Path(path)

    if path_obj.is_absolute():
        return path_obj.resolve()

    if base_path is None:
        base = get_project_root()
    else:
        base = Path(base_path).resolve()

    return (base / path_obj).resolve()


def should_ignore_path(
    path: Path | str,
    ignore_patterns: List[str] | None = None,
    project_root: Path | str | None = None,
) -> bool:
    """Check if a path should be ignored based on patterns.

    Args:
        path: The path to check.
        ignore_patterns: List of glob patterns to match against.
            If None, uses DEFAULT_IGNORE_PATTERNS.
        project_root: The project root for relative path calculation.
            If None, uses get_project_root().

    Returns:
        True if the path should be ignored, False otherwise.

    Example:
        >>> should_ignore_path("node_modules/lodash/index.js")
        >>> should_ignore_path("src/main.py", ["*.pyc", "__pycache__"])
    """
    path_obj = Path(path)

    if ignore_patterns is None:
        ignore_patterns = DEFAULT_IGNORE_PATTERNS

    if project_root is None:
        root = get_project_root()
    else:
        root = Path(project_root).resolve()

    # Get path relative to project root for pattern matching
    try:
        rel_path = path_obj.relative_to(root)
    except ValueError:
        # Path is not under project root, use as-is
        rel_path = path_obj

    path_str = str(rel_path)
    path_parts = path_str.split(os.sep)

    for pattern in ignore_patterns:
        # Check if the full path matches
        if fnmatch.fnmatch(path_str, pattern):
            return True

        # Check if any path component matches
        for part in path_parts:
            if fnmatch.fnmatch(part, pattern):
                return True
            # Handle patterns like "dir/*"
            if pattern.endswith("/*") or pattern.endswith("/**"):
                dir_pattern = pattern.rstrip("/*")
                if fnmatch.fnmatch(part, dir_pattern):
                    return True

    return False


def is_text_file(path: Path | str, sample_size: int = 8192) -> bool:
    """Check if a file is a text file (not binary).

    Uses a heuristic that checks for null bytes in the file sample.

    Args:
        path: Path to the file.
        sample_size: Number of bytes to read for checking.

    Returns:
        True if the file appears to be text, False if binary.

    Example:
        >>> is_text_file("/path/to/file.py")
    """
    path_obj = Path(path)

    if not path_obj.exists() or not path_obj.is_file():
        return False

    try:
        with open(path_obj, "rb") as f:
            chunk = f.read(sample_size)
            if b"\x00" in chunk:
                return False
            return True
    except (IOError, OSError, PermissionError):
        return False


def get_relative_path(
    path: Path | str,
    base_path: Path | str,
) -> Path:
    """Get the relative path from base_path to path.

    Args:
        path: The target path.
        base_path: The base path to calculate relative to.

    Returns:
        Relative path from base_path to path.

    Example:
        >>> get_relative_path("/project/src/main.py", "/project")
        PosixPath('src/main.py')
    """
    path_obj = Path(path).resolve()
    base_obj = Path(base_path).resolve()

    return path_obj.relative_to(base_obj)


def find_files(
    root: Path | str,
    patterns: List[str],
    ignore_patterns: List[str] | None = None,
) -> List[Path]:
    """Find files matching patterns within a directory.

    Args:
        root: Root directory to search.
        patterns: List of glob patterns to match.
        ignore_patterns: List of patterns for paths to ignore.

    Returns:
        List of matching file paths.

    Example:
        >>> find_files(".", ["*.py"], ["__pycache__", "*.pyc"])
    """
    root_path = Path(root).resolve()
    matches: List[Path] = []

    if ignore_patterns is None:
        ignore_patterns = DEFAULT_IGNORE_PATTERNS

    for pattern in patterns:
        for path in root_path.rglob(pattern):
            if path.is_file():
                if not should_ignore_path(path, ignore_patterns, root_path):
                    matches.append(path)

    # Remove duplicates while preserving order
    seen: set = set()
    unique_matches: List[Path] = []
    for path in matches:
        if path not in seen:
            seen.add(path)
            unique_matches.append(path)

    return unique_matches
