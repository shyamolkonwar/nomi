"""MCP tool router for request dispatching.

This module provides the ToolRouter class that routes MCP tool requests
to the appropriate handlers based on tool name.
"""

import logging
from typing import Any, Callable, Dict, Optional

from nomi.mcp.schemas.response_schema import ErrorResponse
from nomi.mcp.tools import get_tool

logger = logging.getLogger(__name__)


class ToolRouter:
    """Routes MCP tool requests to appropriate handlers.

    The ToolRouter maintains a registry of tool handlers and dispatches
    incoming requests to the correct handler based on the tool name.
    It also handles validation and error responses for unknown tools.

    Attributes:
        _handlers: Dictionary mapping tool names to handler functions.
        _custom_handlers: Dictionary of user-registered custom handlers.
    """

    def __init__(self) -> None:
        """Initialize the tool router."""
        self._handlers: Dict[str, Callable[..., Any]] = {}
        self._custom_handlers: Dict[str, Callable[..., Any]] = {}

    def register_tool(self, name: str, handler: Callable[..., Any]) -> None:
        """Register a custom tool handler.

        Args:
            name: The tool name to register.
            handler: The handler function for the tool.

        Raises:
            ValueError: If a handler is already registered for this tool.
        """
        if name in self._handlers or name in self._custom_handlers:
            raise ValueError(f"Handler already registered for tool: {name}")

        self._custom_handlers[name] = handler
        logger.debug(f"Registered custom handler for tool: {name}")

    def unregister_tool(self, name: str) -> bool:
        """Unregister a custom tool handler.

        Args:
            name: The tool name to unregister.

        Returns:
            True if the handler was removed, False if it didn't exist.
        """
        if name in self._custom_handlers:
            del self._custom_handlers[name]
            logger.debug(f"Unregistered custom handler for tool: {name}")
            return True
        return False

    def route_request(
        self,
        tool_name: str,
        params: Dict[str, Any],
        **context: Any,
    ) -> Dict[str, Any]:
        """Route a tool request to the appropriate handler.

        Args:
            tool_name: The name of the tool to invoke.
            params: The tool parameters from the request.
            **context: Additional context passed to handlers (e.g., dependencies).

        Returns:
            The handler's response or an error response.

        Raises:
            ToolNotFoundError: If the tool is not found (unless raise_on_error=False).
        """
        logger.info(
            "Routing tool request",
            extra={"tool_name": tool_name, "params_keys": list(params.keys())},
        )

        # Check custom handlers first
        if tool_name in self._custom_handlers:
            handler = self._custom_handlers[tool_name]
            return self._execute_handler(handler, tool_name, params, **context)

        # Check built-in tools
        tool_def = get_tool(tool_name)
        if tool_def is None:
            logger.warning(f"Tool not found: {tool_name}")
            return self._create_error_response(
                error="tool_not_found",
                message=f"Tool '{tool_name}' is not available",
            )

        return self._execute_handler(tool_def.handler, tool_name, params, **context)

    def _execute_handler(
        self,
        handler: Callable[..., Any],
        tool_name: str,
        params: Dict[str, Any],
        **context: Any,
    ) -> Dict[str, Any]:
        """Execute a tool handler and handle any errors.

        Args:
            handler: The handler function to execute.
            tool_name: The name of the tool (for logging).
            params: The tool parameters.
            **context: Additional context for the handler.

        Returns:
            The handler's result or an error response.
        """
        try:
            # Import asyncio to handle async handlers
            import asyncio

            # Check if handler is async
            if asyncio.iscoroutinefunction(handler):
                # For async handlers, we need to run them in an event loop
                # This assumes route_request is called from within an async context
                # or we need to handle it differently
                raise RuntimeError("Async handlers should be executed through ToolExecutor, not directly")
            else:
                # Sync handler - call directly with context
                result = handler(params, **context)

            logger.info(f"Tool '{tool_name}' executed successfully")
            return result  # type: ignore[no-any-return]

        except Exception as e:
            logger.error(f"Tool '{tool_name}' execution failed: {e}")
            return self._create_error_response(
                error="execution_error",
                message=str(e),
                details={"tool_name": tool_name},
            )

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
        response = ErrorResponse(
            error=error,
            message=message,
            details=details,
        )
        return response.model_dump()

    def list_available_tools(self) -> list[str]:
        """Get a list of all available tool names.

        Returns:
            List of available tool names.
        """
        from nomi.mcp.tools import get_all_tools

        built_in = [tool.name for tool in get_all_tools()]
        custom = list(self._custom_handlers.keys())
        return sorted(set(built_in + custom))
