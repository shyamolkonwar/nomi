"""Context API schemas for Nomi.

This module defines Pydantic models for context-related API requests and responses.
"""

from typing import List, Optional, Tuple

from pydantic import BaseModel, Field


class FocalCodeEntry(BaseModel):
    """Represents a focal code unit in the context response."""

    name: str = Field(..., description="Symbol name")
    code: str = Field(..., description="Full implementation code")
    file_path: str = Field(..., description="Absolute path to source file")
    line_range: Tuple[int, int] = Field(..., description="Start and end line numbers")


class DependencyEntry(BaseModel):
    """Represents a dependency in the context response."""

    name: str = Field(..., description="Symbol name")
    signature: str = Field(..., description="Declaration without body")
    file_path: str = Field(..., description="Absolute path to source file")


class ResponseMetadata(BaseModel):
    """Metadata about a context response."""

    total_tokens: int = Field(..., description="Estimated total token count")
    search_duration_ms: float = Field(..., description="Search duration in milliseconds")


class RepoMapEntry(BaseModel):
    """Repository map structure for context responses."""

    root_path: str = Field(..., description="Root path of the repository")
    files: List[str] = Field(default_factory=list, description="List of relevant files")
    modules: List[str] = Field(default_factory=list, description="List of modules/directories")


class ContextRequest(BaseModel):
    """Request model for building context."""

    query: str = Field(..., description="Natural language query or symbol name")
    max_tokens: Optional[int] = Field(default=4000, description="Maximum token budget")
    dependency_depth: Optional[int] = Field(default=1, description="Dependency expansion depth")


class ContextResponse(BaseModel):
    """Response model for context requests."""

    query: str = Field(..., description="Original query")
    focal_code: List[FocalCodeEntry] = Field(default_factory=list, description="Primary target code units")
    dependencies: List[DependencyEntry] = Field(default_factory=list, description="Dependency skeletons")
    repo_map: Optional[RepoMapEntry] = Field(default=None, description="Repository structure overview")
    metadata: ResponseMetadata = Field(..., description="Response metadata")


class SymbolContextRequest(BaseModel):
    """Request model for building context for a specific symbol."""

    symbol_name: str = Field(..., description="Exact symbol name")
    max_tokens: Optional[int] = Field(default=4000, description="Maximum token budget")
    dependency_depth: Optional[int] = Field(default=1, description="Dependency expansion depth")


class FileContextRequest(BaseModel):
    """Request model for building context for a file."""

    file_path: str = Field(..., description="Absolute path to source file")
    focal_symbol: Optional[str] = Field(default=None, description="Optional specific symbol to focus on")
    max_tokens: Optional[int] = Field(default=4000, description="Maximum token budget")
    dependency_depth: Optional[int] = Field(default=1, description="Dependency expansion depth")


class ContextStats(BaseModel):
    """Statistics about the context engine."""

    total_indexed_symbols: int = Field(..., description="Total number of indexed symbols")
    total_files: int = Field(..., description="Total number of indexed files")
    avg_context_build_time_ms: float = Field(..., description="Average context build time")
    cache_hit_rate: float = Field(default=0.0, description="Context cache hit rate")
