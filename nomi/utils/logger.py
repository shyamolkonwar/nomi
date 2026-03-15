"""Logging utilities for Nomi.

This module provides structured logging capabilities using structlog
or standard library logging with consistent formatting.
"""

import logging
import sys
from typing import Any

import structlog
from structlog.types import FilteringBoundLogger


DEFAULT_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
STRUCTURED_LOG_FORMAT = "{asctime} {levelname} {event} {logger}"


def configure_logging(
    log_level: str = "INFO",
    use_structlog: bool = True,
    json_format: bool = False,
) -> None:
    """Configure logging for Nomi.
    
    Sets up either structlog or standard library logging based on
    the configuration parameters.
    
    Args:
        log_level: The logging level to use (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        use_structlog: Whether to use structlog for structured logging.
        json_format: Whether to output logs in JSON format (structlog only).
    
    Example:
        >>> configure_logging(log_level="DEBUG")
        >>> configure_logging(log_level="INFO", json_format=True)
    """
    level = getattr(logging, log_level.upper(), logging.INFO)
    
    if use_structlog:
        _configure_structlog(level, json_format)
    else:
        _configure_stdlib_logging(level)


def _configure_structlog(level: int, json_format: bool) -> None:
    """Configure structlog for structured logging.
    
    Args:
        level: The logging level.
        json_format: Whether to use JSON formatting.
    """
    processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
    ]
    
    if json_format:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=sys.stdout.isatty()))
    
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Configure standard library logging to use structlog
    logging.basicConfig(
        format="%(message)s",
        level=level,
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def _configure_stdlib_logging(level: int) -> None:
    """Configure standard library logging.
    
    Args:
        level: The logging level.
    """
    logging.basicConfig(
        format=DEFAULT_LOG_FORMAT,
        level=level,
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def get_logger(name: str | None = None) -> FilteringBoundLogger | logging.Logger:
    """Get a logger instance.
    
    Returns either a structlog logger or standard library logger
    depending on configuration.
    
    Args:
        name: The name of the logger. If None, uses the calling module name.
    
    Returns:
        A logger instance configured for use.
    
    Example:
        >>> logger = get_logger(__name__)
        >>> logger.info("Starting process", task="initialization")
    """
    if structlog.is_configured():
        return structlog.get_logger(name)
    return logging.getLogger(name)


class LoggerMixin:
    """Mixin class that provides a logger property.
    
    Classes can inherit from this mixin to automatically get
    a logger property that uses the class name.
    
    Example:
        >>> class MyClass(LoggerMixin):
        ...     def do_something(self):
        ...         self.logger.info("Doing something")
    """
    
    _logger: FilteringBoundLogger | logging.Logger | None = None
    
    @property
    def logger(self) -> FilteringBoundLogger | logging.Logger:
        """Get a logger for this class instance."""
        if self._logger is None:
            self._logger = get_logger(self.__class__.__name__)
        return self._logger


def log_operation(
    logger: FilteringBoundLogger | logging.Logger,
    operation: str,
    **context: Any,
) -> None:
    """Log an operation with structured context.
    
    Args:
        logger: The logger to use.
        operation: Description of the operation.
        **context: Additional context key-value pairs.
    
    Example:
        >>> logger = get_logger(__name__)
        >>> log_operation(logger, "indexing", file_count=42, duration_ms=150)
    """
    if hasattr(logger, "info"):
        logger.info(operation, **context)
    else:
        # Standard library logger fallback
        context_str = " ".join(f"{k}={v!r}" for k, v in context.items())
        logger.info(f"{operation} {context_str}")
