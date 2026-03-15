"""Symbol lookup module for Nomi.

This module provides fast lookup operations for indexed code symbols,
supporting exact match, prefix match, and pattern-based searches.
"""

import logging
import re
from typing import List, Optional, Tuple

from nomi.storage.models import CodeUnit
from nomi.storage.sqlite.symbol_store import SymbolStore

logger = logging.getLogger(__name__)


class SymbolLookup:
    """Provides fast lookup operations for indexed code symbols.

    This class offers various lookup methods including exact name matching,
    prefix matching, file-based lookups, and regex pattern matching.
    """

    def __init__(self, symbol_store: SymbolStore) -> None:
        """Initialize the symbol lookup.

        Args:
            symbol_store: The SymbolStore instance to query.
        """
        self.symbol_store = symbol_store

    def lookup_exact(self, name: str) -> Optional[CodeUnit]:
        """Look up a symbol by exact name match.

        Args:
            name: The exact symbol name to search for.

        Returns:
            The matching CodeUnit if found, None otherwise.
        """
        try:
            # Search with exact match pattern
            results = self.symbol_store.search_symbols(name)

            # Filter for exact match (case-insensitive)
            name_lower = name.lower()
            for unit in results:
                symbol_name = self._extract_symbol_name(unit.id)
                if symbol_name.lower() == name_lower:
                    return unit

            return None

        except Exception as e:
            logger.error(f"Failed to lookup exact symbol '{name}': {e}")
            return None

    def lookup_by_prefix(self, prefix: str) -> List[CodeUnit]:
        """Look up symbols by prefix match.

        Args:
            prefix: The prefix to match against symbol names.

        Returns:
            List of CodeUnits with matching prefixes.
        """
        if not prefix:
            return []

        try:
            # Use the symbol store's search with prefix pattern
            # The store uses LIKE %query%, so we need to filter for prefix
            results = self.symbol_store.search_symbols(prefix)

            # Filter for prefix match (case-insensitive)
            prefix_lower = prefix.lower()
            matching_units = []

            for unit in results:
                symbol_name = self._extract_symbol_name(unit.id)
                if symbol_name.lower().startswith(prefix_lower):
                    matching_units.append(unit)

            return matching_units

        except Exception as e:
            logger.error(f"Failed to lookup symbols by prefix '{prefix}': {e}")
            return []

    def lookup_by_file(self, file_path: str) -> List[CodeUnit]:
        """Look up all symbols in a specific file.

        Args:
            file_path: Absolute path to the source file.

        Returns:
            List of CodeUnits from the file.
        """
        try:
            return self.symbol_store.get_symbols_by_file(file_path)
        except Exception as e:
            logger.error(f"Failed to lookup symbols for file '{file_path}': {e}")
            return []

    def lookup_by_pattern(self, pattern: str) -> List[CodeUnit]:
        """Look up symbols matching a regex pattern.

        Args:
            pattern: The regex pattern to match against symbol names.

        Returns:
            List of CodeUnits with matching symbol names.
        """
        try:
            # Compile the regex pattern
            regex = re.compile(pattern, re.IGNORECASE)

            # Get all symbols and filter
            all_symbols = self.symbol_store.get_all_symbols()
            matching_units = []

            for symbol_name in all_symbols:
                if regex.search(symbol_name):
                    # Search for this specific symbol
                    results = self.symbol_store.search_symbols(symbol_name)
                    for unit in results:
                        unit_symbol_name = self._extract_symbol_name(unit.id)
                        if unit_symbol_name == symbol_name:
                            matching_units.append(unit)
                            break

            return matching_units

        except re.error as e:
            logger.error(f"Invalid regex pattern '{pattern}': {e}")
            return []
        except Exception as e:
            logger.error(f"Failed to lookup symbols by pattern '{pattern}': {e}")
            return []

    def get_symbol_location(self, name: str) -> Optional[Tuple[str, int, int]]:
        """Get the location of a symbol.

        Args:
            name: The symbol name to locate.

        Returns:
            Tuple of (file_path, line, column) if found, None otherwise.
            Line and column are 1-indexed.
        """
        unit = self.lookup_exact(name)

        if unit is None:
            return None

        try:
            # Extract line and column from line_range
            start_line = unit.line_range[0]
            # Column information isn't stored in CodeUnit currently
            # Return 1 as default column
            return (unit.file_path, start_line, 1)
        except (IndexError, TypeError):
            return None

    def _extract_symbol_name(self, unit_id: str) -> str:
        """Extract the symbol name from a unit ID.

        Args:
            unit_id: The code unit ID (format: repo_path/file:symbol_name).

        Returns:
            The symbol name.
        """
        if ":" in unit_id:
            return unit_id.split(":")[-1]
        return unit_id
