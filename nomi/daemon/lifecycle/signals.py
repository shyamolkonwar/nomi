"""Signal handling for daemon lifecycle management.

This module provides signal handlers for graceful shutdown,
configuration reload, and other lifecycle events.
"""

import signal
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from nomi.daemon.runtime.daemon import NomiDaemon


# Global reference to daemon instance for signal handlers
_daemon_instance: "NomiDaemon | None" = None


def setup_signal_handlers(daemon: "NomiDaemon") -> None:
    """Set up signal handlers for the daemon process.

    Configures handlers for SIGTERM, SIGINT, and SIGHUP signals
    to manage daemon lifecycle gracefully.

    Args:
        daemon: The NomiDaemon instance to control.

    Example:
        >>> daemon = NomiDaemon(config, project_root)
        >>> setup_signal_handlers(daemon)
        >>> daemon.start()
    """
    global _daemon_instance
    _daemon_instance = daemon

    signal.signal(signal.SIGTERM, handle_sigterm)
    signal.signal(signal.SIGINT, handle_sigint)

    if hasattr(signal, "SIGHUP"):
        signal.signal(signal.SIGHUP, handle_sighup)


def handle_sigterm(signum: int, frame) -> None:
    """Handle SIGTERM signal for graceful shutdown.

    SIGTERM is typically sent by process managers (systemd, etc.)
    to request a clean shutdown.

    Args:
        signum: Signal number (always signal.SIGTERM).
        frame: Current stack frame (unused).
    """
    import logging

    logger = logging.getLogger(__name__)

    logger.info("SIGTERM received, initiating graceful shutdown...")

    if _daemon_instance is not None:
        _daemon_instance.stop()

    sys.exit(0)


def handle_sigint(signum: int, frame) -> None:
    """Handle SIGINT signal (Ctrl+C) for graceful shutdown.

    SIGINT is sent when the user presses Ctrl+C in the terminal.

    Args:
        signum: Signal number (always signal.SIGINT).
        frame: Current stack frame (unused).
    """
    import logging

    logger = logging.getLogger(__name__)

    logger.info("SIGINT received, initiating graceful shutdown...")

    if _daemon_instance is not None:
        _daemon_instance.stop()

    sys.exit(0)


def handle_sighup(signum: int, frame) -> None:
    """Handle SIGHUP signal for configuration reload.

    SIGHUP is traditionally used to signal a process to reload
    its configuration without restarting.

    Args:
        signum: Signal number (always signal.SIGHUP).
        frame: Current stack frame (unused).
    """
    import logging

    logger = logging.getLogger(__name__)

    logger.info("SIGHUP received, reloading configuration...")

    if _daemon_instance is not None:
        _daemon_instance.reload_config()
