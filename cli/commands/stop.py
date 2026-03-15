"""Stop command for Nomi CLI.

This module provides the stop command for gracefully shutting down the Nomi daemon.
"""

import json
import os
import signal
import time
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console

console = Console()
app = typer.Typer(help="Stop the Nomi daemon")

# Lock file location
LOCK_FILE_NAME = ".nomi/daemon.lock"
# Timeout for graceful shutdown (seconds)
SHUTDOWN_TIMEOUT = 10


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


def read_lock_file(lock_file: Path) -> tuple[Optional[int], Optional[int]]:
    """Read PID and port from lock file.

    Args:
        lock_file: Path to the lock file.

    Returns:
        Tuple of (pid, port). Either may be None if not found.
    """
    try:
        with open(lock_file, "r") as f:
            data = json.load(f)
            return data.get("pid"), data.get("port")
    except (json.JSONDecodeError, FileNotFoundError, KeyError):
        return None, None


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


def stop_daemon(pid: int, timeout: int = SHUTDOWN_TIMEOUT) -> bool:
    """Stop the daemon gracefully.

    Sends SIGTERM and waits for the process to terminate.

    Args:
        pid: Process ID of the daemon.
        timeout: Seconds to wait for graceful shutdown.

    Returns:
        True if daemon stopped successfully, False otherwise.
    """
    # Send SIGTERM for graceful shutdown
    try:
        os.kill(pid, signal.SIGTERM)
    except (OSError, ProcessLookupError) as e:
        console.print(f"[yellow]Could not send signal to process: {e}[/yellow]")
        return False

    # Wait for process to terminate
    start_time = time.time()
    while time.time() - start_time < timeout:
        if not is_process_running(pid):
            return True
        time.sleep(0.5)

    # Process still running after timeout
    return False


def force_kill(pid: int) -> bool:
    """Force kill a process.

    Args:
        pid: Process ID to kill.

    Returns:
        True if kill signal was sent successfully.
    """
    try:
        os.kill(pid, signal.SIGKILL)
        return True
    except (OSError, ProcessLookupError):
        return False


@app.command(name="stop")
def stop_command(
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Force kill the daemon (SIGKILL)",
    ),
    timeout: int = typer.Option(
        SHUTDOWN_TIMEOUT,
        "--timeout",
        "-t",
        help="Seconds to wait for graceful shutdown",
        min=1,
        max=60,
    ),
) -> None:
    """Stop the running Nomi daemon.

    Finds the daemon lock file, reads the PID, and sends a termination
    signal for graceful shutdown. Use --force to send SIGKILL instead.
    """
    # Find lock file
    lock_file = find_daemon_lock_file()

    if lock_file is None:
        console.print("[yellow]No running daemon found (no lock file).[/yellow]")
        raise typer.Exit(0)

    # Read PID from lock file
    pid, port = read_lock_file(lock_file)

    if pid is None:
        console.print("[yellow]Invalid lock file. Cleaning up...[/yellow]")
        lock_file.unlink(missing_ok=True)
        raise typer.Exit(0)

    # Check if process is actually running
    if not is_process_running(pid):
        console.print(f"[yellow]Daemon process (PID: {pid}) is not running.[/yellow]")
        lock_file.unlink(missing_ok=True)
        raise typer.Exit(0)

    console.print(f"[blue]Stopping Nomi daemon (PID: {pid})...[/blue]")

    if force:
        # Force kill
        console.print("[yellow]Sending SIGKILL...[/yellow]")
        if force_kill(pid):
            console.print("[green]Daemon stopped (force killed).[/green]")
        else:
            console.print("[red]Failed to kill daemon process.[/red]")
            raise typer.Exit(1)
    else:
        # Graceful shutdown
        if stop_daemon(pid, timeout):
            console.print("[green]Daemon stopped gracefully.[/green]")
        else:
            console.print("[yellow]Daemon did not stop in time. Use --force to kill.[/yellow]")
            raise typer.Exit(1)

    # Clean up lock file
    lock_file.unlink(missing_ok=True)


if __name__ == "__main__":
    app()
