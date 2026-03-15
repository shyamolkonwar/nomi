"""Dependency expansion tool for MCP.

This module provides the expand_dependencies tool for traversing
the dependency graph and finding related symbols.
"""

import logging
from typing import Any, Dict, List

from nomi.core.graph.dependency_graph import DependencyGraph
from nomi.core.index.lookup import SymbolLookup
from nomi.mcp.schemas.request_schema import ExpandDependenciesRequest
from nomi.mcp.schemas.response_schema import DependencyInfo, ExpandDependenciesResponse

logger = logging.getLogger(__name__)


def get_expand_dependencies_tool_definition() -> Dict[str, Any]:
    """Get the tool definition for expand_dependencies.

    Returns:
        Tool definition dictionary with name, description, and input schema.
    """
    return {
        "name": "expand_dependencies",
        "description": (
            "Expand and explore symbol dependencies in the codebase. "
            "Traverses the dependency graph starting from a symbol and returns "
            "related symbols up to the specified depth. "
            "Use this tool to understand what a symbol depends on or what depends on it."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbol_name": {
                    "type": "string",
                    "description": "Symbol name to start dependency expansion from",
                },
                "depth": {
                    "type": "integer",
                    "description": "How many hops to follow in the dependency graph (1-3)",
                    "minimum": 1,
                    "maximum": 3,
                    "default": 1,
                },
            },
            "required": ["symbol_name"],
        },
    }


async def expand_dependencies_tool(
    request: ExpandDependenciesRequest,
    dependency_graph: DependencyGraph,
    symbol_lookup: SymbolLookup,
    **kwargs: Any,
) -> ExpandDependenciesResponse:
    """Handle the expand_dependencies tool invocation.

    Args:
        request: The tool request with parameters.
        dependency_graph: The DependencyGraph instance to use.
        symbol_lookup: The SymbolLookup for resolving symbols.

    Returns:
        ExpandDependenciesResponse with dependency information.
    """
    logger.info(
        "Executing expand_dependencies tool",
        extra={
            "symbol_name": request.symbol_name,
            "depth": request.depth,
        },
    )

    try:
        # Find the starting symbol
        unit = symbol_lookup.lookup_exact(request.symbol_name)

        if not unit:
            raise ValueError(f"Symbol not found: {request.symbol_name}")

        # Get dependencies with specified depth
        depth = request.depth or 1
        dep_ids = dependency_graph.get_dependencies(unit.id, depth=depth)

        # Remove the starting symbol itself
        if unit.id in dep_ids:
            dep_ids.remove(unit.id)

        # Build dependency info list
        dependencies: List[DependencyInfo] = []
        for dep_id in dep_ids:
            dep_info = _resolve_dependency_info(dep_id, symbol_lookup, dependency_graph)
            if dep_info:
                dependencies.append(dep_info)

        # Sort by file path for consistent output
        dependencies.sort(key=lambda d: (d.file_path, d.line_number))

        logger.info(
            "expand_dependencies completed successfully",
            extra={
                "symbol_name": request.symbol_name,
                "unit_id": unit.id,
                "dependencies_count": len(dependencies),
                "depth": depth,
            },
        )

        return ExpandDependenciesResponse(
            symbol_name=_extract_symbol_name(unit.id),
            unit_id=unit.id,
            depth=depth,
            dependencies=dependencies,
            total_dependencies=len(dependencies),
        )

    except Exception as e:
        logger.error(f"expand_dependencies failed: {e}")
        raise


def _resolve_dependency_info(
    unit_id: str,
    symbol_lookup: SymbolLookup,
    dependency_graph: DependencyGraph,
) -> DependencyInfo:
    """Resolve dependency information for a unit ID.

    Args:
        unit_id: The unit ID to resolve.
        symbol_lookup: The SymbolLookup instance.
        dependency_graph: The DependencyGraph instance.

    Returns:
        DependencyInfo if the unit can be resolved, None otherwise.
    """
    try:
        symbol_name = _extract_symbol_name(unit_id)
        unit = symbol_lookup.lookup_exact(symbol_name)

        if not unit:
            # Try to get info from graph store
            return DependencyInfo(
                symbol_name=symbol_name,
                unit_id=unit_id,
                unit_kind="unknown",
                file_path="unknown",
                line_number=0,
                relationship="unknown",
            )

        return DependencyInfo(
            symbol_name=symbol_name,
            unit_id=unit_id,
            unit_kind=unit.unit_kind.value,
            file_path=unit.file_path,
            line_number=unit.line_range[0],
            relationship="dependency",
        )

    except Exception as e:
        logger.warning(f"Failed to resolve dependency info for {unit_id}: {e}")
        return DependencyInfo(
            symbol_name=_extract_symbol_name(unit_id),
            unit_id=unit_id,
            unit_kind="unknown",
            file_path="unknown",
            line_number=0,
            relationship="unknown",
        )


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
