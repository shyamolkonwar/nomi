"""MCP tool executor with validation and error handling.

This module provides the ToolExecutor class that handles async tool execution,
parameter validation against schemas, and response wrapping.
"""

import asyncio
import logging
from typing import Any, Dict, Optional

from nomi.mcp.schemas.request_schema import (
    BuildContextRequest,
    ExpandDependenciesRequest,
    GetRepoMapRequest,
    GetSymbolContextRequest,
    SearchSymbolRequest,
)
from nomi.mcp.schemas.response_schema import ErrorResponse
from nomi.mcp.tools import ToolDefinition, get_tool

logger = logging.getLogger(__name__)


class ToolExecutor:
    """Executes MCP tools with validation and error handling.

    The ToolExecutor handles async tool execution, validates parameters
    against tool schemas, and wraps responses in a standardized format.
    It provides graceful error handling and detailed error messages.

    Attributes:
        _context: Shared context (dependencies) passed to all tool handlers.
    """

    def __init__(self, **context: Any) -> None:
        """Initialize the tool executor with shared context.

        Args:
            **context: Shared dependencies passed to all tool handlers.
                Common context includes:
                - context_builder: ContextBuilder instance
                - symbol_search: SymbolSearch instance
                - repo_map_builder: RepoMapBuilder instance
                - dependency_graph: DependencyGraph instance
                - symbol_lookup: SymbolLookup instance
        """
        self._context = context

    async def execute(
        self,
        tool_name: str,
        params: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute a tool with the given parameters.

        Args:
            tool_name: The name of the tool to execute.
            params: The tool parameters from the request.

        Returns:
            Standardized response dictionary with either result content or error.
        """
        logger.info(
            "Executing tool",
            extra={"tool_name": tool_name, "params": params},
        )

        # Get the tool definition
        tool_def = get_tool(tool_name)
        if tool_def is None:
            return self._create_error_response(
                error="tool_not_found",
                message=f"Tool '{tool_name}' is not available",
            )

        # Validate parameters against schema
        try:
            validated_params = self._validate_params(tool_name, params)
        except ValueError as e:
            return self._create_error_response(
                error="invalid_params",
                message=f"Parameter validation failed: {e}",
            )

        # Execute the tool
        try:
            result = await self._execute_tool(tool_def, validated_params)

            # Wrap successful result
            return self._wrap_success_response(result)

        except Exception as e:
            logger.exception(f"Tool execution failed: {tool_name}")
            return self._create_error_response(
                error="execution_error",
                message=str(e),
                details={"tool_name": tool_name},
            )

    def _validate_params(
        self,
        tool_name: str,
        params: Dict[str, Any],
    ) -> Any:
        """Validate and parse parameters against the tool's request schema.

        Args:
            tool_name: The name of the tool.
            params: Raw parameters from the request.

        Returns:
            Validated Pydantic model instance.

        Raises:
            ValueError: If validation fails.
        """
        # Map tool names to their request schema classes
        schema_map = {
            "get_repo_map": GetRepoMapRequest,
            "search_symbol": SearchSymbolRequest,
            "get_symbol_context": GetSymbolContextRequest,
            "expand_dependencies": ExpandDependenciesRequest,
            "build_context": BuildContextRequest,
        }

        schema_class = schema_map.get(tool_name)
        if schema_class is None:
            raise ValueError(f"Unknown tool schema for: {tool_name}")

        try:
            return schema_class(**params)
        except Exception as e:
            raise ValueError(f"Invalid parameters: {e}")

    async def _execute_tool(
        self,
        tool_def: ToolDefinition,
        validated_params: Any,
    ) -> Any:
        """Execute the tool handler with validated parameters.

        Args:
            tool_def: The tool definition.
            validated_params: Validated Pydantic model instance.

        Returns:
            The tool's result.
        """
        handler = tool_def.handler

        # Prepare arguments - params plus context
        kwargs = {**self._context}

        # Execute the handler
        if asyncio.iscoroutinefunction(handler):
            result = await handler(validated_params, **kwargs)
        else:
            # Run sync handlers in thread pool to not block
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, handler, validated_params, **kwargs)

        return result

    def _wrap_success_response(self, result: Any) -> Dict[str, Any]:
        """Wrap a successful result in the MCP response format.

        Args:
            result: The raw result from the tool handler.

        Returns:
            Standardized MCP response dictionary.
        """
        # If result is already a dict, use it directly
        if isinstance(result, dict):
            return {
                "content": [
                    {
                        "type": "text",
                        "text": str(result),
                    }
                ],
                "data": result,
            }

        # If result is a Pydantic model, convert to dict
        if hasattr(result, "model_dump"):
            data = result.model_dump()
            return {
                "content": [
                    {
                        "type": "text",
                        "text": str(data),
                    }
                ],
                "data": data,
            }

        # Fallback for other types
        return {
            "content": [
                {
                    "type": "text",
                    "text": str(result),
                }
            ],
            "data": result,
        }

    def _create_error_response(
        self,
        error: str,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Create a standardized error response.

        Args:
            error: The error type/code.
            message: Human-readable error message.
            details: Optional additional details.

        Returns:
            Error response dictionary.
        """
        error_response = ErrorResponse(
            error=error,
            message=message,
            details=details,
        )

        return {
            "content": [
                {
                    "type": "text",
                    "text": f"Error: {message}",
                }
            ],
            "isError": True,
            "error": error_response.model_dump(),
        }

    async def execute_batch(
        self,
        requests: list[tuple[str, Dict[str, Any]]],
    ) -> list[Dict[str, Any]]:
        """Execute multiple tool requests concurrently.

        Args:
            requests: List of (tool_name, params) tuples.

        Returns:
            List of response dictionaries in the same order.
        """
        results: list[Dict[str, Any]] = []
        for tool_name, params in requests:
            try:
                result = await self.execute(tool_name, params)
                results.append(result)
            except Exception as e:
                results.append(
                    self._create_error_response(
                        error="batch_execution_error",
                        message=str(e),
                    )
                )
        return results
