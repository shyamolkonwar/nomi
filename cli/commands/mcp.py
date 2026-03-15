"""MCP command for Nomi CLI.

This module provides the MCP command for running the Nomi MCP server
over stdio transport for integration with AI coding agents.
"""

import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from nomi.config.loader import load_config
from nomi.core.context.context_builder import ContextBuilder
from nomi.core.graph.dependency_graph import DependencyGraph
from nomi.core.index.lookup import SymbolLookup
from nomi.core.index.search import SymbolSearch
from nomi.mcp.server import create_mcp_server
from nomi.repo_map.map_builder import RepoMapBuilder
from nomi.storage.sqlite.symbol_store import SymbolStore

console = Console()
app = typer.Typer(help="Run Nomi MCP server over stdio")


@app.command(name="mcp")
def mcp_command(
    config: Optional[str] = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to configuration file",
    ),
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose logging",
    ),
) -> None:
    """Run the Nomi MCP server over stdio transport.

    This command starts the MCP server that communicates over stdin/stdout,
    making it compatible with AI coding agents that support the Model Context
    Protocol.

    The server must be run from a directory that has been initialized with
    'nomi init' and has a .nomi.json configuration file.
    """
    log_level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        stream=sys.stderr,
    )

    logger = logging.getLogger(__name__)

    try:
        if config:
            nomi_config = load_config(config_path=config)
        else:
            nomi_config = load_config()
    except FileNotFoundError:
        console.print("[red]Error: No configuration file found.[/red]")
        console.print("[yellow]Run 'nomi init' first to initialize the project.[/yellow]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Error loading configuration: {e}[/red]")
        raise typer.Exit(1)

    project_root = Path(nomi_config.project_root)
    storage_dir = project_root / ".nomi" / "cache"
    db_path = storage_dir / "nomi.db"

    if not db_path.exists():
        console.print("[red]Error: Database not found.[/red]")
        console.print("[yellow]Run 'nomi start' first to initialize the database and index your codebase.[/yellow]")
        raise typer.Exit(1)

    logger.info(f"Initializing MCP server: project_root={project_root}, db_path={db_path}")

    try:
        symbol_store = SymbolStore(db_path)
        symbol_search = SymbolSearch(symbol_store)
        symbol_lookup = SymbolLookup(symbol_store)
        dependency_graph = DependencyGraph(str(db_path))

        graph_traversal = dependency_graph.get_traversal()
        repo_map_builder = RepoMapBuilder(graph_traversal, symbol_store)

        context_builder = ContextBuilder(
            symbol_search=symbol_search,
            dependency_graph=dependency_graph,
            symbol_lookup=symbol_lookup,
        )

        mcp_server = create_mcp_server(
            context_builder=context_builder,
            symbol_search=symbol_search,
            repo_map_builder=repo_map_builder,
            dependency_graph=dependency_graph,
            symbol_lookup=symbol_lookup,
        )

        logger.info("MCP server initialized, starting stdio transport")
        asyncio.run(mcp_server.run_stdio())

    except Exception as e:
        logger.exception("MCP server failed")
        console.print(f"[red]Error: MCP server failed: {e}[/red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
