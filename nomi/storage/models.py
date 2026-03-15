from enum import Enum
from typing import List, Tuple, Optional

from pydantic import BaseModel, Field


class UnitKind(str, Enum):
    """Type of code unit."""

    FUNCTION = "FUNCTION"
    CLASS = "CLASS"
    METHOD = "METHOD"
    INTERFACE = "INTERFACE"
    MODULE = "MODULE"
    VARIABLE = "VARIABLE"


class EdgeType(str, Enum):
    """Type of dependency edge."""

    CALLS = "CALLS"
    IMPORTS = "IMPORTS"
    DEFINES = "DEFINES"
    IMPLEMENTS = "IMPLEMENTS"


class CodeUnit(BaseModel):
    """Represents a single unit of code (function, class, etc.)."""

    id: str = Field(..., description="Unique identifier: repo_path/file:symbol_name")
    unit_kind: UnitKind = Field(..., description="Type of code unit")
    file_path: str = Field(..., description="Absolute path to source file")
    byte_range: Tuple[int, int] = Field(..., description="Start, end byte offsets")
    line_range: Tuple[int, int] = Field(..., description="Start, end line numbers")
    signature: str = Field(..., description="Declaration without body")
    body: str = Field(..., description="Full implementation")
    dependencies: List[str] = Field(default_factory=list, description="Symbol IDs this unit depends on")
    docstring: Optional[str] = Field(default=None, description="Documentation string")
    language: str = Field(..., description="Programming language (python, typescript, go, etc.)")


class DependencyEdge(BaseModel):
    """Represents a dependency relationship between two code units."""

    source_id: str = Field(..., description="Source code unit ID")
    target_id: str = Field(..., description="Target code unit ID")
    edge_type: EdgeType = Field(..., description="Type of dependency relationship")
