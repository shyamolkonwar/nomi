"""Repository map tool for MCP.

This module provides the get_repo_map tool that returns a high-level
overview of the repository structure with important symbols.
"""

import logging
from typing import Any, Dict

from nomi.mcp.schemas.request_schema import GetRepoMapRequest
from nomi.mcp.schemas.response_schema import GetRepoMapResponse, ModuleInfo
from nomi.repo_map.map_builder import RepoMapBuilder

logger = logging.getLogger(__name__)


def get_repo_map_tool_definition() -> Dict[str, Any]:
    """Get the tool definition for get_repo_map.

    Returns:
        Tool definition dictionary with name, description, and input schema.
    """
    return {
        "name": "get_repo_map",
        "description": (
            "Get a high-level overview of the repository structure. "
            "Returns a compact map organized by modules with the most important symbols "
            "ranked by their significance (based on PageRank centrality). "
            "Use this tool to understand the codebase structure and identify key components."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "max_entries": {
                    "type": "integer",
                    "description": "Maximum number of symbols to include in the map (10-500)",
                    "minimum": 10,
                    "maximum": 500,
                    "default": 100,
                },
                "max_symbols_per_module": {
                    "type": "integer",
                    "description": "Maximum symbols to include per module (1-50)",
                    "minimum": 1,
                    "maximum": 50,
                    "default": 10,
                },
            },
        },
    }


async def get_repo_map_tool(
    request: GetRepoMapRequest,
    repo_map_builder: RepoMapBuilder,
) -> GetRepoMapResponse:
    """Handle the get_repo_map tool invocation.

    Args:
        request: The tool request with parameters.
        repo_map_builder: The RepoMapBuilder instance to use.

    Returns:
        GetRepoMapResponse with the repository structure.
    """
    logger.info(
        "Executing get_repo_map tool",
        extra={
            "max_entries": request.max_entries,
            "max_symbols_per_module": request.max_symbols_per_module,
        },
    )

    try:
        # Build the repository map
        repo_map = repo_map_builder.build_map(
            max_entries=request.max_entries or 100,
            max_symbols_per_module=request.max_symbols_per_module or 10,
        )

        # Convert to response format
        modules = []
        for module in repo_map.modules:
            important_symbols = [
                {
                    "symbol_name": entry.symbol_name,
                    "unit_kind": entry.unit_kind,
                    "file_path": entry.file_path,
                    "line_number": entry.line_number,
                    "importance_score": round(entry.importance_score, 3),
                    "is_exported": entry.is_exported,
                }
                for entry in module.symbols
            ]

            modules.append(
                ModuleInfo(
                    name=module.name,
                    path=module.path,
                    symbol_count=module.symbol_count,
                    important_symbols=important_symbols,
                )
            )

        top_level_symbols = [
            {
                "symbol_name": entry.symbol_name,
                "unit_kind": entry.unit_kind,
                "file_path": entry.file_path,
                "line_number": entry.line_number,
                "importance_score": round(entry.importance_score, 3),
            }
            for entry in repo_map.top_level_symbols
        ]

        logger.info(
            "get_repo_map completed successfully",
            extra={
                "modules_count": len(modules),
                "total_symbols": repo_map.total_symbols,
            },
        )

        return GetRepoMapResponse(
            modules=modules,
            total_modules=repo_map.total_modules,
            total_symbols=repo_map.total_symbols,
            top_level_symbols=top_level_symbols,
        )

    except Exception as e:
        logger.error(f"get_repo_map failed: {e}")
        raise
