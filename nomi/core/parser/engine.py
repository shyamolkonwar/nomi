"""Tree-sitter parsing engine for Nomi.

This module provides a wrapper around tree-sitter for parsing source code
across multiple programming languages with graceful error handling.
"""

import logging
from pathlib import Path
from typing import Dict, Optional

from tree_sitter import Language as TSLanguage, Parser, Tree

from nomi.discovery.language_detector import Language

logger = logging.getLogger(__name__)


class TreeSitterEngine:
    """Tree-sitter parsing engine supporting multiple languages.

    This class provides parsers for supported languages and handles
    incremental parsing with graceful error recovery.
    """

    # Grammar module names for tree-sitter-language pack
    _GRAMMAR_MODULES: Dict[Language, str] = {
        Language.PYTHON: "tree_sitter_python",
        Language.TYPESCRIPT: "tree_sitter_typescript",
        Language.JAVASCRIPT: "tree_sitter_javascript",
        Language.GO: "tree_sitter_go",
        Language.RUST: "tree_sitter_rust",
        Language.JAVA: "tree_sitter_java",
        Language.CPP: "tree_sitter_cpp",
    }

    def __init__(self) -> None:
        """Initialize the Tree-sitter engine with parsers for supported languages."""
        self._parsers: Dict[Language, Parser] = {}
        self._languages: Dict[Language, TSLanguage] = {}
        self._initialize_parsers()

    def _initialize_parsers(self) -> None:
        """Initialize parsers for all supported languages."""
        for language in Language:
            if language == Language.UNKNOWN:
                continue
            try:
                self.load_language(language)
            except Exception as e:
                logger.warning(f"Failed to load parser for {language.value}: {e}")

    def load_language(self, language: Language) -> Optional[TSLanguage]:
        """Load tree-sitter grammar for a language.

        Args:
            language: The programming language to load.

        Returns:
            The tree-sitter Language object, or None if loading fails.
        """
        if language in self._languages:
            return self._languages[language]

        if language == Language.UNKNOWN:
            return None

        module_name = self._GRAMMAR_MODULES.get(language)
        if not module_name:
            logger.warning(f"No grammar module configured for {language.value}")
            return None

        try:
            # Import the language module dynamically
            module = __import__(module_name)
            ts_language = TSLanguage(module.language())
            self._languages[language] = ts_language

            # Create and configure parser
            parser = Parser()
            parser.set_language(ts_language)
            self._parsers[language] = parser

            logger.debug(f"Successfully loaded parser for {language.value}")
            return ts_language

        except ImportError:
            logger.warning(
                f"Grammar module '{module_name}' not installed. "
                f"Install with: pip install {module_name.replace('_', '-')}"
            )
            return None
        except Exception as e:
            logger.error(f"Failed to load language {language.value}: {e}")
            return None

    def parse_file(self, file_path: str, language: Language) -> Optional[Tree]:
        """Parse a source file and return the syntax tree.

        Args:
            file_path: Absolute path to the source file.
            language: The programming language of the file.

        Returns:
            The parsed syntax tree, or None if parsing fails.
        """
        path = Path(file_path)
        if not path.exists():
            logger.error(f"File not found: {file_path}")
            return None

        try:
            source_bytes = path.read_bytes()
        except Exception as e:
            logger.error(f"Failed to read file {file_path}: {e}")
            return None

        return self.parse_bytes(source_bytes, language)

    def parse_bytes(self, source_bytes: bytes, language: Language) -> Optional[Tree]:
        """Parse source code bytes and return the syntax tree.

        Args:
            source_bytes: The source code as bytes.
            language: The programming language of the code.

        Returns:
            The parsed syntax tree, or None if parsing fails.
        """
        if language == Language.UNKNOWN:
            logger.warning("Cannot parse file with unknown language")
            return None

        parser = self._parsers.get(language)
        if not parser:
            # Try to load the language on-demand
            self.load_language(language)
            parser = self._parsers.get(language)

        if not parser:
            logger.error(f"No parser available for {language.value}")
            return None

        try:
            # Parse with error recovery (tree-sitter is tolerant to errors by default)
            tree = parser.parse(source_bytes)
            return tree
        except Exception as e:
            logger.error(f"Failed to parse source: {e}")
            return None

    def get_parser_for_python(self) -> Optional[Parser]:
        """Get the parser for Python.

        Returns:
            The Python parser, or None if not available.
        """
        return self._parsers.get(Language.PYTHON)

    def get_parser_for_typescript(self) -> Optional[Parser]:
        """Get the parser for TypeScript.

        Returns:
            The TypeScript parser, or None if not available.
        """
        return self._parsers.get(Language.TYPESCRIPT)

    def get_parser_for_javascript(self) -> Optional[Parser]:
        """Get the parser for JavaScript.

        Returns:
            The JavaScript parser, or None if not available.
        """
        return self._parsers.get(Language.JAVASCRIPT)

    def get_parser_for_go(self) -> Optional[Parser]:
        """Get the parser for Go.

        Returns:
            The Go parser, or None if not available.
        """
        return self._parsers.get(Language.GO)

    def get_parser_for_rust(self) -> Optional[Parser]:
        """Get the parser for Rust.

        Returns:
            The Rust parser, or None if not available.
        """
        return self._parsers.get(Language.RUST)

    def get_parser_for_java(self) -> Optional[Parser]:
        """Get the parser for Java.

        Returns:
            The Java parser, or None if not available.
        """
        return self._parsers.get(Language.JAVA)

    def get_parser_for_cpp(self) -> Optional[Parser]:
        """Get the parser for C++.

        Returns:
            The C++ parser, or None if not available.
        """
        return self._parsers.get(Language.CPP)

    def is_language_supported(self, language: Language) -> bool:
        """Check if a language has a loaded parser.

        Args:
            language: The language to check.

        Returns:
            True if the language parser is available.
        """
        return language in self._parsers

    def get_loaded_languages(self) -> list[Language]:
        """Get list of languages with loaded parsers.

        Returns:
            List of loaded languages.
        """
        return list(self._parsers.keys())
