"""Query resolution module for Nomi context engine.

This module provides symbol resolution from various input formats including
natural language queries, symbol names, and file paths.
"""

import logging
import re
from typing import List, Optional

from nomi.core.index.lookup import SymbolLookup
from nomi.core.index.search import SymbolSearch
from nomi.storage.models import CodeUnit

logger = logging.getLogger(__name__)


class ContextResolver:
    """Resolves developer queries into concrete code units.

    This class provides multiple resolution strategies:
    - Query parsing: Extracts symbol references from natural language
    - Symbol name lookup: Direct symbol resolution
    - File path lookup: Resolve all symbols in a file

    Attributes:
        symbol_search: Fuzzy search for symbol discovery.
        symbol_lookup: Exact lookup operations.
    """

    def __init__(
        self,
        symbol_search: SymbolSearch,
        symbol_lookup: SymbolLookup,
    ) -> None:
        """Initialize the context resolver.

        Args:
            symbol_search: The SymbolSearch instance for fuzzy matching.
            symbol_lookup: The SymbolLookup instance for exact lookups.
        """
        self.symbol_search = symbol_search
        self.symbol_lookup = symbol_lookup

    def resolve_from_query(self, query: str, limit: int = 10) -> List[CodeUnit]:
        """Resolve symbols from a natural language query.

        Stage 1 of the context retrieval pipeline:
        1. Parse query to extract symbol names
        2. Search symbol index for each extracted symbol
        3. Rank candidates by relevance
        4. Return top matches

        Args:
            query: The developer's natural language query.
            limit: Maximum number of results to return.

        Returns:
            List of matching CodeUnit objects, ranked by relevance.
        """
        if not query or not query.strip():
            logger.warning("Empty query provided to resolve_from_query")
            return []

        try:
            # Stage 1: Extract symbol names from query
            symbol_names = self.extract_symbols_from_query(query)
            logger.debug(f"Extracted symbols from query: {symbol_names}")

            # Stage 2 & 3: Search and rank candidates
            results: List[CodeUnit] = []
            seen_ids: set[str] = set()

            # First try exact lookups for extracted symbols
            for symbol_name in symbol_names:
                unit = self.resolve_from_symbol_name(symbol_name)
                if unit and unit.id not in seen_ids:
                    results.append(unit)
                    seen_ids.add(unit.id)

            # Then perform fuzzy search on the full query
            search_results = self.symbol_search.search(query, limit=limit * 2)

            for search_result in search_results:
                if search_result.code_unit.id not in seen_ids:
                    results.append(search_result.code_unit)
                    seen_ids.add(search_result.code_unit.id)

                if len(results) >= limit:
                    break

            logger.info(
                f"Resolved {len(results)} units from query", extra={"query": query, "results_count": len(results)}
            )

            return results[:limit]

        except Exception as e:
            logger.error(f"Failed to resolve query '{query}': {e}")
            return []

    def resolve_from_symbol_name(
        self,
        symbol_name: str,
        file_hint: Optional[str] = None,
    ) -> Optional[CodeUnit]:
        """Resolve a specific symbol by name.

        Args:
            symbol_name: The exact or approximate symbol name.
            file_hint: Optional file path to disambiguate multiple matches.

        Returns:
            The matching CodeUnit if found, None otherwise.
        """
        if not symbol_name or not symbol_name.strip():
            return None

        try:
            # First try exact lookup
            unit = self.symbol_lookup.lookup_exact(symbol_name)
            if unit:
                return unit

            # Fall back to fuzzy search
            search_results = self.symbol_search.search(symbol_name, limit=5)

            if not search_results:
                return None

            # If file hint provided, prefer matches from that file
            if file_hint:
                for result in search_results:
                    if result.code_unit.file_path == file_hint:
                        return result.code_unit

            # Return the best match
            return search_results[0].code_unit

        except Exception as e:
            logger.error(f"Failed to resolve symbol '{symbol_name}': {e}")
            return None

    def resolve_from_file_path(
        self,
        file_path: str,
        line_number: Optional[int] = None,
    ) -> List[CodeUnit]:
        """Resolve all symbols in a specific file.

        Args:
            file_path: Absolute path to the source file.
            line_number: Optional line number to find symbols at that location.

        Returns:
            List of CodeUnit objects from the file.
        """
        if not file_path or not file_path.strip():
            logger.warning("Empty file path provided to resolve_from_file_path")
            return []

        try:
            units = self.symbol_lookup.lookup_by_file(file_path)

            if line_number is not None:
                # Filter units that contain the specified line
                filtered_units = []
                for unit in units:
                    start_line, end_line = unit.line_range
                    if start_line <= line_number <= end_line:
                        filtered_units.append(unit)

                # If no exact match, return units near that line
                if not filtered_units:
                    filtered_units = sorted(units, key=lambda u: abs(u.line_range[0] - line_number))[:3]

                return filtered_units

            return units

        except Exception as e:
            logger.error(f"Failed to resolve file '{file_path}': {e}")
            return []

    def extract_symbols_from_query(self, query: str) -> List[str]:
        """Extract potential symbol names from a query string.

        Uses regex patterns to identify:
        - CamelCase identifiers (likely class names)
        - snake_case identifiers (likely function/variable names)
        - Backtick-quoted symbols
        - Quoted strings that look like symbols

        Args:
            query: The query string to parse.

        Returns:
            List of extracted symbol name candidates.
        """
        if not query:
            return []

        symbols: List[str] = []

        # Pattern 1: Backtick-quoted symbols (`symbol_name`)
        backtick_pattern = r"`([^`]+)`"
        symbols.extend(re.findall(backtick_pattern, query))

        # Pattern 2: Single-quoted symbols ('symbol_name')
        single_quote_pattern = r"'([a-zA-Z_][a-zA-Z0-9_]*)'"
        symbols.extend(re.findall(single_quote_pattern, query))

        # Pattern 3: Double-quoted symbols ("symbol_name")
        double_quote_pattern = r'"([a-zA-Z_][a-zA-Z0-9_]*)"'
        symbols.extend(re.findall(double_quote_pattern, query))

        # Pattern 4: CamelCase identifiers (ClassNames)
        camel_pattern = r"\b([A-Z][a-z]+(?:[A-Z][a-z]+)*)\b"
        camel_matches = re.findall(camel_pattern, query)
        symbols.extend(camel_matches)

        # Pattern 5: snake_case identifiers (function_names)
        snake_pattern = r"\b([a-z][a-z0-9]*(?:_[a-z0-9]+)*)\b"
        snake_matches = re.findall(snake_pattern, query)

        # Filter snake_case to exclude common words
        common_words = {
            "the",
            "and",
            "for",
            "are",
            "but",
            "not",
            "you",
            "all",
            "can",
            "had",
            "her",
            "was",
            "one",
            "our",
            "out",
            "day",
            "get",
            "has",
            "him",
            "his",
            "how",
            "its",
            "may",
            "new",
            "now",
            "old",
            "see",
            "two",
            "who",
            "boy",
            "did",
            "she",
            "use",
            "her",
            "way",
            "many",
            "oil",
            "sit",
            "set",
            "run",
            "eat",
            "far",
            "sea",
            "eye",
            "ago",
            "off",
            "too",
            "any",
            "try",
            "ask",
            "end",
            "why",
            "let",
            "put",
            "say",
            "she",
            "try",
            "way",
            "own",
            "say",
            "too",
            "old",
            "tell",
            "very",
            "when",
            "much",
            "would",
            "there",
            "their",
            "what",
            "said",
            "each",
            "which",
            "will",
            "about",
            "could",
            "other",
            "after",
            "first",
            "never",
            "these",
            "think",
            "where",
            "being",
            "every",
            "great",
            "might",
            "shall",
            "still",
            "those",
            "while",
            "this",
            "that",
            "with",
            "have",
            "from",
            "they",
            "know",
            "want",
            "been",
            "good",
            "much",
            "some",
            "time",
            "than",
            "them",
            "well",
            "were",
            "look",
            "more",
            "find",
            "here",
            "over",
            "such",
            "take",
            "make",
            "come",
            "made",
            "most",
            "only",
            "work",
            "life",
            "even",
            "back",
            "into",
            "just",
            "also",
            "your",
            "call",
            "came",
            "come",
            "dont",
            "feel",
            "seem",
            "turn",
            "hand",
            "part",
            "move",
            "both",
            "five",
            "once",
            "same",
            "must",
            "name",
            "left",
            "each",
            "done",
            "open",
            "case",
            "show",
            "live",
            "play",
            "went",
            "told",
            "seen",
            "hear",
            "talk",
            "soon",
            "read",
            "stop",
            "face",
            "fact",
            "land",
            "line",
            "kind",
            "next",
            "word",
            "came",
            "need",
            "feel",
            "seem",
            "turn",
            "hand",
            "high",
            "sure",
            "upon",
            "head",
            "help",
            "home",
            "side",
            "both",
            "five",
            "once",
            "same",
            "must",
            "name",
            "left",
            "each",
            "done",
            "open",
            "case",
            "show",
            "live",
            "play",
            "went",
            "told",
            "seen",
            "hear",
        }

        for match in snake_matches:
            if match not in common_words and len(match) > 1:
                symbols.append(match)

        # Remove duplicates while preserving order
        seen: set[str] = set()
        unique_symbols: List[str] = []
        for symbol in symbols:
            if symbol not in seen and len(symbol) > 1:
                seen.add(symbol)
                unique_symbols.append(symbol)

        return unique_symbols
