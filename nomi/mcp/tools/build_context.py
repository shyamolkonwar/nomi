"""Build context tool for MCP.

This module provides the build_context tool for executing the full
5-stage context retrieval pipeline.
"""

import logging
from typing import Any, Dict, List

from nomi.core.context.context_builder import BuildConfig, ContextBuilder
from nomi.mcp.schemas.request_schema import BuildContextRequest
from nomi.mcp.schemas.response_schema import BuildContextResponse
from nomi.storage.models import CodeUnit

logger = logging.getLogger(__name__)


def get_build_context_tool_definition() -> Dict[str, Any]:
    """Get the tool definition for build_context.

    Returns:
        Tool definition dictionary with name, description, and input schema.
    """
    return {
        "name": "build_context",
        "description": (
            "Build a complete context bundle for a natural language query. "
            "Executes the full 5-stage retrieval pipeline to assemble context "
            "optimized for AI coding agents. Returns focal code units with full "
            "implementation and lightweight skeletons of related dependencies. "
            "Use this tool for complex queries that require comprehensive context."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language query describing what context is needed",
                },
                "max_tokens": {
                    "type": "integer",
                    "description": "Maximum estimated tokens for the context bundle (500-16000)",
                    "minimum": 500,
                    "maximum": 16000,
                    "default": 4000,
                },
                "dependency_depth": {
                    "type": "integer",
                    "description": "Depth of dependency expansion (1-3)",
                    "minimum": 1,
                    "maximum": 3,
                    "default": 1,
                },
            },
            "required": ["query"],
        },
    }


async def build_context_tool(
    request: BuildContextRequest,
    context_builder: ContextBuilder,
    **kwargs: Any,
) -> BuildContextResponse:
    """Handle the build_context tool invocation.

    Args:
        request: The tool request with parameters.
        context_builder: The ContextBuilder instance to use.

    Returns:
        BuildContextResponse with the complete context bundle.
    """
    logger.info(
        "Executing build_context tool",
        extra={
            "query": request.query,
            "max_tokens": request.max_tokens,
            "dependency_depth": request.dependency_depth,
        },
    )

    try:
        # Create build config from request
        config = BuildConfig(
            dependency_depth=request.dependency_depth or 1,
            max_context_tokens=request.max_tokens or 4000,
            include_repo_map=True,
            skeletonize_dependencies=True,
            prioritize_same_file=True,
        )

        # Update context builder with new config
        original_config = context_builder.config
        context_builder.config = config

        try:
            # Build the context bundle
            bundle = context_builder.build(request.query)
        finally:
            # Restore original config
            context_builder.config = original_config

        # Format focal code
        focal_code = _format_focal_code(bundle.focal_units)

        # Format complete context
        context = _format_complete_context(bundle)

        # Build response
        focal_units_data = [
            {
                "symbol_name": _extract_symbol_name(unit.id),
                "unit_id": unit.id,
                "unit_kind": unit.unit_kind.value,
                "file_path": unit.file_path,
                "line_range": unit.line_range,
                "signature": unit.signature,
            }
            for unit in bundle.focal_units
        ]

        dependency_skeletons_data = [
            {
                "symbol_name": _extract_symbol_name(skeleton.id),
                "unit_id": skeleton.id,
                "unit_kind": skeleton.unit_kind,
                "file_path": skeleton.file_path,
                "line_range": skeleton.line_range,
                "signature": skeleton.signature,
            }
            for skeleton in bundle.dependency_skeletons
        ]

        logger.info(
            "build_context completed successfully",
            extra={
                "query": request.query,
                "focal_units": len(bundle.focal_units),
                "dependencies": len(bundle.dependency_skeletons),
                "token_count": bundle.metadata.total_tokens,
            },
        )

        return BuildContextResponse(
            query=request.query,
            focal_code=focal_code,
            context=context,
            focal_units=focal_units_data,
            dependency_skeletons=dependency_skeletons_data,
            token_count=bundle.metadata.total_tokens,
            num_focal_units=len(bundle.focal_units),
            num_dependencies=len(bundle.dependency_skeletons),
        )

    except Exception as e:
        logger.error(f"build_context failed: {e}")
        raise


def _format_focal_code(units: List[CodeUnit]) -> str:
    """Format focal units as a code string.

    Args:
        units: List of focal code units.

    Returns:
        Formatted code string.
    """
    if not units:
        return ""

    parts = []
    for unit in units:
        parts.append(f"# {unit.file_path}:{unit.line_range[0]}")
        parts.append(unit.signature)
        if unit.docstring:
            parts.append(f'"""{unit.docstring}"""')
        parts.append(unit.body)
        parts.append("")

    return "\n".join(parts)


def _format_complete_context(bundle: Any) -> str:
    """Format the complete context bundle as a string.

    Args:
        bundle: The ContextBundle to format.

    Returns:
        Complete formatted context string.
    """
    parts = []

    # Header
    parts.append(f"# Context for: {bundle.query}")
    parts.append("")

    # Repository map if available
    if bundle.repository_map:
        parts.append("## Repository Structure")
        parts.append(f"Root: {bundle.repository_map.root_path}")
        if bundle.repository_map.modules:
            parts.append(f"Modules: {', '.join(bundle.repository_map.modules[:10])}")
        parts.append("")

    # Focal units
    if bundle.focal_units:
        parts.append(f"## Focal Units ({len(bundle.focal_units)})")
        parts.append("")
        for unit in bundle.focal_units:
            parts.append(f"### {unit.id}")
            parts.append(f"File: {unit.file_path}:{unit.line_range[0]}-{unit.line_range[1]}")
            parts.append("```")
            parts.append(unit.signature)
            parts.append(unit.body)
            parts.append("```")
            parts.append("")

    # Dependency skeletons
    if bundle.dependency_skeletons:
        parts.append(f"## Dependencies ({len(bundle.dependency_skeletons)})")
        parts.append("")
        for skeleton in bundle.dependency_skeletons:
            parts.append(
                f"- `{skeleton.id}` ({skeleton.unit_kind}) at " f"{skeleton.file_path}:{skeleton.line_range[0]}"
            )

    # Metadata
    parts.append("")
    parts.append("---")
    parts.append(
        f"Tokens: {bundle.metadata.total_tokens} | "
        f"Focal: {bundle.metadata.num_focal_units} | "
        f"Deps: {bundle.metadata.num_dependencies}"
    )

    return "\n".join(parts)


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
