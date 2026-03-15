"""MCP (Model Context Protocol) server for Nomi.

This module provides the main MCP server implementation that handles
protocol messages and dispatches tool requests.
"""

import asyncio
import json
import logging
import sys
from typing import Any, Dict, Optional

from nomi.core.context.context_builder import ContextBuilder
from nomi.core.graph.dependency_graph import DependencyGraph
from nomi.core.index.lookup import SymbolLookup
from nomi.core.index.search import SymbolSearch
from nomi.mcp.handlers.executor import ToolExecutor
from nomi.mcp.tools import get_all_tools
from nomi.repo_map.map_builder import RepoMapBuilder

logger = logging.getLogger(__name__)

# MCP Protocol version
MCP_PROTOCOL_VERSION = "2024-11-05"


class MCPServer:
    """MCP server implementation for Nomi context engine.

    This class implements the Model Context Protocol, handling:
    - initialize: Client initialization
    - tools/list: List available tools
    - tools/call: Execute tool requests

    Supports both stdio and HTTP transports.

    Attributes:
        context_builder: ContextBuilder for building context bundles.
        symbol_search: SymbolSearch for fuzzy symbol lookup.
        repo_map_builder: RepoMapBuilder for repository maps.
        dependency_graph: DependencyGraph for dependency traversal.
        symbol_lookup: SymbolLookup for exact symbol lookup.
        tool_executor: ToolExecutor for running tools.
    """

    def __init__(
        self,
        context_builder: ContextBuilder,
        symbol_search: SymbolSearch,
        repo_map_builder: RepoMapBuilder,
        dependency_graph: DependencyGraph,
        symbol_lookup: Optional[SymbolLookup] = None,
    ) -> None:
        """Initialize the MCP server.

        Args:
            context_builder: ContextBuilder instance.
            symbol_search: SymbolSearch instance.
            repo_map_builder: RepoMapBuilder instance.
            dependency_graph: DependencyGraph instance.
            symbol_lookup: Optional SymbolLookup instance.
        """
        self.context_builder = context_builder
        self.symbol_search = symbol_search
        self.repo_map_builder = repo_map_builder
        self.dependency_graph = dependency_graph
        self.symbol_lookup = symbol_lookup

        # Initialize tool executor with shared context
        self.tool_executor = ToolExecutor(
            context_builder=context_builder,
            symbol_search=symbol_search,
            repo_map_builder=repo_map_builder,
            dependency_graph=dependency_graph,
            symbol_lookup=symbol_lookup,
        )

        logger.info("MCP server initialized")

    async def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle an incoming MCP request.

        Args:
            request: The JSON-RPC request dictionary.

        Returns:
            The response dictionary.
        """
        method = request.get("method")
        request_id = request.get("id")
        params = request.get("params", {})

        logger.debug(f"Handling MCP request: {method}")

        try:
            if method == "initialize":
                return self._handle_initialize(request_id, params)
            elif method == "tools/list":
                return self._handle_tools_list(request_id)
            elif method == "tools/call":
                return await self._handle_tools_call(request_id, params)
            elif method == "notifications/initialized":
                # Notification, no response needed
                return {}
            else:
                return self._create_error_response(
                    request_id=request_id,
                    code=-32601,
                    message=f"Method not found: {method}",
                )
        except Exception as e:
            logger.exception(f"Error handling request: {method}")
            return self._create_error_response(
                request_id=request_id,
                code=-32603,
                message=f"Internal error: {str(e)}",
            )

    def _handle_initialize(
        self,
        request_id: Optional[Any],
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Handle initialize request.

        Args:
            request_id: The request ID.
            params: Initialize parameters.

        Returns:
            Initialize response.
        """
        client_info = params.get("clientInfo", {})

        logger.info(f"Client initializing: {client_info.get('name')} {client_info.get('version')}")

        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {
                    "tools": {
                        "listChanged": False,
                    },
                },
                "serverInfo": {
                    "name": "nomi-mcp",
                    "version": "0.1.0",
                },
            },
        }

    def _handle_tools_list(self, request_id: Optional[Any]) -> Dict[str, Any]:
        """Handle tools/list request.

        Args:
            request_id: The request ID.

        Returns:
            Tools list response.
        """
        tools = get_all_tools()
        tool_definitions = [tool.to_dict() for tool in tools]

        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "tools": tool_definitions,
            },
        }

    async def _handle_tools_call(
        self,
        request_id: Optional[Any],
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Handle tools/call request.

        Args:
            request_id: The request ID.
            params: Tool call parameters.

        Returns:
            Tool call response.
        """
        tool_name = params.get("name")
        arguments = params.get("arguments", {})

        if not tool_name:
            return self._create_error_response(
                request_id=request_id,
                code=-32602,
                message="Missing required parameter: name",
            )

        # Execute the tool
        result = await self.tool_executor.execute(tool_name, arguments)

        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": result,
        }

    def _create_error_response(
        self,
        request_id: Optional[Any],
        code: int,
        message: str,
        data: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """Create a JSON-RPC error response.

        Args:
            request_id: The request ID.
            code: Error code.
            message: Error message.
            data: Optional additional error data.

        Returns:
            Error response dictionary.
        """
        error = {
            "code": code,
            "message": message,
        }
        if data is not None:
            error["data"] = data

        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "error": error,
        }

    async def run_stdio(self) -> None:
        """Run the MCP server over stdio transport."""
        logger.info("Starting MCP server on stdio")

        while True:
            try:
                # Read a line from stdin
                line = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)

                if not line:
                    break

                line = line.strip()
                if not line:
                    continue

                # Parse the request
                try:
                    request = json.loads(line)
                except json.JSONDecodeError as e:
                    response = self._create_error_response(
                        request_id=None,
                        code=-32700,
                        message=f"Parse error: {e}",
                    )
                    self._send_response(response)
                    continue

                # Handle the request
                response = await self.handle_request(request)

                # Send the response (if not a notification)
                if request.get("id") is not None and response:
                    self._send_response(response)

            except KeyboardInterrupt:
                break
            except Exception as e:
                logger.exception("Error in stdio loop")
                response = self._create_error_response(
                    request_id=None,
                    code=-32603,
                    message=f"Internal error: {e}",
                )
                self._send_response(response)

    def _send_response(self, response: Dict[str, Any]) -> None:
        """Send a response to stdout.

        Args:
            response: The response dictionary.
        """
        try:
            output = json.dumps(response, default=str)
            print(output, flush=True)
        except Exception as e:
            logger.error(f"Failed to send response: {e}")


class MCPHTTPServer:
    """HTTP transport for MCP server using FastAPI."""

    def __init__(self, mcp_server: MCPServer) -> None:
        """Initialize the HTTP server.

        Args:
            mcp_server: The MCP server instance.
        """
        self.mcp_server = mcp_server

    def create_app(self) -> Any:
        """Create a FastAPI application for MCP over HTTP.

        Returns:
            FastAPI application instance.
        """
        try:
            from fastapi import FastAPI, Request, Response
            from fastapi.responses import JSONResponse

            app = FastAPI(title="Nomi MCP Server")

            @app.post("/mcp")
            async def handle_mcp_request(request: Request) -> Response:
                """Handle MCP requests over HTTP."""
                body = None
                try:
                    body = await request.json()
                    result = await self.mcp_server.handle_request(body)
                    return JSONResponse(content=result)
                except Exception as e:
                    request_id = body.get("id") if body else None
                    error_response = self.mcp_server._create_error_response(
                        request_id=request_id,
                        code=-32603,
                        message=f"Internal error: {e}",
                    )
                    return JSONResponse(content=error_response, status_code=500)

            @app.get("/health")
            async def health_check() -> Dict[str, str]:
                """Health check endpoint."""
                return {"status": "healthy", "service": "nomi-mcp"}

            return app

        except ImportError:
            raise ImportError("FastAPI is required for HTTP transport")


def create_mcp_server(
    context_builder: ContextBuilder,
    symbol_search: SymbolSearch,
    repo_map_builder: RepoMapBuilder,
    dependency_graph: DependencyGraph,
    symbol_lookup: Optional[SymbolLookup] = None,
) -> MCPServer:
    """Create and configure an MCP server instance.

    This is the main factory function for creating an MCP server with
    all necessary dependencies wired together.

    Args:
        context_builder: ContextBuilder for building context bundles.
        symbol_search: SymbolSearch for fuzzy symbol lookup.
        repo_map_builder: RepoMapBuilder for repository maps.
        dependency_graph: DependencyGraph for dependency traversal.
        symbol_lookup: Optional SymbolLookup for exact symbol lookup.

    Returns:
        Configured MCPServer instance.

    Example:
        >>> server = create_mcp_server(
        ...     context_builder=context_builder,
        ...     symbol_search=symbol_search,
        ...     repo_map_builder=repo_map_builder,
        ...     dependency_graph=dep_graph,
        ...     symbol_lookup=symbol_lookup,
        ... )
        >>> await server.run_stdio()
    """
    return MCPServer(
        context_builder=context_builder,
        symbol_search=symbol_search,
        repo_map_builder=repo_map_builder,
        dependency_graph=dependency_graph,
        symbol_lookup=symbol_lookup,
    )
