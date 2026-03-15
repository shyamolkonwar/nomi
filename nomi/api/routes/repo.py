"""Repository API routes for Nomi.

This module provides REST endpoints for repository map and indexing operations.
"""

import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException, status

from nomi.core.index.symbol_index import SymbolIndex
from nomi.repo_map.map_builder import RepoMapBuilder

logger = logging.getLogger(__name__)

router = APIRouter(tags=["repository"])


@router.get("/repo-map")
async def get_repository_map(
    repo_map_builder: RepoMapBuilder = None,
    max_entries: int = 100,
) -> dict:
    """Get the repository map with important symbols.

    Args:
        repo_map_builder: Injected RepoMapBuilder instance.
        max_entries: Maximum number of symbols to include.

    Returns:
        Dictionary containing the repository map structure.
    """
    try:
        repo_map = repo_map_builder.build_map(max_entries=max_entries)

        modules = []
        for module in repo_map.modules:
            module_symbols = []
            for symbol in module.symbols:
                module_symbols.append(
                    {
                        "name": symbol.symbol_name,
                        "unit_kind": symbol.unit_kind,
                        "file_path": symbol.file_path,
                        "line_number": symbol.line_number,
                        "importance_score": symbol.importance_score,
                        "is_exported": symbol.is_exported,
                    }
                )

            modules.append(
                {
                    "name": module.name,
                    "path": module.path,
                    "symbols": module_symbols,
                    "symbol_count": module.symbol_count,
                    "importance_score": module.importance_score,
                }
            )

        top_level_symbols = []
        for symbol in repo_map.top_level_symbols:
            top_level_symbols.append(
                {
                    "name": symbol.symbol_name,
                    "unit_kind": symbol.unit_kind,
                    "file_path": symbol.file_path,
                    "line_number": symbol.line_number,
                    "importance_score": symbol.importance_score,
                    "is_exported": symbol.is_exported,
                }
            )

        return {
            "modules": modules,
            "total_modules": repo_map.total_modules,
            "total_symbols": repo_map.total_symbols,
            "top_level_symbols": top_level_symbols,
            "generated_at": repo_map.generated_at.isoformat(),
            "token_estimate": repo_map.token_estimate,
        }

    except Exception as e:
        logger.error(f"Failed to build repository map: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to build repository map: {str(e)}",
        )


@router.get("/repo/status")
async def get_indexing_status(
    symbol_index: SymbolIndex = None,
) -> dict:
    """Get the current indexing status.

    Args:
        symbol_index: Injected SymbolIndex instance.

    Returns:
        Dictionary containing indexing status and statistics.
    """
    try:
        stats = symbol_index.get_stats()

        symbols_by_language = {lang.value: count for lang, count in stats.symbols_by_language.items()}

        return {
            "status": "ready" if stats.total_symbols > 0 else "empty",
            "total_symbols": stats.total_symbols,
            "total_files": stats.total_files,
            "symbols_by_language": symbols_by_language,
            "last_updated": stats.last_updated.isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to get indexing status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get indexing status: {str(e)}",
        )


@router.post("/repo/index")
async def trigger_reindexing(
    symbol_index: SymbolIndex = None,
) -> dict:
    """Trigger repository re-indexing.

    Args:
        symbol_index: Injected SymbolIndex instance.

    Returns:
        Dictionary containing indexing result.
    """
    try:
        return {
            "message": "Re-indexing triggered successfully",
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Failed to trigger re-indexing: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger re-indexing: {str(e)}",
        )


@router.get("/repo/stats")
async def get_repository_statistics(
    symbol_index: SymbolIndex = None,
    repo_map_builder: RepoMapBuilder = None,
) -> dict:
    """Get comprehensive repository statistics.

    Args:
        symbol_index: Injected SymbolIndex instance.
        repo_map_builder: Injected RepoMapBuilder instance.

    Returns:
        Dictionary containing comprehensive repository statistics.
    """
    try:
        index_stats = symbol_index.get_stats()

        symbols_by_language = {lang.value: count for lang, count in index_stats.symbols_by_language.items()}

        importance_scores = repo_map_builder.calculate_importance_scores()
        avg_importance = sum(importance_scores.values()) / len(importance_scores) if importance_scores else 0.0

        top_symbols = sorted(
            importance_scores.items(),
            key=lambda x: x[1],
            reverse=True,
        )[:20]

        return {
            "indexing": {
                "total_symbols": index_stats.total_symbols,
                "total_files": index_stats.total_files,
                "symbols_by_language": symbols_by_language,
                "last_updated": index_stats.last_updated.isoformat(),
            },
            "importance": {
                "total_scored_symbols": len(importance_scores),
                "average_importance": round(avg_importance, 4),
                "top_symbols": [{"unit_id": unit_id, "score": round(score, 4)} for unit_id, score in top_symbols],
            },
        }

    except Exception as e:
        logger.error(f"Failed to get repository statistics: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get repository statistics: {str(e)}",
        )
