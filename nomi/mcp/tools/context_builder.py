"""Context builder tool for MCP.

This module provides the get_symbol_context tool for retrieving
full implementation details of specific symbols.
"""

import logging
from typing import Any, Dict, List, Optional

from nomi.core.context.context_builder import ContextBuilder
from nomi.core.index.lookup import SymbolLookup
from nomi.mcp.schemas.request_schema import GetSymbolContextRequest
from nomi.mcp.schemas.response_schema import DependencyInfo, GetSymbolContextResponse
from nomi.storage.models import CodeUnit

logger = logging.getLogger(__name__)


def get_symbol_context_tool_definition() -> Dict[str, Any]:
    """Get the tool definition for get_symbol_context.

    Returns:
        Tool definition dictionary with name, description, and input schema.
    """
    return {
        "name": "get_symbol_context",
        "description": (
            "Get full implementation context for a specific symbol. "
            "Returns the complete code including body, signature, and location information. "
            "Optionally includes dependencies of the symbol. "
            "Use this tool to understand how a specific function, class, or method is implemented."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbol_name": {
                    "type": "string",
                    "description": "Exact or approximate symbol name to look up",
                },
                "include_dependencies": {
                    "type": "boolean",
                    "description": "Whether to include dependency information",
                    "default": True,
                },
            },
            "required": ["symbol_name"],
        },
    }


async def get_symbol_context_tool(
    request: GetSymbolContextRequest,
    context_builder: ContextBuilder,
    symbol_lookup: SymbolLookup,
) -> GetSymbolContextResponse:
    """Handle the get_symbol_context tool invocation.

    Args:
        request: The tool request with parameters.
        context_builder: The ContextBuilder instance to use.
        symbol_lookup: The SymbolLookup for direct symbol access.

    Returns:
        GetSymbolContextResponse with full symbol implementation.
    """
    logger.info(
        "Executing get_symbol_context tool",
        extra={
            "symbol_name": request.symbol_name,
            "include_dependencies": request.include_dependencies,
        },
    )

    try:
        # Look up the symbol
        unit = symbol_lookup.lookup_exact(request.symbol_name)

        if not unit:
            # Try fuzzy search as fallback
            search_results = context_builder.symbol_search.search(request.symbol_name, limit=1)
            if search_results:
                unit = search_results[0].code_unit

        if not unit:
            raise ValueError(f"Symbol not found: {request.symbol_name}")

        # Get dependencies if requested
        dependencies: Optional[List[DependencyInfo]] = None
        if request.include_dependencies:
            dependencies = _get_dependencies(unit, context_builder, symbol_lookup)

        logger.info(
            "get_symbol_context completed successfully",
            extra={
                "symbol_name": request.symbol_name,
                "unit_id": unit.id,
                "has_dependencies": dependencies is not None,
            },
        )

        return GetSymbolContextResponse(
            symbol_name=_extract_symbol_name(unit.id),
            unit_id=unit.id,
            code=unit.body,
            file_path=unit.file_path,
            line_range=unit.line_range,
            signature=unit.signature,
            docstring=unit.docstring,
            unit_kind=unit.unit_kind.value,
            language=unit.language,
            dependencies=dependencies,
        )

    except Exception as e:
        logger.error(f"get_symbol_context failed: {e}")
        raise


def _get_dependencies(
    unit: CodeUnit,
    context_builder: ContextBuilder,
    symbol_lookup: SymbolLookup,
) -> List[DependencyInfo]:
    """Get dependency information for a code unit.

    Args:
        unit: The code unit to get dependencies for.
        context_builder: The ContextBuilder for dependency access.
        symbol_lookup: The SymbolLookup for resolving dependencies.

    Returns:
        List of DependencyInfo objects.
    """
    dependencies: List[DependencyInfo] = []

    try:
        # Get direct dependencies
        dep_ids = context_builder.dependency_graph.get_dependencies(unit.id, depth=1)

        for dep_id in dep_ids:
            # Look up the dependency unit
            dep_unit = None
            try:
                dep_unit = symbol_lookup.lookup_exact(_extract_symbol_name(dep_id))
            except Exception:
                pass

            if not dep_unit:
                continue

            dep_info = DependencyInfo(
                symbol_name=_extract_symbol_name(dep_id),
                unit_id=dep_id,
                unit_kind=dep_unit.unit_kind.value,
                file_path=dep_unit.file_path,
                line_number=dep_unit.line_range[0],
                relationship="calls",
            )
            dependencies.append(dep_info)

    except Exception as e:
        logger.warning(f"Failed to get dependencies for {unit.id}: {e}")

    return dependencies


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
