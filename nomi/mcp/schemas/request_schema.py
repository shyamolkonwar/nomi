"""MCP request schemas for Nomi.

This module defines the request models for MCP tool invocations,
following the Model Context Protocol specification.
"""

from typing import Optional

from pydantic import BaseModel, Field


class GetRepoMapRequest(BaseModel):
    """Request to get a high-level overview of the repository structure.

    Returns a compact map showing important symbols organized by module,
    ranked by importance scores.
    """

    max_entries: Optional[int] = Field(
        default=100,
        description="Maximum number of symbols to include in the map",
        ge=10,
        le=500,
    )
    max_symbols_per_module: Optional[int] = Field(
        default=10,
        description="Maximum symbols to include per module",
        ge=1,
        le=50,
    )


class SearchSymbolRequest(BaseModel):
    """Request to search for symbols using fuzzy matching.

    Performs fuzzy search across all indexed symbols and returns
    ranked results based on relevance scores.
    """

    query: str = Field(
        ...,
        description="Search query string (symbol name or partial match)",
        min_length=1,
        max_length=200,
    )
    limit: Optional[int] = Field(
        default=10,
        description="Maximum number of results to return",
        ge=1,
        le=100,
    )


class GetSymbolContextRequest(BaseModel):
    """Request to get full context for a specific symbol.

    Retrieves the complete implementation of a symbol including
    its body, signature, and optionally its dependencies.
    """

    symbol_name: str = Field(
        ...,
        description="Exact or approximate symbol name to look up",
        min_length=1,
        max_length=200,
    )
    include_dependencies: Optional[bool] = Field(
        default=True,
        description="Whether to include dependency information",
    )


class ExpandDependenciesRequest(BaseModel):
    """Request to expand and explore symbol dependencies.

    Traverses the dependency graph starting from a symbol and
    returns related symbols up to the specified depth.
    """

    symbol_name: str = Field(
        ...,
        description="Symbol name to start dependency expansion from",
        min_length=1,
        max_length=200,
    )
    depth: Optional[int] = Field(
        default=1,
        description="How many hops to follow in the dependency graph (1-3)",
        ge=1,
        le=3,
    )


class BuildContextRequest(BaseModel):
    """Request to build a complete context bundle for a query.

    Executes the full 5-stage context retrieval pipeline to assemble
    a context bundle optimized for AI coding agents.
    """

    query: str = Field(
        ...,
        description="Natural language query describing what context is needed",
        min_length=1,
        max_length=1000,
    )
    max_tokens: Optional[int] = Field(
        default=4000,
        description="Maximum estimated tokens for the context bundle",
        ge=500,
        le=16000,
    )
    dependency_depth: Optional[int] = Field(
        default=1,
        description="Depth of dependency expansion (1-3)",
        ge=1,
        le=3,
    )
