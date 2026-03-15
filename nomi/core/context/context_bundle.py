"""Context bundle data models for Nomi.

This module defines the data structures for assembled context bundles,
including focal units, dependency skeletons, and metadata.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Tuple

from pydantic import BaseModel, Field

from nomi.storage.models import CodeUnit


@dataclass
class CodeUnitSkeleton:
    """Lightweight representation of a code unit without implementation body.

    Used for non-focal dependencies to reduce token usage while preserving
    structural information.
    """

    id: str
    unit_kind: str
    signature: str
    file_path: str
    line_range: Tuple[int, int]
    docstring: Optional[str] = None


@dataclass
class ContextMetadata:
    """Metadata about a context bundle.

    Tracks creation time, token usage, and statistics about the bundle contents.
    """

    created_at: datetime
    total_tokens: int = 0
    num_focal_units: int = 0
    num_dependencies: int = 0
    search_duration_ms: float = 0.0


@dataclass
class RepositoryMap:
    """High-level structure of the repository.

    Provides an overview of the codebase structure including
    file organization and module hierarchy.
    """

    root_path: str
    files: List[str] = field(default_factory=list)
    modules: List[str] = field(default_factory=list)
    summary: Optional[str] = None


class ContextBundle(BaseModel):
    """Assembled context bundle for AI coding agents.

    A context bundle contains all the information needed for an AI agent
    to understand and work with a specific part of the codebase, including:
    - The original developer query
    - Focal code units (fully detailed)
    - Dependency skeletons (signatures only)
    - Repository structure map
    - Metadata about the bundle

    Attributes:
        query: The original developer query string.
        focal_units: List of primary target CodeUnits with full implementation.
        dependency_skeletons: List of skeletonized dependencies (no bodies).
        repository_map: Optional repository structure overview.
        metadata: Bundle creation metadata and statistics.
    """

    query: str = Field(..., description="Original developer query")
    focal_units: List[CodeUnit] = Field(
        default_factory=list, description="Main target symbols with full implementation"
    )
    dependency_skeletons: List[CodeUnitSkeleton] = Field(
        default_factory=list, description="Related symbols with bodies removed"
    )
    repository_map: Optional[RepositoryMap] = Field(default=None, description="High-level repository structure")
    metadata: ContextMetadata = Field(
        default_factory=lambda: ContextMetadata(created_at=datetime.now()), description="Bundle metadata and statistics"
    )

    class Config:
        """Pydantic configuration."""

        arbitrary_types_allowed = True
