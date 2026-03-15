"""Start command for Nomi CLI.

This module provides the start command for launching the Nomi daemon.
"""

import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.panel import Panel

from nomi.config.loader import load_config
from nomi.daemon.runtime.daemon import NomiDaemon

console = Console()
app = typer.Typer(help="Start the Nomi daemon")

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


def is_daemon_running(project_root: Path) -> tuple[bool, Optional[int]]:
    """Check if the Nomi daemon is already running.

    Args:
        project_root: Root directory of the project.

    Returns:
        Tuple of (is_running, pid). PID is None if not running.
    """
    lock_file = get_lock_file_path(project_root)

    if not lock_file.exists():
        return False, None

    try:
        with open(lock_file, "r") as f:
            data = json.load(f)
            pid = data.get("pid")

        if pid is None:
            return False, None

        # Check if process exists
        try:
            os.kill(pid, 0)
            return True, pid
        except (OSError, ProcessLookupError):
            # Process doesn't exist, clean up stale lock file
            lock_file.unlink(missing_ok=True)
            return False, None

    except (json.JSONDecodeError, FileNotFoundError, KeyError):
        # Invalid lock file, clean it up
        lock_file.unlink(missing_ok=True)
        return False, None


def write_lock_file(project_root: Path, pid: int, port: int) -> None:
    """Write the daemon lock file.

    Args:
        project_root: Root directory of the project.
        pid: Process ID of the daemon.
        port: Port the API server is listening on.
    """
    lock_file = get_lock_file_path(project_root)
    lock_file.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "pid": pid,
        "port": port,
        "started_at": time.time(),
    }

    with open(lock_file, "w") as f:
        json.dump(data, f, indent=2)


def daemonize() -> None:
    """Daemonize the current process (Unix only).

    Performs a double fork to detach from the terminal.
    """
    if sys.platform == "win32":
        return

    # First fork
    try:
        pid = os.fork()
        if pid > 0:
            sys.exit(0)
    except OSError as e:
        console.print(f"[red]Fork failed: {e}[/red]")
        sys.exit(1)

    # Decouple from parent environment
    os.chdir("/")
    os.setsid()
    os.umask(0)

    # Second fork
    try:
        pid = os.fork()
        if pid > 0:
            sys.exit(0)
    except OSError as e:
        console.print(f"[red]Fork failed: {e}[/red]")
        sys.exit(1)

    # Redirect standard file descriptors
    sys.stdout.flush()
    sys.stderr.flush()

    with open("/dev/null", "r") as f:
        os.dup2(f.fileno(), sys.stdin.fileno())
    with open("/dev/null", "a+") as f:
        os.dup2(f.fileno(), sys.stdout.fileno())
    with open("/dev/null", "a+") as f:
        os.dup2(f.fileno(), sys.stderr.fileno())


@app.command(name="start")
def start_command(
    port: int = typer.Option(
        8345,
        "--port",
        "-p",
        help="API server port",
        min=1024,
        max=65535,
    ),
    mcp: bool = typer.Option(
        True,
        "--mcp/--no-mcp",
        help="Enable MCP server",
    ),
    watch: bool = typer.Option(
        True,
        "--watch/--no-watch",
        help="Enable file watching",
    ),
    background: bool = typer.Option(
        False,
        "--background",
        "-b",
        help="Run in background (daemonize)",
    ),
    config: Optional[str] = typer.Option(
        None,
        "--config",
        "-c",
        help="Path to configuration file",
    ),
) -> None:
    """Start the Nomi daemon.

    Initializes and starts all Nomi services including the file watcher,
    API server, and optional MCP server.
    """
    # Load configuration
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

    project_root = nomi_config.project_root

    # Check if already running
    is_running, existing_pid = is_daemon_running(project_root)
    if is_running:
        console.print(f"[yellow]Nomi daemon is already running (PID: {existing_pid})[/yellow]")
        console.print("[blue]Use 'nomi status' to check details or 'nomi stop' to restart.[/blue]")
        raise typer.Exit(0)

    # Update config with CLI options
    nomi_config.server_port = port
    nomi_config.enable_mcp = mcp
    nomi_config.watch = watch

    console.print("[blue]Starting Nomi daemon...[/blue]")

    # Daemonize if requested
    if background:
        if sys.platform == "win32":
            console.print("[yellow]Background mode not supported on Windows. Running in foreground.[/yellow]")
        else:
            console.print("[blue]Daemonizing...[/blue]")
            daemonize()

    # Initialize and start daemon
    try:
        daemon = NomiDaemon(config=nomi_config, project_root=str(project_root))
        daemon.initialize()

        # Write lock file before starting
        write_lock_file(project_root, os.getpid(), port)

        # Display startup info (only if not daemonized)
        if not background or sys.platform == "win32":
            endpoints = [
                f"[green]API Server:[/green] http://localhost:{port}",
            ]
            if mcp:
                endpoints.append("[green]MCP Server:[/green] Enabled")
            if watch:
                endpoints.append("[green]File Watcher:[/green] Enabled")

            console.print(
                Panel(
                    "\n".join(endpoints),
                    title="[bold]Nomi Daemon Started[/bold]",
                    border_style="green",
                )
            )

            console.print(f"[dim]Project: {project_root}[/dim]")
            console.print(f"[dim]PID: {os.getpid()}[/dim]")
            console.print("\n[dim]Press Ctrl+C to stop[/dim]\n")

        # Start the daemon (this blocks)
        daemon.start()

    except KeyboardInterrupt:
        console.print("\n[yellow]Received interrupt signal. Shutting down...[/yellow]")
    except Exception as e:
        console.print(f"[red]Error starting daemon: {e}[/red]")
        # Clean up lock file on error
        lock_file = get_lock_file_path(project_root)
        lock_file.unlink(missing_ok=True)
        raise typer.Exit(1)
    finally:
        # Clean up lock file on exit
        lock_file = get_lock_file_path(project_root)
        lock_file.unlink(missing_ok=True)


if __name__ == "__main__":
    app()
