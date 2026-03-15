"""Search command for Nomi CLI.

This module provides the search command for searching symbols from CLI.
"""

import json
from typing import Optional

import requests
import typer
from rich.console import Console
from rich.table import Table

console = Console()
app = typer.Typer(help="Search for symbols")


def get_api_port() -> Optional[int]:
    """Get the API port from the daemon lock file.

    Returns:
        Port number if daemon is running, None otherwise.
    """
    import json as json_module
    from pathlib import Path

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


def search_symbols(
    query: str,
    port: int,
    limit: int = 10,
) -> list[dict]:
    """Search for symbols via the API.

    Args:
        query: Search query string.
        port: API server port.
        limit: Maximum number of results.

    Returns:
        List of symbol results.
    """
    try:
        response = requests.post(
            f"http://localhost:{port}/symbol/search",
            json={"query": query, "limit": limit},
            timeout=5,
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("results", [])
        return []
    except requests.RequestException:
        return []


@app.command(name="search")
def search_command(
    query: str = typer.Argument(
        ...,
        help="Search query for symbols",
    ),
    limit: int = typer.Option(
        10,
        "--limit",
        "-l",
        help="Maximum number of results",
        min=1,
        max=100,
    ),
    format: str = typer.Option(
        "table",
        "--format",
        "-f",
        help="Output format (table, json)",
    ),
) -> None:
    """Search for symbols in the indexed repository.

    Performs a fuzzy search across all indexed symbols and returns
    ranked results matching the query.
    """
    # Get API port
    port = get_api_port()

    if port is None:
        console.print("[red]Error: Nomi daemon is not running.[/red]")
        console.print("[yellow]Start the daemon with: nomi start[/yellow]")
        raise typer.Exit(1)

    # Validate format
    if format not in ("table", "json"):
        console.print(f"[red]Error: Invalid format '{format}'. Use 'table' or 'json'.[/red]")
        raise typer.Exit(1)

    console.print(f"[blue]Searching for: {query}[/blue]")

    # Perform search
    results = search_symbols(query, port, limit)

    if not results:
        console.print("[yellow]No results found.[/yellow]")
        raise typer.Exit(0)

    # Output results
    if format == "json":
        console.print(json.dumps(results, indent=2))
    else:
        # Table format
        table = Table(
            title=f"Search Results: {query}",
            show_header=True,
            header_style="bold cyan",
        )
        table.add_column("Name", style="green", no_wrap=True)
        table.add_column("Type", style="magenta", no_wrap=True)
        table.add_column("File", style="blue")
        table.add_column("Line", style="dim", justify="right")
        table.add_column("Score", style="yellow", justify="right")

        for result in results:
            symbol = result.get("symbol", {})
            table.add_row(
                symbol.get("name", "Unknown"),
                symbol.get("type", "unknown"),
                symbol.get("file_path", "Unknown"),
                str(symbol.get("line", "-")),
                f"{result.get('score', 0):.2f}",
            )

        console.print(table)
        console.print(f"\n[dim]Showing {len(results)} result(s)[/dim]")


if __name__ == "__main__":
    app()
