"""Context API routes for Nomi.

This module provides REST endpoints for building context bundles.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, status

from nomi.api.schemas.context_schema import (
    ContextRequest,
    ContextResponse,
    ContextStats,
    FileContextRequest,
    FocalCodeEntry,
    DependencyEntry,
    RepoMapEntry,
    ResponseMetadata,
    SymbolContextRequest,
)
from nomi.core.context.context_builder import BuildConfig, ContextBuilder

logger = logging.getLogger(__name__)

router = APIRouter(tags=["context"])


def _build_config_from_request(
    max_tokens: Optional[int],
    dependency_depth: Optional[int],
) -> BuildConfig:
    """Create BuildConfig from request parameters."""
    return BuildConfig(
        max_context_tokens=max_tokens or 4000,
        dependency_depth=dependency_depth or 1,
    )


def _convert_bundle_to_response(bundle, query: str) -> ContextResponse:
    """Convert a ContextBundle to API response format."""
    focal_code = [
        FocalCodeEntry(
            name=unit.id.split(":")[-1] if ":" in unit.id else unit.id,
            code=unit.body,
            file_path=unit.file_path,
            line_range=unit.line_range,
        )
        for unit in bundle.focal_units
    ]

    dependencies = [
        DependencyEntry(
            name=skeleton.id.split(":")[-1] if ":" in skeleton.id else skeleton.id,
            signature=skeleton.signature,
            file_path=skeleton.file_path,
        )
        for skeleton in bundle.dependency_skeletons
    ]

    repo_map = None
    if bundle.repository_map:
        repo_map = RepoMapEntry(
            root_path=bundle.repository_map.root_path,
            files=bundle.repository_map.files,
            modules=bundle.repository_map.modules,
        )

    metadata = ResponseMetadata(
        total_tokens=bundle.metadata.total_tokens,
        search_duration_ms=bundle.metadata.search_duration_ms,
    )

    return ContextResponse(
        query=query,
        focal_code=focal_code,
        dependencies=dependencies,
        repo_map=repo_map,
        metadata=metadata,
    )


@router.post("/context", response_model=ContextResponse)
async def build_context(
    request: ContextRequest,
    context_builder,
) -> ContextResponse:
    """Build context bundle for a natural language query.

    Args:
        request: Context request with query and options.
        context_builder: Injected ContextBuilder instance.

    Returns:
        ContextResponse with focal code, dependencies, and metadata.
    """
    try:
        config = _build_config_from_request(
            request.max_tokens,
            request.dependency_depth,
        )
        context_builder.config = config

        bundle = context_builder.build(request.query)

        return _convert_bundle_to_response(bundle, request.query)

    except Exception as e:
        logger.error(f"Failed to build context: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to build context: {str(e)}",
        )


@router.post("/context/symbol", response_model=ContextResponse)
async def build_context_for_symbol(
    request: SymbolContextRequest,
    context_builder,
) -> ContextResponse:
    """Build context bundle for a specific symbol.

    Args:
        request: Symbol context request with symbol name and options.
        context_builder: Injected ContextBuilder instance.

    Returns:
        ContextResponse centered on the specified symbol.
    """
    try:
        config = _build_config_from_request(
            request.max_tokens,
            request.dependency_depth,
        )
        context_builder.config = config

        bundle = context_builder.build_for_symbol(request.symbol_name)

        return _convert_bundle_to_response(bundle, f"symbol:{request.symbol_name}")

    except Exception as e:
        logger.error(f"Failed to build context for symbol: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to build context for symbol: {str(e)}",
        )


@router.post("/context/file", response_model=ContextResponse)
async def build_context_for_file(
    request: FileContextRequest,
    context_builder,
) -> ContextResponse:
    """Build context bundle for a specific file.

    Args:
        request: File context request with file path and options.
        context_builder: Injected ContextBuilder instance.

    Returns:
        ContextResponse for the specified file.
    """
    try:
        config = _build_config_from_request(
            request.max_tokens,
            request.dependency_depth,
        )
        context_builder.config = config

        bundle = context_builder.build_for_file(
            request.file_path,
            request.focal_symbol,
        )

        query = f"file:{request.file_path}"
        if request.focal_symbol:
            query += f"#{request.focal_symbol}"

        return _convert_bundle_to_response(bundle, query)

    except Exception as e:
        logger.error(f"Failed to build context for file: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to build context for file: {str(e)}",
        )


@router.get("/context/stats", response_model=ContextStats)
async def get_context_stats(
    context_builder,
) -> ContextStats:
    """Get statistics about the context engine.

    Args:
        context_builder: Injected ContextBuilder instance.

    Returns:
        ContextStats with indexing and performance statistics.
    """
    try:
        return ContextStats(
            total_indexed_symbols=0,
            total_files=0,
            avg_context_build_time_ms=0.0,
            cache_hit_rate=0.0,
        )
    except Exception as e:
        logger.error(f"Failed to get context stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get context stats: {str(e)}",
        )
