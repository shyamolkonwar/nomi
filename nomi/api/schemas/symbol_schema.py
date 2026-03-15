"""Symbol API schemas for Nomi.

This module defines Pydantic models for symbol search and lookup API requests and responses.
"""

from typing import List, Optional

from pydantic import BaseModel, Field


class SymbolResult(BaseModel):
    """Represents a single symbol search result."""

    name: str = Field(..., description="Symbol name")
    unit_kind: str = Field(..., description="Type of code unit (function, class, method, etc.)")
    file_path: str = Field(..., description="Absolute path to source file")
    line_number: int = Field(..., description="Line number where symbol is defined")
    match_score: float = Field(..., description="Match relevance score (0.0 to 1.0)")


class SymbolSearchRequest(BaseModel):
    """Request model for symbol search."""

    query: str = Field(..., description="Search query string")
    limit: Optional[int] = Field(default=10, description="Maximum number of results to return")


class SymbolSearchResponse(BaseModel):
    """Response model for symbol search."""

    results: List[SymbolResult] = Field(default_factory=list, description="List of matching symbols")
    total_found: int = Field(..., description="Total number of matches found")


class SymbolDetail(BaseModel):
    """Detailed information about a symbol."""

    name: str = Field(..., description="Symbol name")
    unit_kind: str = Field(..., description="Type of code unit")
    file_path: str = Field(..., description="Absolute path to source file")
    line_range: tuple[int, int] = Field(..., description="Start and end line numbers")
    signature: str = Field(..., description="Declaration without body")
    docstring: Optional[str] = Field(default=None, description="Documentation string if available")


class FileSymbolsResponse(BaseModel):
    """Response model for getting symbols in a file."""

    file_path: str = Field(..., description="Absolute path to source file")
    symbols: List[SymbolDetail] = Field(default_factory=list, description="List of symbols in the file")
    total_symbols: int = Field(..., description="Total number of symbols")


class PrefixSearchResponse(BaseModel):
    """Response model for prefix-based symbol search."""

    prefix: str = Field(..., description="Search prefix")
    matches: List[SymbolResult] = Field(default_factory=list, description="List of matching symbols")
    total_matches: int = Field(..., description="Total number of matches")
