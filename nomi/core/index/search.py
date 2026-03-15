"""Fuzzy symbol search module for Nomi.

This module provides fuzzy matching search capabilities for code symbols,
supporting similarity-based ranking and context-aware results.
"""

import difflib
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from nomi.storage.models import CodeUnit
from nomi.storage.sqlite.symbol_store import SymbolStore

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """Result of a symbol search operation."""

    code_unit: CodeUnit
    match_score: float
    match_type: str


class SymbolSearch:
    """Provides fuzzy search capabilities for code symbols.

    This class offers fuzzy matching using difflib, with support for
    ranking results by relevance and boosting results based on context.
    """

    def __init__(self, symbol_store: SymbolStore) -> None:
        """Initialize the symbol search.

        Args:
            symbol_store: The SymbolStore instance to query.
        """
        self.symbol_store = symbol_store

    def search(self, query: str, limit: int = 10) -> List[SearchResult]:
        """Search for symbols using fuzzy matching.

        Args:
            query: The search query string.
            limit: Maximum number of results to return.

        Returns:
            List of SearchResult objects ranked by match score.
        """
        if not query:
            return []

        try:
            # Get all symbol names for fuzzy matching
            all_symbols = self.symbol_store.get_all_symbols()

            if not all_symbols:
                return []

            # Use difflib for fuzzy matching
            query_lower = query.lower()

            # First try exact match
            exact_matches = []
            prefix_matches = []
            fuzzy_matches = []

            for symbol_name in all_symbols:
                symbol_lower = symbol_name.lower()

                if symbol_lower == query_lower:
                    exact_matches.append((symbol_name, 1.0))
                elif symbol_lower.startswith(query_lower):
                    # Calculate prefix match score
                    score = 0.8 + (0.2 * len(query) / len(symbol_name))
                    prefix_matches.append((symbol_name, min(score, 0.99)))

            # Get fuzzy matches using difflib
            if len(exact_matches) + len(prefix_matches) < limit:
                close_matches = difflib.get_close_matches(query, all_symbols, n=limit * 2, cutoff=0.3)

                for symbol_name in close_matches:
                    if symbol_name not in [m[0] for m in exact_matches + prefix_matches]:
                        # Calculate similarity ratio
                        matcher = difflib.SequenceMatcher(None, query_lower, symbol_name.lower())
                        score = matcher.ratio()
                        if score >= 0.3:
                            fuzzy_matches.append((symbol_name, score))

            # Combine all matches and sort by score
            all_matches = exact_matches + prefix_matches + fuzzy_matches
            all_matches.sort(key=lambda x: x[1], reverse=True)

            # Build results
            results = []
            seen_units = set()

            for symbol_name, score in all_matches[:limit]:
                # Get the code unit for this symbol
                units = self.symbol_store.search_symbols(symbol_name)

                for unit in units:
                    unit_symbol = self._extract_symbol_name(unit.id)
                    if unit_symbol == symbol_name and unit.id not in seen_units:
                        seen_units.add(unit.id)

                        # Determine match type
                        if score >= 0.99:
                            match_type = "exact"
                        elif score >= 0.8:
                            match_type = "prefix"
                        else:
                            match_type = "fuzzy"

                        results.append(
                            SearchResult(
                                code_unit=unit,
                                match_score=round(score, 3),
                                match_type=match_type,
                            )
                        )
                        break

            return results

        except Exception as e:
            logger.error(f"Failed to search symbols with query '{query}': {e}")
            return []

    def search_with_context(self, query: str, file_context: Optional[str] = None) -> List[SearchResult]:
        """Search for symbols with context-aware ranking.

        Results from the same file or directory are boosted in ranking.

        Args:
            query: The search query string.
            file_context: Optional file path to boost results from the same context.

        Returns:
            List of SearchResult objects ranked by relevance.
        """
        results = self.search(query, limit=50)  # Get more results for re-ranking

        if not file_context or not results:
            return results[:10]

        try:
            context_path = Path(file_context)
            context_dir = context_path.parent

            # Boost scores based on context
            boosted_results = []

            for result in results:
                boost = 0.0
                result_path = Path(result.code_unit.file_path)

                # Same file gets highest boost
                if result_path == context_path:
                    boost = 0.3
                # Same directory gets medium boost
                elif result_path.parent == context_dir:
                    boost = 0.15
                # Same parent directory gets small boost
                elif result_path.parent.parent == context_dir.parent:
                    boost = 0.05

                boosted_score = min(result.match_score + boost, 1.0)

                boosted_results.append(
                    SearchResult(
                        code_unit=result.code_unit,
                        match_score=round(boosted_score, 3),
                        match_type=result.match_type,
                    )
                )

            # Re-sort by boosted score
            boosted_results.sort(key=lambda x: x.match_score, reverse=True)

            return boosted_results[:10]

        except Exception as e:
            logger.error(f"Failed to apply context boost: {e}")
            return results[:10]

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
