"""Configuration loader for Nomi.

This module provides utilities for loading, validating, and managing
Nomi configuration from various sources including JSON files and defaults.
"""

import json
from pathlib import Path
from typing import Any
from nomi.config.schema import NomiConfig, ConfigValidationError


DEFAULT_CONFIG_FILENAME = ".nomi.json"


def load_config(
    config_path: Path | str | None = None,
    project_root: Path | str | None = None,
) -> NomiConfig:
    """Load Nomi configuration from a JSON file.

    This function attempts to load configuration from the specified path,
    or looks for a .nomi.json file in the current directory or project root.

    Args:
        config_path: Explicit path to the configuration file. If None,
            searches for .nomi.json in current directory and project root.
        project_root: Root directory of the project. Used to resolve
            relative paths in the configuration.

    Returns:
        Validated NomiConfig instance.

    Raises:
        ConfigValidationError: If the configuration file is invalid.
        FileNotFoundError: If the specified config file does not exist.

    Example:
        >>> config = load_config()
        >>> config = load_config("/path/to/config.json")
        >>> config = load_config(project_root="/path/to/project")
    """
    if config_path is not None:
        config_file = Path(config_path)
        if not config_file.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        return _load_from_file(config_file, project_root)

    # Search for config file
    search_paths = [Path.cwd()]

    if project_root is not None:
        root = Path(project_root)
        if root not in search_paths:
            search_paths.append(root)

    for search_path in search_paths:
        config_file = search_path / DEFAULT_CONFIG_FILENAME
        if config_file.exists():
            return _load_from_file(config_file, project_root)

    # No config file found, return defaults
    return create_default_config(project_root)


def _load_from_file(
    config_file: Path,
    project_root: Path | str | None = None,
) -> NomiConfig:
    """Load and validate configuration from a JSON file.

    Args:
        config_file: Path to the JSON configuration file.
        project_root: Optional project root for path resolution.

    Returns:
        Validated NomiConfig instance.

    Raises:
        ConfigValidationError: If the configuration is invalid.
        json.JSONDecodeError: If the file contains invalid JSON.
    """
    try:
        with open(config_file, "r", encoding="utf-8") as f:
            data: dict[str, Any] = json.load(f)
    except json.JSONDecodeError as e:
        raise ConfigValidationError(
            f"Invalid JSON in configuration file: {e}",
            field=None,
        ) from e

    # Set project root from config file location if not specified
    if project_root is not None:
        data["project_root"] = str(project_root)
    elif "project_root" not in data:
        data["project_root"] = str(config_file.parent)

    try:
        return NomiConfig(**data)
    except ValueError as e:
        raise ConfigValidationError(
            f"Configuration validation failed: {e}",
            field=None,
        ) from e


def create_default_config(
    project_root: Path | str | None = None,
) -> NomiConfig:
    """Create a default Nomi configuration.

    Creates a configuration with all default values. If a project root
    is specified, it will be used to resolve relative paths.

    Args:
        project_root: Optional root directory for the project.

    Returns:
        NomiConfig instance with default values.

    Example:
        >>> config = create_default_config()
        >>> config = create_default_config("/path/to/project")
    """
    kwargs: dict[str, Any] = {}

    if project_root is not None:
        kwargs["project_root"] = Path(project_root)

    return NomiConfig(**kwargs)


def save_config(
    config: NomiConfig,
    config_path: Path | str | None = None,
) -> Path:
    """Save a Nomi configuration to a JSON file.

    Args:
        config: The NomiConfig instance to save.
        config_path: Path where to save the configuration. If None,
            saves to .nomi.json in the project root.

    Returns:
        Path to the saved configuration file.

    Example:
        >>> config = create_default_config()
        >>> save_config(config, "/path/to/.nomi.json")
    """
    if config_path is None:
        config_file = config.project_root / DEFAULT_CONFIG_FILENAME
    else:
        config_file = Path(config_path)

    # Ensure parent directory exists
    config_file.parent.mkdir(parents=True, exist_ok=True)

    # Convert to dict for serialization
    data = config.model_dump()

    # Convert Path objects to strings for JSON serialization
    for key, value in data.items():
        if isinstance(value, Path):
            data[key] = str(value)

    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, sort_keys=True)

    return config_file


class ConfigLoader:
    """Configuration loader with caching support.

    This class provides a more sophisticated configuration loader
    that can cache configurations and watch for changes.

    Attributes:
        config_path: Path to the configuration file.
        project_root: Root directory of the project.
        _cached_config: Cached configuration instance.
    """

    def __init__(
        self,
        config_path: Path | str | None = None,
        project_root: Path | str | None = None,
    ) -> None:
        """Initialize the configuration loader.

        Args:
            config_path: Path to the configuration file.
            project_root: Root directory of the project.
        """
        self.config_path = Path(config_path) if config_path else None
        self.project_root = Path(project_root) if project_root else Path.cwd()
        self._cached_config: NomiConfig | None = None

    def load(self, use_cache: bool = True) -> NomiConfig:
        """Load the configuration.

        Args:
            use_cache: Whether to use cached configuration if available.

        Returns:
            Validated NomiConfig instance.
        """
        if use_cache and self._cached_config is not None:
            return self._cached_config

        config = load_config(self.config_path, self.project_root)
        self._cached_config = config
        return config

    def reload(self) -> NomiConfig:
        """Force reload the configuration from disk.

        Returns:
            Freshly loaded NomiConfig instance.
        """
        self._cached_config = None
        return self.load(use_cache=False)

    def invalidate_cache(self) -> None:
        """Invalidate the cached configuration."""
        self._cached_config = None

    @property
    def has_config_file(self) -> bool:
        """Check if a configuration file exists."""
        if self.config_path:
            return self.config_path.exists()

        return (self.project_root / DEFAULT_CONFIG_FILENAME).exists()
