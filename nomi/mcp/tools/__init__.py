"""MCP tool definitions and registry.

This module provides all available MCP tools for Nomi, including
tool definitions and handlers for agent integration.
"""

from typing import Any, Callable, Dict, List, Optional

from nomi.mcp.tools.build_context import (
    build_context_tool,
    get_build_context_tool_definition,
)
from nomi.mcp.tools.context_builder import (
    get_symbol_context_tool,
    get_symbol_context_tool_definition,
)
from nomi.mcp.tools.dependency_expand import (
    expand_dependencies_tool,
    get_expand_dependencies_tool_definition,
)
from nomi.mcp.tools.repo_map import (
    get_repo_map_tool,
    get_repo_map_tool_definition,
)
from nomi.mcp.tools.symbol_lookup import (
    get_search_symbol_tool_definition,
    search_symbol_tool,
)

# Type alias for tool handler functions
ToolHandler = Callable[..., Any]


class ToolDefinition:
    """Definition of an MCP tool.

    Encapsulates the tool's metadata (name, description, schema)
    and its handler function.
    """

    def __init__(
        self,
        name: str,
        description: str,
        input_schema: Dict[str, Any],
        handler: ToolHandler,
    ) -> None:
        """Initialize a tool definition.

        Args:
            name: The tool name (must be unique).
            description: Human-readable description for LLM understanding.
            input_schema: JSON schema for tool parameters.
            handler: Async function to execute the tool.
        """
        self.name = name
        self.description = description
        self.input_schema = input_schema
        self.handler = handler

    def to_dict(self) -> Dict[str, Any]:
        """Convert to MCP tool definition dictionary.

        Returns:
            Dictionary suitable for tools/list response.
        """
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }


# Registry of all available tools
_TOOLS: Dict[str, ToolDefinition] = {}


def register_tool(
    name: str,
    description: str,
    input_schema: Dict[str, Any],
    handler: ToolHandler,
) -> ToolDefinition:
    """Register a new tool.

    Args:
        name: The tool name.
        description: Tool description.
        input_schema: Input parameter schema.
        handler: Tool handler function.

    Returns:
        The registered ToolDefinition.

    Raises:
        ValueError: If a tool with the same name is already registered.
    """
    if name in _TOOLS:
        raise ValueError(f"Tool '{name}' is already registered")

    tool = ToolDefinition(
        name=name,
        description=description,
        input_schema=input_schema,
        handler=handler,
    )
    _TOOLS[name] = tool
    return tool


def get_tool(name: str) -> Optional[ToolDefinition]:
    """Get a tool by name.

    Args:
        name: The tool name to look up.

    Returns:
        The ToolDefinition if found, None otherwise.
    """
    return _TOOLS.get(name)


def get_all_tools() -> List[ToolDefinition]:
    """Get all registered tools.

    Returns:
        List of all ToolDefinition objects.
    """
    return list(_TOOLS.values())


def _initialize_tools() -> None:
    """Initialize the default tool registry.

    Registers all built-in Nomi MCP tools.
    """
    global _TOOLS
    _TOOLS = {}

    # Register get_repo_map tool
    repo_map_def = get_repo_map_tool_definition()
    register_tool(
        name=repo_map_def["name"],
        description=repo_map_def["description"],
        input_schema=repo_map_def["inputSchema"],
        handler=get_repo_map_tool,
    )

    # Register search_symbol tool
    search_def = get_search_symbol_tool_definition()
    register_tool(
        name=search_def["name"],
        description=search_def["description"],
        input_schema=search_def["inputSchema"],
        handler=search_symbol_tool,
    )

    # Register get_symbol_context tool
    context_def = get_symbol_context_tool_definition()
    register_tool(
        name=context_def["name"],
        description=context_def["description"],
        input_schema=context_def["inputSchema"],
        handler=get_symbol_context_tool,
    )

    # Register expand_dependencies tool
    expand_def = get_expand_dependencies_tool_definition()
    register_tool(
        name=expand_def["name"],
        description=expand_def["description"],
        input_schema=expand_def["inputSchema"],
        handler=expand_dependencies_tool,
    )

    # Register build_context tool
    build_def = get_build_context_tool_definition()
    register_tool(
        name=build_def["name"],
        description=build_def["description"],
        input_schema=build_def["inputSchema"],
        handler=build_context_tool,
    )


# Initialize tools on module load
_initialize_tools()


__all__ = [
    "ToolDefinition",
    "ToolHandler",
    "get_all_tools",
    "get_tool",
    "register_tool",
]
