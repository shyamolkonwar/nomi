"""Symbol API routes for Nomi.

This module provides REST endpoints for symbol search and lookup operations.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Path, Query, status

from nomi.api.schemas.symbol_schema import (
    FileSymbolsResponse,
    PrefixSearchResponse,
    SymbolDetail,
    SymbolResult,
    SymbolSearchRequest,
    SymbolSearchResponse,
)
from nomi.core.index.lookup import SymbolLookup
from nomi.core.index.search import SymbolSearch

logger = logging.getLogger(__name__)

router = APIRouter(tags=["symbols"])


def _convert_unit_to_detail(unit) -> SymbolDetail:
    """Convert a CodeUnit to SymbolDetail."""
    symbol_name = unit.id.split(":")[-1] if ":" in unit.id else unit.id
    return SymbolDetail(
        name=symbol_name,
        unit_kind=unit.unit_kind.value,
        file_path=unit.file_path,
        line_range=unit.line_range,
        signature=unit.signature,
        docstring=unit.docstring,
    )


def _convert_search_result_to_symbol_result(result) -> SymbolResult:
    """Convert a SearchResult to SymbolResult."""
    unit = result.code_unit
    symbol_name = unit.id.split(":")[-1] if ":" in unit.id else unit.id
    return SymbolResult(
        name=symbol_name,
        unit_kind=unit.unit_kind.value,
        file_path=unit.file_path,
        line_number=unit.line_range[0],
        match_score=result.match_score,
    )


@router.get("/symbol/{name}", response_model=SymbolDetail)
async def get_symbol_by_name(
    name: str = Path(..., description="Exact symbol name"),
    symbol_lookup: SymbolLookup = None,
) -> SymbolDetail:
    """Get a symbol by its exact name.

    Args:
        name: The exact symbol name to look up.
        symbol_lookup: Injected SymbolLookup instance.

    Returns:
        SymbolDetail with full symbol information.

    Raises:
        HTTPException: If symbol is not found.
    """
    try:
        unit = symbol_lookup.lookup_exact(name)

        if not unit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Symbol not found: {name}",
            )

        return _convert_unit_to_detail(unit)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to lookup symbol '{name}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to lookup symbol: {str(e)}",
        )


@router.post("/symbol/search", response_model=SymbolSearchResponse)
async def search_symbols(
    request: SymbolSearchRequest,
    symbol_search: SymbolSearch = None,
) -> SymbolSearchResponse:
    """Search for symbols using fuzzy matching.

    Args:
        request: Symbol search request with query and limit.
        symbol_search: Injected SymbolSearch instance.

    Returns:
        SymbolSearchResponse with matching symbols.
    """
    try:
        results = symbol_search.search(request.query, limit=request.limit or 10)

        symbol_results = [
            _convert_search_result_to_symbol_result(result)
            for result in results
        ]

        return SymbolSearchResponse(
            results=symbol_results,
            total_found=len(symbol_results),
        )

    except Exception as e:
        logger.error(f"Failed to search symbols: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to search symbols: {str(e)}",
        )


@router.get("/symbol/file/{file_path:path}", response_model=FileSymbolsResponse)
async def get_symbols_in_file(
    file_path: str = Path(..., description="Absolute path to source file"),
    symbol_lookup: SymbolLookup = None,
) -> FileSymbolsResponse:
    """Get all symbols in a specific file.

    Args:
        file_path: Absolute path to the source file.
        symbol_lookup: Injected SymbolLookup instance.

    Returns:
        FileSymbolsResponse with all symbols in the file.
    """
    try:
        units = symbol_lookup.lookup_by_file(file_path)

        symbols = [_convert_unit_to_detail(unit) for unit in units]

        return FileSymbolsResponse(
            file_path=file_path,
            symbols=symbols,
            total_symbols=len(symbols),
        )

    except Exception as e:
        logger.error(f"Failed to get symbols for file '{file_path}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get symbols for file: {str(e)}",
        )


@router.get("/symbol/prefix/{prefix}", response_model=PrefixSearchResponse)
async def search_symbols_by_prefix(
    prefix: str = Path(..., description="Symbol name prefix"),
    limit: Optional[int] = Query(default=10, description="Maximum results to return"),
    symbol_lookup: SymbolLookup = None,
) -> PrefixSearchResponse:
    """Search for symbols by prefix match.

    Args:
        prefix: The prefix to match against symbol names.
        limit: Maximum number of results to return.
        symbol_lookup: Injected SymbolLookup instance.

    Returns:
        PrefixSearchResponse with matching symbols.
    """
    try:
        units = symbol_lookup.lookup_by_prefix(prefix)

        # Apply limit
        limited_units = units[:limit] if limit else units

        matches = [
            SymbolResult(
                name=unit.id.split(":")[-1] if ":" in unit.id else unit.id,
                unit_kind=unit.unit_kind.value,
                file_path=unit.file_path,
                line_number=unit.line_range[0],
                match_score=1.0,
            )
            for unit in limited_units
        ]

        return PrefixSearchResponse(
            prefix=prefix,
            matches=matches,
            total_matches=len(units),
        )

    except Exception as e:
        logger.error(f"Failed to search symbols by prefix '{prefix}': {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to search symbols by prefix: {str(e)}",
        )
