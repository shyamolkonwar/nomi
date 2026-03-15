"""MCP schemas package.

This package contains request and response schemas for MCP tool invocations.
"""

from nomi.mcp.schemas.request_schema import (
    BuildContextRequest,
    ExpandDependenciesRequest,
    GetRepoMapRequest,
    GetSymbolContextRequest,
    SearchSymbolRequest,
)
from nomi.mcp.schemas.response_schema import (
    BuildContextResponse,
    DependencyInfo,
    ErrorResponse,
    ExpandDependenciesResponse,
    GetRepoMapResponse,
    GetSymbolContextResponse,
    ModuleInfo,
    SearchSymbolResponse,
    SymbolMatch,
)

__all__ = [
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
