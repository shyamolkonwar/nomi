"""Main entry point for Nomi CLI.

This module provides the main Typer application and global CLI configuration.
"""

import logging
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

from cli.commands import context, init, search, start, status, stop

__version__ = "0.1.0"

console = Console()

# Create the main Typer app
app = typer.Typer(
    name="nomi",
    help="Nomi - Local context engine for AI coding agents",
    no_args_is_help=True,
    add_completion=True,
)

# Register all commands
app.command(name="init")(init.init_command)
app.command(name="start")(start.start_command)
app.command(name="stop")(stop.stop_command)
app.command(name="status")(status.status_command)
app.command(name="search")(search.search_command)
app.command(name="context")(context.context_command)


def setup_logging(verbose: bool = False) -> None:
    """Set up logging configuration.

    Args:
        verbose: Whether to enable verbose (DEBUG) logging.
    """
    level = logging.DEBUG if verbose else logging.INFO
    format_string = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    logging.basicConfig(
        level=level,
        format=format_string,
        handlers=[
            logging.StreamHandler(sys.stderr),
        ],
    )


def version_callback(value: bool) -> None:
    """Callback for --version flag.

    Args:
        value: Whether --version was passed.
    """
    if value:
        console.print(f"Nomi version {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose logging",
    ),
    version: bool = typer.Option(
        False,
        "--version",
        help="Show version information",
        callback=version_callback,
        is_eager=True,
    ),
) -> None:
    """Nomi - Local context engine for AI coding agents.

    Nomi indexes your codebase and provides intelligent context retrieval
    for AI coding agents through an MCP-compatible API.

    Quick Start:
        nomi init          # Initialize Nomi in your project
        nomi start         # Start the daemon
        nomi status        # Check daemon status

    Commands:
        init    Initialize configuration and storage
        start   Start the daemon with API and optional MCP
        stop    Stop the running daemon
        status  Show daemon status and statistics
        search  Search for symbols in the codebase
        context Build context bundles for queries

    For more help on a specific command:
        nomi <command> --help
    """
    setup_logging(verbose)


if __name__ == "__main__":
    app()
