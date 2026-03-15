"""MCP (Model Context Protocol) integration package for Nomi.

This package provides the Model Context Protocol server and tools
for integrating Nomi with AI coding agents.

Example:
    >>> from nomi.mcp import create_mcp_server, get_all_tools
    >>>
    >>> # Create server with dependencies
    >>> server = create_mcp_server(
    ...     context_builder=context_builder,
    ...     symbol_search=symbol_search,
    ...     repo_map_builder=repo_map_builder,
    ...     dependency_graph=dep_graph,
    ... )
    >>>
    >>> # Run server over stdio
    >>> await server.run_stdio()
"""

from nomi.mcp.handlers import ToolExecutor, ToolRouter
from nomi.mcp.schemas import (
    BuildContextRequest,
    BuildContextResponse,
    DependencyInfo,
    ErrorResponse,
    ExpandDependenciesRequest,
    ExpandDependenciesResponse,
    GetRepoMapRequest,
    GetRepoMapResponse,
    GetSymbolContextRequest,
    GetSymbolContextResponse,
    ModuleInfo,
    SearchSymbolRequest,
    SearchSymbolResponse,
    SymbolMatch,
)
from nomi.mcp.server import MCPServer, MCPHTTPServer, create_mcp_server
from nomi.mcp.tools import ToolDefinition, ToolHandler, get_all_tools, get_tool, register_tool

__all__ = [
    # Server
    "MCPServer",
    "MCPHTTPServer",
    "create_mcp_server",
    # Handlers
    "ToolExecutor",
    "ToolRouter",
    # Tools
    "ToolDefinition",
    "ToolHandler",
    "get_all_tools",
    "get_tool",
    "register_tool",
    # Request schemas
    "BuildContextRequest",
    "ExpandDependenciesRequest",
    "GetRepoMapRequest",
    "GetSymbolContextRequest",
    "SearchSymbolRequest",
    # Response schemas
    "BuildContextResponse",
    "DependencyInfo",
    "ErrorResponse",
    "ExpandDependenciesResponse",
    "GetRepoMapResponse",
    "GetSymbolContextResponse",
    "ModuleInfo",
    "SearchSymbolResponse",
    "SymbolMatch",
]
