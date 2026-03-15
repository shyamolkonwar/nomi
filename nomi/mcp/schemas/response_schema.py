"""MCP response schemas for Nomi.

This module defines the response models for MCP tool invocations,
following the Model Context Protocol specification.
"""

from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field


class ModuleInfo(BaseModel):
    """Information about a module/directory in the repository."""

    name: str = Field(..., description="Module name (directory name)")
    path: str = Field(..., description="Relative path to the module")
    symbol_count: int = Field(..., description="Total number of symbols in the module")
    important_symbols: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Top important symbols in this module",
    )


class SymbolMatch(BaseModel):
    """A single symbol search result."""

    symbol_name: str = Field(..., description="Name of the matched symbol")
    unit_id: str = Field(..., description="Unique identifier for the symbol")
    unit_kind: str = Field(..., description="Type of code unit (function, class, etc.)")
    file_path: str = Field(..., description="Path to the source file")
    line_number: int = Field(..., description="Line number where symbol is defined")
    match_score: float = Field(..., description="Relevance score (0.0-1.0)", ge=0.0, le=1.0)
    match_type: str = Field(..., description="Type of match: exact, prefix, or fuzzy")
    signature: Optional[str] = Field(default=None, description="Symbol signature/declaration")


class DependencyInfo(BaseModel):
    """Information about a symbol dependency."""

    symbol_name: str = Field(..., description="Name of the dependency symbol")
    unit_id: str = Field(..., description="Unique identifier for the dependency")
    unit_kind: str = Field(..., description="Type of code unit")
    file_path: str = Field(..., description="Path to the source file")
    line_number: int = Field(..., description="Line number where symbol is defined")
    relationship: str = Field(..., description="Type of dependency relationship")


class GetRepoMapResponse(BaseModel):
    """Response containing the repository structure map.

    Provides a compact overview of the codebase organized by modules,
    with important symbols ranked by their significance.
    """

    modules: List[ModuleInfo] = Field(
        default_factory=list,
        description="List of modules with their important symbols",
    )
    total_modules: int = Field(..., description="Total number of modules in the repository")
    total_symbols: int = Field(..., description="Total number of indexed symbols")
    top_level_symbols: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Most important symbols across the entire repository",
    )


class SearchSymbolResponse(BaseModel):
    """Response containing symbol search results.

    Returns ranked list of symbols matching the search query,
    with relevance scores and match information.
    """

    results: List[SymbolMatch] = Field(
        default_factory=list,
        description="List of matching symbols ranked by relevance",
    )
    total_found: int = Field(..., description="Total number of matches found")
    query: str = Field(..., description="The original search query")


class GetSymbolContextResponse(BaseModel):
    """Response containing full context for a symbol.

    Provides the complete implementation including body, signature,
    location information, and optionally dependency details.
    """

    symbol_name: str = Field(..., description="Name of the symbol")
    unit_id: str = Field(..., description="Unique identifier for the symbol")
    code: str = Field(..., description="Full implementation code (body)")
    file_path: str = Field(..., description="Path to the source file")
    line_range: Tuple[int, int] = Field(..., description="Start and end line numbers")
    signature: str = Field(..., description="Symbol signature/declaration")
    docstring: Optional[str] = Field(default=None, description="Documentation string if available")
    unit_kind: str = Field(..., description="Type of code unit")
    language: str = Field(..., description="Programming language")
    dependencies: Optional[List[DependencyInfo]] = Field(
        default=None,
        description="List of direct dependencies if requested",
    )


class ExpandDependenciesResponse(BaseModel):
    """Response containing expanded dependency information.

    Returns all symbols reachable from the starting symbol within
    the specified depth in the dependency graph.
    """

    symbol_name: str = Field(..., description="Name of the starting symbol")
    unit_id: str = Field(..., description="Unique identifier for the starting symbol")
    depth: int = Field(..., description="Depth of expansion performed")
    dependencies: List[DependencyInfo] = Field(
        default_factory=list,
        description="List of dependencies at the specified depth",
    )
    total_dependencies: int = Field(..., description="Total number of dependencies found")


class BuildContextResponse(BaseModel):
    """Response containing a complete context bundle.

    Provides an assembled context bundle optimized for AI agents,
    including focal code, related dependencies, and metadata.
    """

    query: str = Field(..., description="The original query")
    focal_code: str = Field(..., description="Primary code units with full implementation")
    context: str = Field(..., description="Complete formatted context string")
    focal_units: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="List of focal code units with metadata",
    )
    dependency_skeletons: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Lightweight skeletons of related dependencies",
    )
    token_count: int = Field(..., description="Estimated token count")
    num_focal_units: int = Field(..., description="Number of focal units included")
    num_dependencies: int = Field(..., description="Number of dependency skeletons included")


class ErrorResponse(BaseModel):
    """Error response for failed tool invocations.

    Provides structured error information including the error type
    and a human-readable message.
    """

    error: str = Field(..., description="Error type/code")
    message: str = Field(..., description="Human-readable error message")
    details: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Additional error details if available",
    )
