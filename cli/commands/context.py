"""Context command for Nomi CLI.

This module provides the context command for building and displaying context.
"""

import json
from pathlib import Path
from typing import Optional

import requests
import typer
from rich.console import Console
from rich.panel import Panel
console = Console()
app = typer.Typer(help="Build and display context")


def get_api_port() -> Optional[int]:
    """Get the API port from the daemon lock file.

    Returns:
        Port number if daemon is running, None otherwise.
    """
    import json as json_module

    current = Path.cwd().resolve()
    lock_file_name = ".nomi/daemon.lock"

    while current != current.parent:
        lock_file = current / lock_file_name
        if lock_file.exists():
            try:
                with open(lock_file, "r") as f:
                    data = json_module.load(f)
                    return data.get("port")
            except (json_module.JSONDecodeError, FileNotFoundError):
                return None
        current = current.parent

    return None


def build_context(
    query: str,
    port: int,
    max_tokens: Optional[int] = None,
    depth: Optional[int] = None,
) -> Optional[dict]:
    """Build context via the API.

    Args:
        query: Context query (symbol name or search term).
        port: API server port.
        max_tokens: Maximum tokens for context.
        depth: Dependency depth for traversal.

    Returns:
        Context data if successful, None otherwise.
    """
    payload: dict = {"query": query}
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    if depth is not None:
        payload["depth"] = depth

    try:
        response = requests.post(
            f"http://localhost:{port}/context",
            json=payload,
            timeout=10,
        )
        if response.status_code == 200:
            return response.json()
        return None
    except requests.RequestException:
        return None


@app.command(name="context")
def context_command(
    query: str = typer.Argument(
        ...,
        help="Query for context (symbol name or search term)",
    ),
    max_tokens: Optional[int] = typer.Option(
        None,
        "--max-tokens",
        "-t",
        help="Maximum tokens for context bundle",
        min=100,
        max=100000,
    ),
    depth: Optional[int] = typer.Option(
        None,
        "--depth",
        "-d",
        help="Dependency depth for traversal",
        min=1,
        max=10,
    ),
    format: str = typer.Option(
        "formatted",
        "--format",
        "-f",
        help="Output format (formatted, json, raw)",
    ),
) -> None:
    """Build and display context for a query.

    Builds a context bundle containing relevant symbols, files, and
    dependencies for the given query.
    """
    # Get API port
    port = get_api_port()

    if port is None:
        console.print("[red]Error: Nomi daemon is not running.[/red]")
        console.print("[yellow]Start the daemon with: nomi start[/yellow]")
        raise typer.Exit(1)

    # Validate format
    valid_formats = ("formatted", "json", "raw")
    if format not in valid_formats:
        console.print(f"[red]Error: Invalid format '{format}'. Use {', '.join(valid_formats)}.[/red]")
        raise typer.Exit(1)

    console.print(f"[blue]Building context for: {query}[/blue]")

    # Build context
    result = build_context(query, port, max_tokens, depth)

    if result is None:
        console.print("[red]Error: Failed to build context.[/red]")
        console.print("[yellow]Make sure the daemon is running and the repository is indexed.[/yellow]")
        raise typer.Exit(1)

    # Output context
    if format == "json":
        console.print(json.dumps(result, indent=2))
    elif format == "raw":
        # Output just the context content
        content = result.get("context", "")
        console.print(content)
    else:
        # Formatted output
        _display_formatted_context(result)


def _display_formatted_context(result: dict) -> None:
    """Display context in a formatted way.

    Args:
        result: Context result from API.
    """
    # Display metadata
    metadata = result.get("metadata", {})

    if metadata:
        meta_items = []
        if "token_count" in metadata:
            meta_items.append(f"Tokens: {metadata['token_count']}")
        if "file_count" in metadata:
            meta_items.append(f"Files: {metadata['file_count']}")
        if "symbol_count" in metadata:
            meta_items.append(f"Symbols: {metadata['symbol_count']}")

        if meta_items:
            console.print(
                Panel(
                    " | ".join(meta_items),
                    title="[bold]Context Metadata[/bold]",
                    border_style="blue",
                )
            )

    # Display context content
    context_content = result.get("context", "")

    if context_content:
        console.print("\n[bold]Context Bundle:[/bold]\n")
        # Try to detect language for syntax highlighting
        # Default to plain text
        console.print(context_content)
    else:
        console.print("[yellow]No context content returned.[/yellow]")

    # Display sources if available
    sources = result.get("sources", [])
    if sources:
        console.print("\n[bold]Sources:[/bold]")
        for i, source in enumerate(sources[:10], 1):  # Limit to 10 sources
            file_path = source.get("file_path", "Unknown")
            line = source.get("line", "-")
            symbol_type = source.get("type", "unknown")
            console.print(f"  {i}. [cyan]{file_path}[/cyan]:[dim]{line}[/dim] ([magenta]{symbol_type}[/magenta])")

        if len(sources) > 10:
            console.print(f"  ... and {len(sources) - 10} more")


if __name__ == "__main__":
    app()
