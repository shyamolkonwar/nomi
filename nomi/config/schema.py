"""Configuration schema for Nomi.

This module defines Pydantic models for validating and managing Nomi configuration.
"""

from typing import List
from pathlib import Path
from pydantic import BaseModel, Field, field_validator


DEFAULT_IGNORE_PATTERNS: List[str] = [
    ".git",
    "node_modules",
    "dist",
    "build",
    "vendor",
    ".cache",
    "__pycache__",
    ".venv",
    "venv",
    "*.pyc",
    "*.pyo",
    "*.so",
    "*.dylib",
    "*.dll",
    ".DS_Store",
    "*.log",
    ".env",
    ".env.*",
]

DEFAULT_LANGUAGES: List[str] = [
    "python",
    "typescript",
    "javascript",
    "go",
    "rust",
    "java",
    "cpp",
    "c",
]


class NomiConfig(BaseModel):
    """Main configuration model for Nomi.
    
    This class defines all configuration options for the Nomi context engine,
    including language support, file watching, MCP integration, and ignore patterns.
    
    Attributes:
        languages: List of programming languages to analyze and index.
        watch: Whether to enable file watching for automatic reindexing.
        enable_mcp: Whether to enable MCP (Model Context Protocol) integration.
        ignore_patterns: List of glob patterns for files/directories to ignore.
        project_root: Root directory of the project being analyzed.
        max_file_size: Maximum file size in bytes to process (default: 1MB).
        index_cache_dir: Directory to store index cache files.
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR).
        server_port: Port number for the API server.
    """
    
    languages: List[str] = Field(
        default_factory=lambda: DEFAULT_LANGUAGES.copy(),
        description="List of programming languages to analyze and index",
    )
    watch: bool = Field(
        default=True,
        description="Enable file watching for automatic reindexing",
    )
    enable_mcp: bool = Field(
        default=True,
        description="Enable MCP (Model Context Protocol) integration",
    )
    ignore_patterns: List[str] = Field(
        default_factory=lambda: DEFAULT_IGNORE_PATTERNS.copy(),
        description="List of glob patterns for files/directories to ignore",
    )
    project_root: Path = Field(
        default=Path("."),
        description="Root directory of the project being analyzed",
    )
    max_file_size: int = Field(
        default=1_048_576,  # 1MB
        description="Maximum file size in bytes to process",
        ge=1024,  # Minimum 1KB
    )
    index_cache_dir: Path = Field(
        default=Path(".nomi/cache"),
        description="Directory to store index cache files",
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR)",
    )
    server_port: int = Field(
        default=8765,
        description="Port number for the API server",
        ge=1024,
        le=65535,
    )
    
    @field_validator("languages")
    @classmethod
    def validate_languages(cls, v: List[str]) -> List[str]:
        """Validate that languages list is not empty and contains valid values."""
        if not v:
            raise ValueError("At least one language must be specified")
        
        valid_languages = {
            "python", "typescript", "javascript", "go", "rust",
            "java", "cpp", "c", "ruby", "php", "swift", "kotlin",
        }
        
        invalid = set(v) - valid_languages
        if invalid:
            raise ValueError(f"Unsupported languages: {invalid}")
        
        return v
    
    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate that log level is one of the allowed values."""
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        upper_v = v.upper()
        if upper_v not in valid_levels:
            raise ValueError(f"Invalid log level: {v}. Must be one of {valid_levels}")
        return upper_v
    
    @field_validator("project_root", "index_cache_dir")
    @classmethod
    def validate_path(cls, v: Path) -> Path:
        """Convert string paths to Path objects."""
        if isinstance(v, str):
            return Path(v)
        return v
    
    class Config:
        """Pydantic configuration."""
        
        validate_assignment = True
        str_strip_whitespace = True
        json_schema_extra = {
            "example": {
                "languages": ["python", "typescript", "go"],
                "watch": True,
                "enable_mcp": True,
                "ignore_patterns": DEFAULT_IGNORE_PATTERNS[:5],
                "project_root": ".",
                "max_file_size": 1048576,
                "log_level": "INFO",
                "server_port": 8765,
            }
        }


class ConfigValidationError(Exception):
    """Exception raised when configuration validation fails."""
    
    def __init__(self, message: str, field: str | None = None) -> None:
        """Initialize the validation error.
        
        Args:
            message: Human-readable error message.
            field: Name of the field that failed validation, if applicable.
        """
        super().__init__(message)
        self.field = field
        self.message = message
