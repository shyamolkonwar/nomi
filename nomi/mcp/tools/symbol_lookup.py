"""Symbol lookup tool for MCP.

This module provides the search_symbol tool for fuzzy symbol search.
"""

import logging
from typing import Any, Dict, List

from nomi.core.index.search import SymbolSearch
from nomi.mcp.schemas.request_schema import SearchSymbolRequest
from nomi.mcp.schemas.response_schema import SearchSymbolResponse, SymbolMatch

logger = logging.getLogger(__name__)


def get_search_symbol_tool_definition() -> Dict[str, Any]:
    """Get the tool definition for search_symbol.

    Returns:
        Tool definition dictionary with name, description, and input schema.
    """
    return {
        "name": "search_symbol",
        "description": (
            "Search for code symbols using fuzzy matching. "
            "Finds functions, classes, methods, and other symbols matching the query. "
            "Returns ranked results with match scores. "
            "Use this tool to locate specific symbols or discover related code."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query string (symbol name or partial match)",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of results to return (1-100)",
                    "minimum": 1,
                    "maximum": 100,
                    "default": 10,
                },
            },
            "required": ["query"],
        },
    }


async def search_symbol_tool(
    request: SearchSymbolRequest,
    symbol_search: SymbolSearch,
    **kwargs: Any,
) -> SearchSymbolResponse:
    """Handle the search_symbol tool invocation.

    Args:
        request: The tool request with search parameters.
        symbol_search: The SymbolSearch instance to use.

    Returns:
        SearchSymbolResponse with ranked search results.
    """
    logger.info(
        "Executing search_symbol tool",
        extra={
            "query": request.query,
            "limit": request.limit,
        },
    )

    try:
        # Perform the search
        search_results = symbol_search.search(
            query=request.query,
            limit=request.limit or 10,
        )

        # Convert to response format
        results: List[SymbolMatch] = []
        for result in search_results:
            unit = result.code_unit
            match = SymbolMatch(
                symbol_name=_extract_symbol_name(unit.id),
                unit_id=unit.id,
                unit_kind=unit.unit_kind.value,
                file_path=unit.file_path,
                line_number=unit.line_range[0],
                match_score=result.match_score,
                match_type=result.match_type,
                signature=unit.signature,
            )
            results.append(match)

        logger.info(
            "search_symbol completed successfully",
            extra={
                "query": request.query,
                "results_count": len(results),
            },
        )

        return SearchSymbolResponse(
            results=results,
            total_found=len(results),
            query=request.query,
        )

    except Exception as e:
        logger.error(f"search_symbol failed: {e}")
        raise


def _extract_symbol_name(unit_id: str) -> str:
    """Extract the symbol name from a unit ID.

    Args:
        unit_id: The code unit ID (format: repo_path/file:symbol_name).

    Returns:
        The symbol name.
    """
    if ":" in unit_id:
        return unit_id.split(":")[-1]
    return unit_id
