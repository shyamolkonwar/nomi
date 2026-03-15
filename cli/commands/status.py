"""Status command for Nomi CLI.

This module provides the status command for checking Nomi daemon status.
"""

import json
import os
import time

from pathlib import Path
from typing import Optional, Tuple

import requests
import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()
app = typer.Typer(help="Show Nomi daemon status")

# Lock file location
LOCK_FILE_NAME = ".nomi/daemon.lock"


def get_lock_file_path(project_root: Path) -> Path:
    """Get the path to the daemon lock file.

    Args:
        project_root: Root directory of the project.

    Returns:
        Path to the lock file.
    """
    return project_root / LOCK_FILE_NAME


def find_daemon_lock_file() -> Optional[Path]:
    """Find the daemon lock file by searching upward.

    Searches from current directory up to find a .nomi/daemon.lock file.

    Returns:
        Path to the lock file if found, None otherwise.
    """
    current = Path.cwd().resolve()

    while current != current.parent:
        lock_file = current / LOCK_FILE_NAME
        if lock_file.exists():
            return lock_file
        current = current.parent

    return None


def read_lock_file(lock_file: Path) -> Tuple[Optional[int], Optional[int], Optional[float]]:
    """Read PID, port, and start time from lock file.

    Args:
        lock_file: Path to the lock file.

    Returns:
        Tuple of (pid, port, started_at). Any may be None if not found.
    """
    try:
        with open(lock_file, "r") as f:
            data = json.load(f)
            return (
                data.get("pid"),
                data.get("port"),
                data.get("started_at"),
            )
    except (json.JSONDecodeError, FileNotFoundError, KeyError):
        return None, None, None


def is_process_running(pid: int) -> bool:
    """Check if a process with the given PID is running.

    Args:
        pid: Process ID to check.

    Returns:
        True if process exists, False otherwise.
    """
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def format_duration(seconds: float) -> str:
    """Format duration in a human-readable way.

    Args:
        seconds: Duration in seconds.

    Returns:
        Formatted duration string.
    """
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        return f"{minutes}m"
    elif seconds < 86400:
        hours = int(seconds / 3600)
        minutes = int((seconds % 3600) / 60)
        return f"{hours}h {minutes}m"
    else:
        days = int(seconds / 86400)
        hours = int((seconds % 86400) / 3600)
        return f"{days}d {hours}h"


def query_daemon_health(port: int) -> Tuple[bool, dict]:
    """Query the daemon API for health status.

    Args:
        port: Port the API server is listening on.

    Returns:
        Tuple of (success, data). Data contains health info if successful.
    """
    try:
        response = requests.get(
            f"http://localhost:{port}/health",
            timeout=2,
        )
        if response.status_code == 200:
            return True, response.json()
        return False, {}
    except requests.RequestException:
        return False, {}


def query_daemon_stats(port: int) -> Tuple[bool, dict]:
    """Query the daemon API for repository stats.

    Args:
        port: Port the API server is listening on.

    Returns:
        Tuple of (success, data). Data contains stats if successful.
    """
    try:
        response = requests.get(
            f"http://localhost:{port}/repo/stats",
            timeout=2,
        )
        if response.status_code == 200:
            return True, response.json()
        return False, {}
    except requests.RequestException:
        return False, {}


@app.command(name="status")
def status_command() -> None:
    """Show Nomi daemon status.

    Displays information about the daemon including running state,
    PID, uptime, indexed files, and API endpoint.
    """
    # Find lock file
    lock_file = find_daemon_lock_file()

    if lock_file is None:
        console.print(
            Panel(
                "[red]Not running[/red]\n\n" "No daemon lock file found.\n" "Run 'nomi start' to start the daemon.",
                title="Nomi Status",
                border_style="red",
            )
        )
        raise typer.Exit(0)

    # Get project root from lock file location
    project_root = lock_file.parent.parent

    # Read lock file
    pid, port, started_at = read_lock_file(lock_file)

    # Check if process is running
    is_running = False
    if pid is not None:
        is_running = is_process_running(pid)

    if not is_running:
        # Clean up stale lock file
        lock_file.unlink(missing_ok=True)
        console.print(
            Panel(
                "[red]Not running[/red]\n\n"
                "Daemon process is not running (stale lock file removed).\n"
                "Run 'nomi start' to start the daemon.",
                title="Nomi Status",
                border_style="red",
            )
        )
        raise typer.Exit(0)

    # Calculate uptime
    uptime = "Unknown"
    if started_at is not None:
        uptime_seconds = time.time() - started_at
        uptime = format_duration(uptime_seconds)

    # Query daemon for health and stats
    health = "unknown"
    indexed_files = "Unknown"
    total_symbols = "Unknown"

    if port is not None:
        health_ok, health_data = query_daemon_health(port)
        if health_ok:
            health = health_data.get("status", "unknown")

        stats_ok, stats_data = query_daemon_stats(port)
        if stats_ok:
            indexed_files = str(stats_data.get("total_files", "Unknown"))
            total_symbols = str(stats_data.get("total_symbols", "Unknown"))

    # Create status table
    table = Table(show_header=False, box=None)
    table.add_column("Key", style="cyan", no_wrap=True)
    table.add_column("Value", style="white")

    table.add_row("Status", "[green]Running[/green]" if is_running else "[red]Not running[/red]")
    table.add_row("PID", str(pid) if pid else "Unknown")
    table.add_row("Uptime", uptime)
    table.add_row("Indexed files", indexed_files)
    table.add_row("Total symbols", total_symbols)

    if port:
        table.add_row("API endpoint", f"http://localhost:{port}")
    table.add_row("Health", health.capitalize() if health != "unknown" else "[yellow]Unknown[/yellow]")
    table.add_row("Project root", str(project_root))

    # Display status
    console.print(
        Panel(
            table,
            title="[bold]Nomi Status[/bold]",
            border_style="green" if is_running else "red",
        )
    )

    # Show quick commands
    console.print("\n[dim]Commands:[/dim]")
    console.print("  [cyan]nomi stop[/cyan]      - Stop the daemon")
    console.print("  [cyan]nomi search[/cyan]    - Search for symbols")
    console.print("  [cyan]nomi context[/cyan]   - Build context")


if __name__ == "__main__":
    app()
