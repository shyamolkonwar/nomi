"""Language detection for repository files.

This module provides utilities to detect programming languages based on
file extensions and paths.
"""

from enum import Enum
from pathlib import Path
from typing import List, Dict, Optional


class Language(Enum):
    """Enumeration of supported programming languages."""

    PYTHON = "python"
    TYPESCRIPT = "typescript"
    JAVASCRIPT = "javascript"
    GO = "go"
    RUST = "rust"
    JAVA = "java"
    CPP = "cpp"
    UNKNOWN = "unknown"


class FileExtensionMap:
    """Mapping of file extensions to programming languages."""

    EXTENSION_MAP: Dict[str, Language] = {
        # Python
        ".py": Language.PYTHON,
        ".pyw": Language.PYTHON,
        ".pyi": Language.PYTHON,
        # TypeScript
        ".ts": Language.TYPESCRIPT,
        ".tsx": Language.TYPESCRIPT,
        ".mts": Language.TYPESCRIPT,
        ".cts": Language.TYPESCRIPT,
        # JavaScript
        ".js": Language.JAVASCRIPT,
        ".jsx": Language.JAVASCRIPT,
        ".mjs": Language.JAVASCRIPT,
        ".cjs": Language.JAVASCRIPT,
        # Go
        ".go": Language.GO,
        # Rust
        ".rs": Language.RUST,
        # Java
        ".java": Language.JAVA,
        # C++
        ".cpp": Language.CPP,
        ".cc": Language.CPP,
        ".cxx": Language.CPP,
        ".hpp": Language.CPP,
        ".h": Language.CPP,
        ".hh": Language.CPP,
        ".hxx": Language.CPP,
    }

    @classmethod
    def get_language(cls, extension: str) -> Language:
        """Get language for a file extension.

        Args:
            extension: File extension (with or without leading dot)

        Returns:
            Language enum value, or Language.UNKNOWN if not recognized
        """
        ext = extension.lower() if not extension.startswith(".") else extension.lower()
        return cls.EXTENSION_MAP.get(ext, Language.UNKNOWN)

    @classmethod
    def get_extensions(cls, language: Language) -> List[str]:
        """Get all file extensions for a language.

        Args:
            language: Language enum value

        Returns:
            List of file extensions (with leading dot)
        """
        if language == Language.UNKNOWN:
            return []
        return [ext for ext, lang in cls.EXTENSION_MAP.items() if lang == language]


class LanguageDetector:
    """Detector for identifying programming languages from file paths."""

    def __init__(self, custom_mappings: Optional[Dict[str, Language]] = None):
        """Initialize the language detector.

        Args:
            custom_mappings: Optional custom extension to language mappings
        """
        self._extension_map = dict(FileExtensionMap.EXTENSION_MAP)
        if custom_mappings:
            self._extension_map.update(custom_mappings)

    def detect_language(self, file_path: str) -> Language:
        """Detect the programming language of a file.

        Args:
            file_path: Path to the file (absolute or relative)

        Returns:
            Language enum value
        """
        path = Path(file_path)
        extension = path.suffix.lower()
        return self._extension_map.get(extension, Language.UNKNOWN)

    def get_extension(self, language: Language) -> str:
        """Get the primary file extension for a language.

        Args:
            language: Language enum value

        Returns:
            Primary file extension (with leading dot), or empty string for UNKNOWN
        """
        if language == Language.UNKNOWN:
            return ""

        extensions = FileExtensionMap.get_extensions(language)
        if not extensions:
            return ""

        # Return the most common extension
        priority_map: Dict[Language, str] = {
            Language.PYTHON: ".py",
            Language.TYPESCRIPT: ".ts",
            Language.JAVASCRIPT: ".js",
            Language.GO: ".go",
            Language.RUST: ".rs",
            Language.JAVA: ".java",
            Language.CPP: ".cpp",
        }

        return priority_map.get(language, extensions[0])

    def is_supported(self, file_path: str) -> bool:
        """Check if a file has a supported/recognized extension.

        Args:
            file_path: Path to the file

        Returns:
            True if the file extension is recognized
        """
        return self.detect_language(file_path) != Language.UNKNOWN

    def get_all_extensions(self) -> List[str]:
        """Get all recognized file extensions.

        Returns:
            List of all supported file extensions (with leading dot)
        """
        return list(self._extension_map.keys())

    def get_supported_extensions_for_language(self, language: Language) -> List[str]:
        """Get all supported extensions for a specific language.

        Args:
            language: Language enum value

        Returns:
            List of file extensions for the language
        """
        return FileExtensionMap.get_extensions(language)
