"""Symbol index manager for Nomi.

This module provides the SymbolIndex class for managing the indexing
of code symbols from source files into the storage system.
"""

import logging
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from nomi.core.parser.ast_extractor import ASTExtractor
from nomi.discovery.language_detector import Language
from nomi.storage.models import CodeUnit
from nomi.storage.sqlite.symbol_store import SymbolStore

logger = logging.getLogger(__name__)


@dataclass
class IndexResult:
    """Result of a batch indexing operation."""

    indexed_count: int
    failed_files: List[str]
    duration_ms: float


@dataclass
class IndexStats:
    """Statistics about the current index state."""

    total_symbols: int
    total_files: int
    symbols_by_language: Dict[Language, int]
    last_updated: datetime


class SymbolIndex:
    """Manages the indexing of code symbols from source files.

    This class provides methods to index individual files or batches of files,
    remove indexed files, and retrieve statistics about the index.
    """

    def __init__(self, db_path: str) -> None:
        """Initialize the symbol index.

        Args:
            db_path: Path to the SQLite database file.
        """
        self.db_path = Path(db_path)
        self.symbol_store = SymbolStore(self.db_path)
        self.ast_extractor = ASTExtractor()
        self._last_updated = datetime.now()

    def index_file(self, file_path: str, language: Language) -> List[CodeUnit]:
        """Index a single source file.

        Parses the file using ASTExtractor and stores all extracted
        CodeUnits in the SymbolStore.

        Args:
            file_path: Absolute path to the source file.
            language: The programming language of the file.

        Returns:
            List of indexed CodeUnits.
        """
        path = Path(file_path)
        if not path.exists():
            logger.warning(f"File does not exist: {file_path}")
            return []

        if language == Language.UNKNOWN:
            logger.warning(f"Unknown language for file: {file_path}")
            return []

        try:
            # Remove existing entries for this file first
            self.symbol_store.delete_by_file(file_path)

            # Extract code units from the file
            code_units = self.ast_extractor.extract_from_file(file_path, language)

            # Store each code unit
            for unit in code_units:
                self.symbol_store.insert_code_unit(unit)

            self._last_updated = datetime.now()

            logger.info(f"Indexed {len(code_units)} symbols from {file_path}")

            return code_units

        except Exception as e:
            logger.error(f"Failed to index file {file_path}: {e}")
            return []

    def index_files(self, file_paths: List[str]) -> IndexResult:
        """Index multiple source files in batch.

        Args:
            file_paths: List of absolute paths to source files.

        Returns:
            IndexResult containing statistics about the operation.
        """
        from nomi.discovery.language_detector import LanguageDetector

        detector = LanguageDetector()
        failed_files: List[str] = []
        total_indexed = 0

        start_time = time.perf_counter()

        for file_path in file_paths:
            language = detector.detect_language(file_path)

            if language == Language.UNKNOWN:
                logger.debug(f"Skipping unsupported file: {file_path}")
                continue

            code_units = self.index_file(file_path, language)

            if code_units:
                total_indexed += len(code_units)
            else:
                # Check if file actually has no symbols vs failed to parse
                path = Path(file_path)
                if path.exists() and path.stat().st_size > 0:
                    # File exists and has content but no symbols extracted
                    # This could be normal (e.g., config file) or a failure
                    pass

        duration_ms = (time.perf_counter() - start_time) * 1000

        result = IndexResult(
            indexed_count=total_indexed,
            failed_files=failed_files,
            duration_ms=duration_ms,
        )

        logger.info(
            f"Batch indexing complete: {result.indexed_count} symbols "
            f"from {len(file_paths)} files in {result.duration_ms:.2f}ms"
        )

        return result

    def remove_file(self, file_path: str) -> None:
        """Remove all indexed symbols for a file.

        Args:
            file_path: Absolute path to the source file.
        """
        try:
            self.symbol_store.delete_by_file(file_path)
            self._last_updated = datetime.now()
            logger.info(f"Removed indexed symbols for file: {file_path}")
        except Exception as e:
            logger.error(f"Failed to remove file {file_path} from index: {e}")

    def get_stats(self) -> IndexStats:
        """Get statistics about the current index state.

        Returns:
            IndexStats containing total symbols, files, and breakdown by language.
        """
        try:
            # Get all symbols to calculate statistics
            # Note: This could be optimized with a dedicated query
            import sqlite3

            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Get total symbols
                cursor.execute("SELECT COUNT(*) FROM code_units")
                total_symbols = cursor.fetchone()[0]

                # Get total files
                cursor.execute("SELECT COUNT(*) FROM files")
                total_files = cursor.fetchone()[0]

                # Get symbols by language
                cursor.execute("SELECT language, COUNT(*) FROM code_units GROUP BY language")
                rows = cursor.fetchall()

                symbols_by_language: Dict[Language, int] = {}
                for row in rows:
                    lang_str = row[0]
                    count = row[1]
                    try:
                        lang = Language(lang_str)
                        symbols_by_language[lang] = count
                    except ValueError:
                        # Unknown language in database
                        symbols_by_language[Language.UNKNOWN] = symbols_by_language.get(Language.UNKNOWN, 0) + count

            return IndexStats(
                total_symbols=total_symbols,
                total_files=total_files,
                symbols_by_language=symbols_by_language,
                last_updated=self._last_updated,
            )

        except Exception as e:
            logger.error(f"Failed to get index stats: {e}")
            return IndexStats(
                total_symbols=0,
                total_files=0,
                symbols_by_language={},
                last_updated=self._last_updated,
            )
