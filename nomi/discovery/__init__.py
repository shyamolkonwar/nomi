"""Discovery module for Nomi - repository scanning and language detection.

This module provides utilities for scanning repositories and detecting
programming languages from file paths.
"""

from nomi.discovery.language_detector import LanguageDetector, Language
from nomi.discovery.repo_scanner import RepoScanner, DiscoveredFile, ScanStats

__all__ = [
    "LanguageDetector",
    "Language",
    "RepoScanner",
    "DiscoveredFile",
    "ScanStats",
]
