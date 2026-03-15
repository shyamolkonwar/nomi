"""Initialize command for Nomi CLI.

This module provides the init command for setting up Nomi in a project directory.
"""

import json
import os
from pathlib import Path
from typing import List, Optional

import typer
from rich.console import Console
from rich.prompt import Confirm, Prompt

from nomi.config.loader import save_config
from nomi.config.schema import NomiConfig

console = Console()
app = typer.Typer(help="Initialize Nomi in a project directory")

# Language detection patterns
LANGUAGE_PATTERNS = {
    "python": ["*.py", "requirements.txt", "pyproject.toml", "setup.py"],
    "typescript": ["*.ts", "*.tsx", "tsconfig.json"],
    "javascript": ["*.js", "*.jsx", "package.json"],
    "go": ["*.go", "go.mod", "go.sum"],
    "rust": ["*.rs", "Cargo.toml", "Cargo.lock"],
    "java": ["*.java", "pom.xml", "build.gradle"],
    "cpp": ["*.cpp", "*.cc", "*.hpp", "CMakeLists.txt"],
    "c": ["*.c", "*.h"],
    "ruby": ["*.rb", "Gemfile"],
    "php": ["*.php", "composer.json"],
    "swift": ["*.swift", "Package.swift"],
    "kotlin": ["*.kt", "*.kts"],
}


def detect_languages(path: str) -> List[str]:
    """Detect programming languages in a repository.

    Scans the directory for language-specific files to determine
    which languages are used in the project.

    Args:
        path: Root directory of the project to analyze.

    Returns:
        List of detected language names.
    """
    project_path = Path(path).resolve()
    detected: set[str] = set()

    if not project_path.exists():
        return []

    for language, patterns in LANGUAGE_PATTERNS.items():
        for pattern in patterns:
            try:
                if list(project_path.rglob(pattern)):
                    detected.add(language)
                    break
            except (PermissionError, OSError):
                continue

    return sorted(list(detected))


def create_config(path: str, languages: List[str]) -> NomiConfig:
    """Create a new Nomi configuration.

    Args:
        path: Project root directory.
        languages: List of languages to configure.

    Returns:
        Configured NomiConfig instance.
    """
    project_path = Path(path).resolve()

    config = NomiConfig(
        languages=languages,
        project_root=project_path,
        index_cache_dir=project_path / ".nomi" / "cache",
    )

    return config


def setup_storage(path: str) -> Path:
    """Set up the Nomi storage directory.

    Creates the .nomi/ directory structure for storing
    indexes, cache, and runtime files.

    Args:
        path: Project root directory.

    Returns:
        Path to the storage directory.
    """
    project_path = Path(path).resolve()
    storage_dir = project_path / ".nomi"

    # Create main storage directory
    storage_dir.mkdir(parents=True, exist_ok=True)

    # Create subdirectories
    (storage_dir / "cache").mkdir(exist_ok=True)
    (storage_dir / "logs").mkdir(exist_ok=True)

    return storage_dir


@app.command(name="init")
def init_command(
    path: Optional[str] = typer.Argument(
        default=".",
        help="Path to project directory (default: current directory)",
    ),
    languages: Optional[str] = typer.Option(
        None,
        "--languages",
        "-l",
        help="Comma-separated list of languages (auto-detect if not specified)",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip prompts and use defaults",
    ),
) -> None:
    """Initialize Nomi in a project directory.

    Creates a .nomi.json configuration file, detects languages in the repository,
    and sets up the Nomi storage directory structure.
    """
    project_path = Path(path).resolve() if path else Path.cwd()

    # Check if path exists
    if not project_path.exists():
        console.print(f"[red]Error: Path does not exist: {project_path}[/red]")
        raise typer.Exit(1)

    if not project_path.is_dir():
        console.print(f"[red]Error: Path is not a directory: {project_path}[/red]")
        raise typer.Exit(1)

    # Check if already initialized
    config_file = project_path / ".nomi.json"
    if config_file.exists():
        if not yes:
            overwrite = Confirm.ask(
                f"Nomi is already initialized in {project_path}. Overwrite?",
                default=False,
            )
            if not overwrite:
                console.print("[yellow]Initialization cancelled.[/yellow]")
                raise typer.Exit(0)

    # Detect or use specified languages
    if languages:
        detected_languages = [lang.strip() for lang in languages.split(",")]
        console.print(f"[blue]Using specified languages: {', '.join(detected_languages)}[/blue]")
    else:
        console.print("[blue]Detecting languages...[/blue]")
        detected_languages = detect_languages(str(project_path))
        if detected_languages:
            console.print(f"[green]Detected languages: {', '.join(detected_languages)}[/green]")
        else:
            console.print("[yellow]No languages detected. Using defaults.[/yellow]")
            detected_languages = ["python", "typescript", "javascript"]

    # Interactive configuration if not --yes
    if not yes:
        # Confirm languages
        lang_input = Prompt.ask(
            "Languages to analyze (comma-separated)",
            default=", ".join(detected_languages),
        )
        detected_languages = [lang.strip() for lang in lang_input.split(",")]

        # Additional options
        enable_watch = Confirm.ask("Enable file watching?", default=True)
        enable_mcp = Confirm.ask("Enable MCP server?", default=True)
    else:
        enable_watch = True
        enable_mcp = True

    # Validate languages
    valid_languages = {
        "python", "typescript", "javascript", "go", "rust",
        "java", "cpp", "c", "ruby", "php", "swift", "kotlin",
    }
    invalid_languages = set(detected_languages) - valid_languages
    if invalid_languages:
        console.print(f"[red]Error: Unsupported languages: {', '.join(invalid_languages)}[/red]")
        console.print(f"[yellow]Supported languages: {', '.join(sorted(valid_languages))}[/yellow]")
        raise typer.Exit(1)

    # Create configuration
    try:
        config = create_config(str(project_path), detected_languages)
        config.watch = enable_watch
        config.enable_mcp = enable_mcp

        # Save configuration
        save_config(config, config_file)
        console.print(f"[green]Created configuration: {config_file}[/green]")

    except Exception as e:
        console.print(f"[red]Error creating configuration: {e}[/red]")
        raise typer.Exit(1)

    # Set up storage directory
    try:
        storage_dir = setup_storage(str(project_path))
        console.print(f"[green]Created storage directory: {storage_dir}[/green]")
    except Exception as e:
        console.print(f"[red]Error creating storage directory: {e}[/red]")
        raise typer.Exit(1)

    # Create .gitignore entry if .git exists
    git_dir = project_path / ".git"
    if git_dir.exists():
        gitignore_file = project_path / ".gitignore"
        gitignore_entry = ".nomi/"

        try:
            if gitignore_file.exists():
                content = gitignore_file.read_text()
                if gitignore_entry not in content:
                    with open(gitignore_file, "a") as f:
                        f.write(f"\n{gitignore_entry}\n")
                    console.print(f"[green]Added {gitignore_entry} to .gitignore[/green]")
            else:
                gitignore_file.write_text(f"{gitignore_entry}\n")
                console.print(f"[green]Created .gitignore with {gitignore_entry}[/green]")
        except Exception as e:
            console.print(f"[yellow]Warning: Could not update .gitignore: {e}[/yellow]")

    console.print("\n[bold green]Nomi initialized successfully![/bold green]")
    console.print(f"\nNext steps:")
    console.print(f"  1. Review configuration: {config_file}")
    console.print(f"  2. Start the daemon: nomi start")
    console.print(f"  3. Check status: nomi status")


if __name__ == "__main__":
    app()
